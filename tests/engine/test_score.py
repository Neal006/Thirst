from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from weather_helpers import SUBMIT, diurnal_rows, flat_rows, ist

from engine import score
from engine.errors import EngineError
from engine.factors import Factors, load_factors
from engine.forecast import WeatherRow
from engine.planner import plan_from_rows
from engine.units import floor_hour

NOW = ist(2026, 10, 10, 12, 0)
LEVELS = (1.0, 0.85, 0.7)


@pytest.fixture(scope="module")
def fx() -> Factors:
    return load_factors()


@pytest.fixture(scope="module")
def flat_fx(tmp_path_factory: pytest.TempPathFactory) -> Factors:
    sweep = {"gpus": {"RTX-4090": {
        "levels": {"1.0": {"tau": 1.0, "eps": 1.0}, "0.85": {"tau": 0.97, "eps": 1.0},
                   "0.7": {"tau": 0.9, "eps": 1.0}},
        "u": 0.9, "p_idle_w": 45.0}}}
    path = tmp_path_factory.mktemp("sweep") / "sweep.json"
    path.write_text(json.dumps(sweep), encoding="utf-8")
    return load_factors(sweep_path=path)


def make_plan(fx: Factors, rows: list[WeatherRow] | None = None, **kw: Any) -> dict[str, Any]:
    from weather_helpers import request

    kw.setdefault("pausable", False)
    kw.setdefault("deadline", SUBMIT + timedelta(hours=30))
    return plan_from_rows(request(**kw), rows or diurnal_rows(SUBMIT), fx)


@pytest.fixture(scope="module")
def plan(fx: Factors) -> dict[str, Any]:
    return make_plan(fx)


def receipt_from(
    plan: dict[str, Any], which: str = "best", scale: float = 1.0, method: str = "nvml_energy"
) -> dict[str, Any]:
    """A receipt whose energy follows the Base, Best or chosen plan of ``plan``."""
    entry = plan[which]
    hours = plan["forecast_snapshot"]["slots"]
    slots = []
    for h, (kwh, overlay) in enumerate(zip(entry["gpu_kwh"], entry["series_overlay"], strict=True)):
        if kwh <= 0:
            continue
        running = overlay["state"] == "run"
        slots.append({
            "hour": hours[h],
            "run_kwh": kwh * scale if running else 0.0,
            "idle_kwh": 0.0 if running else kwh * scale,
            "level": overlay["level"] or 1.0,
        })
    end = datetime.fromisoformat(slots[-1]["hour"]) + timedelta(hours=1)
    return {"job_id": "j_aaaaaaaaaaaa", "end_ts": end.isoformat(), "method": method,
            "slots": slots}


def scored(fx: Factors, plan: dict[str, Any], **kw: Any) -> dict[str, Any]:
    rec = receipt_from(plan, **kw)
    return score.receipt_footprints(rec, plan, (), fx)


# formulas ---------------------------------------------------------------------------------


def test_capture_is_clipped_and_flags_no_room(fx: Factors) -> None:
    fs = fx.central()
    assert score.capture(0.9, 0.8, fs) == (pytest.approx(0.5), False)
    assert score.capture(1.3, 0.8, fs) == (0.0, False)  # worse than Base
    assert score.capture(0.5, 0.8, fs) == (1.0, False)  # better than Best
    assert score.capture(0.8, 0.98, fs) == (None, True)  # 1 - J_best = 0.02 < 0.03
    assert score.capture(0.8, 0.97, fs)[1] is False  # exactly at the threshold has room


def test_j_of_base_is_one(fx: Factors) -> None:
    assert score.j_value(5, 7, 9, 5, 7, 9, fx.central()) == pytest.approx(1.0)
    assert score.j_value(0, 0, 0, 5, 7, 9, fx.central()) == 0.0
    assert score.j_value(1, 1, 1, 0, 0, 0, fx.central()) == 0.0  # empty Base cannot divide


