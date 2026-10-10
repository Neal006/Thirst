"""Bad and hostile input must raise EngineError (never hang, crash or score silently)."""

from __future__ import annotations

import copy
import math
from datetime import timedelta
from typing import Any

import pytest
from weather_helpers import SUBMIT, diurnal_rows, ist, request

from engine import factors as factors_mod
from engine import score
from engine.errors import EngineError
from engine.explain import explain_template
from engine.factors import Factors, load_cities, load_factors
from engine.forecast import WeatherRow
from engine.planner import plan_from_rows
from engine.units import clock_text, when_text

NOW = ist(2026, 10, 10, 12, 0)


@pytest.fixture(scope="module")
def fx() -> Factors:
    return load_factors()


@pytest.fixture(scope="module")
def plan(fx: Factors) -> dict[str, Any]:
    req = request(pausable=False, deadline=SUBMIT + timedelta(hours=30))
    return plan_from_rows(req, diurnal_rows(SUBMIT), fx)


def good_receipt(plan: dict[str, Any]) -> dict[str, Any]:
    hour = plan["forecast_snapshot"]["slots"][3]
    return {"job_id": "j_aaaaaaaaaaaa", "end_ts": NOW.isoformat(), "method": "nvml_energy",
            "slots": [{"hour": hour, "run_kwh": 0.5, "idle_kwh": 0.0, "level": 0.7}]}


def with_slot(plan: dict[str, Any], **changes: Any) -> dict[str, Any]:
    rec = good_receipt(plan)
    rec["slots"][0] = {**rec["slots"][0], **changes}
    return rec


# receipts ---------------------------------------------------------------------------------


def test_the_good_receipt_scores(fx: Factors, plan: dict[str, Any]) -> None:
    assert score.receipt_footprints(good_receipt(plan), plan, (), fx)["kwh"] == 0.5


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"run_kwh": 1e7}, "implausible_energy"),
        ({"run_kwh": 1e-9}, "invalid_field"),  # noise, not a job
        ({"idle_kwh": 1e7}, "implausible_energy"),
        ({"run_kwh": math.inf}, "invalid_field"),
        ({"run_kwh": math.nan}, "invalid_field"),
        ({"idle_kwh": math.nan}, "invalid_field"),
        ({"level": math.nan}, "invalid_field"),
        ({"run_kwh": "0.5"}, "invalid_field"),
        ({"run_kwh": True}, "invalid_field"),
        ({"hour": "not a time"}, "invalid_field"),
        ({"hour": "2026-10-10T03:00:00"}, "invalid_field"),  # no timezone
        ({"hour": "2100-01-01T00:00:00+05:30"}, "slot_out_of_range"),
        ({"hour": "2026-10-09T10:00:00+05:30"}, "slot_out_of_range"),
    ],
)
def test_bad_slot_values_raise_engine_error(
    fx: Factors, plan: dict[str, Any], changes: dict[str, Any], code: str
) -> None:
    with pytest.raises(EngineError) as err:
        score.receipt_footprints(with_slot(plan, **changes), plan, (), fx)
    assert err.value.code == code


@pytest.mark.parametrize("missing", ["hour", "run_kwh", "idle_kwh", "level"])
def test_missing_slot_keys_raise_engine_error(
    fx: Factors, plan: dict[str, Any], missing: str
) -> None:
    rec = good_receipt(plan)
    del rec["slots"][0][missing]
    with pytest.raises(EngineError) as err:
        score.receipt_footprints(rec, plan, (), fx)
    assert err.value.code == "invalid_field"


def test_too_many_slots_are_rejected(fx: Factors, plan: dict[str, Any]) -> None:
    rec = good_receipt(plan)
    rec["slots"] = rec["slots"] * 73
    with pytest.raises(EngineError) as err:
        score.receipt_footprints(rec, plan, (), fx)
    assert err.value.code == "invalid_field"


def test_receipt_without_slots_key_is_invalid(fx: Factors, plan: dict[str, Any]) -> None:
    with pytest.raises(EngineError):
        score.receipt_footprints({"job_id": "j_a"}, plan, (), fx)


