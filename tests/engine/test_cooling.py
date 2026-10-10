from __future__ import annotations

import pytest

from engine import cooling
from engine.cooling import Cooling
from engine.errors import EngineError
from engine.factors import Factors, load_factors


@pytest.fixture(scope="module")
def fx() -> Factors:
    return load_factors()


def test_cop_stays_in_bounds_over_the_whole_temperature_range(fx: Factors) -> None:
    c = fx.central()
    for half_degrees in range(0, 101):
        t = half_degrees / 2
        for rated in (c["cop_rated_room_ac"], c["cop_rated_air_chiller"]):
            assert 1.5 <= cooling.cop(t, rated, c) <= 6.0


def test_cop_at_reference_and_hot_temperature(fx: Factors) -> None:
    c = fx.central()
    assert cooling.cop(35, 3.0, c) == pytest.approx(3.0)
    assert cooling.cop(45, 3.0, c) == pytest.approx(2.25)


def test_pue_room_ac_at_35c(fx: Factors) -> None:
    assert cooling.pue(Cooling.ROOM_AC, 35, fx.central()) == pytest.approx(1 + 1 / 3 + 0.05)


def test_pue_air_chiller_uses_its_own_rated_cop(fx: Factors) -> None:
    assert cooling.pue(Cooling.AIR_CHILLER, 35, fx.central()) == pytest.approx(1 + 1 / 4.5 + 0.05)


def test_pue_evaporative_uses_user_value_or_default(fx: Factors) -> None:
    c = fx.central()
    assert cooling.pue(Cooling.EVAPORATIVE, 30, c, pue_user=1.25) == 1.25
    assert cooling.pue(Cooling.EVAPORATIVE, 30, c) == 1.4


@pytest.mark.parametrize("bad", [0.99, 3.01, -1.0])
def test_pue_user_must_be_between_1_and_3(fx: Factors, bad: float) -> None:
    with pytest.raises(EngineError) as err:
        cooling.pue(Cooling.EVAPORATIVE, 30, fx.central(), pue_user=bad)
    assert err.value.code == "invalid_field"


def test_ac_types_use_no_direct_water(fx: Factors) -> None:
    c = fx.central()
    for kind in (Cooling.ROOM_AC, Cooling.AIR_CHILLER):
        for tw in (0.0, 15.0, 30.0):
            assert cooling.wue(kind, tw, c) == 0.0


def test_evaporative_wue_follows_wet_bulb_and_is_clipped(fx: Factors) -> None:
    c = fx.central()
    assert cooling.wue(Cooling.EVAPORATIVE, 25, c) == pytest.approx(2.7)
    assert cooling.wue(Cooling.EVAPORATIVE, 50, c) == 4.0
    assert cooling.wue(Cooling.EVAPORATIVE, -10, c) == 0.0


def test_range_sets_order_pue_and_wue_low_central_high(fx: Factors) -> None:
    low, mid, high = fx.low(), fx.central(), fx.high()
    for kind in (Cooling.ROOM_AC, Cooling.AIR_CHILLER):
        pues = [cooling.pue(kind, 38, s) for s in (low, mid, high)]
        assert pues == sorted(pues)
    assert cooling.wue(Cooling.EVAPORATIVE, 24, low) < cooling.wue(Cooling.EVAPORATIVE, 24, mid)
    assert cooling.wue(Cooling.EVAPORATIVE, 24, mid) < cooling.wue(Cooling.EVAPORATIVE, 24, high)


def test_parse_accepts_known_values_and_rejects_others() -> None:
    assert Cooling.parse("room_ac") is Cooling.ROOM_AC
    with pytest.raises(EngineError) as err:
        Cooling.parse("heat_pump")
    assert err.value.code == "invalid_field"
