"""Receipt scoring, site score, badges, divisions and leaderboard rows (plan 02.8, TRD 5.9).

For every receipt three versions of the same footprint are computed with the *forecast snapshot
saved at submit time*, so a wrong forecast never lowers a score (Idea 7.2):

* Base   - the same work at full power, starting at slot 0
* Best   - the saved J-optimal plan, scaled to this receipt's energy (terms are linear in energy)
* Actual - the measured run and idle energy

Absolute litres and kilograms use observed weather where it exists.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

from .cooling import Cooling
from .errors import EngineError
from .factors import Factors, FactorSet, get_city, load_factors
from .footprint import Totals, footprint
from .forecast import ForecastSnapshot, Intensities, WeatherRow, derive
from .planner import LEVELS
from .units import WINDOW_SLOTS, ensure_ist, floor_hour

MEASURED_METHODS = frozenset({"nvml_energy", "nvml_power_integration"})
WINDOW_DAYS = 30
RECENT_RECEIPTS = 10
MAX_RECEIPT_SLOTS = 72  # a receipt covers at most 72 hours (plan 08 §3.4)
MIN_RUN_KWH = 1e-3  # below 1 Wh the ratios against Base are numerical noise, not a job
MAX_BASE_SLOTS = 4 * WINDOW_SLOTS  # more Base hours than this can only come from bad energy values
NEEDS_FLEXIBLE = "needs_flexible_receipt"
_HOUR = timedelta(hours=1)
_PARTS_MAX = 70.0  # A (50) + C (20); B is not rated in v0


# --------------------------------------------------------------------------- small formulas


def j_value(
    w: float, c: float, e: float, w_b: float, c_b: float, e_b: float, fs: FactorSet
) -> float:
    """Combined footprint relative to Base: 0.45 W/W_b + 0.35 C/C_b + 0.20 E/E_b."""

    def ratio(x: float, base: float) -> float:
        return x / base if base > 0 else 0.0

    return (
        fs["j_w_water"] * ratio(w, w_b)
        + fs["j_w_carbon"] * ratio(c, c_b)
        + fs["j_w_energy"] * ratio(e, e_b)
    )


def capture(j_actual: float, j_best: float, fs: FactorSet) -> tuple[float | None, bool]:
    """(Capture, no_room). With almost nothing to save Capture is None and no_room is True."""
    room = 1.0 - j_best
    if room < fs["no_room_threshold"]:
        return None, True
    return min(max((1.0 - j_actual) / room, 0.0), 1.0), False


def division(gpu_count: int, fs: FactorSet | None = None) -> str:
    fs = fs or load_factors().central()
    if gpu_count <= fs["div_d1_max"]:
        return "D1"
    if gpu_count <= fs["div_d2_max"]:
        return "D2"
    return "D3" if gpu_count <= fs["div_d3_max"] else "D4"


def badge(score: float | None, flex_share: float, fs: FactorSet | None = None) -> str | None:
    """Badge name, or None. Gold and Platinum need at least 30% of energy from flexible jobs."""
    if score is None:
        return None
    fs = fs or load_factors().central()
    if flex_share >= fs["flex_share_gold"]:
        if score >= fs["badge_platinum"]:
            return "platinum"
        if score >= fs["badge_gold"]:
            return "gold"
    if score >= fs["badge_silver"]:
        return "silver"
    return "bronze" if score >= fs["badge_bronze"] else None


# --------------------------------------------------------------------------- receipt footprints


def _fp(t: Totals, fs: FactorSet) -> dict[str, float]:
    return {
        "E_gpu_kwh": t.e_gpu_kwh,
        "E_fac_kwh": t.e_fac_kwh,
        "litres": t.water_l,
        "W_l": t.stress_l,
        "C_kg": t.co2_kg,
        "person_days": t.person_days(fs),
    }


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise EngineError("invalid_field", f"slots: {name} must be a finite number.")
    return float(value)


def _parse_slot(
    slot: Mapping[str, Any], snap: ForecastSnapshot
) -> tuple[datetime, int, float, float, float]:
    """One receipt slot as (hour, snapshot index, run kWh, idle kWh, level), fully validated."""
    try:
        hour = floor_hour(datetime.fromisoformat(slot["hour"]))
        raw_run, raw_idle, raw_level = slot["run_kwh"], slot["idle_kwh"], slot["level"]
    except (KeyError, TypeError, ValueError):
        raise EngineError(
            "invalid_field",
            "slots: each slot needs hour (with timezone), run_kwh, idle_kwh and level.",
        ) from None
    run_kwh, idle_kwh = _finite(raw_run, "run_kwh"), _finite(raw_idle, "idle_kwh")
    level_value = _finite(raw_level, "level")
    idx = round((hour - snap.slots[0]) / _HOUR)
    if not 0 <= idx < WINDOW_SLOTS + MAX_RECEIPT_SLOTS:
        raise EngineError("slot_out_of_range", "Some hours are outside the job's start and end.")
    if run_kwh < 0 or idle_kwh < 0:
        raise EngineError("invalid_field", "slots: energy must not be negative.")
    level = min(LEVELS, key=lambda x: abs(x - level_value))
    if abs(level - level_value) > 1e-6:
        raise EngineError("invalid_field", "slots: level must be 1.0, 0.85 or 0.7.")
    return hour, idx, run_kwh, idle_kwh, level


def _group_hours(
    receipt: Mapping[str, Any], snap: ForecastSnapshot, max_hour_kwh: float
) -> tuple[dict[int, float], dict[int, float], dict[int, float], list[str]]:
    """Receipt slots summed per snapshot hour: run kWh, idle kWh, level, extrapolated hours."""
    slots = receipt.get("slots")
    if not isinstance(slots, list | tuple) or not 1 <= len(slots) <= MAX_RECEIPT_SLOTS:
        raise EngineError("invalid_field", f"slots: send between 1 and {MAX_RECEIPT_SLOTS} slots.")
    run: dict[int, float] = {}
    idle: dict[int, float] = {}
    level: dict[int, float] = {}
    biggest: dict[int, float] = {}
    extrapolated: list[str] = []
    for s in slots:
        hour, idx, run_kwh, idle_kwh, lv = _parse_slot(s, snap)
        if idx >= WINDOW_SLOTS and hour.isoformat() not in extrapolated:
            extrapolated.append(hour.isoformat())
        run[idx] = run.get(idx, 0.0) + run_kwh
        idle[idx] = idle.get(idx, 0.0) + idle_kwh
        if run[idx] + idle[idx] > max_hour_kwh:
            raise EngineError(
                "implausible_energy",
                "This energy is more than your GPUs can draw. Receipt rejected.",
            )
        if run_kwh >= biggest.get(idx, -1.0):
            level[idx], biggest[idx] = lv, run_kwh
    if sum(run.values()) < MIN_RUN_KWH:
        raise EngineError(
            "invalid_field", "slots: a receipt needs at least 1 Wh of run energy in total."
        )
    return run, idle, level, extrapolated


def _base_energy(e_base_gpu: float, n_kw: float, f0: float) -> list[float]:
    """Base GPU energy per slot: full power from slot 0 (partial first slot) until done."""
    hours_left = e_base_gpu / n_kw if n_kw > 0 else 0.0
    out: list[float] = []
    while hours_left > 1e-12:
        if len(out) >= MAX_BASE_SLOTS:
            raise EngineError(
                "implausible_energy",
                "This energy is more than your GPUs can draw. Receipt rejected.",
            )
        use = min(f0 if not out else 1.0, hours_left)
        out.append(use * n_kw)
        hours_left -= use
    return out


def _padded(values: Sequence[float], n: int) -> list[float]:
    return [*values, *([0.0] * (n - len(values)))]


def _extended(inten: Intensities, n: int) -> Intensities:
    """Repeat the last slot's values so hours past the snapshot can be scored (extrapolated)."""

    def ext(values: tuple[float, ...]) -> tuple[float, ...]:
        return values + (values[-1],) * (n - len(values)) if n > len(values) else values

    return Intensities(
        ext(inten.tw), ext(inten.pue), ext(inten.wue), ext(inten.ci), ext(inten.ewif)
    )


