"""PUE and WUE per cooling type (plan step 02.4).

All IT electricity becomes heat that the cooling system must remove. Lab room ACs and air-cooled
chillers use no direct water but draw more power on hot afternoons (lower COP). Cooling towers use
direct water that rises with the wet-bulb temperature.
"""

from __future__ import annotations

from enum import StrEnum

from .errors import EngineError
from .factors import FactorSet

PUE_USER_MIN, PUE_USER_MAX = 1.0, 3.0


class Cooling(StrEnum):
    ROOM_AC = "room_ac"
    AIR_CHILLER = "air_chiller"
    EVAPORATIVE = "evaporative"

    @classmethod
    def parse(cls, value: str) -> Cooling:
        try:
            return cls(value)
        except ValueError:
            allowed = ", ".join(c.value for c in cls)
            raise EngineError("invalid_field", f"cooling must be one of: {allowed}") from None


def _clip(x: float, low: float, high: float) -> float:
    return min(max(x, low), high)


def rated_cop(kind: Cooling, fs: FactorSet) -> float:
    """Rated COP of an AC-type system (0 for cooling towers, which do not use it)."""
    if kind is Cooling.ROOM_AC:
        return fs["cop_rated_room_ac"]
    if kind is Cooling.AIR_CHILLER:
        return fs["cop_rated_air_chiller"]
    return 0.0


def cop(t_c: float, rated: float, fs: FactorSet) -> float:
    """COP at outdoor temperature ``t_c``, falling with heat and clipped to the allowed band."""
    raw = rated * (1 - fs["cop_temp_slope"] * (t_c - fs["cop_ref_temp_c"]))
    return _clip(raw, fs["cop_min"], fs["cop_max"])


def pue(kind: Cooling, t_c: float, fs: FactorSet, pue_user: float | None = None) -> float:
    """Power usage effectiveness: facility energy per unit of IT energy."""
    if pue_user is not None:
        is_number = isinstance(pue_user, int | float) and not isinstance(pue_user, bool)
        if not is_number or not PUE_USER_MIN <= pue_user <= PUE_USER_MAX:
            raise EngineError("invalid_field", "pue must be a number from 1.0 to 3.0.")
    if kind is Cooling.EVAPORATIVE:
        return pue_user if pue_user is not None else fs["pue_evaporative_default"]
    return 1.0 + 1.0 / cop(t_c, rated_cop(kind, fs), fs) + fs["pue_misc"]


def wue(kind: Cooling, tw_c: float, fs: FactorSet) -> float:
    """Direct water use in litres per kWh of IT energy."""
    if kind is not Cooling.EVAPORATIVE:
        return 0.0
    return _clip(fs["wue_a"] + fs["wue_b"] * tw_c, 0.0, fs["wue_max"])
