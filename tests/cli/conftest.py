"""Shared fixtures for the CLI tests."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import thirst_fakes  # noqa: E402
import thirst_rig  # noqa: E402


@pytest.fixture
def clock() -> thirst_fakes.FakeClock:
    return thirst_fakes.FakeClock()


@pytest.fixture
def nvml_api() -> thirst_fakes.FakeNvml:
    return thirst_fakes.FakeNvml()


@pytest.fixture
def smi() -> thirst_fakes.FakeSmi:
    return thirst_fakes.FakeSmi()


@pytest.fixture(autouse=True)
def thirst_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Every CLI test gets its own state folder; the real ~/.thirst is never touched."""
    target = tmp_path / "thirst-home"
    monkeypatch.setenv("THIRST_HOME", str(target))
    for name in ("THIRST_API_URL", "THIRST_TOKEN", "CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER"):
        monkeypatch.delenv(name, raising=False)
    yield target


@pytest.fixture
def rig(thirst_home: Path) -> thirst_rig.CliRig:
    return thirst_rig.CliRig(thirst_home)
