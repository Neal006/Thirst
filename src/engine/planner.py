"""Planner: Base, non-pausable and pausable schedules, Pareto set and ranges (plan 02.7, TRD 5.8).

A *plan* is a list of runs (slot, power-cap level, hours running). Slots between the first and last
run that have no run are paused: the GPUs idle with memory allocated (idle energy is counted).
Footprint terms are linear in GPU energy, so every cost below is a dot product with per-slot
coefficients.

"Best" (used by the score, TRD 5.9) is the plan that minimises J, i.e. the same search with the
J weights instead of the user's alpha, under the job's own pausable setting. It is returned next
to the Pareto set so the receipt scorer never has to re-run the planner.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from .cooling import Cooling
from .errors import EngineError
from .factors import Factors, FactorSet, GpuParams, get_city, load_factors
from .footprint import Coefficients, Totals, coefficients, footprint
from .forecast import ForecastSnapshot, Intensities, WeatherRow, build_snapshot, intensities
from .units import WINDOW_SLOTS, clock_text, deadline_slots, ensure_ist, floor_hour, slot0_capacity

LEVELS = (1.0, 0.85, 0.7)
ALPHA_STEPS = 10
MAX_GPUS = 4096
MAX_WORK_HOURS = 48.0
_EPS = 1e-9  # work left over that counts as done
_TIE = 1e-9  # relative cost difference that counts as a real improvement
_SETS = ("low", "central", "high")
Weights = tuple[float, float, float]  # water, carbon, facility energy


@dataclass(frozen=True, slots=True)
class PlanRequest:
    city: str
    cooling: str
    pue_user: float | None
    gpu_model: str
    gpu_count: int
    work_hours: float
    deadline: datetime
    pausable: bool
    alpha: float
    submit_ts: datetime
    site_id: str | None = None
    pausable_allowed: bool = True  # False forces a non-pausable plan (D15)
    force_now: bool = False  # True: chosen is the Base plan (``thirst run --now``)


@dataclass(frozen=True, slots=True)
class Run:
    slot: int
    level: float
    hours: float  # time spent running in the slot (at most the slot capacity)


@dataclass(frozen=True, slots=True)
class Plan:
    runs: tuple[Run, ...]  # in time order
    kind: str  # "base", "non_pausable" or "pausable"
    notes: tuple[str, ...] = ()


_Candidate = tuple["Plan", tuple[tuple[int, float], ...]]  # plan and its (slot, GPU kWh) pairs


@dataclass(frozen=True, slots=True)
class _Ctx:
    work_hours: float
    h_d: int  # slots that end on or before the deadline
    caps: tuple[float, ...]  # capacity of each slot (slot 0 is partial, decision D7)
    tau: dict[float, float]
    run_kw: dict[float, float]  # kWh of GPU energy per hour of running, per level
    idle_kw: float
    coef: Coefficients  # central set, per kWh of GPU energy
    w_base: float
    c_base: float
    e_base: float
    max_gaps: int
    fixed: tuple[_Candidate, ...] = ()  # every constant-level plan that meets the deadline


@dataclass(frozen=True, slots=True)
class _Env:
    req: PlanRequest
    snap: ForecastSnapshot
    fx: Factors
    gpu: GpuParams
    sigma: float
    ctx: _Ctx
    base: Plan
    pausable: bool
    capped: bool
    fs: dict[str, FactorSet]
    inten: dict[str, Intensities]


# --------------------------------------------------------------------------- energy and cost


def _gpu_kwh(ctx: _Ctx, plan: Plan) -> list[float]:
    """GPU energy per slot (kWh), including idle energy in paused slots."""
    g = [0.0] * WINDOW_SLOTS
    for run in plan.runs:
        g[run.slot] += ctx.run_kw[run.level] * run.hours
    busy = {r.slot for r in plan.runs}
    for h in range(plan.runs[0].slot, plan.runs[-1].slot + 1):
        if h not in busy:
            g[h] += ctx.idle_kw * ctx.caps[h]
    return g


def _kwh_cost(ctx: _Ctx, weights: Weights) -> list[float]:
    """Weighted, base-normalised footprint of one kWh of GPU energy in each slot."""
    w_w, w_c, w_e = weights
    return [
        w_w * s / ctx.w_base + w_c * c / ctx.c_base + w_e * e / ctx.e_base
        for s, c, e in zip(ctx.coef.stress, ctx.coef.co2, ctx.coef.e_fac, strict=True)
    ]


def _objective(ctx: _Ctx, plan: Plan, kwh_cost: Sequence[float]) -> float:
    return sum(g * c for g, c in zip(_gpu_kwh(ctx, plan), kwh_cost, strict=True))


def _alpha_weights(alpha: float, fx: Factors) -> Weights:
    split = fx.central()["plan_w_split"]
    return split * alpha, split * (1 - alpha), 1 - split


def _j_weights(fx: Factors) -> Weights:
    c = fx.central()
    return c["j_w_water"], c["j_w_carbon"], c["j_w_energy"]


# --------------------------------------------------------------------------- base and non-pausable


def _constant_runs(ctx: _Ctx, start: int, level: float) -> list[Run] | None:
    """Runs at one level from ``start`` until the work is done, or None if the deadline is hit."""
    remaining = ctx.work_hours
    runs: list[Run] = []
    h = start
    while remaining > _EPS:
        if h >= ctx.h_d:
            return None
        hours = min(ctx.caps[h], remaining / ctx.tau[level])
        runs.append(Run(h, level, hours))
        remaining -= hours * ctx.tau[level]
        h += 1
    return runs


def _fixed_candidates(ctx: _Ctx) -> tuple[_Candidate, ...]:
    """All constant-level plans in (start, level) order; independent of the cost weights."""
    out: list[_Candidate] = []
    for start in range(ctx.h_d):
        for level in LEVELS:
            runs = _constant_runs(ctx, start, level)
            if runs is not None:
                energy = tuple((r.slot, ctx.run_kw[r.level] * r.hours) for r in runs)
                out.append((Plan(tuple(runs), "non_pausable"), energy))
    return tuple(out)


def _plan_non_pausable(ctx: _Ctx, kwh_cost: Sequence[float]) -> Plan:
    """Exact search over every start slot and constant level (at most 48 x 3 candidates)."""
    best: Plan | None = None
    best_cost = math.inf
    for candidate, energy in ctx.fixed:
        cost = sum(kwh * kwh_cost[h] for h, kwh in energy)
        if cost < best_cost * (1 - _TIE):  # ties keep the earlier start, then the higher level
            best, best_cost = candidate, cost
    if best is None:  # pragma: no cover - the Base plan is always a valid candidate
        raise EngineError("deadline_too_soon", "The job does not fit before the deadline.")
    return best


# --------------------------------------------------------------------------- pausable


def _best_levels(ctx: _Ctx, kwh_cost: Sequence[float]) -> tuple[list[float], list[float]]:
    """Cheapest level per slot (higher level wins ties) and its cost per unit of work."""
    levels: list[float] = []
    costs: list[float] = []
    for h in range(ctx.h_d):
        best_level, best_cost = LEVELS[0], math.inf
        for level in LEVELS:
            cost = ctx.run_kw[level] * kwh_cost[h] / ctx.tau[level]
            if cost < best_cost * (1 - _TIE):
                best_level, best_cost = level, cost
        levels.append(best_level)
        costs.append(best_cost)
    return levels, costs


def _gaps(selected: set[int]) -> list[tuple[int, int]]:
    """Pause gaps as (first slot, length), in time order."""
    ordered = sorted(selected)
    return [(a + 1, b - a - 1) for a, b in zip(ordered, ordered[1:], strict=False) if b - a > 1]


def _drop_redundant(
    ctx: _Ctx, selected: set[int], levels: Sequence[float], costs: Sequence[float]
) -> None:
    """Drop the most expensive block-edge slots while the work is still covered (decision D8)."""

    def work(h: int) -> float:
        return ctx.tau[levels[h]] * ctx.caps[h]

    while True:
        total = sum(work(h) for h in selected)
        removable = [
            h
            for h in selected
            if (h - 1 not in selected or h + 1 not in selected)
            and total - work(h) >= ctx.work_hours - _EPS
        ]
        if not removable:
            return
        selected.remove(max(removable, key=lambda h: (costs[h], h)))  # ties: drop the later slot


def _runs_from(ctx: _Ctx, selected: set[int], levels: Sequence[float]) -> tuple[Run, ...]:
    """Full-capacity runs, with the last one trimmed so that exactly the needed work is done."""
    runs = [Run(h, levels[h], ctx.caps[h]) for h in sorted(selected)]
    total = sum(ctx.tau[r.level] * r.hours for r in runs)
    last = runs[-1]
    excess_hours = (total - ctx.work_hours) / ctx.tau[last.level]
    runs[-1] = replace(last, hours=max(last.hours - excess_hours, 0.0))
    return tuple(runs)


def _plan_pausable(ctx: _Ctx, kwh_cost: Sequence[float]) -> Plan | None:
    """Cheapest-slots plan with at most ``max_gaps`` pauses, or None if it cannot be made."""
    levels, costs = _best_levels(ctx, kwh_cost)
    selected: set[int] = set()
    covered = 0.0
    for h in sorted(range(ctx.h_d), key=lambda x: (costs[x], x)):
        selected.add(h)
        covered += ctx.tau[levels[h]] * ctx.caps[h]
        if covered >= ctx.work_hours - _EPS:
            break
    if covered < ctx.work_hours - _EPS:
        return None  # even every slot at its cheapest level cannot finish in time
    _drop_redundant(ctx, selected, levels, costs)
    for _ in range(WINDOW_SLOTS):
        gaps = _gaps(selected)
        if len(gaps) <= ctx.max_gaps:
            return Plan(_runs_from(ctx, selected, levels), "pausable")
        first, length = min(gaps, key=lambda g: (g[1], g[0]))  # fill the shortest gap
        selected.update(range(first, first + length))
        _drop_redundant(ctx, selected, levels, costs)
    return None  # pragma: no cover - every pass removes a gap, so 48 passes always suffice


def _solve(env: _Env, weights: Weights) -> Plan:
    """Best plan for one set of cost weights."""
    ctx = env.ctx
    kwh_cost = _kwh_cost(ctx, weights)
    fixed = _plan_non_pausable(ctx, kwh_cost)
    if not env.pausable:
        return fixed
    paused = _plan_pausable(ctx, kwh_cost)
    if paused is None:  # no room for pauses: the cheapest levels cannot finish in time
        return replace(fixed, notes=("pause_no_room",))
    if _objective(ctx, paused, kwh_cost) < _objective(ctx, fixed, kwh_cost) * (1 - _TIE):
        return replace(paused, notes=("pausable_won",))
    return replace(fixed, notes=("non_pausable_won",))


# --------------------------------------------------------------------------- setup


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _validate(req: PlanRequest) -> None:
    """Check types and ranges first, so bad input never reaches arithmetic that would crash."""
    if (
        isinstance(req.gpu_count, bool)
        or not isinstance(req.gpu_count, int)
        or not 1 <= req.gpu_count <= MAX_GPUS
    ):
        raise EngineError("invalid_field", f"gpu_count: use a whole number from 1 to {MAX_GPUS}.")
    if not _is_number(req.work_hours) or not 0 < req.work_hours <= MAX_WORK_HOURS:
        raise EngineError("invalid_field", "work_hours: use a number above 0 and up to 48.")
    if not _is_number(req.alpha) or not 0 <= req.alpha <= 1:
        raise EngineError("invalid_field", "alpha: use a step of 0.1 from 0 to 1.")
    if abs(req.alpha * ALPHA_STEPS - round(req.alpha * ALPHA_STEPS)) > 1e-6:
        raise EngineError("invalid_field", "alpha: use a step of 0.1 from 0 to 1.")
    if not isinstance(req.pausable, bool) or not isinstance(req.pausable_allowed, bool):
        raise EngineError("invalid_field", "pausable: use true or false.")
    if not isinstance(req.force_now, bool):
        raise EngineError("invalid_field", "force_now: use true or false.")
    if req.pue_user is not None and not _is_number(req.pue_user):
        raise EngineError("invalid_field", "pue: use a number from 1.0 to 3.0.")
    for name in ("submit_ts", "deadline"):
        value = getattr(req, name)
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise EngineError("invalid_field", f"{name}: use a time with a timezone offset.")


def _build_ctx(req: PlanRequest, snap: ForecastSnapshot, fx: Factors, gpu: GpuParams,
               sigma: float, h_d: int) -> _Ctx:
    fs = fx.central()
    caps = (slot0_capacity(req.submit_ts), *([1.0] * (WINDOW_SLOTS - 1)))
    n_kw = req.gpu_count * gpu.u * gpu.model.p_max_w / 1000
    ctx = _Ctx(
        work_hours=req.work_hours,
        h_d=h_d,
        caps=caps,
        tau={lv: gpu.levels[lv].tau for lv in LEVELS},
        run_kw={lv: n_kw * gpu.levels[lv].eps * gpu.levels[lv].tau for lv in LEVELS},
        idle_kw=req.gpu_count * gpu.p_idle_w / 1000,
        coef=coefficients(snap.derived, fs, sigma),
        w_base=1.0,
        c_base=1.0,
        e_base=1.0,
        max_gaps=int(fs["max_pause_gaps"]),
    )
    return ctx


def _with_base_totals(ctx: _Ctx, base: Plan) -> _Ctx:
    g = _gpu_kwh(ctx, base)

    def total(per_kwh: Sequence[float]) -> float:
        return max(sum(x * c for x, c in zip(g, per_kwh, strict=True)), 1e-12)

    return replace(ctx, w_base=total(ctx.coef.stress), c_base=total(ctx.coef.co2),
                   e_base=total(ctx.coef.e_fac))


def _build_env(req: PlanRequest, snap: ForecastSnapshot, fx: Factors) -> _Env:
    _validate(req)
    city = get_city(req.city)
    Cooling.parse(req.cooling)
    gpu = fx.gpu_params(req.gpu_model)
    if snap.city != req.city or snap.cooling != req.cooling:
        raise ValueError("forecast snapshot does not match the request")
    if floor_hour(req.submit_ts) != snap.slots[0]:
        raise ValueError("forecast snapshot does not start at the submit hour")
    h_d, capped = deadline_slots(req.submit_ts, req.deadline)
    capacity = slot0_capacity(req.submit_ts) + max(h_d - 1, 0) if h_d else 0.0
    if capacity < req.work_hours - _EPS:
        if h_d >= WINDOW_SLOTS:  # a later deadline cannot help: the planning window is the limit
            raise EngineError(
                "invalid_field",
                f"work_hours: from this start the 48-hour planning window fits at most "
                f"{capacity:.1f} h of work.",
            )
        finish = ensure_ist(req.submit_ts) + timedelta(hours=req.work_hours)
        raise EngineError(
            "deadline_too_soon",
            f"This job needs until {clock_text(finish)} at full power. Pick a later deadline.",
        )
    sigma = fx.stress_weight(city.stress_category)
    ctx = _build_ctx(req, snap, fx, gpu, sigma, h_d)
    runs = _constant_runs(ctx, 0, 1.0)
    if runs is None:  # pragma: no cover - guarded by the capacity check above
        raise EngineError("deadline_too_soon", "The job does not fit before the deadline.")
    base = Plan(tuple(runs), "base")
    sets = {"low": fx.low(), "central": fx.central(), "high": fx.high()}
    inten = {
        "low": intensities(snap, fx, sets["low"]),
        "central": snap.derived,
        "high": intensities(snap, fx, sets["high"]),
    }
    ctx = _with_base_totals(ctx, base)
    ctx = replace(ctx, fixed=_fixed_candidates(ctx))
    return _Env(req, snap, fx, gpu, sigma, ctx, base, req.pausable and req.pausable_allowed,
                capped, sets, inten)


# --------------------------------------------------------------------------- output


def _r(x: float) -> float:
    return round(x, 6)


def _set_totals(env: _Env, g: Sequence[float]) -> dict[str, Totals]:
    return {n: footprint(g, env.inten[n], env.fs[n], env.sigma)[1] for n in _SETS}


_METRICS: tuple[tuple[str, Callable[[Totals], float]], ...] = (
    ("E_gpu_kwh", lambda t: t.e_gpu_kwh),
    ("E_fac_kwh", lambda t: t.e_fac_kwh),
    ("W_l", lambda t: t.stress_l),
    ("C_kg", lambda t: t.co2_kg),
    ("D_l", lambda t: t.direct_l),
    ("I_l", lambda t: t.indirect_l),
)
_SAVING_METRICS: tuple[tuple[str, Callable[[Totals], float]], ...] = (
    ("water_pct", lambda t: t.stress_l),
    ("co2_pct", lambda t: t.co2_kg),
    ("energy_pct", lambda t: t.e_fac_kwh),
)


def _triple(values: dict[str, float]) -> list[float]:
    """[min, central, max] over the low, central and high factor sets."""
    return [_r(min(values.values())), _r(values["central"]), _r(max(values.values()))]


def _saving_pct(base: float, value: float) -> float:
    return 0.0 if base <= 0 else (base - value) / base * 100


def _savings(
    base: dict[str, Totals], plan: dict[str, Totals]
) -> tuple[dict[str, list[int]], dict[str, float]]:
    ranges: dict[str, list[int]] = {}
    central: dict[str, float] = {}
    for key, pick in _SAVING_METRICS:
        pct = {n: _saving_pct(pick(base[n]), pick(plan[n])) for n in _SETS}
        low, high = round(min(pct.values()), 6), round(max(pct.values()), 6)
        ranges[key] = [math.floor(low), math.ceil(high)]
        central[key] = _r(pct["central"])
    return ranges, central


def _states(plan: Plan) -> list[tuple[float, str]]:
    """(level, state) for each of the 48 slots; state is off, run or pause."""
    out: list[tuple[float, str]] = [(0.0, "off")] * WINDOW_SLOTS
    by_slot = {r.slot: r for r in plan.runs}
    for h in range(plan.runs[0].slot, plan.runs[-1].slot + 1):
        out[h] = (by_slot[h].level, "run") if h in by_slot else (0.0, "pause")
    return out


def _schedule(env: _Env, plan: Plan) -> list[dict[str, Any]]:
    by_slot = {r.slot: r for r in plan.runs}
    rows = []
    for h in range(plan.runs[0].slot, plan.runs[-1].slot + 1):
        run = by_slot.get(h)
        rows.append({
            "slot": env.snap.slots[h].isoformat(),
            "level": run.level if run else 0.0,
            "state": "run" if run else "pause",
            "fraction": _r(run.hours if run else env.ctx.caps[h]),
        })
    return rows


def _times(env: _Env, plan: Plan) -> tuple[datetime, datetime]:
    first, last = plan.runs[0], plan.runs[-1]
    submit = ensure_ist(env.req.submit_ts)
    start = submit if first.slot == 0 else env.snap.slots[first.slot]
    anchor = submit if last.slot == 0 else env.snap.slots[last.slot]
    return start, anchor + timedelta(hours=last.hours)


def _level_summary(plan: Plan) -> str:
    levels = sorted({r.level for r in plan.runs}, reverse=True)
    return "/".join(f"{round(lv * 100)}%" for lv in levels)


def _entry(
    env: _Env, plan: Plan, base: dict[str, Totals]
) -> tuple[dict[str, Any], dict[str, Totals]]:
    g = _gpu_kwh(env.ctx, plan)
    totals = _set_totals(env, g)
    start, finish = _times(env, plan)
    ranges, central = _savings(base, totals)
    entry = {
        "kind": plan.kind,
        "start": start.isoformat(),
        "finish": finish.isoformat(),
        "level_summary": _level_summary(plan),
        "schedule": _schedule(env, plan),
        "totals": {key: _triple({n: pick(t) for n, t in totals.items()}) for key, pick in _METRICS},
        "savings_ranges": ranges,
        "savings_central": central,
        "point": {"W_l": _r(totals["central"].stress_l), "C_kg": _r(totals["central"].co2_kg)},
        "series_overlay": [
            {"slot": env.snap.slots[h].isoformat(), "level": lv, "state": st}
            for h, (lv, st) in enumerate(_states(plan))
        ],
        "gpu_kwh": [_r(x) for x in g],
        "notes": list(plan.notes),
    }
    return entry, totals


def _points(pareto: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unique (W, C) points of the Pareto set with the alphas that produce them."""
    points: list[dict[str, Any]] = []
    index: dict[tuple[float, float], int] = {}
    for entry in pareto:
        key = (round(entry["point"]["W_l"], 4), round(entry["point"]["C_kg"], 4))
        if key in index:
            points[index[key]]["alphas"].append(entry["alpha"])
        else:
            index[key] = len(points)
            points.append({**entry["point"], "alphas": [entry["alpha"]]})
    return points


