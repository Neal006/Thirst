"""Per-hour energy buckets in IST (plan 04.3.c). Shared by the NVML meter and the modelled meter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
_HOUR = timedelta(hours=1)
STATES = ("wait", "run", "idle")


@dataclass(frozen=True)
class SlotEnergy:
    """One IST hour of a receipt (contract 08 §3.4)."""

    hour: str
    run_kwh: float
    idle_kwh: float
    level: float


def floor_hour(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


class SlotLedger:
    """Adds energy to hourly slots. An interval that crosses an hour is split by time."""

    def __init__(self) -> None:
        self._energy: dict[datetime, dict[str, float]] = {}
        self._by_level: dict[datetime, dict[float, float]] = {}

    def add(self, end: datetime, seconds: float, state: str, level: float, kwh: float) -> None:
        """Credit ``kwh`` used in the ``seconds`` before ``end`` to ``state`` ("run" or "idle")."""
        end_ist = end.astimezone(IST)
        if seconds <= 0:
            self._credit(floor_hour(end_ist), state, level, kwh)
            return
        start = end_ist - timedelta(seconds=seconds)
        cursor = start
        while cursor < end_ist:
            boundary = min(floor_hour(cursor) + _HOUR, end_ist)
            share = (boundary - cursor).total_seconds() / seconds
            self._credit(floor_hour(cursor), state, level, kwh * share)
            cursor = boundary

    def _credit(self, hour: datetime, state: str, level: float, kwh: float) -> None:
        self._energy.setdefault(hour, {"run": 0.0, "idle": 0.0})[state] += kwh
        by_level = self._by_level.setdefault(hour, {})
        by_level[level] = by_level.get(level, 0.0) + kwh

    def slots(self) -> tuple[SlotEnergy, ...]:
        """Slots in time order. The level is the one that used the most energy in that hour."""
        result = []
        for hour in sorted(self._energy):
            levels = self._by_level[hour]
            level = max(levels, key=lambda item: (levels[item], item))
            parts = self._energy[hour]
            result.append(SlotEnergy(hour.isoformat(), parts["run"], parts["idle"], level))
        return tuple(result)

    def totals_kwh(self) -> tuple[float, float]:
        run = sum(parts["run"] for parts in self._energy.values())
        idle = sum(parts["idle"] for parts in self._energy.values())
        return run, idle
