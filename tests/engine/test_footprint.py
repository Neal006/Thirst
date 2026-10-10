from __future__ import annotations

import pytest

from engine.factors import Factors, load_factors
from engine.footprint import coefficients, footprint
from engine.forecast import Intensities


@pytest.fixture(scope="module")
def fx() -> Factors:
    return load_factors()


def inten(n: int = 1, pue: float = 1.3833, wue: float = 0.0, ci: float = 0.7,
          ewif: float = 2.5) -> Intensities:
    return Intensities(tw=(20.0,) * n, pue=(pue,) * n, wue=(wue,) * n, ci=(ci,) * n,
                       ewif=(ewif,) * n)


def test_one_kwh_matches_the_hand_calculation(fx: Factors) -> None:
    slots, totals = footprint([1.0], inten(), fx.central(), sigma_site=2.5)
    e_it = 1.2
    e_fac = e_it * 1.3833
    assert totals.e_gpu_kwh == 1.0
    assert totals.e_it_kwh == pytest.approx(e_it)
    assert totals.e_fac_kwh == pytest.approx(e_fac)
    assert totals.direct_l == 0.0
    assert totals.indirect_l == pytest.approx(e_fac * 2.5)
    assert totals.stress_l == pytest.approx(e_fac * 2.5 * 2.5)
    assert totals.co2_kg == pytest.approx(e_fac * 0.7)
    assert len(slots) == 1


def test_direct_water_is_stress_weighted_with_the_site_weight(fx: Factors) -> None:
    _, totals = footprint([1.0], inten(wue=2.0), fx.central(), sigma_site=2.0, sigma_grid=1.0)
    d = 1.2 * 2.0
    i = 1.2 * 1.3833 * 2.5
    assert totals.direct_l == pytest.approx(d)
    assert totals.stress_l == pytest.approx(d * 2.0 + i * 1.0)


def test_footprint_is_linear_in_energy(fx: Factors) -> None:
    base = [0.5, 1.0, 0.0, 2.0]
    _, one = footprint(base, inten(4), fx.central(), 2.0)
    _, three = footprint([3 * g for g in base], inten(4), fx.central(), 2.0)
    for name in ("e_gpu_kwh", "e_it_kwh", "e_fac_kwh", "direct_l", "indirect_l", "stress_l",
                 "co2_kg"):
        assert getattr(three, name) == pytest.approx(3 * getattr(one, name))


def test_totals_are_the_sum_of_the_slots(fx: Factors) -> None:
    slots, totals = footprint([1.0, 2.0, 3.0], inten(3, wue=1.0), fx.central(), 1.5)
    assert totals.stress_l == pytest.approx(sum(s.stress_l for s in slots))
    assert totals.co2_kg == pytest.approx(sum(s.co2_kg for s in slots))
    assert totals.e_fac_kwh == pytest.approx(sum(s.e_fac_kwh for s in slots))


def test_person_days_use_unweighted_litres(fx: Factors) -> None:
    _, totals = footprint([10.0], inten(wue=1.0), fx.central(), sigma_site=2.5)
    assert totals.person_days(fx.central()) == pytest.approx(
        (totals.direct_l + totals.indirect_l) / 135
    )
    assert totals.water_l == pytest.approx(totals.direct_l + totals.indirect_l)


def test_more_energy_slots_than_intensities_is_an_error(fx: Factors) -> None:
    with pytest.raises(ValueError, match="slots"):
        footprint([1.0, 1.0], inten(1), fx.central(), 1.0)


def test_coefficients_match_footprint_per_kwh(fx: Factors) -> None:
    n = 3
    it = inten(n, wue=0.8)
    coef = coefficients(it, fx.central(), sigma_site=2.0)
    for h in range(n):
        energies = [0.0] * n
        energies[h] = 1.0
        _, t = footprint(energies, it, fx.central(), 2.0)
        assert coef.stress[h] == pytest.approx(t.stress_l)
        assert coef.co2[h] == pytest.approx(t.co2_kg)
        assert coef.e_fac[h] == pytest.approx(t.e_fac_kwh)
        assert coef.direct[h] == pytest.approx(t.direct_l)
        assert coef.indirect[h] == pytest.approx(t.indirect_l)


def test_empty_energy_gives_zero_totals(fx: Factors) -> None:
    slots, totals = footprint([], inten(1), fx.central(), 1.0)
    assert slots == []
    assert totals.e_fac_kwh == 0.0
