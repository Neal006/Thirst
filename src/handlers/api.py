"""HTTP API router: /plan, /sites, /receipts, /leaderboard, /assumptions (plan 05.5-05.8).

Handlers stay thin: checks live in ``validation`` and ``security``, I/O in ``store`` and the
science in ``engine``. Errors are always ``{"error": code, "message": plain words}``; an
unexpected failure is logged with its stack trace and answered with a generic 503.

Receipt checks run cheapest first and verify the signature before parsing the JSON (TRD 14):
headers, body size, signature (which includes the 10 minute window), site, JSON, validation,
plan ownership, plausibility, scoring, one transaction.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import Response
from aws_lambda_powertools.logging import correlation_paths

from engine import planner, score
from engine.factors import Factors, load_factors
from engine.units import IST, floor_hour

from . import assumptions, http, security, store, validation
from .cache import TtlCache
from .errors import TRY_AGAIN, ApiError
from .http import MAX_BODY_RECEIPT, MAX_BODY_SMALL

CACHE_SECONDS = 20  # site pages and leaderboards (PRD 6.2.7: on the board within a minute)
# Anyone can register a site and a site's token can sign receipts, so work and storage are capped.
MAX_SITES_PER_DAY = 1000  # new sites per IST day, whole service (far above judging traffic)
MAX_RECEIPTS_PER_SITE_PER_DAY = 2000
LEADERBOARD_MAX_ROWS = 100
RECEIPT_MAX_AGE = timedelta(days=30)  # older receipts could never be scored into the 30-day window
CLOCK_SKEW = timedelta(seconds=security.MAX_SKEW_SECONDS)
DIVISIONS = ("D1", "D2", "D3", "D4")

logger = Logger(service="thirst")
app = http.new_app(logger)

_site_cache = TtlCache(CACHE_SECONDS)
_board_cache = TtlCache(CACHE_SECONDS)


def _now() -> datetime:
    return datetime.now(IST)


def reset_caches() -> None:
    _site_cache.clear()
    _board_cache.clear()


# ---------------------------------------------------------------------- helpers


_json = http.json_response
_parse = http.parse_json


def _new_id(prefix: str, size: int = 10) -> str:  # a module-level name so tests can replace it
    return http.new_id(prefix, size)


def _body(limit: int) -> bytes:
    return http.read_body(app, limit)


def _tables() -> store.Tables:
    return store.get_tables()


def _require_site(site_id: str) -> dict[str, Any]:
    site = store.SiteRepo(_tables().sites).get(site_id)
    if site is None:
        raise ApiError(404, "site_not_found", "We couldn't find that site.")
    return site


def _division(site: Mapping[str, Any], fx: Factors) -> str:
    return str(site.get("division") or score.division(int(site["gpu_count"]), fx.central()))


def _site_view(site_id: str, site: dict[str, Any], now: datetime) -> dict[str, Any]:
    """The site page, cached for 20 s per warm instance."""
    cached = _site_cache.get(site_id, now)
    if cached is not None:
        return dict(cached)
    receipts = store.ReceiptRepo(_tables().receipts).last_30_days(site_id, now)
    view = score.site_page_view(site, receipts, now, load_factors())
    _site_cache.put(site_id, view, now)
    return view


# ---------------------------------------------------------------------- POST /plan


@app.post("/plan")
def post_plan() -> Response[str]:
    body = _parse(_body(MAX_BODY_SMALL))
    now = _now()
    site = None
    if isinstance(body, Mapping) and "site_id" in body:
        site = _require_site(validation.site_id(body["site_id"]))
    inp = validation.plan_request(body, now, site)
    tables = _tables()
    window = store.WeatherRepo(tables.weather).window(inp.city, floor_hour(now), 48)
    result = planner.plan_from_rows(inp.to_request(now), window.rows)
    age = None if window.issued is None else int((now - window.issued).total_seconds() // 3600)
    result = {**result, "plan_id": _new_id("p_"), "forecast_age_hours": age}
    store.PlanRepo(tables.plans).put(result, inp.site_id)
    return _json(200, {k: v for k, v in result.items() if k != "forecast_snapshot"})


# ---------------------------------------------------------------------- /sites


@app.post("/sites")
def post_site() -> Response[str]:
    inp = validation.site_request(_parse(_body(MAX_BODY_SMALL)))
    now = _now()
    if not store.PlanRepo(_tables().plans).bump_quota(now, MAX_SITES_PER_DAY, scope="sites"):
        raise ApiError(429, "rate_limited", "Too many new sites today. Please try again tomorrow.")
    fx = load_factors()
    repo = store.SiteRepo(_tables().sites)
    division = score.division(inp.gpu_count, fx.central())
    for _ in range(3):  # a collision of 50 random bits is a bug, but retrying is free
        site_id = _new_id("s_")
        item = {
            "site_id": site_id,
            "name": inp.name,
            "org": inp.org,
            "city": inp.city,
            "cooling": inp.cooling,
            "gpu_count": inp.gpu_count,
            "division": division,
            "coverage_declared": inp.coverage_declared,
            "public": inp.public,
            "simulated": False,
            "created_at": now.isoformat(),
        }
        try:
            repo.create(item)
            break
        except store.SiteExists:
            continue
    else:
        raise ApiError(503, "try_again", TRY_AGAIN)
    _board_cache.clear()  # the new site is listed (unrated) straight away
    token = security.site_token(security.load_secret(), site_id)  # shown once, never stored
    return _json(201, {"site_id": site_id, "token": token, "division": division})


@app.get("/sites/<site_id>")
def get_site(site_id: str) -> Response[str]:
    sid = validation.site_id(site_id)
    site = _require_site(sid)
    return _json(200, _site_view(sid, site, _now()))


# ---------------------------------------------------------------------- /receipts


def _check_plausible(
    inp: validation.ReceiptInput, gpu_count: int, p_max_w: float, tolerance: float
) -> None:
    """Total kWh may not exceed what the GPUs could draw in the job's time (TRD 7.1)."""
    hours = (inp.end_ts - inp.start_ts).total_seconds() / 3600
    allowed = gpu_count * p_max_w / 1000 * hours * tolerance
    if sum(s["run_kwh"] + s["idle_kwh"] for s in inp.slots) > allowed:
        raise ApiError(
            422,
            "implausible_energy",
            "This energy is more than your GPUs can draw. Receipt rejected.",
        )


