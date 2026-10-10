"""The real NVML adapter, driven through a fake ``pynvml`` module injected via sys.modules."""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest
from thirst import nvml
from thirst.errors import GpuError

NOT_SUPPORTED = 3
NO_PERMISSION = 4
UNINITIALIZED = 1
DRIVER_NOT_LOADED = 9
LIBRARY_NOT_FOUND = 12


class FakeNvmlError(Exception):
    def __init__(self, value: int) -> None:
        super().__init__(f"nvml error {value}")
        self.value = value


def make_fake_module(
    *, devices: int = 2, energy_error: int | None = None, init_error: int | None = None
) -> types.ModuleType:
    module = types.ModuleType("pynvml")
    state: dict[str, Any] = {"limits": {0: 300_000, 1: 250_000}, "shutdowns": 0, "set": []}
    module.state = state  # type: ignore[attr-defined]
    module.NVMLError = FakeNvmlError  # type: ignore[attr-defined]
    module.NVML_ERROR_NOT_SUPPORTED = NOT_SUPPORTED  # type: ignore[attr-defined]
    module.NVML_ERROR_NO_PERMISSION = NO_PERMISSION  # type: ignore[attr-defined]
    module.NVML_CLOCK_GRAPHICS = 0  # type: ignore[attr-defined]

    def init() -> None:
        if init_error is not None:
            raise FakeNvmlError(init_error)

    def handle(index: int) -> int:
        if not 0 <= index < devices:
            raise FakeNvmlError(2)
        return index

    def energy(h: int) -> int:
        if energy_error is not None:
            raise FakeNvmlError(energy_error)
        return 1000 * (h + 1)

    def set_limit(h: int, mw: int) -> None:
        if state.get("set_error"):
            raise FakeNvmlError(state["set_error"])
        state["set"].append((h, mw))
        state["limits"][h] = mw

    def shutdown() -> None:
        state["shutdowns"] += 1

    module.nvmlInit = init  # type: ignore[attr-defined]
    module.nvmlShutdown = shutdown  # type: ignore[attr-defined]
    module.nvmlDeviceGetCount = lambda: devices  # type: ignore[attr-defined]
    module.nvmlDeviceGetHandleByIndex = handle  # type: ignore[attr-defined]
    module.nvmlDeviceGetUUID = lambda h: f"GPU-uuid-{h}"  # type: ignore[attr-defined]
    module.nvmlDeviceGetName = lambda h: b"NVIDIA GeForce RTX 4090"  # type: ignore[attr-defined]
    module.nvmlSystemGetDriverVersion = lambda: "550.54"  # type: ignore[attr-defined]
    module.nvmlDeviceGetTotalEnergyConsumption = energy  # type: ignore[attr-defined]
    module.nvmlDeviceGetPowerUsage = lambda h: 123_000 + h  # type: ignore[attr-defined]
    module.nvmlDeviceGetPowerManagementLimitConstraints = lambda h: (100_000, 450_000)  # type: ignore[attr-defined]
    module.nvmlDeviceGetPowerManagementDefaultLimit = lambda h: 450_000  # type: ignore[attr-defined]
    module.nvmlDeviceGetPowerManagementLimit = lambda h: state["limits"][h]  # type: ignore[attr-defined]
    module.nvmlDeviceSetPowerManagementLimit = set_limit  # type: ignore[attr-defined]
    module.nvmlDeviceGetMaxClockInfo = lambda h, kind: 2520  # type: ignore[attr-defined]
    return module


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    module = make_fake_module()
    monkeypatch.setitem(sys.modules, "pynvml", module)
    return module


def test_reads_identity_and_values(fake: types.ModuleType) -> None:
    api = nvml.open_nvml()

    assert api.device_count() == 2
    assert api.uuid(1) == "GPU-uuid-1"
    assert api.name(0) == "NVIDIA GeForce RTX 4090"  # bytes decoded
    assert api.driver_version() == "550.54"
    assert api.total_energy_mj(1) == 2000
    assert api.power_mw(0) == 123_000


def test_reads_power_limits(fake: types.ModuleType) -> None:
    api = nvml.open_nvml()

    assert api.limit_constraints_mw(0) == (100_000, 450_000)
    assert api.default_limit_mw(0) == 450_000
    assert api.current_limit_mw(1) == 250_000
    assert api.max_graphics_clock_mhz(0) == 2520


def test_set_limit_calls_nvml(fake: types.ModuleType) -> None:
    api = nvml.open_nvml()

    api.set_limit_mw(0, 380_000)

    assert fake.state["set"] == [(0, 380_000)]  # type: ignore[attr-defined]


def test_no_permission_has_its_own_error(fake: types.ModuleType) -> None:
    fake.state["set_error"] = NO_PERMISSION  # type: ignore[attr-defined]
    api = nvml.open_nvml()

    with pytest.raises(nvml.LimitPermissionDenied):
        api.set_limit_mw(0, 380_000)


def test_not_supported_limit_has_its_own_error(fake: types.ModuleType) -> None:
    fake.state["set_error"] = NOT_SUPPORTED  # type: ignore[attr-defined]
    api = nvml.open_nvml()

    with pytest.raises(nvml.LimitNotSupported):
        api.set_limit_mw(0, 380_000)


def test_missing_energy_counter_is_a_distinct_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pynvml", make_fake_module(energy_error=NOT_SUPPORTED))
    api = nvml.open_nvml()

    with pytest.raises(nvml.EnergyCounterUnsupported):
        api.total_energy_mj(0)


def test_other_nvml_failures_become_plain_gpu_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pynvml", make_fake_module(energy_error=999))
    api = nvml.open_nvml()

    with pytest.raises(GpuError) as err:
        api.total_energy_mj(0)

    assert "NVIDIA" in err.value.message
    assert err.value.exit_code == 5


def test_shutdown_is_called_once_even_if_closed_twice(fake: types.ModuleType) -> None:
    api = nvml.open_nvml()

    api.shutdown()
    api.shutdown()

    assert fake.state["shutdowns"] == 1  # type: ignore[attr-defined]


def test_no_gpu_raises_a_plain_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pynvml", make_fake_module(devices=0))

    with pytest.raises(GpuError) as err:
        nvml.open_nvml()

    assert "No NVIDIA GPU" in err.value.message
    assert "--modelled" in err.value.message


@pytest.mark.parametrize("code", [DRIVER_NOT_LOADED, LIBRARY_NOT_FOUND, UNINITIALIZED])
def test_missing_driver_raises_a_plain_error(monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    monkeypatch.setitem(sys.modules, "pynvml", make_fake_module(init_error=code))

    with pytest.raises(GpuError) as err:
        nvml.open_nvml()

    assert "driver" in err.value.message.lower()
    assert "Traceback" not in err.value.message


def test_missing_python_package_raises_a_plain_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pynvml", None)  # makes `import pynvml` fail

    with pytest.raises(GpuError) as err:
        nvml.open_nvml()

    assert "nvidia-ml-py" in err.value.message
