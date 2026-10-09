"""Hourly grid shares, carbon and water intensity (plan step 02.5).

Two input kinds (``grid_shares.json``, plan 08 §2.4):

* ``hod_profile`` (Option A): an hour-of-day share profile from 5-minute national data. Solar is
  scaled by forecast radiation relative to the profile's mean radiation for that hour.
* ``annual`` (Option B): annual shares only. Solar is scaled by radiation relative to the mean
  radiation of the supplied window.

Solar changes are taken from (or given to) coal, so the shares keep summing to one.
Intensities are *average*, not marginal (Idea section 6.5).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .factors import FactorSet

SOURCES = ("coal", "gas", "nuclear", "hydro", "solar", "wind", "other")
_SUM_TOLERANCE = 1e-3  # input files are rounded to four decimals
DEFAULT_PATH = Path(__file__).parent / "data" / "grid_shares.json"


@dataclass(frozen=True, slots=True)
class GridModel:
    """Parsed ``grid_shares.json``."""

    kind: str
    annual_shares: Mapping[str, float]
    s_avg_solar: float
    profiles: Mapping[int, Mapping[str, float]] | None
    mean_radiation_profile: Mapping[int, float] | None
    status: str
    source: str


def calibrate_coal_ef(annual_shares: Mapping[str, float], ef_gas: float, target: float) -> float:
    """Coal CO2 factor (kg/kWh) that makes the annual mix match ``target`` (the CEA grid factor)."""
    s_coal = annual_shares.get("coal", 0.0)
    if s_coal <= 0:
        raise ValueError("cannot calibrate: the annual coal share must be positive")
    return (target - annual_shares.get("gas", 0.0) * ef_gas) / s_coal


def _normalised(raw: Mapping[str, Any], what: str) -> dict[str, float]:
    shares = {k: float(raw.get(k, 0.0)) for k in SOURCES}
    if any(v < 0 for v in shares.values()):
        raise ValueError(f"{what}: shares must not be negative")
    total = sum(shares.values())
    if abs(total - 1.0) > _SUM_TOLERANCE:
        raise ValueError(f"{what}: shares must sum to 1 (got {total:.4f})")
    return {k: v / total for k, v in shares.items()}


def load_grid(path: Path | str | None = None) -> GridModel:
    """Read and validate a grid shares file."""
    data = json.loads(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    kind = data.get("kind")
    if kind not in ("annual", "hod_profile"):
        raise ValueError(f"grid_shares kind must be 'annual' or 'hod_profile' (got {kind!r})")
    annual = _normalised(data.get("annual_shares", {}), "annual shares")
    profiles: dict[int, dict[str, float]] | None = None
    mean_rad: dict[int, float] | None = None
    if kind == "hod_profile":
        profiles = {
            int(h): _normalised(p, f"profile hour {h}") for h, p in data["profiles"].items()
        }
        mean_rad = {int(h): float(v) for h, v in data["mean_radiation_profile"].items()}
        if set(profiles) != set(range(24)) or set(mean_rad) != set(range(24)):
            raise ValueError("hod_profile needs profiles and mean radiation for hours 0 to 23")
    return GridModel(
        kind=kind,
        annual_shares=annual,
        s_avg_solar=float(data.get("s_avg_solar", annual["solar"])),
        profiles=profiles,
        mean_radiation_profile=mean_rad,
        status=str(data.get("status", "sourced")),
        source=str(data.get("source", "")),
    )


def _shift_solar(base: Mapping[str, float], base_solar: float, solar: float) -> dict[str, float]:
    """Set solar to ``solar`` and move the difference to or from coal (then gas, then other)."""
    shares = dict(base)
    shares["solar"] = solar
    coal = base["coal"] - (solar - base_solar)
    if coal < 0:
        deficit = -coal
        coal = 0.0
        for name in ("gas", "other"):
            take = min(deficit, shares[name])
            shares[name] -= take
            deficit -= take
    shares["coal"] = coal
    total = sum(shares.values())  # differs from 1 only when coal, gas and other ran out
    return {k: v / total for k, v in shares.items()}


def hourly_shares(
    model: GridModel,
    hours_of_day: Sequence[int],
    rad: Sequence[float],
    fs: FactorSet,
) -> list[dict[str, float]]:
    """Generation shares per slot, from its hour of day (0-23) and forecast radiation (W/m2)."""
    if len(hours_of_day) != len(rad):
        raise ValueError("hours_of_day and rad must have the same length")
    cap = fs["solar_share_cap"]
    mean_window = sum(rad) / len(rad) if rad else 0.0
    out: list[dict[str, float]] = []
    for hod, r in zip(hours_of_day, rad, strict=True):
        if model.kind == "hod_profile":
            assert model.profiles is not None and model.mean_radiation_profile is not None  # noqa: S101
            base = model.profiles[hod]
            base_solar = base["solar"]
            mean_r = model.mean_radiation_profile[hod]
            solar = min(cap, base_solar * r / mean_r) if mean_r > 0 else base_solar
        else:
            base = model.annual_shares
            base_solar = model.s_avg_solar
            solar = min(cap, base_solar * r / mean_window) if mean_window > 0 else 0.0
        out.append(_shift_solar(base, base_solar, solar))
    return out


def ci(shares: Mapping[str, float], fs: FactorSet) -> float:
    """Carbon intensity in kg CO2 per kWh (average mix, direct combustion basis)."""
    return sum(share * fs[f"ef_{name}"] for name, share in shares.items())


def ewif(shares: Mapping[str, float], fs: FactorSet) -> float:
    """Electricity water intensity in litres consumed per kWh."""
    return sum(share * fs[f"wf_{name}"] for name, share in shares.items()) * fs["grid_loss_factor"]