def _series(env: _Env, plan: Plan) -> list[dict[str, Any]]:
    d = env.snap.derived
    return [
        {
            "slot": env.snap.slots[h].isoformat(),
            "direct_l_per_kwh": _r(d.wue[h]),
            "grid_l_per_kwh": _r(d.ewif[h]),
            "co2_kg_per_kwh": _r(d.ci[h]),
            "temp_c": _r(env.snap.temp_c[h]),
            "tw_c": _r(d.tw[h]),
            "level": lv,
            "state": st,
        }
        for h, (lv, st) in enumerate(_states(plan))
    ]


def _unique(items: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _global_notes(env: _Env, chosen_notes: Sequence[str], j_best: float) -> list[str]:
    notes: list[str] = []
    if env.req.pausable and not env.req.pausable_allowed:
        notes.append("pause_unsupported")
    if env.snap.source == "cached":
        notes.append("forecast_cached")
    if env.capped:
        notes.append("deadline_capped")
    if 1 - j_best < env.fx.central()["no_room_threshold"]:
        notes.append("no_room")
    return _unique([*notes, *chosen_notes])


def _inputs(req: PlanRequest) -> dict[str, Any]:
    return {
        "city": req.city,
        "cooling": req.cooling,
        "pue": req.pue_user,
        "gpu_model": req.gpu_model,
        "gpu_count": req.gpu_count,
        "work_hours": req.work_hours,
        "deadline": ensure_ist(req.deadline).isoformat(),
        "pausable": req.pausable,
        "pausable_allowed": req.pausable_allowed,
        "alpha": req.alpha,
        "force_now": req.force_now,
        "site_id": req.site_id,
    }


def plan(req: PlanRequest, snap: ForecastSnapshot, fx: Factors | None = None) -> dict[str, Any]:
    """Plan a job. Returns the ``POST /plan`` body of plan 08 §3.1 (``plan_id`` left empty)."""
    fx = fx or load_factors()
    env = _build_env(req, snap, fx)
    base_entry, base_totals = _entry(env, env.base, _set_totals(env, _gpu_kwh(env.ctx, env.base)))
    plans = [_solve(env, _alpha_weights(i / ALPHA_STEPS, fx)) for i in range(ALPHA_STEPS + 1)]
    entries = [_entry(env, p, base_totals) for p in plans]
    pareto = [{"alpha": i / ALPHA_STEPS, **e} for i, (e, _) in enumerate(entries)]
    best_plan = _solve(env, _j_weights(fx))
    best_entry, _ = _entry(env, best_plan, base_totals)
    j_best = _objective(env.ctx, best_plan, _kwh_cost(env.ctx, _j_weights(fx)))
    idx = int(round(req.alpha * ALPHA_STEPS + 1e-9))
    chosen, chosen_plan, chosen_totals = copy.deepcopy(pareto[idx]), plans[idx], entries[idx][1]
    if req.force_now:  # the user starts now: the Base plan, with no saving against itself
        chosen = {"alpha": pareto[idx]["alpha"], **copy.deepcopy(base_entry)}
        chosen["notes"] = [*chosen["notes"], "start_now_forced"]
        chosen_plan, chosen_totals = env.base, base_totals
    days = [chosen_totals[n].person_days(env.fs[n]) for n in _SETS]
    return {
        "plan_id": "",
        "submit_ts": ensure_ist(req.submit_ts).isoformat(),
        "inputs": _inputs(req),
        "base": base_entry,
        "best": best_entry,
        "j_best": _r(j_best),
        "chosen": chosen,
        "pareto": pareto,
        "points": _points(pareto),
        "savings_ranges": copy.deepcopy(chosen["savings_ranges"]),
        "series": _series(env, chosen_plan),
        "person_days_range": [round(min(days), 4), round(max(days), 4)],
        "tags": {
            "energy": "modelled",
            "water": "modelled",
            "co2": "modelled",
            "tau": "measured" if env.gpu.measured else "placeholder",
            "forecast": snap.source,
        },
        "notes": _global_notes(env, chosen["notes"], j_best),
        "factor_version": fx.version,
        "assumptions_url": "/assumptions",
        "forecast_snapshot": snap.to_json(),
    }


def plan_from_rows(
    req: PlanRequest, rows: Sequence[WeatherRow], fx: Factors | None = None
) -> dict[str, Any]:
    """Build the forecast snapshot from weather rows and plan in one call."""
    _validate(req)
    fx = fx or load_factors()
    snap = build_snapshot(req.city, req.cooling, rows, fx, req.submit_ts, pue_user=req.pue_user)
    return plan(req, snap, fx)
