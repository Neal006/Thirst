from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from engine import grid
from engine.factors import Factors, load_factors

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
SOURCES = ("coal", "gas", "nuclear", "hydro", "solar", "wind", "other")


@pytest.fixture(scope="module")
def fx() -> Factors:
    return load_factors()


@pytest.fixture(scope="module", params=["grid_shares_a.json", "grid_shares_b.json"])
def model(request: pytest.FixtureRequest) -> grid.GridModel:
    return grid.load_grid(FIXTURES / request.param)


HOURS = [h % 24 for h in range(48)]
CLEAR_DAY = [max(0.0, 800 * (1 - ((h - 12) / 6) ** 2)) for h in HOURS]


def test_calibrate_coal_ef_matches_the_target() -> None:
    annual = {"coal": 0.745, "gas": 0.02, "nuclear": 0.025, "hydro": 0.085, "solar": 0.06,
              "wind": 0.04, "other": 0.025}
    ef_coal = grid.calibrate_coal_ef(annual, ef_gas=0.49, target=0.727)
    yearly = annual["coal"] * ef_coal + annual["gas"] * 0.49
    assert yearly == pytest.approx(0.727, abs=1e-9)
    assert 0.85 <= ef_coal <= 1.10


def test_calibrate_rejects_a_grid_with_no_coal() -> None:
    with pytest.raises(ValueError, match="coal"):
        grid.calibrate_coal_ef({"coal": 0.0, "gas": 1.0}, ef_gas=0.49, target=0.727)


def test_load_grid_kinds() -> None:
    a = grid.load_grid(FIXTURES / "grid_shares_a.json")
    b = grid.load_grid(FIXTURES / "grid_shares_b.json")
    assert (a.kind, b.kind) == ("hod_profile", "annual")
    assert set(a.annual_shares) == set(SOURCES)


def test_load_grid_rejects_shares_that_do_not_sum_to_one(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"kind":"annual","annual_shares":{"coal":0.5,"gas":0.1},"s_avg_solar":0.0}',
                   encoding="utf-8")
    with pytest.raises(ValueError, match="sum"):
        grid.load_grid(bad)


def test_shares_sum_to_one_every_hour(model: grid.GridModel, fx: Factors) -> None:
    for rad in (CLEAR_DAY, [0.0] * 48, [300.0] * 48, [5000.0] * 48):
        for shares in grid.hourly_shares(model, HOURS, rad, fx.central()):
            assert sum(shares.values()) == pytest.approx(1.0, abs=1e-6)
            assert all(v >= 0 for v in shares.values())
            assert set(shares) == set(SOURCES)


@given(rad=st.lists(st.floats(min_value=0, max_value=1200), min_size=48, max_size=48))
def test_shares_sum_to_one_for_random_radiation(rad: list[float]) -> None:
    fx = load_factors()
    for kind in ("grid_shares_a.json", "grid_shares_b.json"):
        m = grid.load_grid(FIXTURES / kind)
        for shares in grid.hourly_shares(m, HOURS, rad, fx.central()):
            assert sum(shares.values()) == pytest.approx(1.0, abs=1e-6)


def test_solar_share_is_capped(model: grid.GridModel, fx: Factors) -> None:
    for shares in grid.hourly_shares(model, HOURS, [1e6] * 48, fx.central()):
        assert shares["solar"] <= 0.6 + 1e-9


def test_coal_never_goes_negative_and_overflow_is_renormalised(fx: Factors) -> None:
    m = grid.GridModel(
        kind="annual", annual_shares={"coal": 0.05, "gas": 0.05, "nuclear": 0.0, "hydro": 0.0,
                                      "solar": 0.05, "wind": 0.85, "other": 0.0},
        s_avg_solar=0.05, profiles=None, mean_radiation_profile=None, status="test", source="test")
    # One very sunny hour among dark ones: solar jumps to the cap and would need more coal
    # than exists.
    shares = grid.hourly_shares(m, HOURS, [0.0] * 47 + [1e6], fx.central())[-1]
    assert shares["coal"] == 0.0
    assert shares["gas"] == 0.0  # gas gives way after coal
    assert shares["solar"] > 0.05  # solar rose from its 5% average
    assert sum(shares.values()) == pytest.approx(1.0, abs=1e-6)
    assert all(v >= 0 for v in shares.values())


def test_clear_midday_is_cleaner_than_midnight(model: grid.GridModel, fx: Factors) -> None:
    shares = grid.hourly_shares(model, HOURS, CLEAR_DAY, fx.central())
    ci = [grid.ci(s, fx.central()) for s in shares]
    assert ci[12] < ci[0]
    ew = [grid.ewif(s, fx.central()) for s in shares]
    assert ew[12] < ew[0]


def test_overcast_day_is_dirtier_than_clear_day(model: grid.GridModel, fx: Factors) -> None:
    clear = grid.hourly_shares(model, HOURS, CLEAR_DAY, fx.central())
    cloudy = grid.hourly_shares(model, HOURS, [d * 0.2 for d in CLEAR_DAY], fx.central())
    clear_ci = grid.ci(clear[12], fx.central())
    cloudy_ci = grid.ci(cloudy[12], fx.central())
    if model.kind == "hod_profile":
        assert cloudy_ci > clear_ci
    else:
        # Option B divides by the window's mean radiation, so it only sees the *shape* of the
        # day, not absolute cloudiness. Scaling every hour equally changes nothing.
        assert cloudy_ci == pytest.approx(clear_ci)


def test_night_with_zero_radiation_is_fine(model: grid.GridModel, fx: Factors) -> None:
    shares = grid.hourly_shares(model, HOURS, [0.0] * 48, fx.central())
    assert all(sum(s.values()) == pytest.approx(1.0, abs=1e-6) for s in shares)


def test_ewif_extremes(fx: Factors) -> None:
    c = fx.central()
    solar_only = {k: (1.0 if k == "solar" else 0.0) for k in SOURCES}
    coal_only = {k: (1.0 if k == "coal" else 0.0) for k in SOURCES}
    assert grid.ewif(solar_only, c) == 0.0
    assert grid.ewif(coal_only, c) == pytest.approx(c["wf_coal"])
    assert grid.ci(coal_only, c) == pytest.approx(c["ef_coal"])


def test_ewif_scales_with_grid_loss_factor(fx: Factors) -> None:
    c = fx.central()
    coal_only = {k: (1.0 if k == "coal" else 0.0) for k in SOURCES}
    lossy = type(c)(values={**c.values, "grid_loss_factor": 1.1}, name="lossy")
    assert grid.ewif(coal_only, lossy) == pytest.approx(1.1 * c["wf_coal"])


def test_inputs_must_have_matching_lengths(model: grid.GridModel, fx: Factors) -> None:
    with pytest.raises(ValueError, match="length"):
        grid.hourly_shares(model, HOURS, [0.0] * 47, fx.central())