@pytest.mark.parametrize(
    ("value", "flex", "expected"),
    [(95, 0.5, "platinum"), (90, 0.30, "platinum"), (90, 0.29, "silver"), (80, 0.5, "gold"),
     (75, 0.3, "gold"), (75, 0.1, "silver"), (74.99, 1.0, "silver"), (60, 0.0, "silver"),
     (59.99, 1.0, "bronze"), (45, 0.0, "bronze"), (44.99, 1.0, None), (None, 1.0, None)],
)
def test_badges(value: float | None, flex: float, expected: str | None) -> None:
    assert score.badge(value, flex) == expected


@pytest.mark.parametrize(
    ("gpus", "expected"),
    [(1, "D1"), (16, "D1"), (17, "D2"), (256, "D2"), (257, "D3"), (4096, "D3"), (4097, "D4")],
)
def test_divisions(gpus: int, expected: str) -> None:
    assert score.division(gpus) == expected


# receipt footprints ------------------------------------------------------------------------


def test_following_the_best_plan_captures_everything(fx: Factors, plan: dict[str, Any]) -> None:
    res = scored(fx, plan, which="best")
    assert res["scoring"]["J"]["base"] == pytest.approx(1.0)
    assert res["scoring"]["J"]["actual"] == pytest.approx(res["scoring"]["J"]["best"], abs=1e-6)
    assert res["capture"] == pytest.approx(1.0, abs=1e-6)
    assert res["flexible"] is True
    assert res["no_room"] is False


def test_running_the_base_plan_captures_nothing(fx: Factors, plan: dict[str, Any]) -> None:
    res = scored(fx, plan, which="base")
    assert res["scoring"]["J"]["actual"] == pytest.approx(1.0, abs=1e-6)
    assert res["capture"] == pytest.approx(0.0, abs=1e-6)


def test_base_energy_at_full_power_equals_the_run_energy(fx: Factors, plan: dict[str, Any]) -> None:
    rec = receipt_from(plan, which="base")
    total_run = sum(s["run_kwh"] for s in rec["slots"])
    res = score.receipt_footprints(rec, plan, (), fx)
    assert res["scoring"]["base"]["E_gpu_kwh"] == pytest.approx(total_run)
    assert res["scoring"]["actual"]["E_gpu_kwh"] == pytest.approx(total_run)


def test_capped_energy_implies_a_base_of_the_same_work(fx: Factors, plan: dict[str, Any]) -> None:
    rec = receipt_from(plan, which="best")
    res = score.receipt_footprints(rec, plan, (), fx)
    eps = 0.8  # placeholder 70% level
    expected_base = sum(s["run_kwh"] for s in rec["slots"]) / eps
    assert res["scoring"]["base"]["E_gpu_kwh"] == pytest.approx(expected_base)


@settings(max_examples=100, deadline=None)
@given(
    hours=st.lists(st.integers(0, 60), min_size=1, max_size=12, unique=True),
    kwh=st.lists(st.floats(0.0, 0.9), min_size=12, max_size=12),
    idle=st.lists(st.floats(0.0, 0.09), min_size=12, max_size=12),
    levels=st.lists(st.sampled_from(LEVELS), min_size=12, max_size=12),
)
def test_capture_is_always_between_zero_and_one(
    hours: list[int], kwh: list[float], idle: list[float], levels: list[float]
) -> None:
    assume(sum(kwh[: len(hours)]) >= 0.01)  # a receipt needs a real amount of run energy
    fx = load_factors()
    base_plan = make_plan(fx)
    first = datetime.fromisoformat(base_plan["forecast_snapshot"]["slots"][0])
    slots = [
        {"hour": (first + timedelta(hours=h)).isoformat(), "run_kwh": k, "idle_kwh": i, "level": lv}
        for h, k, i, lv in zip(hours, kwh, idle, levels, strict=False)
    ]
    rec = {"job_id": "j_x", "end_ts": NOW.isoformat(), "method": "nvml_energy", "slots": slots}
    res = score.receipt_footprints(rec, base_plan, (), fx)
    j = res["scoring"]["J"]
    assert j["base"] == pytest.approx(1.0)  # holds for any receipt, by construction
    if res["capture"] is None:
        assert 1 - j["best"] < 0.03
    else:
        expected = (1 - j["actual"]) / (1 - j["best"])
        assert res["capture"] == pytest.approx(min(max(expected, 0.0), 1.0))


