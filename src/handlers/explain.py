"""POST /explain: a plain-words explanation, from a template or an optional agent (plan 05.9).

The template (``engine.explain.explain_template``) is the default and the fallback. The agent
(Strands on Bedrock) is only used when ``BEDROCK_MODEL_ID`` is set, the daily limit allows it,
and it answers within ``AGENT_TIMEOUT_S``. The agent never touches the engine directly: its
``make_plan`` tool runs the model's arguments through the same validators as ``POST /plan``, so a
prompt-injected city or count is rejected. Its answer is returned as plain text, capped, and
discarded if it states a percentage that is not in the facts it was given.
"""

from __future__ import annotations

import concurrent.futures
import os
import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import Response
from aws_lambda_powertools.logging import correlation_paths

from engine import planner
from engine.errors import EngineError
from engine.explain import explain_template
from engine.factors import Factors, load_factors
from engine.units import IST, floor_hour

from . import http, store, validation
from .errors import ApiError
from .http import MAX_BODY_SMALL

MAX_TEXT = 500
DAILY_LIMIT = 3000
AGENT_TIMEOUT_S: float = 20
MAX_EXPLANATION = 1500
MAX_OUTPUT_TOKENS = 1000

SYSTEM_PROMPT = (
    "You are the explainer for Thirst, a tool that plans GPU jobs in India to use less water "
    "and produce less CO2. You only explain; you never decide or change a plan. "
    "To turn a request into a plan, call make_plan once with the details the user gave. "
    "Never invent numbers: only quote numbers that the tools returned. "
    "Always say that energy, water and CO2 figures are modelled. "
    "Savings are ranges, so say 'between X and Y%'. "
    "Answer in 3 short sentences of plain words, with no formatting."
)
FORM_HINT = (
    "We could not read that sentence automatically. Please fill in the form on the Plan page."
)

logger = Logger(service="thirst")
app = http.new_app(logger)

_FORBIDDEN = frozenset({"Cc", "Cf", "Cs", "Co", "Cn"})
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_CO2 = re.compile(r"CO[2₂]")  # a chemical formula, not a figure
# Words that carry a figure without digits ("ninety percent"). Small counts such as "one" are fine.
_NUMBER_WORDS = re.compile(
    r"\b(?:eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|percent|per\s+cent)\b",
    re.IGNORECASE,
)
CONNECT_TIMEOUT_S = 3
READ_TIMEOUT_S = 15


def _now() -> datetime:
    return datetime.now(IST)


@dataclass(frozen=True, slots=True)
class AgentContext:
    """What a runner needs: the prompt and the only two things the model may call."""

    system_prompt: str
    prompt: str
    make_plan: Callable[..., dict[str, Any]]
    get_assumptions: Callable[[], list[dict[str, Any]]]


Runner = Callable[[AgentContext], str]


# ---------------------------------------------------------------------- the tools


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    chosen = result["chosen"]
    return {
        "start": chosen["start"],
        "finish": chosen["finish"],
        "level_summary": chosen["level_summary"],
        "savings_ranges": result["savings_ranges"],
        "person_days_range": result["person_days_range"],
        "tags": result["tags"],
        "notes": result["notes"],
    }


def _tool_plan(
    now: datetime, weather: store.WeatherRepo, forms: list[dict[str, Any]], seen: list[str]
) -> Callable[..., dict[str, Any]]:
    """``make_plan`` for the model: validated exactly like the API, never stored."""

    def make_plan(**args: Any) -> dict[str, Any]:
        body = {k: v for k, v in args.items() if k != "deadline_iso"}
        body["deadline"] = args.get("deadline_iso")
        try:
            inp = validation.plan_request(body, now)
            window = weather.window(inp.city, floor_hour(now), 48)
            result = planner.plan_from_rows(inp.to_request(now), window.rows)
        except (ApiError, EngineError) as err:
            return {"error": err.message}
        forms.append(
            {
                "city": inp.city,
                "cooling": inp.cooling,
                "gpu_model": inp.gpu_model,
                "gpu_count": inp.gpu_count,
                "work_hours": inp.work_hours,
                "deadline": inp.deadline.isoformat(),
                "pausable": inp.pausable,
                "alpha": inp.alpha,
            }
        )
        summary = _summary(result)
        seen.append(str(summary))  # every figure the tool returned may be quoted
        return summary

    return make_plan