def _plan_for(inp: validation.ReceiptInput, site_id: str, now: datetime) -> dict[str, Any] | None:
    if inp.plan_id is None:
        return None
    plan = store.PlanRepo(_tables().plans).get(inp.plan_id)
    if plan is None:
        raise ApiError(404, "plan_not_found", "We couldn't find that plan.")
    if plan.get("site_id") != site_id:  # also true for a plan made without a site (D23)
        raise ApiError(403, "plan_site_mismatch", "This plan belongs to another site.")
    if int(plan["ttl"]) <= int(now.timestamp()):  # DynamoDB deletes expired items late
        raise ApiError(404, "plan_not_found", "We couldn't find that plan.")
    submitted = datetime.fromisoformat(plan["submit_ts"])
    if inp.start_ts < floor_hour(submitted):
        raise ApiError(422, "slot_out_of_range", "Some hours are outside the job's start and end.")
    return plan


def _plausibility_inputs(
    plan: dict[str, Any] | None, site: Mapping[str, Any], fx: Factors
) -> tuple[int, float]:
    if plan is not None:
        gpu = fx.gpus[plan["inputs"]["gpu_model"]]
        return int(plan["inputs"]["gpu_count"]), gpu.p_max_w
    return int(site["gpu_count"]), max(m.p_max_w for m in fx.gpus.values())


def _scored(
    inp: validation.ReceiptInput, plan: dict[str, Any] | None, weather: store.WeatherRepo
) -> dict[str, Any] | None:
    if plan is None:
        return None
    doc = {
        "job_id": inp.job_id,
        "end_ts": inp.canonical_end,
        "method": inp.method,
        "slots": [dict(s) for s in inp.slots],
    }
    hours = [datetime.fromisoformat(s["hour"]) for s in inp.slots]
    observed = weather.observed(plan["inputs"]["city"], hours)
    return score.receipt_footprints(doc, plan, observed)


