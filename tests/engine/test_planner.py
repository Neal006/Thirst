from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from weather_helpers import (
    DEADLINE,
    SUBMIT,
    diurnal_rows,
    flat_rows,
    ist,
    random_rows,
    request,
    split_window_rows,
)

from engine import planner
from engine.errors import EngineError
from engine.factors import Factors, load_factors
from engine.footprint import footprint
from engine.forecast import WeatherRow, build_snapshot
from engine.planner import plan_from_rows
from engine.units import IST, WINDOW_SLOTS

LEVELS = (1.0, 0.85, 0.7)


@pytest.fixture(scope="module")
def fx() -> Factors:
    return load_factors()


@pytest.fixture(scope="module")
def flat_fx(tmp_path_factory: pytest.TempPathFactory) -> Factors:
    """Sweep where capping saves no energy per unit of work (eps = 1 at every level)."""
    sweep = {"gpus": {"RTX-4090": {
        "levels": {"1.0": {"tau": 1.0, "eps": 1.0}, "0.85": {"tau": 0.97, "eps": 1.0},
                   "0.7": {"tau": 0.9, "eps": 1.0}},
        "u": 0.9, "p_idle_w": 45.0}}}
    path = tmp_path_factory.mktemp("sweep") / "sweep.json"
    path.write_text(json.dumps(sweep), encoding="utf-8")
    return load_factors(sweep_path=path)


def run(fx: Factors, rows: list[WeatherRow] | None = None, **overrides: Any) -> dict[str, Any]:
    return plan_from_rows(request(**overrides), rows or diurnal_rows(SUBMIT), fx)


def pause_gaps(schedule: list[dict[str, Any]]) -> int:
    states = [row["state"] for row in schedule]
    previous = ["run", *states[:-1]]
    return sum(1 for now, before in zip(states, previous, strict=True)
               if now == "pause" and before != "pause")


def work_done(fx: Factors, schedule: list[dict[str, Any]]) -> float:
    levels = fx.gpu_params("RTX-4090").levels
    return sum(levels[r["level"]].tau * r["fraction"] for r in schedule if r["state"] == "run")


def objective(result: dict[str, Any], entry: dict[str, Any], alpha: float) -> float:
    """Alpha-weighted, base-normalised cost from the central totals of a plan entry."""
    base = result["base"]["totals"]
    w, c, e = ((entry["totals"][k][1] / base[k][1]) for k in ("W_l", "C_kg", "E_fac_kwh"))
    return 0.8 * alpha * w + 0.8 * (1 - alpha) * c + 0.2 * e


# 1 ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("pausable", [False, True])
def test_flat_intensities_give_best_equal_to_base_and_no_room(
    flat_fx: Factors, pausable: bool
) -> None:
    result = run(flat_fx, flat_rows(SUBMIT), pausable=pausable)
    assert result["best"]["schedule"] == result["base"]["schedule"]
    assert result["best"]["start"] == SUBMIT.isoformat()
    assert 1 - result["j_best"] < 0.03
    assert "no_room" in result["notes"]


def test_varying_intensities_leave_room_to_shift(fx: Factors) -> None:
    result = run(fx)
    assert 1 - result["j_best"] > 0.03
    assert "no_room" not in result["notes"]


# 2 ---------------------------------------------------------------------------------------


@settings(max_examples=500, deadline=None)
@given(
    work=st.floats(min_value=0.5, max_value=20),
    extra=st.floats(min_value=1.0, max_value=48),
    pausable=st.booleans(),
    seed=st.integers(0, 10_000),
    alpha_step=st.integers(0, 10),
)
def test_every_plan_meets_the_deadline_and_work(
    work: float, extra: float, pausable: bool, seed: int, alpha_step: int
) -> None:
    fx = load_factors()
    offset = min(work + extra, 48.0)
    deadline = SUBMIT + timedelta(hours=offset)
    req = request(work_hours=work, deadline=deadline, pausable=pausable, alpha=alpha_step / 10)
    result = plan_from_rows(req, random_rows(SUBMIT, 72, seed), fx)
    for entry in (result["base"], result["best"], *result["pareto"]):
        schedule = entry["schedule"]
        last_end = datetime.fromisoformat(schedule[-1]["slot"]) + timedelta(hours=1)
        assert last_end <= deadline + timedelta(seconds=1)  # (a) nothing ends after the deadline
        assert work_done(fx, schedule) >= work - 1e-6  # (b) all the work is done
        assert pause_gaps(schedule) <= 3  # (c) at most three pauses