def _tool_assumptions(fx: Factors) -> Callable[[], list[dict[str, Any]]]:
    keys = ("id", "label", "value", "low", "high", "unit", "status")
    rows = [{k: row[k] for k in keys if k in row} for row in fx.table()]
    return lambda: rows


def strands_tools(ctx: AgentContext) -> list[Any]:
    """The two Strands tools. Their schemas come from these signatures and docstrings."""
    from strands import tool

    @tool
    def make_plan(
        city: str,
        cooling: str,
        gpu_model: str,
        gpu_count: int,
        work_hours: float,
        deadline_iso: str,
        pausable: bool = False,
        alpha: float = 0.5,
    ) -> dict[str, Any]:
        """Make the lowest-cost plan that meets the deadline.

        Args:
            city: One of Chennai, Bengaluru, Hyderabad, Mumbai, Delhi, Pune.
            cooling: room_ac, air_chiller or evaporative.
            gpu_model: GPU id such as RTX-4090.
            gpu_count: Number of GPUs.
            work_hours: Hours of full-power work the job needs.
            deadline_iso: Deadline as an ISO 8601 time with offset, e.g. 2026-10-10T09:00:00+05:30.
            pausable: True if the job can be paused and resumed.
            alpha: 0 favours less CO2, 1 favours less water; default 0.5.
        """
        return ctx.make_plan(
            city=city,
            cooling=cooling,
            gpu_model=gpu_model,
            gpu_count=gpu_count,
            work_hours=work_hours,
            deadline_iso=deadline_iso,
            pausable=pausable,
            alpha=alpha,
        )

    @tool
    def get_assumptions() -> list[dict[str, Any]]:
        """Return every model factor with its value, unit and status (measured, sourced, ...)."""
        return ctx.get_assumptions()

    return [make_plan, get_assumptions]


def _strands_runner(ctx: AgentContext) -> str:
    from botocore.config import Config
    from strands import Agent
    from strands.models import BedrockModel

    # A thread cannot be killed after the 20 s backstop, so the call must give up by itself.
    model = BedrockModel(
        model_id=os.environ["BEDROCK_MODEL_ID"],
        region_name=os.environ.get("BEDROCK_REGION") or None,
        max_tokens=MAX_OUTPUT_TOKENS,
        boto_client_config=Config(
            connect_timeout=CONNECT_TIMEOUT_S,
            read_timeout=READ_TIMEOUT_S,
            retries={"max_attempts": 1},
        ),
    )
    agent = Agent(
        model=model,
        tools=strands_tools(ctx),
        system_prompt=ctx.system_prompt,
        callback_handler=None,
    )
    return str(agent(ctx.prompt))


def _build_runner() -> Runner:
    return _strands_runner


# ---------------------------------------------------------------------- helpers


def _plain(text: str) -> str:
    """Plain text: control characters removed, whitespace collapsed, length capped."""
    spaced = "".join(" " if c in "\n\r\t" else c for c in text)
    kept = "".join(c for c in spaced if unicodedata.category(c) not in _FORBIDDEN)
    return " ".join(kept.split())[:MAX_EXPLANATION]


def _numbers(text: str) -> set[float]:
    return {float(n) for n in _NUMBER.findall(_CO2.sub("", text))}


def _invents_numbers(answer: str, *facts: str) -> bool:
    """True if the answer states a number that is not in the facts, or spells a big one out.

    Every digit run in the answer must also occur in the plan facts the model was given, so it
    can repeat a figure but not make one up. Words like "ninety" and "percent" are refused
    outright because they would slip past a digit check.
    """
    if _NUMBER_WORDS.search(answer):
        return True
    allowed: set[float] = set()
    for fact in facts:
        allowed |= _numbers(fact)
    return not _numbers(answer) <= allowed


