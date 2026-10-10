"""Measured power-cap sweep (plan 04.5, TRD 6.4, contract 08 §2.5).

For each cap level the workload runs a fixed number of steps; we record wall time and GPU energy:
``tau_l = time_100 / time_l`` and ``eps_l = (energy_l / steps) / (energy_100 / steps)``. Idle power
is measured for ``idle_seconds`` with the model loaded and no work. The GPU and torch parts sit
behind the ``Workload`` protocol; the real run (``TorchResnetWorkload``) needs the GPU box.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from .errors import CliError, GpuError
from .gpus import GpuModel
from .ledger import IST
from .nvml import EnergyCounterUnsupported, NvmlApi
from .powercap import PowerCap, SmiRunner, run_command

DEFAULT_LEVELS = (1.0, 0.85, 0.7)
DEFAULT_STEPS = 300
DEFAULT_WARMUP = 30
DEFAULT_IDLE_S = 60.0
DEFAULT_SETTLE_S = 5.0
WORKLOAD_TEXT = "resnet18 random 128x3x32x32, {warmup} warmup + {steps} steps"


class Workload(Protocol):
    def warmup(self, steps: int) -> None: ...
    def run(self, steps: int) -> None: ...  # must synchronise the GPU before it returns
    def idle(self, seconds: float) -> None: ...


@dataclass(frozen=True)
class LevelResult:
    seconds: float
    energy_mj: float


@dataclass(frozen=True)
class SweepResult:
    entry: dict[str, Any]
    gate_failures: tuple[str, ...]


# ------------------------------------------------------------ formulas and gates


def compute_levels(results: Mapping[float, LevelResult]) -> dict[str, dict[str, float]]:
    """tau and eps per level, relative to the 100% run (TRD 6.4). Steps are equal at every level."""
    full = results.get(1.0)
    if full is None:
        raise CliError("The sweep needs a 100% power run to compare against.")
    if full.energy_mj <= 0 or full.seconds <= 0:
        raise GpuError("No energy was measured at full power, so the sweep cannot be computed.")
    return {
        str(level): {
            "tau": full.seconds / result.seconds,
            "eps": result.energy_mj / full.energy_mj,
        }
        for level, result in sorted(results.items(), reverse=True)
    }


def gate_failures(levels: Mapping[str, Mapping[str, float]]) -> tuple[str, ...]:
    """Sanity gates (4.5.f): 0.7 <= tau_85 <= 1.0, 0.6 <= eps_85 <= 1.05, tau_70 <= tau_85."""
    t85, e85, t70 = levels["0.85"]["tau"], levels["0.85"]["eps"], levels["0.7"]["tau"]
    failures = []
    if not 0.7 <= t85 <= 1.0:
        failures.append(f"tau at 85% is {t85:.3f}; expected between 0.7 and 1.0.")
    if not 0.6 <= e85 <= 1.05:
        failures.append(f"eps at 85% is {e85:.3f}; expected between 0.6 and 1.05.")
    if t70 > t85:
        failures.append(f"tau at 70% ({t70:.3f}) is higher than at 85% ({t85:.3f}).")
    return tuple(failures)


def parse_levels(text: str) -> tuple[float, ...]:
    """'100,85,70' -> (1.0, 0.85, 0.7). Must include 100."""
    try:
        values = [float(part) / 100 for part in text.split(",")]
    except ValueError:
        raise CliError("--levels must be percentages such as 100,85,70.") from None
    if not values or any(not 0 < v <= 1 for v in values) or len(set(values)) != len(values):
        raise CliError("--levels must be distinct percentages above 0 and at most 100.")
    if 1.0 not in values:
        raise CliError("--levels must include 100 (the full-power run to compare against).")
    return tuple(values)


# ------------------------------------------------------------ measuring


class _EnergyProbe:
    """Total GPU energy in mJ, from the NVML counters of the swept GPUs."""

    def __init__(self, api: NvmlApi, indices: Sequence[int]) -> None:
        self._api = api
        self._indices = tuple(indices)

    def read_mj(self) -> float:
        try:
            return float(sum(self._api.total_energy_mj(i) for i in self._indices))
        except EnergyCounterUnsupported:
            raise GpuError(
                "This GPU has no energy counter (it is older than Volta), "
                "so the sweep cannot measure energy."
            ) from None


@dataclass(frozen=True)
class _Plan:
    steps: int
    warmup: int
    settle_s: float


def _measure_level(
    level: float,
    probe: _EnergyProbe,
    workload: Workload,
    cap_factory: Callable[[], PowerCap],
    clock: Callable[[], float],
    sleep: Callable[[float], Any],
    plan: _Plan,
) -> LevelResult:
    with cap_factory() as cap:
        if not cap.apply(level):
            raise GpuError(
                f"Could not set the {round(level * 100)}% power cap, so the sweep cannot run. "
                "Run as root, or allow `sudo -n nvidia-smi` (see the lab setup notes)."
            )
        sleep(plan.settle_s)
        workload.warmup(plan.warmup)
        before, started = probe.read_mj(), clock()
        workload.run(plan.steps)
        seconds, after = clock() - started, probe.read_mj()
    return LevelResult(seconds=seconds, energy_mj=after - before)


def _measure_idle(
    probe: _EnergyProbe, workload: Workload, clock: Callable[[], float], seconds: float
) -> float:
    before, started = probe.read_mj(), clock()
    workload.idle(seconds)
    elapsed, after = clock() - started, probe.read_mj()
    return (after - before) / 1000.0 / max(elapsed, 1e-9)  # mJ -> J, then W (all swept GPUs)


def run_sweep(
    api: NvmlApi,
    indices: Sequence[int],
    gpu: GpuModel,
    workload: Workload,
    *,
    levels: Sequence[float] = DEFAULT_LEVELS,
    steps: int = DEFAULT_STEPS,
    warmup: int = DEFAULT_WARMUP,
    idle_seconds: float = DEFAULT_IDLE_S,
    settle_seconds: float = DEFAULT_SETTLE_S,
    smi: SmiRunner = run_command,
    mono: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Any] = time.sleep,
    now: Callable[[], datetime] = lambda: datetime.now(IST),
) -> SweepResult:
    """Run the sweep on the given GPUs (one model). Restores the cap after every level."""
    probe = _EnergyProbe(api, indices)
    probe.read_mj()  # fail early, in plain words, if there is no energy counter
    plan = _Plan(steps, warmup, settle_seconds)

    def cap_factory() -> PowerCap:
        return PowerCap(api, tuple(indices), smi=smi, sleep=sleep)

    results = {
        level: _measure_level(level, probe, workload, cap_factory, mono, sleep, plan)
        for level in sorted(levels, reverse=True)
    }
    idle_w = _measure_idle(probe, workload, mono, idle_seconds) / len(indices)
    computed = compute_levels(results)
    full = results[1.0]
    avg_w = full.energy_mj / 1000.0 / full.seconds / len(indices)
    entry = {
        "gpu_name": api.name(indices[0]),
        "driver": api.driver_version(),
        "measured_at": now().astimezone(IST).isoformat(timespec="minutes"),
        "workload": WORKLOAD_TEXT.format(warmup=warmup, steps=steps),
        "steps": steps,
        "levels": computed,
        "u": avg_w / gpu.p_max_w,
        "p_idle_w": idle_w,
        "runs": 1,
        "raw": [_raw(level, result, steps, len(indices)) for level, result in results.items()],
    }
    return SweepResult(entry, gate_failures(computed) if {"0.85", "0.7"} <= set(computed) else ())


def _raw(level: float, result: LevelResult, steps: int, gpu_count: int) -> dict[str, Any]:
    return {
        "level": level,
        "seconds": result.seconds,
        "energy_mj": result.energy_mj,
        "avg_power_w": result.energy_mj / 1000.0 / result.seconds / gpu_count,
        "steps": steps,
    }


# ------------------------------------------------------------ the output file


def merge_sweep(
    existing: Mapping[str, Any], gpu_id: str, entry: Mapping[str, Any]
) -> dict[str, Any]:
    """A new document where this GPU's entry is replaced and the other GPUs are kept."""
    gpus = {**(existing.get("gpus") or {}), gpu_id: dict(entry)}
    return {**existing, "gpus": gpus}


