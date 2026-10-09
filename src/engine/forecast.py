"""48-slot forecast snapshot: raw weather plus derived cooling and grid intensities (plan 02.6).

A snapshot stores the raw weather and the *central* derived arrays. The low and high arrays are
recomputed from the raw weather with ``intensities()`` when ranges are needed.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from . import cooling as cooling_mod
from . import grid as grid_mod
from .cooling import Cooling
from .factors import DATA_DIR, Factors, FactorSet, get_city
from .units import IST, WINDOW_SLOTS, ensure_ist, floor_hour, slot0_capacity, slot_starts
from .wetbulb import stull_tw_checked

SAMPLE_PATH = DATA_DIR / "sample_forecast.json"
_ROUND = 5


@dataclass(frozen=True, slots=True)
class WeatherRow:
    """One hour of weather at a city (IST hour start)."""

    hour: datetime
    temp_c: float
    rh_pct: float
    rad_wm2: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "hour", floor_hour(self.hour))  # raises if naive


@dataclass(frozen=True, slots=True)
class Intensities:
    """Per-slot derived values."""

    tw: tuple[float, ...]
    pue: tuple[float, ...]
    wue: tuple[float, ...]
    ci: tuple[float, ...]
    ewif: tuple[float, ...]

    def __len__(self) -> int:
        return len(self.pue)


@dataclass(frozen=True, slots=True)
class ForecastSnapshot:
    city: str
    cooling: str
    pue_user: float | None
    submit_ts: datetime
    slots: tuple[datetime, ...]
    temp_c: tuple[float, ...]
    rh_pct: tuple[float, ...]
    rad_wm2: tuple[float, ...]
    derived: Intensities
    source: str  # "live" or "cached"
    slot0_capacity: float
    factor_version: str

    def to_json(self) -> dict[str, Any]:
        def arr(values: Sequence[float]) -> list[float]:
            return [round(v, _ROUND) for v in values]

        return {
            "city": self.city,
            "cooling": self.cooling,
            "pue_user": self.pue_user,
            "submit_ts": self.submit_ts.isoformat(),
            "slots": [s.isoformat() for s in self.slots],
            "temp_c": arr(self.temp_c),
            "rh_pct": arr(self.rh_pct),
            "rad_wm2": arr(self.rad_wm2),
            "tw": arr(self.derived.tw),
            "pue": arr(self.derived.pue),
            "wue": arr(self.derived.wue),
            "ci": arr(self.derived.ci),
            "ewif": arr(self.derived.ewif),
            "source": self.source,
            "slot0_capacity": round(self.slot0_capacity, 6),
            "factor_version": self.factor_version,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ForecastSnapshot:
        def tup(key: str) -> tuple[float, ...]:
            return tuple(float(v) for v in data[key])

        return cls(
            city=data["city"],
            cooling=data["cooling"],
            pue_user=data.get("pue_user"),
            submit_ts=ensure_ist(datetime.fromisoformat(data["submit_ts"])),
            slots=tuple(ensure_ist(datetime.fromisoformat(s)) for s in data["slots"]),
            temp_c=tup("temp_c"),
            rh_pct=tup("rh_pct"),
            rad_wm2=tup("rad_wm2"),
            derived=Intensities(tup("tw"), tup("pue"), tup("wue"), tup("ci"), tup("ewif")),
            source=data["source"],
            slot0_capacity=float(data["slot0_capacity"]),
            factor_version=data["factor_version"],
        )


def load_sample_rows(city: str, path: Path | str | None = None) -> list[WeatherRow]:
    """Rows of the saved Open-Meteo sample for the grid point nearest to ``city``."""
    info = get_city(city)
    entries = json.loads(Path(path or SAMPLE_PATH).read_text(encoding="utf-8"))
    best = min(
        entries,
        key=lambda e: (e["latitude"] - info.lat) ** 2 + (e["longitude"] - info.lon) ** 2,
    )
    hourly = best["hourly"]
    return [
        WeatherRow(
            datetime.fromisoformat(t).replace(tzinfo=IST),
            float(temp),
            float(rh),
            float(rad),
        )
        for t, temp, rh, rad in zip(
            hourly["time"],
            hourly["temperature_2m"],
            hourly["relative_humidity_2m"],
            hourly["shortwave_radiation"],
            strict=True,
        )
    ]


def derive(
    kind: Cooling,
    pue_user: float | None,
    slots: Sequence[datetime],
    temp_c: Sequence[float],
    rh_pct: Sequence[float],
    rad_wm2: Sequence[float],
    fx: Factors,
    fs: FactorSet,
) -> Intensities:
    """Wet-bulb, PUE, WUE, carbon and water intensity per slot for one factor set."""
    tw = tuple(stull_tw_checked(t, rh)[0] for t, rh in zip(temp_c, rh_pct, strict=True))
    pue = tuple(cooling_mod.pue(kind, t, fs, pue_user) for t in temp_c)
    wue = tuple(cooling_mod.wue(kind, w, fs) for w in tw)
    shares = grid_mod.hourly_shares(fx.grid, [s.hour for s in slots], rad_wm2, fs)
    return Intensities(
        tw=tw,
        pue=pue,
        wue=wue,
        ci=tuple(grid_mod.ci(s, fs) for s in shares),
        ewif=tuple(grid_mod.ewif(s, fs) for s in shares),
    )


def intensities(snap: ForecastSnapshot, fx: Factors, fs: FactorSet) -> Intensities:
    """Recompute the derived arrays of ``snap`` for another factor set (low, central or high)."""
    return derive(
        Cooling.parse(snap.cooling),
        snap.pue_user,
        snap.slots,
        snap.temp_c,
        snap.rh_pct,
        snap.rad_wm2,
        fx,
        fs,
    )


def build_snapshot(
    city: str,
    cooling: str,
    rows: Sequence[WeatherRow],
    fx: Factors,
    submit_ts: datetime,
    *,
    pue_user: float | None = None,
) -> ForecastSnapshot:
    """Snapshot for the 48 slots starting at the hour of ``submit_ts``.

    Hours missing from ``rows`` are filled from the saved sample by hour of day, and the snapshot
    is then marked ``cached``.
    """
    get_city(city)
    kind = Cooling.parse(cooling)
    slots = slot_starts(submit_ts, WINDOW_SLOTS)
    live = {r.hour: r for r in rows}
    fallback = {r.hour.hour: r for r in reversed(load_sample_rows(city))}  # first row per hour
    chosen = [live.get(s) or fallback[s.hour] for s in slots]
    source = "live" if all(s in live for s in slots) else "cached"
    temp = tuple(r.temp_c for r in chosen)
    rh = tuple(r.rh_pct for r in chosen)
    rad = tuple(r.rad_wm2 for r in chosen)
    return ForecastSnapshot(
        city=city,
        cooling=kind.value,
        pue_user=pue_user,
        submit_ts=ensure_ist(submit_ts),
        slots=tuple(slots),
        temp_c=temp,
        rh_pct=rh,
        rad_wm2=rad,
        derived=derive(kind, pue_user, slots, temp, rh, rad, fx, fx.central()),
        source=source,
        slot0_capacity=slot0_capacity(submit_ts),
        factor_version=fx.version,
    )