def _observed(
    snap: ForecastSnapshot, rows: Sequence[WeatherRow], fx: Factors, fs: FactorSet
) -> tuple[Intensities, set[int]]:
    """Intensities with observed weather replacing the forecast where an observation exists."""
    by_hour = {r.hour: r for r in rows}
    temp, rh, rad = list(snap.temp_c), list(snap.rh_pct), list(snap.rad_wm2)
    seen: set[int] = set()
    for h, slot in enumerate(snap.slots):
        row = by_hour.get(slot)
        if row is not None:
            temp[h], rh[h], rad[h] = row.temp_c, row.rh_pct, row.rad_wm2
            seen.add(h)
    inten = derive(Cooling.parse(snap.cooling), snap.pue_user, snap.slots, temp, rh, rad, fx, fs)
    return inten, seen


def _totals(
    arrays: Mapping[str, Sequence[float]], inten: Intensities, fs: FactorSet, sigma: float
) -> dict[str, Totals]:
    return {k: footprint(g, inten, fs, sigma)[1] for k, g in arrays.items()}


def receipt_footprints(
    receipt: Mapping[str, Any],
    plan_record: Mapping[str, Any],
    observed_rows: Sequence[WeatherRow] = (),
    fx: Factors | None = None,
) -> dict[str, Any]:
    """Score one receipt against its saved plan (TRD 5.9). Returns the stored scored receipt."""
    fx = fx or load_factors()
    fs = fx.central()
    snap = ForecastSnapshot.from_json(plan_record["forecast_snapshot"])
    inputs = plan_record["inputs"]
    gpu = fx.gpu_params(inputs["gpu_model"])
    sigma = fx.stress_weight(get_city(snap.city).stress_category)
    max_hour_kwh = inputs["gpu_count"] * gpu.model.p_max_w / 1000 * fs["receipt_kwh_tolerance"]
    run, idle, level, extrapolated = _group_hours(receipt, snap, max_hour_kwh)

    e_base_gpu = sum(run[h] / gpu.levels[level[h]].eps for h in run)
    n_kw = inputs["gpu_count"] * gpu.u * gpu.model.p_max_w / 1000
    g_base = _base_energy(e_base_gpu, n_kw, snap.slot0_capacity)
    n = max(WINDOW_SLOTS, max([*run, *idle], default=0) + 1, len(g_base))
    scale = e_base_gpu / max(sum(plan_record["base"]["gpu_kwh"]), 1e-12)
    arrays = {
        "base": _padded(g_base, n),
        "best": _padded([x * scale for x in plan_record["best"]["gpu_kwh"]], n),
        "actual": [run.get(h, 0.0) + idle.get(h, 0.0) for h in range(n)],
    }

    scored = _totals(arrays, _extended(snap.derived, n), fs, sigma)
    base = scored["base"]
    j = {
        k: j_value(
            t.stress_l, t.co2_kg, t.e_fac_kwh, base.stress_l, base.co2_kg, base.e_fac_kwh, fs
        )
        for k, t in scored.items()
    }
    cap, no_room = capture(j["actual"], j["best"], fs)

    obs_inten, seen = _observed(snap, observed_rows, fx, fs)
    absolute = _totals(arrays, _extended(obs_inten, n), fs, sigma)
    hours = sorted({*run, *idle})
    n_observed = sum(1 for h in hours if h in seen)
    return {
        "job_id": receipt.get("job_id"),
        "end_ts": receipt.get("end_ts"),
        "method": receipt.get("method"),
        "kwh": sum(arrays["actual"]),
        "scoring": {**{k: _fp(t, fs) for k, t in scored.items()}, "J": j},
        "absolute": {
            **{k: _fp(t, fs) for k, t in absolute.items()},
            "basis": {"observed": n_observed, "forecast": len(hours) - n_observed},
        },
        "capture": cap,
        "no_room": no_room,
        "flexible": not no_room,
        "tags": {
            "energy": "measured" if receipt.get("method") in MEASURED_METHODS else "modelled",
            "water": "modelled",
            "co2": "modelled",
        },
        "extrapolated_hours": extrapolated,
        # the plan was made with other factor files than the ones scoring it now
        "factor_version_mismatch": snap.factor_version != fx.version,
    }