# 3 ---------------------------------------------------------------------------------------


def test_idle_slots_add_energy_and_cost(fx: Factors) -> None:
    req = request()
    snap = build_snapshot(req.city, req.cooling, diurnal_rows(SUBMIT), fx, SUBMIT)
    env = planner._build_env(req, snap, fx)
    ctx = env.ctx
    runs = tuple(planner.Run(h, 0.7, 1.0) for h in (1, 2, 13, 14))
    gapped = planner.Plan(runs, "pausable")
    g_gapped = planner._gpu_kwh(ctx, gapped)
    g_runs_only = [0.0] * WINDOW_SLOTS
    for r in runs:
        g_runs_only[r.slot] = ctx.run_kw[r.level] * r.hours
    idle_slots = range(3, 13)  # a 10-hour gap
    assert sum(g_gapped) - sum(g_runs_only) == pytest.approx(10 * ctx.idle_kw)
    assert all(g_gapped[h] == pytest.approx(ctx.idle_kw) for h in idle_slots)
    cost = planner._kwh_cost(ctx, (0.4, 0.4, 0.2))
    assert planner._objective(ctx, gapped, cost) > sum(
        g * c for g, c in zip(g_runs_only, cost, strict=True)
    )


# 4 ---------------------------------------------------------------------------------------


def test_deadline_too_soon_names_the_earliest_finish(fx: Factors) -> None:
    with pytest.raises(EngineError) as err:
        run(fx, work_hours=6.0, deadline=SUBMIT + timedelta(hours=5))
    assert err.value.code == "deadline_too_soon"
    assert "03:14" in err.value.message  # submit 21:14 + 6 h at full power
    assert "10 Oct" in err.value.message


def test_deadline_already_passed_is_too_soon(fx: Factors) -> None:
    with pytest.raises(EngineError) as err:
        run(fx, deadline=SUBMIT - timedelta(hours=1))
    assert err.value.code == "deadline_too_soon"


# 5 ---------------------------------------------------------------------------------------


def test_slot_zero_only_offers_the_rest_of_the_hour(fx: Factors) -> None:
    submit = ist(2026, 10, 9, 21, 40)
    req = request(submit_ts=submit, deadline=submit + timedelta(hours=20), pausable=False)
    result = plan_from_rows(req, diurnal_rows(submit), fx)
    first = result["base"]["schedule"][0]
    assert first["slot"] == ist(2026, 10, 9, 21).isoformat()
    assert first["fraction"] == pytest.approx(20 / 60, abs=1e-5)
    assert result["base"]["start"] == submit.isoformat()
    tau_work = sum(r["fraction"] for r in result["base"]["schedule"])  # level 1.0, tau 1.0
    assert tau_work == pytest.approx(6.0, abs=1e-5)
    finish = datetime.fromisoformat(result["base"]["finish"])
    assert finish == submit + timedelta(hours=6)


# 6 ---------------------------------------------------------------------------------------


