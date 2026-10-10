"""Units, IST one-hour slots and time helpers (plan step 02.1).

IST is a fixed UTC+05:30 offset instead of ``ZoneInfo("Asia/Kolkata")``: India has no daylight
saving, and the engine stays free of the ``tzdata`` package that Windows lacks.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), "IST")
SLOT_H = 1.0
WINDOW_SLOTS = 48
PERSON_DAY_L = 135.0  # CPHEEO city water norm, litres per person per day (also in factors.json)

_HOUR = timedelta(hours=1)
_MJ_PER_KWH = 3.6e9  # 1 kWh = 3.6e6 J = 3.6e9 mJ


def ensure_ist(ts: datetime) -> datetime:
    """Return ``ts`` converted to IST. Naive datetimes are rejected."""
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware (use an IST or UTC offset)")
    return ts.astimezone(IST)


def floor_hour(ts: datetime) -> datetime:
    """Start of the IST hour that contains ``ts``."""
    return ensure_ist(ts).replace(minute=0, second=0, microsecond=0)


def slot_starts(t0: datetime, n: int) -> list[datetime]:
    """``n`` consecutive hourly slot starts beginning at the hour that contains ``t0``."""
    first = floor_hour(t0)
    return [first + i * _HOUR for i in range(n)]


def slot0_capacity(submit_ts: datetime) -> float:
    """Share of slot 0 that is still left at submit time (decision D7)."""
    ts = ensure_ist(submit_ts)
    elapsed = ts.minute * 60 + ts.second + ts.microsecond / 1e6
    return 1.0 - elapsed / 3600.0


_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def clock_text(ts: datetime) -> str:
    """``03:14 on 10 Oct`` in IST. Fixed English names, so it does not depend on the locale."""
    t = ensure_ist(ts)
    return f"{t:%H:%M} on {t.day:02d} {_MONTHS[t.month - 1]}"


def when_text(ts: datetime) -> str:
    """``Sat 10 Oct 03:14`` in IST, locale independent."""
    t = ensure_ist(ts)
    return f"{_DAYS[t.weekday()]} {t.day:02d} {_MONTHS[t.month - 1]} {t:%H:%M}"


def mj_to_kwh(millijoules: float) -> float:
    """Convert millijoules (the NVML energy counter unit) to kWh."""
    return millijoules / _MJ_PER_KWH


def w_h_to_kwh(watts: float, hours: float) -> float:
    """Energy in kWh for a constant ``watts`` over ``hours``."""
    return watts * hours / 1000.0


def deadline_slots(submit_ts: datetime, deadline: datetime) -> tuple[int, bool]:
    """Whole one-hour slots, counted from the submit hour, that end on or before ``deadline``.

    Returns ``(slots, capped)``. ``slots`` is limited to ``WINDOW_SLOTS``; ``capped`` is True when
    the deadline is further away than the planning window.
    """
    base = floor_hour(submit_ts)
    whole = max(0, math.floor((ensure_ist(deadline) - base) / _HOUR))
    return min(whole, WINDOW_SLOTS), whole > WINDOW_SLOTS