def test_same_receipt_two_observed_weathers_same_capture_different_litres(fx: Factors) -> None:
    plan_ev = make_plan(fx, cooling="evaporative", deadline=SUBMIT + timedelta(hours=30))
    rec = receipt_from(plan_ev, which="chosen")
    first = floor_hour(SUBMIT)

    def weather(temp: float) -> list[WeatherRow]:
        return [WeatherRow(first + timedelta(hours=i), temp, 60.0, 300.0) for i in range(48)]

    cool = score.receipt_footprints(rec, plan_ev, weather(24.0), fx)
    hot = score.receipt_footprints(rec, plan_ev, weather(40.0), fx)
    assert cool["capture"] == hot["capture"]
    assert cool["scoring"] == hot["scoring"]
    assert hot["absolute"]["actual"]["litres"] > cool["absolute"]["actual"]["litres"]


def test_observed_hours_are_counted_in_the_basis(fx: Factors, plan: dict[str, Any]) -> None:
    rec = receipt_from(plan, which="best")
    hours = [datetime.fromisoformat(s["hour"]) for s in rec["slots"]]
    observed = [WeatherRow(h, 28.0, 60.0, 0.0) for h in hours[:3]]
    res = score.receipt_footprints(rec, plan, observed, fx)
    assert res["absolute"]["basis"] == {"observed": 3, "forecast": len(hours) - 3}
    none = score.receipt_footprints(rec, plan, (), fx)
    assert none["absolute"]["basis"] == {"observed": 0, "forecast": len(hours)}
    # without observations the absolute figures equal the scored ones, up to the 5-decimal
    # rounding of the weather stored in the snapshot
    assert none["absolute"]["actual"] == pytest.approx(none["scoring"]["actual"], rel=1e-4)


def test_flat_conditions_have_no_room_to_shift(flat_fx: Factors) -> None:
    plan_flat = make_plan(flat_fx, flat_rows(SUBMIT))
    res = scored(flat_fx, plan_flat, which="base")
    assert res["capture"] is None
    assert res["no_room"] is True
    assert res["flexible"] is False


def test_splitting_a_job_does_not_change_capture(fx: Factors, plan: dict[str, Any]) -> None:
    whole = score.receipt_footprints(receipt_from(plan, scale=1.0), plan, (), fx)
    half = score.receipt_footprints(receipt_from(plan, scale=0.5), plan, (), fx)
    assert half["capture"] == pytest.approx(whole["capture"])
    # a mediocre job, split in two proportional receipts, keeps its energy-weighted A
    mixed = receipt_from(plan, which="chosen", scale=1.0)
    mixed["slots"] = [{**s, "level": 1.0} for s in mixed["slots"]]  # claims to have run at 100%
    full = score.receipt_footprints(mixed, plan, (), fx)
    part = score.receipt_footprints({**mixed, "slots": [
        {**s, "run_kwh": s["run_kwh"] / 2} for s in mixed["slots"]]}, plan, (), fx)
    site = {"site_id": "s_a", "coverage_declared": 0.0, "public": False}
    one = score.site_score([full], site, NOW, fx)["A"]
    two = score.site_score([part, {**part, "job_id": "j_b"}], site, NOW, fx)["A"]
    assert one == pytest.approx(two)


def test_hours_past_the_snapshot_are_extrapolated(fx: Factors, plan: dict[str, Any]) -> None:
    rec = receipt_from(plan, which="best")
    first = datetime.fromisoformat(plan["forecast_snapshot"]["slots"][0])
    late = (first + timedelta(hours=50)).isoformat()
    rec["slots"].append({"hour": late, "run_kwh": 0.5, "idle_kwh": 0.0, "level": 1.0})
    res = score.receipt_footprints(rec, plan, (), fx)
    assert res["extrapolated_hours"] == [late]
    assert res["kwh"] == pytest.approx(sum(s["run_kwh"] + s["idle_kwh"] for s in rec["slots"]))


def test_hours_before_submit_are_rejected(fx: Factors, plan: dict[str, Any]) -> None:
    rec = receipt_from(plan, which="best")
    first = datetime.fromisoformat(plan["forecast_snapshot"]["slots"][0])
    rec["slots"].append({"hour": (first - timedelta(hours=1)).isoformat(), "run_kwh": 1.0,
                         "idle_kwh": 0.0, "level": 1.0})
    with pytest.raises(EngineError) as err:
        score.receipt_footprints(rec, plan, (), fx)
    assert err.value.code == "slot_out_of_range"