def brute_force_best(fx: Factors, req: Any, rows: list[WeatherRow]) -> tuple[int, float]:
    """Best (start slot, level) found by trying every candidate through footprint()."""
    snap = build_snapshot(req.city, req.cooling, rows, fx, req.submit_ts)
    gpu = fx.gpu_params(req.gpu_model)
    fs = fx.central()
    sigma = fx.stress_weight("extremely_high")  # Chennai placeholder category
    f0 = snap.slot0_capacity
    h_d = int((req.deadline - snap.slots[0]) / timedelta(hours=1))

    def totals(start: int, level: float) -> tuple[float, float, float] | None:
        lv = gpu.levels[level]
        remaining, h, g = req.work_hours, start, [0.0] * WINDOW_SLOTS
        while remaining > 1e-9:
            if h >= h_d:
                return None
            hours = min(f0 if h == 0 else 1.0, remaining / lv.tau)
            g[h] = req.gpu_count * gpu.u * gpu.model.p_max_w / 1000 * lv.eps * lv.tau * hours
            remaining -= hours * lv.tau
            h += 1
        t = footprint(g, snap.derived, fs, sigma)[1]
        return t.stress_l, t.co2_kg, t.e_fac_kwh

    w_b, c_b, e_b = totals(0, 1.0)  # type: ignore[misc]
    best: tuple[float, int, float] | None = None
    for s in range(h_d):
        for level in LEVELS:
            t = totals(s, level)
            if t is None:
                continue
            cost = 0.4 * t[0] / w_b + 0.4 * t[1] / c_b + 0.2 * t[2] / e_b
            if best is None or cost < best[0] * (1 - 1e-9):
                best = (cost, s, level)
    assert best is not None
    return best[1], best[2]


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_non_pausable_matches_brute_force(fx: Factors, seed: int) -> None:
    deadline = ist(2026, 10, 10, 9, 0)
    req = request(gpu_count=1, work_hours=3.0, deadline=deadline, pausable=False, alpha=0.5)
    rows = random_rows(SUBMIT, 72, seed)
    start, level = brute_force_best(fx, req, rows)
    chosen = plan_from_rows(req, rows, fx)["chosen"]
    snap_start = ist(2026, 10, 9, 21) + timedelta(hours=start)
    expected_start = SUBMIT if start == 0 else snap_start
    assert chosen["start"] == expected_start.isoformat()
    assert chosen["level_summary"] == f"{round(level * 100)}%"


# 7 ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("alpha", [0.0, 0.3, 0.5, 1.0])
def test_pausable_is_never_worse_than_non_pausable(fx: Factors, seed: int, alpha: float) -> None:
    rows = random_rows(SUBMIT, 72, seed)
    kw = {"alpha": alpha, "work_hours": 5.0, "deadline": SUBMIT + timedelta(hours=30)}
    fixed = run(fx, rows, pausable=False, **kw)
    paused = run(fx, rows, pausable=True, **kw)
    cost_paused = objective(paused, paused["chosen"], alpha)
    assert cost_paused <= objective(fixed, fixed["chosen"], alpha) + 1e-9


# 8 ---------------------------------------------------------------------------------------


def test_pareto_has_eleven_entries_and_chosen_is_indexed_by_alpha(fx: Factors) -> None:
    # 0.3 * 10 is 3.0000000000000004 and 0.7 * 10 is 7.000000000000001 in floating point
    for alpha in (0.0, 0.1, 0.3, 0.5, 0.7, 1.0):
        result = run(fx, alpha=alpha)
        assert [p["alpha"] for p in result["pareto"]] == [i / 10 for i in range(11)]
        assert result["chosen"] is result["pareto"][round(alpha * 10)]
        assert result["chosen"]["alpha"] == alpha


def test_pareto_points_are_unique_and_trade_water_against_carbon(fx: Factors) -> None:
    result = run(fx, deadline=SUBMIT + timedelta(hours=30))
    points = result["points"]
    keys = [(round(p["W_l"], 4), round(p["C_kg"], 4)) for p in points]
    assert len(keys) == len(set(keys))
    assert sorted(a for p in points for a in p["alphas"]) == [i / 10 for i in range(11)]
    water = [e["point"]["W_l"] for e in result["pareto"]]
    carbon = [e["point"]["C_kg"] for e in result["pareto"]]
    for i in range(10):  # fixed test data only: within 1% (greedy planner, energy still weighs 0.2)
        assert water[i + 1] <= water[i] * 1.01
        assert carbon[i + 1] >= carbon[i] * 0.99


# 9 ---------------------------------------------------------------------------------------


def test_ranges_bracket_the_central_values(fx: Factors) -> None:
    result = run(fx, cooling="evaporative", deadline=SUBMIT + timedelta(hours=30))
    for entry in (result["base"], *result["pareto"], result["best"]):
        for key, (low, mid, high) in entry["totals"].items():
            assert low <= mid <= high, key
        for key, (low, high) in entry["savings_ranges"].items():
            assert low <= entry["savings_central"][key] <= high, key
    low_d, high_d = result["person_days_range"]
    assert 0 < low_d <= high_d


