"""Stull (2011) wet-bulb temperature from air temperature and relative humidity (plan 02.3).

Reference: R. Stull, J. Appl. Meteorol. Climatol. 50 (2011), https://doi.org/10.1175/JAMC-D-11-0143.1
Valid for roughly RH 5 to 99 % and T -20 to 50 degC, accurate to about 0.3 degC.
"""

from __future__ import annotations

import math

RH_MIN, RH_MAX = 5.0, 99.0
T_MIN, T_MAX = -20.0, 50.0


def stull_tw(t_c: float, rh_pct: float) -> float:
    """Wet-bulb temperature in degC. No range checks; see ``stull_tw_checked``."""
    return float(
        t_c * math.atan(0.151977 * math.sqrt(rh_pct + 8.313659))
        + math.atan(t_c + rh_pct)
        - math.atan(rh_pct - 1.676331)
        + 0.00391838 * rh_pct**1.5 * math.atan(0.023101 * rh_pct)
        - 4.686035
    )


def in_valid_range(t_c: float, rh_pct: float) -> bool:
    """True when the inputs are inside the range the Stull fit was made for."""
    return T_MIN <= t_c <= T_MAX and RH_MIN <= rh_pct <= RH_MAX


def stull_tw_checked(t_c: float, rh_pct: float) -> tuple[float, bool]:
    """Wet-bulb with humidity clamped to [5, 99] %; flag is False for out-of-range inputs."""
    clamped = min(max(rh_pct, RH_MIN), RH_MAX)
    return stull_tw(t_c, clamped), in_valid_range(t_c, rh_pct)