def _tags(method: str, scored: dict[str, Any] | None) -> dict[str, str]:
    if method == "unverified":
        return {"energy": "unverified", "water": "modelled", "co2": "modelled"}
    if scored is not None:
        return dict(scored["tags"])
    return {"energy": "modelled", "water": "modelled", "co2": "modelled"}


def _receipt_item(
    inp: validation.ReceiptInput, scored: dict[str, Any] | None, now: datetime
) -> dict[str, Any]:
    counted = scored is not None and inp.method != "unverified"
    kwh = sum(s["run_kwh"] + s["idle_kwh"] for s in inp.slots)
    return {
        "site_id": inp.site_id,
        "job_id": inp.job_id,
        "plan_id": inp.plan_id,
        "start_ts": inp.canonical_start,
        "end_ts": inp.canonical_end,
        "slots": [dict(s) for s in inp.slots],
        "method": inp.method,
        "cap_applied": inp.cap_applied,
        "cap_method": inp.cap_method,
        "gpu": {"name": inp.gpu_name, "driver": inp.gpu_driver, "count": inp.gpu_count},
        "scoring": scored["scoring"] if scored else None,
        "absolute": scored["absolute"] if scored else None,
        "capture": scored["capture"] if scored else None,
        "no_room": bool(scored["no_room"]) if scored else False,
        "flexible": bool(scored["flexible"]) if counted and scored else False,
        "scored": counted,
        "kwh": scored["kwh"] if scored else kwh,
        "tags": _tags(inp.method, scored),
        "extrapolated_hours": scored["extrapolated_hours"] if scored else [],
        "factor_version_mismatch": bool(scored and scored["factor_version_mismatch"]),
        "exit_code": inp.exit_code,
        "interrupted": inp.interrupted,
        "overran": inp.overran,
        "cli_version": inp.cli_version,
        "created_at": now.isoformat(),
    }


def _receipt_response(item: Mapping[str, Any], site_score: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "receipt_id": f"{item['site_id']}#{item['end_ts']}#{item['job_id']}",
        "scoring": item["scoring"],
        "absolute": item["absolute"],
        "capture": item["capture"],
        "no_room": item["no_room"],
        "flexible": item["flexible"],
        "tags": item["tags"],
        "site_score": {
            "value": site_score["value"],
            "badge": site_score["badge"],
            "provisional": site_score["provisional"],
        },
        "url": f"/receipts/{item['site_id']}/{item['job_id']}",
    }


@app.post("/receipts")
def post_receipt() -> Response[str]:
    started = time.perf_counter()
    event = app.current_event.raw_event
    timestamp, signature, site_id = security.require_headers(event.get("headers") or {})
    now = _now()
    if not validation.SITE_ID.fullmatch(site_id):
        raise ApiError(401, "bad_signature", "This receipt could not be verified.")
    raw = _body(MAX_BODY_RECEIPT)
    security.verify_signature(
        security.load_secret(), site_id, timestamp, raw, signature, int(now.timestamp())
    )
    site = _require_site(site_id)  # only a caller with the token learns whether a site exists
    inp = validation.receipt_request(_parse(raw))
    if inp.site_id != site_id:
        raise ApiError(400, "invalid_field", "site_id: must match the X-Thirst-Site header.")
    if inp.end_ts > now + CLOCK_SKEW:
        raise ApiError(400, "invalid_field", "end_ts: is in the future.")
    if inp.end_ts <= now - RECEIPT_MAX_AGE:
        raise ApiError(400, "invalid_field", "end_ts: is older than 30 days.")
    fx = load_factors()
    plan = _plan_for(inp, site_id, now)
    count, p_max_w = _plausibility_inputs(plan, site, fx)
    _check_plausible(inp, count, p_max_w, fx.central()["receipt_kwh_tolerance"])
    tables = _tables()
    if not store.PlanRepo(tables.plans).bump_quota(
        now, MAX_RECEIPTS_PER_SITE_PER_DAY, scope=f"receipts#{site_id}"
    ):
        raise ApiError(
            429, "rate_limited", "Too many receipts today for this site. Please try again tomorrow."
        )
    scored = _scored(inp, plan, store.WeatherRepo(tables.weather))
    item = _receipt_item(inp, scored, now)
    try:
        store.ReceiptRepo(tables.receipts).put_with_guard(item)
    except store.DuplicateJob:
        raise ApiError(409, "duplicate_job", "This receipt was already recorded.") from None
    _site_cache.invalidate(site_id)
    _board_cache.clear()
    page = _site_view(site_id, site, now)
    logger.info(
        f"receipt_recorded site_id={site_id} job_id={inp.job_id} kwh={item['kwh']:.3f} "
        f"capture={item['capture']} latency_ms={(time.perf_counter() - started) * 1000:.0f}"
    )
    return _json(200, _receipt_response(item, page["score"]))