# 10 --------------------------------------------------------------------------------------


@pytest.mark.slow
def test_plan_is_fast_enough_for_a_lambda_request(fx: Factors) -> None:
    req = request(gpu_count=4, work_hours=8.0, deadline=SUBMIT + timedelta(hours=40), pausable=True)
    rows = diurnal_rows(SUBMIT)
    timings = []
    for _ in range(20):
        t0 = time.perf_counter()
        plan_from_rows(req, rows, fx)
        timings.append(time.perf_counter() - t0)
    assert statistics.median(timings) < 0.2


# 11 --------------------------------------------------------------------------------------


def test_forced_non_pausable_adds_a_note_and_never_pauses(fx: Factors) -> None:
    result = run(fx, pausable=True, pausable_allowed=False)
    assert "pause_unsupported" in result["notes"]
    for entry in result["pareto"]:
        assert entry["kind"] != "pausable"
        assert pause_gaps(entry["schedule"]) == 0


# extra behaviour ---------------------------------------------------------------------------


def zigzag_rows() -> list[WeatherRow]:
    """Alternating hot and cool hours: the cheapest slots are every other one."""
    first = ist(2026, 10, 9, 21)
    return [
        WeatherRow(first + timedelta(hours=i), 40.0 if i % 2 else 22.0, 60.0, 0.0)
        for i in range(72)
    ]


def test_pausable_wins_when_the_cheap_hours_are_split_by_a_hot_spell(fx: Factors) -> None:
    kw = {"cooling": "evaporative", "alpha": 1.0, "work_hours": 6.0, "gpu_count": 2,
          "deadline": SUBMIT + timedelta(hours=14)}
    paused = run(fx, split_window_rows(), pausable=True, **kw)
    fixed = run(fx, split_window_rows(), pausable=False, **kw)
    chosen = paused["chosen"]
    assert chosen["kind"] == "pausable"
    assert "pausable_won" in chosen["notes"]
    hot_hours = {"01:00", "02:00"}
    assert {r["slot"][11:16] for r in chosen["schedule"] if r["state"] == "pause"} == hot_hours
    assert chosen["savings_central"]["water_pct"] > fixed["chosen"]["savings_central"]["water_pct"]
    assert work_done(fx, chosen["schedule"]) >= 6.0 - 1e-6


def test_many_cheap_gaps_are_limited_to_three(fx: Factors) -> None:
    result = run(fx, zigzag_rows(), work_hours=6.0, deadline=SUBMIT + timedelta(hours=40),
                 gpu_count=1, alpha=0.5)
    for entry in result["pareto"]:
        assert pause_gaps(entry["schedule"]) <= 3
        assert work_done(fx, entry["schedule"]) >= 6.0 - 1e-6


def test_pausable_falls_back_when_cheapest_levels_cannot_finish(fx: Factors) -> None:
    # 6.5 h of work in 7 slots: fine at 100% (6.77 h) but not at the cheapest level, 70% (6.1 h)
    deadline = SUBMIT + timedelta(hours=6, minutes=50)
    result = run(fx, work_hours=6.5, deadline=deadline, pausable=True)
    assert result["chosen"]["kind"] == "non_pausable"
    assert "gap_limit_fallback" in result["chosen"]["notes"]
    assert work_done(fx, result["chosen"]["schedule"]) >= 6.5 - 1e-6


def test_deadline_beyond_the_window_is_capped(fx: Factors) -> None:
    result = run(fx, deadline=SUBMIT + timedelta(days=5))
    assert "deadline_capped" in result["notes"]
    last = datetime.fromisoformat(result["chosen"]["schedule"][-1]["slot"])
    assert last < ist(2026, 10, 9, 21) + timedelta(hours=WINDOW_SLOTS)


