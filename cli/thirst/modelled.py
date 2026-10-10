"""Modelled energy for machines without an NVIDIA GPU (plan 04.3.e, TRD 6.5).

Power while running at cap level ``l`` is ``u x P_max x eps_l x tau_l`` per GPU; while paused it is
the idle power. The numbers come from the measured sweep when one exists, else from the same
placeholders the engine uses (``factors.json``; a test keeps them equal). Receipts made this way are
tagged ``method = "modelled"`` and get no measurement points in the score.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .gpus import DATA_DIR, GpuModel
from .meter import BaseMeter, GpuInfo, now_ist

logger = logging.getLogger(__name__)

DEFAULT_U = 0.9
# level -> (tau, eps). Equal to the placeholders in src/engine/data/factors.json.
DEFAULT_LEVELS: dict[float, tuple[float, float]] = {
    1.0: (1.0, 1.0),
    0.85: (0.97, 0.88),
    0.7: (0.9, 0.8),
}
SWEEP_FILE = DATA_DIR / "powercap_sweep.json"


@dataclass(frozen=True)
class PowerModel:
    p_max_w: float
    p_idle_w: float
    u: float
    levels: Mapping[float, tuple[float, float]]

    def run_watts(self, level: float) -> float:
        tau, eps = self.levels[min(self.levels, key=lambda known: abs(known - level))]
        return self.u * self.p_max_w * eps * tau


def load_bundled_sweep(path: Path = SWEEP_FILE) -> dict[str, Any] | None:
    """The measured sweep bundled with the CLI, or ``None`` if there is none (or it is broken)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        logger.warning("powercap_sweep.json could not be read; using the default model")
        return None
    return data if isinstance(data, dict) else None


def _measured_levels(entry: Mapping[str, Any]) -> dict[float, tuple[float, float]] | None:
    levels: dict[float, tuple[float, float]] = {}
    for key, value in (entry.get("levels") or {}).items():
        tau, eps = float(value.get("tau", 0.0)), float(value.get("eps", 0.0))
        if tau > 0 and eps > 0:
            levels[float(key)] = (tau, eps)
    return levels or None


def power_model(gpu: GpuModel, sweep: Mapping[str, Any] | None) -> PowerModel:
    """Measured numbers for this GPU model where the sweep has them, else the defaults."""
    entry = ((sweep or {}).get("gpus") or {}).get(gpu.id) or {}
    levels = dict(DEFAULT_LEVELS)
    levels.update(_measured_levels(entry) or {})
    u = float(entry.get("u") or 0.0)
    idle = float(entry.get("p_idle_w") or 0.0)
    return PowerModel(
        p_max_w=gpu.p_max_w,
        p_idle_w=idle if idle > 0 else gpu.p_idle_w,
        u=u if u > 0 else DEFAULT_U,
        levels=levels,
    )


class ModelledMeter(BaseMeter):
    """Same interface as ``Meter``, but estimates energy from the power model."""

    method = "modelled"

    def __init__(
        self,
        model: PowerModel,
        gpu_count: int,
        *,
        gpu_label: str = "modelled GPU",
        interval_s: float = 1.0,
        wall: Callable[[], datetime] = now_ist,
        mono: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(interval_s=interval_s, wall=wall, mono=mono)
        self._model = model
        self._count = gpu_count
        self._label = gpu_label

    def _probe(self) -> tuple[tuple[GpuInfo, ...], str]:
        infos = tuple(GpuInfo(i, f"modelled-{i}", self._label, False) for i in range(self._count))
        return infos, ""

    def _read_gpu(self, info: GpuInfo, seconds: float) -> float:
        running = self._state == "run"
        watts = self._model.run_watts(self._level) if running else self._model.p_idle_w
        return watts * seconds * 1000.0  # W x s = J; x 1000 = mJ
