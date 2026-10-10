"""Shared setup for the commands: the API client and finding out which GPUs the job uses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from . import config
from .context import ApiClient, Context
from .errors import CliError, GpuError
from .gpus import GpuModel, child_environment, resolve_model, select_gpu_indices
from .nvml import NvmlApi


def load_client(ctx: Context) -> tuple[config.Config, ApiClient]:
    """The saved config and an API client for it (``ConfigError`` if not registered)."""
    cfg = config.load(ctx.env)
    return cfg, ctx.make_client(cfg.api_url, cfg.token, cfg.site_id)


def web_url(env: Mapping[str, str]) -> str:
    return env.get("THIRST_WEB_URL", config.DEFAULT_WEB_URL)


@dataclass(frozen=True)
class JobGpus:
    """The GPU model and count for a job. ``api`` is open only if NVML was needed."""

    model: GpuModel
    count: int
    api: NvmlApi | None
    indices: tuple[int, ...]


_FLAGS_HINT = " Or tell Thirst yourself with --gpu-model and --gpus."


def _flag_model(gpu_model: str | None) -> str | None:
    return None if gpu_model in (None, "", "auto") else gpu_model


def _modelled_gpus(gpu_model: str | None, gpus: int | None) -> JobGpus:
    override = _flag_model(gpu_model)
    if override is None or gpus is None:
        raise CliError("--modelled needs --gpu-model and --gpus, because there is no GPU to ask.")
    return JobGpus(resolve_model([], override), gpus, None, ())


def detect_gpus(
    ctx: Context,
    *,
    gpu_model: str | None,
    gpus: int | None,
    need_hardware: bool,
    modelled: bool = False,
) -> JobGpus:
    """Work out the GPU model and count from the flags, asking NVML only when needed.

    With ``need_hardware`` the returned ``api`` stays open (the caller closes it); otherwise NVML
    is closed again before this returns.
    """
    if modelled:
        return _modelled_gpus(gpu_model, gpus)
    override = _flag_model(gpu_model)
    if not need_hardware and override is not None and gpus is not None:
        return JobGpus(resolve_model([], override), gpus, None, ())
    try:
        api = ctx.open_nvml()
    except GpuError as err:
        hint = "" if need_hardware else _FLAGS_HINT
        raise GpuError(err.message + hint) from None
    try:
        found = _read_job_gpus(api, ctx.env, override, gpus, need_hardware)
    except BaseException:
        api.shutdown()
        raise
    if not need_hardware:
        api.shutdown()
        return JobGpus(found.model, found.count, None, found.indices)
    return found


def _read_job_gpus(
    api: NvmlApi,
    env: Mapping[str, str],
    override: str | None,
    gpus: int | None,
    need_hardware: bool,
) -> JobGpus:
    indices = select_gpu_indices(api, child_environment(env))
    model = resolve_model([api.name(i) for i in indices], override)
    if gpus is not None and need_hardware and gpus != len(indices):
        raise CliError(
            f"--gpus {gpus} does not match the {len(indices)} GPU(s) this job can see. "
            "Drop --gpus (the CLI counts them), or change CUDA_VISIBLE_DEVICES."
        )
    return JobGpus(model, gpus if gpus is not None else len(indices), api, indices)
