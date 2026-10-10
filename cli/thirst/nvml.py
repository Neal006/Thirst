"""The one place that talks to NVML (the `nvidia-ml-py` package, imported as ``pynvml``).

Everything else in the CLI uses the ``NvmlApi`` protocol, so tests inject a fake and the code
never needs a GPU. Real calls need an NVIDIA driver, and are listed as "needs the GPU box".
All NVML failures are turned into ``GpuError`` with plain words, never a stack trace.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Protocol

from .errors import GpuError

logger = logging.getLogger(__name__)

_NO_DRIVER_CODES = (1, 9, 12)  # uninitialised, driver not loaded, library not found
_NO_GPU = (
    "No NVIDIA GPU was found on this machine. "
    "Use `--modelled` to estimate energy without a GPU (it is tagged Modelled)."
)
_NO_DRIVER = (
    "Could not talk to the NVIDIA driver. Check that the driver is installed "
    "and that `nvidia-smi` works."
)
_NO_PACKAGE = "The `nvidia-ml-py` package is not installed. Run: pip install nvidia-ml-py"
_NVML_FAILED = "The NVIDIA driver reported an error while reading the GPU. Run `nvidia-smi`."


class EnergyCounterUnsupported(Exception):
    """This GPU has no total-energy counter (before Volta). Fall back to power integration."""


class LimitPermissionDenied(Exception):
    """Setting the power limit needs root (NVML_ERROR_NO_PERMISSION)."""


class LimitNotSupported(Exception):
    """This GPU or driver does not allow changing the power limit."""


class NvmlApi(Protocol):
    """What the meter and the power-cap controller need from NVML. Index = NVML (PCI) order."""

    def device_count(self) -> int: ...
    def uuid(self, index: int) -> str: ...
    def name(self, index: int) -> str: ...
    def driver_version(self) -> str: ...
    def total_energy_mj(self, index: int) -> int: ...
    def power_mw(self, index: int) -> int: ...
    def limit_constraints_mw(self, index: int) -> tuple[int, int]: ...
    def default_limit_mw(self, index: int) -> int: ...
    def current_limit_mw(self, index: int) -> int: ...
    def set_limit_mw(self, index: int, milliwatts: int) -> None: ...
    def max_graphics_clock_mhz(self, index: int) -> int: ...
    def shutdown(self) -> None: ...


def _text(value: Any) -> str:
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)


class PynvmlApi:
    """``NvmlApi`` on top of an initialised ``pynvml`` module."""

    def __init__(self, module: Any) -> None:
        self._nv = module
        self._handles: dict[int, Any] = {}
        self._closed = False

    def _handle(self, index: int) -> Any:
        if index not in self._handles:
            self._handles[index] = self._call(self._nv.nvmlDeviceGetHandleByIndex, index)
        return self._handles[index]

    def _code(self, exc: Exception) -> int | None:
        value = getattr(exc, "value", None)
        return value if isinstance(value, int) else None

    def _call(self, func: Any, *args: Any) -> Any:
        try:
            return func(*args)
        except self._nv.NVMLError as exc:
            logger.debug("NVML call %s failed with code %s", func.__name__, self._code(exc))
            raise GpuError(_NVML_FAILED) from None

    def device_count(self) -> int:
        return int(self._call(self._nv.nvmlDeviceGetCount))

    def uuid(self, index: int) -> str:
        return _text(self._call(self._nv.nvmlDeviceGetUUID, self._handle(index)))

    def name(self, index: int) -> str:
        return _text(self._call(self._nv.nvmlDeviceGetName, self._handle(index)))

    def driver_version(self) -> str:
        return _text(self._call(self._nv.nvmlSystemGetDriverVersion))

    def total_energy_mj(self, index: int) -> int:
        try:
            return int(self._nv.nvmlDeviceGetTotalEnergyConsumption(self._handle(index)))
        except self._nv.NVMLError as exc:
            if self._code(exc) == self._nv.NVML_ERROR_NOT_SUPPORTED:
                raise EnergyCounterUnsupported from None
            raise GpuError(_NVML_FAILED) from None

    def power_mw(self, index: int) -> int:
        return int(self._call(self._nv.nvmlDeviceGetPowerUsage, self._handle(index)))

    def limit_constraints_mw(self, index: int) -> tuple[int, int]:
        low, high = self._call(
            self._nv.nvmlDeviceGetPowerManagementLimitConstraints, self._handle(index)
        )
        return int(low), int(high)

    def default_limit_mw(self, index: int) -> int:
        return int(
            self._call(self._nv.nvmlDeviceGetPowerManagementDefaultLimit, self._handle(index))
        )

    def current_limit_mw(self, index: int) -> int:
        return int(self._call(self._nv.nvmlDeviceGetPowerManagementLimit, self._handle(index)))

    def set_limit_mw(self, index: int, milliwatts: int) -> None:
        try:
            self._nv.nvmlDeviceSetPowerManagementLimit(self._handle(index), int(milliwatts))
        except self._nv.NVMLError as exc:
            code = self._code(exc)
            if code == self._nv.NVML_ERROR_NO_PERMISSION:
                raise LimitPermissionDenied from None
            if code == self._nv.NVML_ERROR_NOT_SUPPORTED:
                raise LimitNotSupported from None
            raise GpuError(_NVML_FAILED) from None

    def max_graphics_clock_mhz(self, index: int) -> int:
        clock = self._nv.NVML_CLOCK_GRAPHICS
        return int(self._call(self._nv.nvmlDeviceGetMaxClockInfo, self._handle(index), clock))

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._nv.nvmlShutdown()
        except self._nv.NVMLError:
            logger.debug("nvmlShutdown failed; ignored")


def open_nvml() -> PynvmlApi:
    """Initialise NVML and return the adapter. Raises ``GpuError`` if there is no usable GPU."""
    try:
        module = importlib.import_module("pynvml")
    except ImportError:
        raise GpuError(_NO_PACKAGE) from None
    try:
        module.nvmlInit()
    except module.NVMLError as exc:
        code = getattr(exc, "value", None)
        raise GpuError(_NO_DRIVER if code in _NO_DRIVER_CODES else _NVML_FAILED) from None
    api = PynvmlApi(module)
    try:
        count = api.device_count()
    except GpuError:
        api.shutdown()
        raise
    if count < 1:
        api.shutdown()
        raise GpuError(_NO_GPU)
    return api
