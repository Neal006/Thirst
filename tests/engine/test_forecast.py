from __future__ import annotations

import json
from datetime import timedelta

import pytest
from weather_helpers import SUBMIT, diurnal_rows, flat_rows

from engine import forecast
from engine.errors import EngineError
from engine.factors import Factors, load_factors
from engine.forecast import ForecastSnapshot, WeatherRow, build_snapshot, intensities
from engine.units import IST, floor_hour


@pytest.fixture(scope="module")
def fx() -> Factors:
    return load_factors()


def snap(
    fx: Factors, rows: list[WeatherRow], cooling: str = "room_ac", pue_user: float | None = None
) -> ForecastSnapshot:
    return build_snapshot("Chennai", cooling, rows, fx, SUBMIT, pue_user=pue_user)


def test_snapshot_has_48_slots_of_every_array(fx: Factors) -> None:
    s = snap(fx, diurnal_rows(SUBMIT))
    assert len(s.slots) == 48
    for arr in (s.temp_c, s.rh_pct, s.rad_wm2, s.derived.tw, s.derived.pue, s.derived.wue,
                s.derived.ci, s.derived.ewif):
        assert len(arr) == 48
    assert s.slots[0] == floor_hour(SUBMIT)
    assert s.source == "live"
    assert s.slot0_capacity == pytest.approx(46 / 60)
    assert s.factor_version == fx.version


def test_wet_bulb_never_exceeds_dry_bulb(fx: Factors) -> None:
    s = snap(fx, diurnal_rows(SUBMIT))
    assert all(tw <= t for tw, t in zip(s.derived.tw, s.temp_c, strict=True))


def test_room_ac_has_no_direct_water_and_cooling_tower_does(fx: Factors) -> None:
    rows = diurnal_rows(SUBMIT)
    assert all(w == 0.0 for w in snap(fx, rows).derived.wue)
    tower = snap(fx, rows, "evaporative")
    assert all(w > 0 for w in tower.derived.wue)
    assert set(tower.derived.pue) == {1.4}
    assert set(snap(fx, rows, "evaporative", pue_user=1.2).derived.pue) == {1.2}


def test_ac_pue_is_higher_in_the_hot_afternoon_than_at_night(fx: Factors) -> None:
    s = snap(fx, diurnal_rows(SUBMIT))
    by_hour = {slot.hour: pue for slot, pue in zip(s.slots, s.derived.pue, strict=True)}
    assert by_hour[15] > by_hour[3]


def test_missing_hours_are_filled_from_the_sample_and_marked_cached(fx: Factors) -> None:
    s = snap(fx, diurnal_rows(SUBMIT, hours=10))
    assert s.source == "cached"
    assert len(s.slots) == 48
    assert all(t > 0 for t in s.temp_c)
    # the first 10 hours still come from the live rows
    assert s.temp_c[:10] == tuple(r.temp_c for r in diurnal_rows(SUBMIT, hours=10))


def test_no_rows_at_all_uses_the_sample_completely(fx: Factors) -> None:
    s = snap(fx, [])
    assert s.source == "cached"
    assert len(s.derived.ci) == 48


def test_rows_outside_the_window_are_ignored(fx: Factors) -> None:
    rows = flat_rows(SUBMIT - timedelta(hours=5), hours=80)
    s = snap(fx, rows)
    assert s.source == "live"
    assert set(s.temp_c) == {30.0}


def test_unknown_city_is_an_engine_error(fx: Factors) -> None:
    with pytest.raises(EngineError) as err:
        build_snapshot("Atlantis", "room_ac", [], fx, SUBMIT)
    assert err.value.code == "unknown_city"


def test_naive_weather_hours_are_rejected() -> None:
    with pytest.raises(EngineError, match="timezone"):
        WeatherRow(hour=SUBMIT.replace(tzinfo=None), temp_c=30, rh_pct=60, rad_wm2=0)


def test_json_round_trip_is_small_and_lossless(fx: Factors) -> None:
    s = snap(fx, diurnal_rows(SUBMIT))
    text = json.dumps(s.to_json())
    assert len(text) < 30_000
    back = ForecastSnapshot.from_json(json.loads(text))
    assert back.slots == s.slots
    assert back.source == s.source
    assert back.derived.ci == pytest.approx(s.derived.ci, abs=1e-4)
    assert back.derived.pue == pytest.approx(s.derived.pue, abs=1e-4)
    assert back.slot0_capacity == pytest.approx(s.slot0_capacity)


def test_intensities_for_range_sets_are_ordered(fx: Factors) -> None:
    s = snap(fx, diurnal_rows(SUBMIT), "evaporative")
    low = intensities(s, fx, fx.low())
    high = intensities(s, fx, fx.high())
    for i in range(48):
        assert low.wue[i] <= s.derived.wue[i] <= high.wue[i]
        assert low.ewif[i] <= s.derived.ewif[i] <= high.ewif[i]
        assert low.ci[i] <= s.derived.ci[i] <= high.ci[i]


def test_intensities_with_the_central_set_reproduce_the_snapshot(fx: Factors) -> None:
    s = snap(fx, diurnal_rows(SUBMIT))
    again = intensities(s, fx, fx.central())
    assert again.ci == pytest.approx(s.derived.ci)
    assert again.pue == pytest.approx(s.derived.pue)


def test_sample_rows_cover_all_seed_cities() -> None:
    for city in ("Chennai", "Bengaluru", "Hyderabad", "Mumbai", "Delhi", "Pune"):
        rows = forecast.load_sample_rows(city)
        assert len(rows) == 96
        assert all(r.hour.utcoffset() == IST.utcoffset(None) for r in rows)
