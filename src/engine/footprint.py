"""Energy, water and carbon footprint of GPU energy per slot (plan 02.6, TRD 5.7).

Per slot, with ``g`` the GPU energy in kWh::

    E_IT  = g * it_overhead          E_fac = E_IT * PUE
    D     = E_IT * WUE               I     = E_fac * EWIF
    W     = D * sigma_site + I * sigma_grid        (stress-weighted litres)
    C     = E_fac * CI

Everything is linear in ``g``, which the score relies on (Best scaling, TRD 5.9).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .factors import FactorSet
from .forecast import Intensities


@dataclass(frozen=True, slots=True)
class SlotFootprint:
    e_gpu_kwh: float
    e_it_kwh: float
    e_fac_kwh: float
    direct_l: float
    indirect_l: float
    stress_l: float
    co2_kg: float

    @property
    def water_l(self) -> float:
        """Unweighted litres consumed (direct plus indirect)."""
        return self.direct_l + self.indirect_l


@dataclass(frozen=True, slots=True)
class Totals(SlotFootprint):
    def person_days(self, fs: FactorSet) -> float:
        """Water as person-days of the city norm, from *unweighted* litres."""
        return self.water_l / fs["person_day_l"]


@dataclass(frozen=True, slots=True)
class Coefficients:
    """Footprint of one kWh of GPU energy in each slot."""

    e_fac: tuple[float, ...]
    direct: tuple[float, ...]
    indirect: tuple[float, ...]
    stress: tuple[float, ...]
    co2: tuple[float, ...]


def coefficients(
    inten: Intensities, fs: FactorSet, sigma_site: float, sigma_grid: float | None = None
) -> Coefficients:
    """Per-kWh-of-GPU-energy factors for every slot. ``sigma_grid`` defaults to ``sigma_site``."""
    s_grid = sigma_site if sigma_grid is None else sigma_grid
    overhead = fs["it_overhead"]
    e_fac, direct, indirect, stress, co2 = [], [], [], [], []
    for pue, wue, ci, ewif in zip(inten.pue, inten.wue, inten.ci, inten.ewif, strict=True):
        fac = overhead * pue
        d = overhead * wue
        i = fac * ewif
        e_fac.append(fac)
        direct.append(d)
        indirect.append(i)
        stress.append(d * sigma_site + i * s_grid)
        co2.append(fac * ci)
    return Coefficients(tuple(e_fac), tuple(direct), tuple(indirect), tuple(stress), tuple(co2))


def footprint(
    gpu_kwh: Sequence[float],
    inten: Intensities,
    fs: FactorSet,
    sigma_site: float,
    sigma_grid: float | None = None,
) -> tuple[list[SlotFootprint], Totals]:
    """Per-slot footprints and their totals for GPU energy ``gpu_kwh`` (slot 0 first)."""
    if len(gpu_kwh) > len(inten):
        raise ValueError("more energy slots than intensity slots")
    coef = coefficients(inten, fs, sigma_site, sigma_grid)
    overhead = fs["it_overhead"]
    slots = [
        SlotFootprint(
            e_gpu_kwh=g,
            e_it_kwh=g * overhead,
            e_fac_kwh=g * coef.e_fac[h],
            direct_l=g * coef.direct[h],
            indirect_l=g * coef.indirect[h],
            stress_l=g * coef.stress[h],
            co2_kg=g * coef.co2[h],
        )
        for h, g in enumerate(gpu_kwh)
    ]
    totals = Totals(
        e_gpu_kwh=sum(s.e_gpu_kwh for s in slots),
        e_it_kwh=sum(s.e_it_kwh for s in slots),
        e_fac_kwh=sum(s.e_fac_kwh for s in slots),
        direct_l=sum(s.direct_l for s in slots),
        indirect_l=sum(s.indirect_l for s in slots),
        stress_l=sum(s.stress_l for s in slots),
        co2_kg=sum(s.co2_kg for s in slots),
    )
    return slots, totals