@pytest.mark.parametrize(
    "bad", [{"run_kwh": -1.0}, {"idle_kwh": -0.1}, {"level": 0.5}],
)
def test_bad_slot_values_are_rejected(
    fx: Factors, plan: dict[str, Any], bad: dict[str, float]
) -> None:
    rec = receipt_from(plan, which="best")
    rec["slots"][0] = {**rec["slots"][0], **bad}
    with pytest.raises(EngineError) as err:
        score.receipt_footprints(rec, plan, (), fx)
    assert err.value.code == "invalid_field"


def test_method_sets_the_energy_tag_and_output_is_json(fx: Factors, plan: dict[str, Any]) -> None:
    measured = scored(fx, plan, method="nvml_energy")
    modelled = scored(fx, plan, method="modelled")
    assert measured["tags"]["energy"] == "measured"
    assert modelled["tags"]["energy"] == "modelled"
    assert measured["tags"]["water"] == "modelled"
    json.dumps(measured)


# site score ---------------------------------------------------------------------------------


def fake(kwh: float, cap: float | None, *, method: str = "nvml_energy", days_ago: float = 1.0,
         job: str = "j_a") -> dict[str, Any]:
    return {
        "job_id": job, "end_ts": (NOW - timedelta(days=days_ago)).isoformat(), "method": method,
        "kwh": kwh, "capture": cap, "flexible": cap is not None, "no_room": cap is None,
        "absolute": {"actual": {"E_fac_kwh": kwh * 1.5, "litres": kwh * 3.0, "W_l": kwh * 6.0,
                                "C_kg": kwh * 0.9, "person_days": kwh * 0.02}},
    }


SITE = {"site_id": "s_aaaaaaaaaa", "name": "Lab", "city": "Chennai", "cooling": "room_ac",
        "gpu_count": 8, "coverage_declared": 0.9, "public": True, "simulated": False}


def test_site_score_follows_the_spec_formula(fx: Factors) -> None:
    receipts = [fake(30, 0.8, job="j_1"), fake(10, 0.4, job="j_2"),
                fake(10, None, method="modelled", job="j_3")]
    res = score.site_score(receipts, SITE, NOW, fx)
    assert res["A"] == pytest.approx(50 * (0.8 * 30 + 0.4 * 10) / 40)
    assert res["C_parts"] == {"measured_share": pytest.approx(10 * 40 / 50), "coverage": 5.0,
                              "public": 5.0}
    assert res["C"] == pytest.approx(18.0)
    assert res["score"] == pytest.approx((35.0 + 18.0) / 70 * 100)
    assert res["flex_share"] == pytest.approx(0.8)
    assert res["badge"] == "gold"
    assert res["provisional"] is True
    assert res["B"] == "not_rated"
    assert res["reason"] is None
    assert res["monthly_absolute"]["kwh"] == 50


def test_no_flexible_receipt_gives_no_score_but_still_part_c(fx: Factors) -> None:
    res = score.site_score([fake(10, None), fake(5, None, job="j_b")], SITE, NOW, fx)
    assert res["score"] is None
    assert res["reason"] == "needs_flexible_receipt"
    assert res["badge"] is None
    assert res["C"] == pytest.approx(10 + 5 + 5)
    empty = score.site_score([], SITE, NOW, fx)
    assert empty["score"] is None
    assert empty["C_parts"]["measured_share"] == 0.0


def test_modelled_receipts_count_in_a_but_give_no_measured_points(fx: Factors) -> None:
    res = score.site_score([fake(10, 1.0, method="modelled")], SITE, NOW, fx)
    assert res["A"] == pytest.approx(50.0)
    assert res["C_parts"]["measured_share"] == 0.0


def test_unverified_receipts_are_ignored_completely(fx: Factors) -> None:
    res = score.site_score([fake(10, 1.0), fake(100, 0.0, method="unverified", job="j_b")],
                           SITE, NOW, fx)
    assert res["A"] == pytest.approx(50.0)
    assert res["receipts"] == 1
    assert res["monthly_absolute"]["kwh"] == 10


