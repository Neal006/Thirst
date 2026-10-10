"""The ``POST /plan`` request (plan 04.6.a, contract 08 §3.1).

Always sends ``site_id`` (decision D23), so the server takes city and cooling from the site and
links the plan to it. ``force_now`` is only sent for ``thirst run --now``.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from .errors import CliError
from .ledger import IST

MAX_WORK_HOURS = 48.0
_ALPHA_STEPS = 10
_DEADLINE_HELP = "Use a date and time such as 2026-10-10 09:00 (India time)."


def parse_deadline(text: str) -> datetime:
    """A deadline as an aware datetime. Text without a zone means India time (IST)."""
    normalised = text.strip().replace(" ", "T", 1)
    if "T" not in normalised:
        raise CliError(f"The deadline needs a date and a time. {_DEADLINE_HELP}")
    try:
        parsed = datetime.fromisoformat(normalised)
    except ValueError:
        raise CliError(f"Could not read the deadline '{text}'. {_DEADLINE_HELP}") from None
    return parsed.replace(tzinfo=IST) if parsed.tzinfo is None else parsed.astimezone(IST)


def _alpha(value: float) -> float:
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise CliError("alpha must be between 0 and 1 in steps of 0.1.")
    if abs(value * _ALPHA_STEPS - round(value * _ALPHA_STEPS)) > 1e-6:
        raise CliError("alpha must be between 0 and 1 in steps of 0.1 (0.3, 0.5, 0.7 ...).")
    return round(value, 1)


def _hours(value: float) -> float:
    if not math.isfinite(value) or not 0 < value <= MAX_WORK_HOURS:
        raise CliError(f"--hours must be above 0 and at most {MAX_WORK_HOURS:g}.")
    return float(value)


def build_plan_request(
    *,
    site_id: str,
    gpu_model: str,
    gpu_count: int,
    work_hours: float,
    deadline: datetime,
    pausable: bool,
    pausable_allowed: bool,
    alpha: float,
    force_now: bool,
) -> dict[str, Any]:
    """The JSON body for ``POST /plan``."""
    if gpu_count < 1:
        raise CliError("The job needs at least one GPU.")
    body: dict[str, Any] = {
        "site_id": site_id,
        "gpu_model": gpu_model,
        "gpu_count": int(gpu_count),
        "work_hours": _hours(work_hours),
        "deadline": deadline.astimezone(IST).isoformat(),
        "pausable": bool(pausable),
        "pausable_allowed": bool(pausable_allowed),
        "alpha": _alpha(alpha),
    }
    if force_now:
        body["force_now"] = True
    return body