def test_scoring_notes_when_the_plan_used_other_factors(
    fx: Factors, plan: dict[str, Any]
) -> None:
    same = score.receipt_footprints(good_receipt(plan), plan, (), fx)
    assert same["factor_version_mismatch"] is False
    old = copy.deepcopy(plan)
    old["forecast_snapshot"]["factor_version"] = "older"
    assert score.receipt_footprints(good_receipt(old), old, (), fx)["factor_version_mismatch"]


# planner ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "override",
    [
        {"alpha": math.nan}, {"alpha": math.inf}, {"alpha": "0.5"}, {"alpha": None},
        {"work_hours": "6"}, {"work_hours": math.nan}, {"work_hours": math.inf},
        {"gpu_count": True}, {"gpu_count": 2.0}, {"gpu_count": "2"},
        {"pue_user": "1.5", "cooling": "evaporative"},
        {"pue_user": math.nan, "cooling": "evaporative"},
        {"pausable": "no"},
    ],
)
def test_planner_rejects_bad_types_with_engine_error(
    fx: Factors, override: dict[str, Any]
) -> None:
    with pytest.raises(EngineError) as err:
        plan_from_rows(request(**override), diurnal_rows(SUBMIT), fx)
    assert err.value.code == "invalid_field"


def test_planner_rejects_naive_times_with_engine_error(fx: Factors) -> None:
    for field in ("submit_ts", "deadline"):
        naive = SUBMIT.replace(tzinfo=None) + timedelta(hours=12)
        with pytest.raises(EngineError) as err:
            plan_from_rows(request(**{field: naive}), diurnal_rows(SUBMIT), fx)
        assert err.value.code == "invalid_field"


def test_chosen_is_a_copy_of_the_pareto_entry(plan: dict[str, Any]) -> None:
    assert plan["chosen"] == plan["pareto"][5]
    assert plan["chosen"] is not plan["pareto"][5]
    assert plan["savings_ranges"] is not plan["chosen"]["savings_ranges"]


# weather ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [{"temp_c": math.nan}, {"temp_c": math.inf}, {"temp_c": 90.0}, {"rh_pct": -1.0},
     {"rh_pct": 101.0}, {"rh_pct": math.nan}, {"rad_wm2": math.nan}, {"rad_wm2": -5.0},
     {"rad_wm2": 5000.0}, {"temp_c": "30"}],
)
def test_weather_rows_must_be_finite_and_plausible(bad: dict[str, Any]) -> None:
    values: dict[str, Any] = {"hour": SUBMIT, "temp_c": 30.0, "rh_pct": 60.0, "rad_wm2": 100.0}
    values.update(bad)
    with pytest.raises(EngineError) as err:
        WeatherRow(**values)
    assert err.value.code == "invalid_field"


# shared state -----------------------------------------------------------------------------


def test_cached_cities_cannot_be_modified() -> None:
    with pytest.raises(AttributeError):  # a read-only mapping has no pop()
        load_cities().pop("Chennai")  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        load_cities()["Atlantis"] = None  # type: ignore[index]
    assert "Chennai" in load_cities()


def test_cached_factors_cannot_be_modified(fx: Factors) -> None:
    with pytest.raises(TypeError):
        fx.grid.annual_shares["coal"] = 0.0  # type: ignore[index]
    with pytest.raises(TypeError):
        fx.gpus["RTX-4090"] = None  # type: ignore[index]
    with pytest.raises(TypeError):
        fx.central().values["wf_coal"] = 0.0  # type: ignore[index]


def test_cached_sweep_data_cannot_be_modified(tmp_path: Any) -> None:
    import json

    path = tmp_path / "s.json"
    path.write_text(json.dumps({"gpus": {"RTX-4090": {
        "levels": {"1.0": {"tau": 1.0, "eps": 1.0}, "0.85": {"tau": 0.9, "eps": 0.9},
                   "0.7": {"tau": 0.8, "eps": 0.8}}, "u": 0.9, "p_idle_w": 40.0}}}))
    sweep = factors_mod.load_factors(sweep_path=path).sweep
    with pytest.raises(TypeError):
        sweep["RTX-4090"]["u"] = 0.1
    with pytest.raises(TypeError):
        sweep["RTX-4090"]["levels"]["0.7"]["tau"] = 0.1