def test_only_the_last_30_days_count(fx: Factors) -> None:
    receipts = [fake(10, 1.0, days_ago=29, job="j_1"), fake(10, 0.0, days_ago=31, job="j_2")]
    res = score.site_score(receipts, SITE, NOW, fx)
    assert res["A"] == pytest.approx(50.0)
    assert res["receipts"] == 1


def test_private_site_loses_the_openness_points(fx: Factors) -> None:
    res = score.site_score([fake(10, 1.0)], {**SITE, "public": False, "coverage_declared": 0.5},
                           NOW, fx)
    assert res["C_parts"]["public"] == 0.0
    assert res["C_parts"]["coverage"] == 0.0


def test_perfect_site_is_capped_at_100(fx: Factors) -> None:
    res = score.site_score([fake(10, 1.0)], SITE, NOW, fx)
    assert res["score"] == pytest.approx(100.0)
    assert res["badge"] == "platinum"


# pages and leaderboard ------------------------------------------------------------------


def test_site_page_lists_the_last_ten_receipts_newest_first_without_gpu_count(
    fx: Factors,
) -> None:
    receipts = [fake(1, 0.5, days_ago=d / 10 + 0.1, job=f"j_{d}") for d in range(15)]
    view = score.site_page_view(SITE, receipts, NOW, fx)
    recent = view["recent_receipts"]
    assert len(recent) == 10
    assert [r["end_ts"] for r in recent] == sorted((r["end_ts"] for r in recent), reverse=True)
    assert view["site"]["division"] == "D1"
    assert "gpu_count" not in json.dumps(view)
    assert view["score"]["value"] == int(view["score"]["value"] * 10) / 10
    assert view["monthly_absolute"]["kwh"] == 15


def test_score_value_never_shows_a_threshold_it_missed(fx: Factors) -> None:
    # score 74.99... must not display as 75.0 next to a Silver badge
    view = score._score_view({"score": 74.99, "provisional": True, "badge": "silver", "A": 0,
                              "B": "not_rated", "C": 0, "C_parts": {}, "flex_share": 1,
                              "reason": None})
    assert view["value"] == 74.9


def test_leaderboard_orders_ranks_and_hides_private_sites(fx: Factors) -> None:
    def site(sid: str, **kw: Any) -> dict[str, Any]:
        return {**SITE, "site_id": sid, "name": sid, **kw}

    sites = [site("s_c"), site("s_a"), site("s_b"), site("s_none"), site("s_priv", public=False),
             site("s_other", gpu_count=100), site("s_pre", division="D1")]
    receipts = {
        "s_a": [fake(10, 0.9)], "s_b": [fake(10, 0.9)], "s_c": [fake(10, 0.5)],
        "s_priv": [fake(10, 1.0)], "s_other": [fake(10, 1.0)], "s_pre": [fake(10, 0.1)],
    }
    rows = score.leaderboard_rows(sites, receipts, "D1", NOW, fx)
    assert [r["site_id"] for r in rows] == ["s_a", "s_b", "s_c", "s_pre", "s_none"]
    assert [r["rank"] for r in rows] == [1, 2, 3, 4, None]  # ties break on site_id
    assert rows[-1]["score"] is None
    assert {r["division"] for r in rows} == {"D1"}
    assert "gpu_count" not in json.dumps(rows)
    assert all("monthly_absolute" in r and "simulated" in r for r in rows)


def test_leaderboard_ties_break_on_flexible_share(fx: Factors) -> None:
    sites = [{**SITE, "site_id": "s_a", "name": "a"}, {**SITE, "site_id": "s_b", "name": "b"}]
    receipts = {
        "s_a": [fake(10, 1.0), fake(10, None, job="j_n")],  # flexible share 0.5
        "s_b": [fake(10, 1.0)],  # flexible share 1.0
    }
    rows = score.leaderboard_rows(sites, receipts, "D1", NOW, fx)
    # s_a: A = 50, s_b: A = 50, both C equal -> same score; s_b has the higher flexible share
    assert rows[0]["score"] == pytest.approx(rows[1]["score"])
    assert [r["site_id"] for r in rows] == ["s_b", "s_a"]
