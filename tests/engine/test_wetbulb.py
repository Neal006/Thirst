from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from engine.wetbulb import in_valid_range, stull_tw, stull_tw_checked


def test_trd_reference_point() -> None:
    assert stull_tw(20, 50) == pytest.approx(13.7, abs=0.1)


@pytest.mark.parametrize(
    ("temp_c", "rh", "expected"),
    [(30, 60, 24.0), (35, 40, 24.5), (25, 90, 23.7), (40, 20, 22.7), (10, 80, 7.9)],
)
def test_extra_reference_points(temp_c: float, rh: float, expected: float) -> None:
    assert stull_tw(temp_c, rh) == pytest.approx(expected, abs=0.1)


temps = st.floats(min_value=-10, max_value=45, allow_nan=False)
humidities = st.floats(min_value=10, max_value=95, allow_nan=False)


@given(temp_c=temps, rh=humidities)
def test_wet_bulb_never_exceeds_dry_bulb_in_valid_range(temp_c: float, rh: float) -> None:
    assert stull_tw(temp_c, rh) <= temp_c + 0.5  # Stull's fit is good to about +-0.3 degC


@given(
    temp_c=st.floats(min_value=10, max_value=45),
    rh=st.floats(min_value=20, max_value=90),
    extra=st.floats(0.5, 5),
)
def test_wet_bulb_rises_with_humidity(temp_c: float, rh: float, extra: float) -> None:
    """Checked over the range the product uses (Indian cities, 10 to 45 degC).

    Stull's empirical fit has tiny non-monotone artefacts in cold, dry air (for example -1 degC at
    10 % RH), which is outside what Thirst needs.
    """
    assert stull_tw(temp_c, rh + extra) > stull_tw(temp_c, rh)


@given(rh=humidities, t=st.floats(min_value=-10, max_value=40), extra=st.floats(0.5, 5))
def test_wet_bulb_rises_with_temperature(rh: float, t: float, extra: float) -> None:
    assert stull_tw(t + extra, rh) > stull_tw(t, rh)


@pytest.mark.parametrize(
    ("temp_c", "rh", "valid"),
    [(20, 50, True), (20, 4, False), (20, 99.5, False), (-25, 50, False), (55, 50, False),
     (50, 99, True), (-20, 5, True)],
)
def test_valid_range(temp_c: float, rh: float, valid: bool) -> None:
    assert in_valid_range(temp_c, rh) is valid


def test_checked_variant_flags_out_of_range_and_clamps_humidity() -> None:
    tw, ok = stull_tw_checked(20, 50)
    assert ok is True
    assert tw == pytest.approx(13.7, abs=0.1)

    tw_low, ok_low = stull_tw_checked(30, 2)
    assert ok_low is False
    assert tw_low == pytest.approx(stull_tw(30, 5))  # RH clamped to 5 for the formula

    tw_hi, ok_hi = stull_tw_checked(30, 100)
    assert ok_hi is False
    assert tw_hi == pytest.approx(stull_tw(30, 99))