# pages and text ------------------------------------------------------------------------


def fake(job: str, end_ts: str) -> dict[str, Any]:
    return {"job_id": job, "end_ts": end_ts, "method": "nvml_energy", "kwh": 1.0, "capture": 0.5,
            "flexible": True, "no_room": False,
            "absolute": {"actual": {"E_fac_kwh": 1, "litres": 1, "W_l": 1, "C_kg": 1,
                                    "person_days": 1}}}


SITE = {"site_id": "s_a", "name": "Lab", "city": "Chennai", "cooling": "room_ac", "gpu_count": 4,
        "public": True}


def test_recent_receipts_sort_by_instant_not_by_text(fx: Factors) -> None:
    # 05:00 UTC is 10:30 IST, later than 08:00 IST even though the text sorts earlier
    receipts = [
        fake("j_ist", "2026-10-10T08:00:00+05:30"),
        fake("j_utc", "2026-10-10T05:00:00+00:00"),
    ]
    view = score.site_page_view(SITE, receipts, NOW, fx)
    assert [r["job_id"] for r in view["recent_receipts"]] == ["j_utc", "j_ist"]


def test_stored_none_values_do_not_crash_the_site_score(fx: Factors) -> None:
    site = {**SITE, "coverage_declared": None}
    assert score.site_score([fake("j_a", "2026-10-10T08:00:00+05:30")], site, NOW, fx)["score"]


def test_mixed_sign_ranges_are_not_called_savings(fx: Factors, plan: dict[str, Any]) -> None:
    mixed = copy.deepcopy(plan)
    mixed["chosen"]["savings_ranges"] = {"water_pct": [-3, 5], "co2_pct": [2, 4],
                                         "energy_pct": [1, 2]}
    text = explain_template(mixed)
    assert "saves between" not in text
    assert "effect is uncertain" in text
    assert "between -3 and 5%" in text


def test_dates_do_not_depend_on_the_locale(plan: dict[str, Any]) -> None:
    text = explain_template(plan)
    assert "Oct" in text
    assert clock_text(ist(2026, 10, 10, 3, 14)) == "03:14 on 10 Oct"
    assert when_text(ist(2026, 10, 10, 3, 14)) == "Sat 10 Oct 03:14"


def test_receipts_with_no_run_energy_are_invalid_not_perfect(
    fx: Factors, plan: dict[str, Any]
) -> None:
    only_idle = with_slot(plan, run_kwh=0.0, idle_kwh=0.5)
    empty = {**good_receipt(plan), "slots": []}
    for rec in (only_idle, empty):
        with pytest.raises(EngineError) as err:
            score.receipt_footprints(rec, plan, (), fx)
        assert err.value.code == "invalid_field"


def test_private_site_page_shows_only_name_division_and_score(fx: Factors) -> None:
    private = {**SITE, "public": False}
    view = score.site_page_view(private, [fake("j_a", "2026-10-10T08:00:00+05:30")], NOW, fx)
    assert view["site"]["name"] == "Lab"
    assert view["site"]["division"] == "D1"
    assert view["score"]["value"] is not None
    assert view["recent_receipts"] == []
    assert view["monthly_absolute"] is None


def test_factor_version_covers_every_data_file(tmp_path: Any) -> None:
    base = load_factors().version
    sweep = tmp_path / "powercap_sweep.json"
    sweep.write_bytes((factors_mod.DATA_DIR / "powercap_sweep.json").read_bytes())
    assert load_factors(sweep_path=sweep).version == base
    sweep.write_bytes(b'{"gpus": {}, "note": "changed"}')
    assert load_factors(sweep_path=sweep).version != base
    gpus = tmp_path / "gpus.json"
    gpus.write_bytes((factors_mod.DATA_DIR / "gpus.json").read_bytes() + b" ")
    assert load_factors(gpus_path=gpus).version != base