def test_plan_output_shape_and_json(fx: Factors) -> None:
    result = run(fx)
    text = json.dumps(result)
    assert len(text) < 120_000
    assert result["plan_id"] == ""
    assert result["tags"] == {"energy": "modelled", "water": "modelled", "co2": "modelled",
                              "tau": "placeholder", "forecast": "live"}
    assert len(result["series"]) == WINDOW_SLOTS
    assert {"direct_l_per_kwh", "grid_l_per_kwh", "co2_kg_per_kwh", "level", "state"} <= (
        result["series"][0].keys()
    )
    assert {r["state"] for r in result["series"]} <= {"off", "run", "pause"}
    assert all(len(e["series_overlay"]) == WINDOW_SLOTS for e in result["pareto"])
    assert result["inputs"]["gpu_model"] == "RTX-4090"
    assert result["forecast_snapshot"]["factor_version"] == fx.version
    assert result["factor_version"] == fx.version


def test_chosen_plan_saves_something_against_base_with_the_placeholder_sweep(fx: Factors) -> None:
    result = run(fx, deadline=SUBMIT + timedelta(hours=30))
    assert result["savings_ranges"]["energy_pct"][1] > 0


def test_cached_forecast_is_tagged_and_noted(fx: Factors) -> None:
    result = run(fx, diurnal_rows(SUBMIT, hours=6))
    assert result["tags"]["forecast"] == "cached"
    assert "forecast_cached" in result["notes"]


def test_measured_sweep_changes_the_tau_tag(tmp_path: Path) -> None:
    sweep = {"gpus": {"RTX-4090": {
        "levels": {"1.0": {"tau": 1.0, "eps": 1.0}, "0.85": {"tau": 0.95, "eps": 0.8},
                   "0.7": {"tau": 0.85, "eps": 0.7}},
        "u": 0.8, "p_idle_w": 30.0}}}
    path = tmp_path / "s.json"
    path.write_text(json.dumps(sweep), encoding="utf-8")
    result = run(load_factors(sweep_path=path))
    assert result["tags"]["tau"] == "measured"


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"gpu_count": 0}, "invalid_field"),
        ({"gpu_count": 5000}, "invalid_field"),
        ({"work_hours": 0.0}, "invalid_field"),
        ({"work_hours": 49.0}, "invalid_field"),
        ({"alpha": 0.35}, "invalid_field"),
        ({"alpha": 1.1}, "invalid_field"),
        ({"city": "Atlantis"}, "unknown_city"),
        ({"gpu_model": "RTX-9999"}, "unknown_gpu"),
        ({"cooling": "heat_pump"}, "invalid_field"),
        ({"cooling": "evaporative", "pue_user": 5.0}, "invalid_field"),
    ],
)
def test_bad_input_is_rejected_with_a_code(
    fx: Factors, override: dict[str, Any], code: str
) -> None:
    with pytest.raises(EngineError) as err:
        if "city" in override:
            plan_from_rows(request(**override), [], fx)
        else:
            run(fx, **override)
    assert err.value.code == code


def test_naive_submit_time_is_rejected(fx: Factors) -> None:
    with pytest.raises(ValueError, match="timezone"):
        run(fx, submit_ts=SUBMIT.replace(tzinfo=None))


def test_snapshot_must_match_the_request(fx: Factors) -> None:
    snap = build_snapshot("Chennai", "room_ac", diurnal_rows(SUBMIT), fx, SUBMIT)
    with pytest.raises(ValueError, match="snapshot"):
        planner.plan(request(city="Pune"), snap, fx)
    later = SUBMIT + timedelta(hours=3)
    with pytest.raises(ValueError, match="snapshot"):
        planner.plan(request(submit_ts=later, deadline=later + timedelta(hours=12)), snap, fx)


def test_default_example_is_reasonable(fx: Factors) -> None:
    """PRD 6.1: Chennai lab, 2 x RTX 4090, 6 h, deadline 09:00, can pause."""
    result = run(fx)
    assert result["base"]["start"] == SUBMIT.isoformat()
    finish = datetime.fromisoformat(result["chosen"]["finish"])
    assert finish <= DEADLINE.astimezone(IST)
    assert result["chosen"]["level_summary"] in {"70%", "85%", "100%/70%", "70%/100%"}
