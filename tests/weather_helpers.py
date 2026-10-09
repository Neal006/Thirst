"""Synthetic weather and request builders shared by the engine tests."""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from typing import Any

from engine.forecast import WeatherRow
from engine.planner import PlanRequest
from engine.units import IST, floor_hour

SUBMIT = datetime(2026, 10, 9, 21, 14, tzinfo=IST)
DEADLINE = datetime(2026, 10, 10, 9, 0, tzinfo=IST)


def ist(*args: int) -> datetime:
    return datetime(*args, tzinfo=IST)


def diurnal_rows(start: datetime, hours: int = 72, mean_temp: float = 30.0) -> list[WeatherRow]:
    """A plausible hot-day cycle: warmest at 15:00, sun between 06:00 and 18:00."""
    first = floor_hour(start)
    rows = []
    for i in range(hours):
        t = first + timedelta(hours=i)
        phase = math.sin((t.hour - 9) / 24 * 2 * math.pi)
        rows.append(
            WeatherRow(
                hour=t,
                temp_c=mean_temp + 5 * phase,
                rh_pct=70 - 15 * phase,
                rad_wm2=max(0.0, 800 * (1 - ((t.hour - 12) / 6) ** 2)),
            )
        )
    return rows


def flat_rows(
    start: datetime, hours: int = 72, temp: float = 30.0, rh: float = 70.0, rad: float = 500.0
) -> list[WeatherRow]:
    first = floor_hour(start)
    return [
        WeatherRow(first + timedelta(hours=i), temp, rh, rad) for i in range(hours)
    ]


def random_rows(start: datetime, hours: int, seed: int) -> list[WeatherRow]:
    rng = random.Random(seed)  # noqa: S311 - test data, not security
    first = floor_hour(start)
    return [
        WeatherRow(
            first + timedelta(hours=i),
            rng.uniform(18, 42),
            rng.uniform(25, 95),
            rng.uniform(0, 900),
        )
        for i in range(hours)
    ]


def request(**overrides: Any) -> PlanRequest:
    """The PRD default example: Chennai lab, 2 x RTX 4090, 6 h, deadline 09:00, can pause."""
    values: dict[str, Any] = {
        "city": "Chennai",
        "cooling": "room_ac",
        "pue_user": None,
        "gpu_model": "RTX-4090",
        "gpu_count": 2,
        "work_hours": 6.0,
        "deadline": DEADLINE,
        "pausable": True,
        "alpha": 0.5,
        "submit_ts": SUBMIT,
    }
    values.update(overrides)
    return PlanRequest(**values)