def _read_existing(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"gpus": {}}
    except (OSError, ValueError):
        raise CliError(
            f"{path} is not valid JSON. Fix or delete it, then run the sweep again."
        ) from None
    if not isinstance(data, dict):
        raise CliError(f"{path} is not valid: expected a JSON object.")
    return data


def write_result(path: Path, gpu_id: str, entry: Mapping[str, Any]) -> None:
    """Merge ``entry`` into the sweep file and write it atomically."""
    merged = merge_sweep(_read_existing(path), gpu_id, entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(merged, indent=2, sort_keys=True, allow_nan=False) + "\n")
        os.replace(temp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temp_name)
        raise


# ------------------------------------------------------------ the real workload (needs the GPU box)


class TorchResnetWorkload:
    """ResNet-18 on random 128x3x32x32 tensors, SGD (TRD 6.4). Needs torch and a CUDA GPU."""

    def __init__(self, device_index: int = 0) -> None:
        try:
            import torch
            import torchvision
        except ImportError:
            raise GpuError(
                'The sweep needs PyTorch. Run: pip install "thirst[sweep]" '
                "(or: pip install torch torchvision)"
            ) from None
        if not torch.cuda.is_available():
            raise GpuError("PyTorch cannot see a CUDA GPU, so the sweep cannot run.")
        self._torch = torch
        device = torch.device("cuda", device_index)
        self._model = torchvision.models.resnet18(num_classes=10).to(device)
        self._optimizer = torch.optim.SGD(self._model.parameters(), lr=0.01, momentum=0.9)
        self._inputs = torch.randn(128, 3, 32, 32, device=device)
        self._labels = torch.randint(0, 10, (128,), device=device)

    def _step(self) -> None:
        torch = self._torch
        self._optimizer.zero_grad(set_to_none=True)
        loss = torch.nn.functional.cross_entropy(self._model(self._inputs), self._labels)
        loss.backward()
        self._optimizer.step()

    def warmup(self, steps: int) -> None:
        for _ in range(steps):
            self._step()
        self._torch.cuda.synchronize()

    def run(self, steps: int) -> None:
        self._torch.cuda.synchronize()
        for _ in range(steps):
            self._step()
        self._torch.cuda.synchronize()

    def idle(self, seconds: float) -> None:
        self._torch.cuda.synchronize()
        time.sleep(seconds)