@app.get("/receipts/<site_id>/<job_id>")
def get_receipt(site_id: str, job_id: str) -> Response[str]:
    sid = validation.site_id(site_id)
    if not validation.JOB_ID.fullmatch(job_id):
        raise ApiError(400, "invalid_field", "job_id: not a valid job id.")
    not_found = ApiError(404, "receipt_not_found", "We couldn't find that receipt.")
    site = store.SiteRepo(_tables().sites).get(sid)
    if site is None or not site.get("public", True):  # private sites are hidden (D26)
        raise not_found
    item = store.ReceiptRepo(_tables().receipts).get(sid, job_id)
    if item is None:
        raise not_found
    extrapolated = set(item.get("extrapolated_hours") or [])
    slots = [
        {**s, "extrapolated": True} if s["hour"] in extrapolated else dict(s) for s in item["slots"]
    ]
    page = _site_view(sid, site, _now())
    return _json(
        200,
        {
            **_receipt_response(item, page["score"]),
            "slots": slots,
            "start_ts": item["start_ts"],
            "end_ts": item["end_ts"],
            "method": item["method"],
            "cap_applied": item["cap_applied"],
            "cap_method": item["cap_method"],
            "gpu": {"name": item["gpu"]["name"]},  # never the GPU count
        },
    )


# ---------------------------------------------------------------------- boards


@app.get("/leaderboard")
def get_leaderboard() -> Response[str]:
    query = app.current_event.query_string_parameters or {}
    division = query.get("division", "D1")
    if division not in DIVISIONS:
        raise ApiError(400, "invalid_field", f"division: use one of {', '.join(DIVISIONS)}.")
    if query.get("period", "30d") != "30d":
        raise ApiError(400, "invalid_field", "period: only 30d is available.")
    if query.get("board", "score") != "score":
        raise ApiError(400, "invalid_field", "board: only score is available.")
    now = _now()
    key = (division, "30d", "score")
    cached = _board_cache.get(key, now)
    if cached is not None:
        return _json(200, cached)
    fx = load_factors()
    tables = _tables()
    sites = store.SiteRepo(tables.sites).scan_all()
    receipts = store.ReceiptRepo(tables.receipts)
    by_site = {
        s["site_id"]: receipts.last_30_days(s["site_id"], now)
        for s in sites
        if _division(s, fx) == division and s.get("public", True)
    }
    rows = score.leaderboard_rows(sites, by_site, division, now, fx)[:LEADERBOARD_MAX_ROWS]
    data = {
        "division": division,
        "period": "30d",
        "board": "score",
        "generated_at": now.isoformat(),
        "rows": rows,
    }
    _board_cache.put(key, data, now)
    return _json(200, data)


@app.get("/assumptions")
def get_assumptions() -> Response[str]:
    return _json(200, assumptions.build(load_factors()), cache="max-age=300")

# ---------------------------------------------------------------------- POST /parse-sentence
from .job_sentence import parse_job_sentence

@app.post("/parse-sentence")
def post_parse_sentence() -> Response[str]:
    body = _parse(_body(MAX_BODY_SMALL))
    if not isinstance(body, Mapping) or not isinstance(body.get("sentence"), str):
        raise ApiError(400, "invalid_field", "body: send a JSON with a string field 'sentence'.")
    result = parse_job_sentence(body["sentence"])
    return _json(200, result)


# ---------------------------------------------------------------------- entry point


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    return app.resolve(event, context)
