"""GPU models and GPU selection (plan 04.3 test 6, decision D25, contract 08 §2.2).

CUDA's default device order (fastest first) is not NVML's order (PCI bus). The runner starts the
child with ``CUDA_DEVICE_ORDER=PCI_BUS_ID`` unless the user chose another order, and this module
maps ``CUDA_VISIBLE_DEVICES`` entries (indices or ``GPU-`` UUIDs) to NVML indices by UUID.
"""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .errors import CliError, GpuError
from .nvml import NvmlApi

VISIBLE_VAR = "CUDA_VISIBLE_DEVICES"
ORDER_VAR = "CUDA_DEVICE_ORDER"
PCI_ORDER = "PCI_BUS_ID"
DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class GpuModel:
    id: str
    label: str
    p_max_w: float
    p_idle_w: float
    patterns: tuple[str, ...]


@functools.lru_cache(maxsize=1)
def load_gpu_models() -> tuple[GpuModel, ...]:
    """The GPU models bundled with the CLI (a copy of the engine's gpus.json)."""
    raw = json.loads((DATA_DIR / "gpus.json").read_text(encoding="utf-8"))
    return tuple(
        GpuModel(
            id=item["id"],
            label=item["label"],
            p_max_w=float(item["p_max_w"]),
            p_idle_w=float(item["p_idle_w"]),
            patterns=tuple(item["nvml_name_patterns"]),
        )
        for item in raw["models"]
    )


def _known_ids() -> str:
    return ", ".join(m.id for m in load_gpu_models())


def _contains_word(name: str, pattern: str) -> bool:
    """Case-insensitive match that does not stop in the middle of a word ('L4' is not 'L40S')."""
    regex = r"(?<![A-Za-z0-9])" + re.escape(pattern) + r"(?![A-Za-z0-9])"
    return re.search(regex, name, re.IGNORECASE) is not None


def match_model(name: str) -> GpuModel:
    """Map an NVML device name to a model id; the longest matching pattern wins."""
    best: tuple[int, GpuModel] | None = None
    for model in load_gpu_models():
        for pattern in model.patterns:
            if _contains_word(name, pattern) and (best is None or len(pattern) > best[0]):
                best = (len(pattern), model)
    if best is None:
        raise CliError(
            f"Thirst does not know the GPU '{name}' yet. "
            f"Pick one with --gpu-model. Known models: {_known_ids()}."
        )
    return best[1]


def resolve_model(names: Sequence[str], override: str | None) -> GpuModel:
    """The one model for all measured GPUs, or the one the user named with ``--gpu-model``."""
    if override is not None:
        for model in load_gpu_models():
            if model.id == override:
                return model
        raise CliError(f"'{override}' is not a known GPU model. Known models: {_known_ids()}.")
    models = {match_model(name).id: match_model(name) for name in names}
    if len(models) > 1:
        raise CliError(
            "This machine has different GPU models "
            f"({', '.join(sorted(models))}). Run one model at a time with CUDA_VISIBLE_DEVICES, "
            "or pass --gpu-model."
        )
    return next(iter(models.values()))


def child_environment(base: Mapping[str, str]) -> dict[str, str]:
    """A copy of the environment for the user's command (never changes ``base``)."""
    env = dict(base)
    env.setdefault(ORDER_VAR, PCI_ORDER)
    env.setdefault("PYTHONUNBUFFERED", "1")  # so tee'd output appears as the job prints it
    return env


def _by_uuid(api: NvmlApi, token: str) -> int:
    if token.startswith("MIG-"):
        raise GpuError("MIG devices in CUDA_VISIBLE_DEVICES are not supported yet.")
    matches = [i for i in range(api.device_count()) if api.uuid(i).startswith(token)]
    if len(matches) != 1:
        raise GpuError(
            f"CUDA_VISIBLE_DEVICES lists {token}, which matches "
            f"{'no GPU' if not matches else 'more than one GPU'} on this machine."
        )
    return matches[0]


def _by_index(api: NvmlApi, token: str, env: Mapping[str, str]) -> int:
    if env.get(ORDER_VAR) != PCI_ORDER:
        raise GpuError(
            f"CUDA_VISIBLE_DEVICES uses GPU numbers, but {ORDER_VAR} is not {PCI_ORDER}, "
            f"so the numbers may not match NVML. Set {ORDER_VAR}={PCI_ORDER} or use GPU- ids."
        )
    index = int(token)
    if index >= api.device_count():
        raise GpuError(
            f"CUDA_VISIBLE_DEVICES lists GPU {index}, but this machine has "
            f"{api.device_count()} GPU(s)."
        )
    return index


def select_gpu_indices(api: NvmlApi, env: Mapping[str, str]) -> tuple[int, ...]:
    """NVML indices of the GPUs the job can see. Without the variable, all GPUs."""
    if VISIBLE_VAR not in env:
        return tuple(range(api.device_count()))
    raw = env[VISIBLE_VAR].strip()
    if not raw:
        raise GpuError("CUDA_VISIBLE_DEVICES is empty, so the job would see no GPU.")
    chosen: list[int] = []
    for token in (part.strip() for part in raw.split(",")):
        if token.startswith(("GPU-", "MIG-")):
            index = _by_uuid(api, token)
        elif token.isdigit():
            index = _by_index(api, token, env)
        else:
            raise GpuError(f"Could not understand '{token}' in CUDA_VISIBLE_DEVICES.")
        if index not in chosen:
            chosen.append(index)
    return tuple(chosen)
