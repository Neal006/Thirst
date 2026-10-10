"""Pure request validators (plan 05.5.a, 05.6, 05.7; contract 08 §3.1, 3.2, 3.4).

Each validator takes a decoded JSON value and returns a frozen object, or raises
``ApiError``. Type errors are 400 ``invalid_field``; unknown cities and GPUs, past deadlines
and slots outside the job have their own codes. Unknown extra fields are ignored. No I/O.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from engine.factors import LEVELS, load_cities, load_gpus
from engine.planner import PlanRequest
from engine.units import IST, floor_hour

from .errors import ApiError

SITE_ID = re.compile(r"s_[a-z2-7]{10}")
PLAN_ID = re.compile(r"p_[a-z2-7]{10}")
JOB_ID = re.compile(r"j_[a-z2-7]{12}")
COOLING = ("room_ac", "air_chiller", "evaporative")
CAP_METHODS = ("nvml", "nvidia_smi", "clock_lock", "none")
METHODS = ("nvml_energy", "nvml_power_integration", "modelled", "unverified")
MAX_RECEIPT_SLOTS = 72
MAX_RECEIPT_HOURS = 72
_ALPHA_STEPS = 10
_FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Cn"})


def _bad(message: str) -> ApiError:
    return ApiError(400, "invalid_field", message)


def _obj(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _bad(f"{name}: send a JSON object.")
    return value


def _number(value: Any, name: str, lo: float, hi: float, *, lo_open: bool = False) -> float:
    ok = isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)
    if not ok or value > hi or value < lo or (lo_open and value == lo):
        sign = "above" if lo_open else "from"
        raise _bad(f"{name}: use a number {sign} {lo:g} to {hi:g}.")
    return float(value)


def _integer(value: Any, name: str, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise _bad(f"{name}: use a whole number from {lo} to {hi}.")
    return value


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise _bad(f"{name}: use true or false.")
    return value


def _choice(value: Any, name: str, options: tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in options:
        raise _bad(f"{name}: use one of {', '.join(options)}.")
    return value


def _text(value: Any, name: str, lo: int, hi: int) -> str:
    """Trimmed text with control, format and private-use characters removed."""
    if not isinstance(value, str):
        raise _bad(f"{name}: use text.")
    cleaned = "".join(c for c in value if unicodedata.category(c) not in _FORBIDDEN_CATEGORIES)
    cleaned = cleaned.strip()
    if not lo <= len(cleaned) <= hi:
        raise _bad(f"{name}: use {lo} to {hi} characters.")
    return cleaned


def _aware(value: Any, name: str) -> datetime:
    """An ISO 8601 time with an offset, converted to IST."""
    if not isinstance(value, str) or len(value) > 40:
        raise _bad(f"{name}: use a time like 2026-10-10T09:00:00+05:30.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise _bad(f"{name}: use a time like 2026-10-10T09:00:00+05:30.") from None
    if parsed.utcoffset() is None:
        raise _bad(f"{name}: add a timezone offset such as +05:30.")
    return parsed.astimezone(IST)


def site_id(value: Any) -> str:
    if not isinstance(value, str) or not SITE_ID.fullmatch(value):
        raise _bad("site_id: not a valid site id.")
    return value


def _city(value: Any) -> str:
    if not isinstance(value, str):
        raise _bad("city: use text.")
    if value not in load_cities():
        raise ApiError(
            400,
            "unknown_city",
            "We only have data for Chennai, Bengaluru, Hyderabad, Mumbai, Delhi and Pune "
            "right now.",
        )
    return value


def _gpu_model(value: Any) -> str:
    if not isinstance(value, str):
        raise _bad("gpu_model: use text.")
    if value not in load_gpus():
        raise ApiError(400, "unknown_gpu", "Pick a GPU from the list.")
    return value


# /plan -------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PlanInput:
    city: str
    cooling: str
    pue_user: float | None
    gpu_model: str
    gpu_count: int
    work_hours: float
    deadline: datetime
    pausable: bool
    pausable_allowed: bool
    alpha: float
    force_now: bool
    site_id: str | None

    def to_request(self, submit_ts: datetime) -> PlanRequest:
        return PlanRequest(
            city=self.city,
            cooling=self.cooling,
            pue_user=self.pue_user,
            gpu_model=self.gpu_model,
            gpu_count=self.gpu_count,
            work_hours=self.work_hours,
            deadline=self.deadline,
            pausable=self.pausable,
            alpha=self.alpha,
            submit_ts=submit_ts,
            site_id=self.site_id,
            pausable_allowed=self.pausable_allowed,
        )


def _required(data: Mapping[str, Any], key: str) -> Any:
    if key not in data:
        raise _bad(f"{key}: required.")
    return data[key]


def plan_request(body: Any, now: datetime, site: Mapping[str, Any] | None = None) -> PlanInput:
    """Validate a ``POST /plan`` body. ``site`` (already looked up) supplies city and cooling."""
    data = _obj(body, "body")
    linked: str | None = None
    if site is not None:
        linked = site_id(site.get("site_id"))
    elif "site_id" in data:
        linked = site_id(data["site_id"])
    defaults = site if site is not None else {}
    city = _city(_required({**defaults, **data}, "city"))
    cooling = _choice(_required({**defaults, **data}, "cooling"), "cooling", COOLING)
    gpu_model = _gpu_model(_required(data, "gpu_model"))
    gpu_count = _integer(data.get("gpu_count"), "gpu_count", 1, 4096)
    work_hours = _number(data.get("work_hours"), "work_hours", 0.0, 48.0, lo_open=True)
    deadline = _aware(data.get("deadline"), "deadline")
    if deadline <= now:
        raise ApiError(400, "deadline_in_past", "The deadline is in the past.")
    pue = _number(data["pue"], "pue", 1.0, 3.0) if "pue" in data else None
    alpha = _number(data.get("alpha", 0.5), "alpha", 0.0, 1.0)
    if abs(alpha * _ALPHA_STEPS - round(alpha * _ALPHA_STEPS)) > 1e-6:
        raise _bad("alpha: use a step of 0.1 from 0 to 1.")
    return PlanInput(
        city=city,
        cooling=cooling,
        pue_user=pue if cooling == "evaporative" else None,
        gpu_model=gpu_model,
        gpu_count=gpu_count,
        work_hours=work_hours,
        deadline=deadline,
        pausable=_boolean(data.get("pausable", False), "pausable"),
        pausable_allowed=_boolean(data.get("pausable_allowed", True), "pausable_allowed"),
        alpha=round(alpha, 1),
        force_now=_boolean(data.get("force_now", False), "force_now"),
        site_id=linked,
    )


# /sites ------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SiteInput:
    name: str
    org: str | None
    city: str
    cooling: str
    gpu_count: int
    coverage_declared: float
    public: bool


def site_request(body: Any) -> SiteInput:
    data = _obj(body, "body")
    org: str | None = None
    if data.get("org") is not None:
        org = _text(data["org"], "org", 0, 80) or None
    return SiteInput(
        name=_text(data.get("name"), "name", 3, 60),
        org=org,
        city=_city(data.get("city")),
        cooling=_choice(data.get("cooling"), "cooling", COOLING),
        gpu_count=_integer(data.get("gpu_count"), "gpu_count", 1, 100000),
        coverage_declared=_number(data.get("coverage_declared", 0.0), "coverage_declared", 0, 1),
        public=_boolean(data.get("public", True), "public"),
    )


# /receipts ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReceiptInput:
    site_id: str
    plan_id: str | None
    job_id: str
    start_ts: datetime
    end_ts: datetime
    slots: tuple[Mapping[str, Any], ...]
    cap_applied: bool
    cap_method: str
    method: str
    gpu_name: str
    gpu_driver: str
    gpu_count: int
    exit_code: int | None
    interrupted: bool
    overran: bool
    cli_version: str | None

    @property
    def canonical_start(self) -> str:
        return self.start_ts.isoformat()

    @property
    def canonical_end(self) -> str:
        return self.end_ts.isoformat()


def _slot(raw: Any, index: int) -> dict[str, Any]:
    slot = _obj(raw, f"slots[{index}]")
    hour = _aware(slot.get("hour"), f"slots[{index}].hour")
    if (hour.minute, hour.second, hour.microsecond) != (0, 0, 0):
        raise _bad(f"slots[{index}].hour: use the start of an hour in IST.")
    level = _number(slot.get("level"), f"slots[{index}].level", 0.0, 1.0)
    snapped = min(LEVELS, key=lambda x: abs(x - level))
    if abs(snapped - level) > 1e-9:
        raise _bad(f"slots[{index}].level: use 1.0, 0.85 or 0.7.")
    return {
        "hour": hour.isoformat(),
        "run_kwh": _number(slot.get("run_kwh"), f"slots[{index}].run_kwh", 0.0, 1e9),
        "idle_kwh": _number(slot.get("idle_kwh"), f"slots[{index}].idle_kwh", 0.0, 1e9),
        "level": snapped,
    }


def _slots(raw: Any, start: datetime, end: datetime) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_RECEIPT_SLOTS:
        raise _bad(f"slots: send between 1 and {MAX_RECEIPT_SLOTS} slots.")
    slots = tuple(_slot(item, i) for i, item in enumerate(raw))
    if len({s["hour"] for s in slots}) != len(slots):
        raise _bad("slots: each hour may appear once.")
    first = floor_hour(start)
    for s in slots:
        hour = datetime.fromisoformat(s["hour"])
        if hour < first or hour > end:
            raise ApiError(
                422, "slot_out_of_range", "Some hours are outside the job's start and end."
            )
    return slots


def receipt_request(body: Any) -> ReceiptInput:
    data = _obj(body, "body")
    method = _choice(data.get("method"), "method", METHODS)
    plan_id = data.get("plan_id")
    if plan_id is None:
        if method != "unverified":
            raise _bad("plan_id: required unless the method is unverified.")
    elif not isinstance(plan_id, str) or not PLAN_ID.fullmatch(plan_id):
        raise _bad("plan_id: not a valid plan id.")
    job = data.get("job_id")
    if not isinstance(job, str) or not JOB_ID.fullmatch(job):
        raise _bad("job_id: not a valid job id.")
    start, end = _aware(data.get("start_ts"), "start_ts"), _aware(data.get("end_ts"), "end_ts")
    if not start < end <= start + timedelta(hours=MAX_RECEIPT_HOURS):
        raise _bad(f"end_ts: must be after start_ts and within {MAX_RECEIPT_HOURS} hours.")
    gpu = _obj(data.get("gpu"), "gpu")
    exit_code = data.get("exit_code")
    version = data.get("cli_version")
    return ReceiptInput(
        site_id=site_id(data.get("site_id")),
        plan_id=plan_id,
        job_id=job,
        start_ts=start,
        end_ts=end,
        slots=_slots(data.get("slots"), start, end),
        cap_applied=_boolean(data.get("cap_applied"), "cap_applied"),
        cap_method=_choice(data.get("cap_method"), "cap_method", CAP_METHODS),
        method=method,
        gpu_name=_text(gpu.get("name"), "gpu.name", 1, 100),
        gpu_driver=_text(gpu.get("driver", ""), "gpu.driver", 0, 40),
        gpu_count=_integer(gpu.get("count"), "gpu.count", 1, 100000),
        exit_code=None if exit_code is None else _integer(exit_code, "exit_code", -255, 255),
        interrupted=_boolean(data.get("interrupted", False), "interrupted"),
        overran=_boolean(data.get("overran", False), "overran"),
        cli_version=None if version is None else _text(version, "cli_version", 1, 32),
    )