# --------------------------------------------------------------------------- site score


def _in_window(receipt: Mapping[str, Any], now: datetime) -> bool:
    end = ensure_ist(datetime.fromisoformat(receipt["end_ts"]))
    return now - timedelta(days=WINDOW_DAYS) < end <= now


def _counted(receipts: Sequence[Mapping[str, Any]], now: datetime) -> list[Mapping[str, Any]]:
    """Receipts from the last 30 days; unverified ones count for nothing (decision D20)."""
    current = ensure_ist(now)
    return [
        r for r in receipts if r.get("method") != "unverified" and _in_window(r, current)
    ]


def _monthly_absolute(counted: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    actual = [r["absolute"]["actual"] for r in counted]
    return {
        "kwh": sum(r["kwh"] for r in counted),
        "facility_kwh": sum(a["E_fac_kwh"] for a in actual),
        "litres": sum(a["litres"] for a in actual),
        "stress_litres": sum(a["W_l"] for a in actual),
        "kg_co2": sum(a["C_kg"] for a in actual),
        "person_days": sum(a["person_days"] for a in actual),
    }


def site_score(
    receipts: Sequence[Mapping[str, Any]],
    site: Mapping[str, Any],
    now: datetime,
    fx: Factors | None = None,
) -> dict[str, Any]:
    """Provisional site score from the last 30 days of scored receipts (Idea 7.3)."""
    fs = (fx or load_factors()).central()
    counted = _counted(receipts, now)
    total_kwh = sum(r["kwh"] for r in counted)
    flexible = [r for r in counted if r.get("flexible") and r.get("capture") is not None]
    flex_kwh = sum(r["kwh"] for r in flexible)
    measured_kwh = sum(r["kwh"] for r in counted if r.get("method") in MEASURED_METHODS)
    c_parts = {
        "measured_share": 10.0 * measured_kwh / total_kwh if total_kwh > 0 else 0.0,
        "coverage": 5.0 if float(site.get("coverage_declared") or 0.0) >= 0.8 else 0.0,
        "public": 5.0 if site.get("public", True) else 0.0,
    }
    c_total = sum(c_parts.values())
    flex_share = flex_kwh / total_kwh if total_kwh > 0 else 0.0
    out: dict[str, Any] = {
        "A": 0.0,
        "B": "not_rated",
        "C": c_total,
        "C_parts": c_parts,
        "score": None,
        "provisional": True,
        "badge": None,
        "flex_share": flex_share,
        "reason": NEEDS_FLEXIBLE,
        "receipts": len(counted),
        "monthly_absolute": _monthly_absolute(counted),
    }
    if flex_kwh <= 0:
        return out
    a_total = 50.0 * sum(r["capture"] * r["kwh"] for r in flexible) / flex_kwh
    value = min((a_total + c_total) / _PARTS_MAX * 100.0, 100.0)
    return {
        **out,
        "A": a_total,
        "score": value,
        "badge": badge(value, flex_share, fs),
        "reason": None,
    }


# --------------------------------------------------------------------------- site pages


def _site_info(site: Mapping[str, Any], fs: FactorSet) -> dict[str, Any]:
    """Public site fields. The exact GPU count is never returned (TRD 5.9)."""
    return {
        "site_id": site["site_id"],
        "name": site["name"],
        "org": site.get("org"),
        "city": site["city"],
        "cooling": site["cooling"],
        "division": site.get("division") or division(int(site["gpu_count"]), fs),
        "simulated": bool(site.get("simulated", False)),
        "public": bool(site.get("public", True)),
    }


def _score_view(result: Mapping[str, Any]) -> dict[str, Any]:
    value = result["score"]
    return {
        # floor to one decimal so the shown value never reaches a badge threshold it missed
        "value": None if value is None else int(value * 10) / 10,
        "provisional": result["provisional"],
        "badge": result["badge"],
        "A": result["A"],
        "B": result["B"],
        "C": result["C"],
        "C_parts": result["C_parts"],
        "flex_share": result["flex_share"],
        "reason": result["reason"],
    }


def site_page_view(
    site: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    now: datetime,
    fx: Factors | None = None,
) -> dict[str, Any]:
    """Data for ``GET /sites/{id}`` (plan 08 §3.3): score, monthly footprint, last 10 receipts."""
    fx = fx or load_factors()
    result = site_score(receipts, site, now, fx)
    info = _site_info(site, fx.central())
    if not info["public"]:  # D26: a private site shows only its name, division and score
        return {"site": info, "score": _score_view(result), "monthly_absolute": None,
                "recent_receipts": []}
    recent = sorted(
        _counted(receipts, now),
        key=lambda r: ensure_ist(datetime.fromisoformat(r["end_ts"])),
        reverse=True,
    )
    return {
        "site": info,
        "score": _score_view(result),
        "monthly_absolute": result["monthly_absolute"],
        "recent_receipts": [
            {
                "job_id": r["job_id"],
                "end_ts": r["end_ts"],
                "kwh": r["kwh"],
                "capture": r.get("capture"),
                "no_room": bool(r.get("no_room")),
                "method": r["method"],
            }
            for r in recent[:RECENT_RECEIPTS]
        ],
    }


def leaderboard_rows(
    sites: Sequence[Mapping[str, Any]],
    receipts_by_site: Mapping[str, Sequence[Mapping[str, Any]]],
    division_id: str,
    now: datetime,
    fx: Factors | None = None,
) -> list[dict[str, Any]]:
    """Rows for one division, best first; unrated sites last with ``rank = None``."""
    fx = fx or load_factors()
    fs = fx.central()
    rows = []
    for site in sites:
        info = _site_info(site, fs)
        if info["division"] != division_id or not info["public"]:  # private sites hidden (D26)
            continue
        res = site_score(receipts_by_site.get(site["site_id"], ()), site, now, fx)
        rows.append(
            {
                "rank": None,
                "site_id": info["site_id"],
                "name": info["name"],
                "simulated": info["simulated"],
                "division": info["division"],
                "badge": res["badge"],
                "score": res["score"],
                "provisional": res["provisional"],
                "A": res["A"],
                "C": res["C"],
                "flex_share": res["flex_share"],
                "monthly_absolute": res["monthly_absolute"],
                "receipts": res["receipts"],
            }
        )
    rows.sort(
        key=lambda r: (r["score"] is None, -(r["score"] or 0.0), -r["flex_share"], r["site_id"])
    )
    rank = 0
    for row in rows:
        if row["score"] is not None:
            rank += 1
            row["rank"] = rank
    return rows