def plan_view(record: Mapping[str, Any]) -> dict[str, Any]:
    """The parts of a plan that ``explain_template`` reads, rebuilt from a stored plan."""
    inputs = record["inputs"]
    base = record["base"]
    if inputs.get("force_now"):
        chosen = {"alpha": inputs["alpha"], **base}
        chosen["notes"] = [*base.get("notes", []), "start_now_forced"]
    else:
        chosen = record["pareto"][round(inputs["alpha"] * 10 + 1e-9)]
    return {
        "submit_ts": record["submit_ts"],
        "chosen": chosen,
        "notes": record["notes"],
        "tags": record["tags"],
    }


def _run_with_timeout(runner: Runner, ctx: AgentContext) -> str:
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(runner, ctx)
    try:
        return future.result(timeout=AGENT_TIMEOUT_S)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _request(body: Any) -> tuple[str | None, str | None]:
    """(text, plan_id): exactly one of them, validated."""
    if not isinstance(body, Mapping):
        raise ApiError(400, "invalid_field", "body: send a JSON object.")
    text, plan_id = body.get("text"), body.get("plan_id")
    if (text is None) == (plan_id is None):
        raise ApiError(400, "invalid_field", "body: send either text or plan_id.")
    if plan_id is not None:
        if not isinstance(plan_id, str) or not validation.PLAN_ID.fullmatch(plan_id):
            raise ApiError(400, "invalid_field", "plan_id: not a valid plan id.")
        return None, plan_id
    if not isinstance(text, str) or not text.strip():
        raise ApiError(400, "invalid_field", "text: write one or two sentences.")
    if len(text) > MAX_TEXT:
        raise ApiError(400, "text_too_long", "Please keep it under 500 characters.")
    return text, None


def _answer(
    explanation: str, source: str, note: str | None, form: dict[str, Any] | None = None
) -> Response[str]:
    return http.json_response(
        200, {"form": form, "explanation": explanation, "source": source, "note": note}
    )


@app.post("/explain")
def post_explain() -> Response[str]:
    text, plan_id = _request(http.parse_json(http.read_body(app, MAX_BODY_SMALL)))
    now = _now()
    tables = store.get_tables()
    plans = store.PlanRepo(tables.plans)
    template, facts, prompt = FORM_HINT, "", text or ""
    if plan_id is not None:
        record = plans.get(plan_id, now)
        if record is None:
            raise ApiError(404, "plan_not_found", "We couldn't find that plan.")
        template = facts = explain_template(plan_view(record))
        prompt = f"{template}\nExplain this plan to the user."
    if not os.environ.get("BEDROCK_MODEL_ID"):
        return _answer(template, "template", None if plan_id else "agent_disabled")
    if not plans.bump_quota(now, DAILY_LIMIT):
        return _answer(template, "template", "daily_limit")
    forms: list[dict[str, Any]] = []
    seen: list[str] = []
    ctx = AgentContext(
        SYSTEM_PROMPT,
        prompt,
        _tool_plan(now, store.WeatherRepo(tables.weather), forms, seen),
        _tool_assumptions(load_factors()),
    )
    try:
        answer = _plain(_run_with_timeout(_build_runner(), ctx))
    except Exception as err:  # the model, the network and the SDK can all fail
        # Narrow handling for known AWS SDK errors to avoid leaking details
        from botocore.exceptions import ClientError, ConnectTimeoutError, ReadTimeoutError, EndpointConnectionError
        # Determine a generic reason code
        reason = getattr(err, "response", {}).get("Error", {}).get("Code", type(err).__name__)
        # Map to stable reason strings for the client
        if reason in ("AccessDeniedException", "ValidationException"):
            note = "bedrock_not_authorized"
        elif reason == "ThrottlingException":
            note = "bedrock_throttled"
        elif isinstance(err, (ConnectTimeoutError, ReadTimeoutError, EndpointConnectionError)):
            note = "bedrock_timeout"
        else:
            note = "agent_failed"
        logger.warning(f"{note} reason={reason}")
        return _answer(template, "template", note)

    if not answer or _invents_numbers(answer, facts, *seen):
        logger.warning("agent_rejected reason=unsupported_number_or_empty")
        return _answer(template, "template", "agent_rejected")
    return _answer(answer, "agent", None, forms[-1] if forms else None)


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    return app.resolve(event, context)
