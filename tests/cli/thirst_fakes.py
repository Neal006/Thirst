"""Test doubles shared by the CLI tests: a fake NVML, a fake clock, a fake `nvidia-smi` runner.

Loaded through ``tests/cli/conftest.py`` (test modules cannot import each other).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from thirst.errors import GpuError
from thirst.nvml import EnergyCounterUnsupported, LimitNotSupported, LimitPermissionDenied

IST = timezone(timedelta(hours=5, minutes=30))


def ist(text: str) -> datetime:
    """``ist("2026-10-10 01:59:30")`` as an IST-aware datetime."""
    return datetime.fromisoformat(text).replace(tzinfo=IST)


class FakeClock:
    """Wall (IST) and monotonic clocks that only move when the test says so."""

    def __init__(self, start: str = "2026-10-10 01:00:00") -> None:
        self._wall = ist(start)
        self._mono = 1000.0

    def wall(self) -> datetime:
        return self._wall

    def mono(self) -> float:
        return self._mono

    def advance(self, seconds: float) -> None:
        self._wall += timedelta(seconds=seconds)
        self._mono += seconds

    def jump_wall(self, seconds: float) -> None:
        """The wall clock moves but the monotonic clock does not (suspend, NTP step)."""
        self._wall += timedelta(seconds=seconds)

    def sleep(self, seconds: float) -> None:
        self.advance(seconds)


@dataclass
class FakeGpu:
    uuid: str
    name: str = "NVIDIA GeForce RTX 4090"
    energy_mj: int | None = 0  # None = no energy counter
    power_mw: int = 200_000
    min_limit_mw: int = 100_000
    default_limit_mw: int = 450_000
    max_limit_mw: int = 450_000
    current_limit_mw: int = 450_000
    max_clock_mhz: int = 2520


@dataclass
class FakeNvml:
    """An ``NvmlApi`` with mutable devices. NVML order here is PCI bus order."""

    gpus: list[FakeGpu] = field(default_factory=lambda: [FakeGpu("GPU-aaaa"), FakeGpu("GPU-bbbb")])
    driver: str = "550.54"
    permission_denied: bool = False
    limit_unsupported: bool = False
    set_failures_left: int = 0
    set_calls: list[tuple[int, int]] = field(default_factory=list)
    shutdowns: int = 0

    def device_count(self) -> int:
        return len(self.gpus)

    def uuid(self, index: int) -> str:
        return self.gpus[index].uuid

    def name(self, index: int) -> str:
        return self.gpus[index].name

    def driver_version(self) -> str:
        return self.driver

    def total_energy_mj(self, index: int) -> int:
        value = self.gpus[index].energy_mj
        if value is None:
            raise EnergyCounterUnsupported
        return value

    def power_mw(self, index: int) -> int:
        return self.gpus[index].power_mw

    def limit_constraints_mw(self, index: int) -> tuple[int, int]:
        return self.gpus[index].min_limit_mw, self.gpus[index].max_limit_mw

    def default_limit_mw(self, index: int) -> int:
        return self.gpus[index].default_limit_mw

    def current_limit_mw(self, index: int) -> int:
        return self.gpus[index].current_limit_mw

    def set_limit_mw(self, index: int, milliwatts: int) -> None:
        if self.permission_denied:
            raise LimitPermissionDenied
        if self.limit_unsupported:
            raise LimitNotSupported
        if self.set_failures_left > 0:
            self.set_failures_left -= 1
            raise GpuError("fake NVML failure")
        self.set_calls.append((index, milliwatts))
        self.gpus[index].current_limit_mw = milliwatts

    def max_graphics_clock_mhz(self, index: int) -> int:
        return self.gpus[index].max_clock_mhz

    def shutdown(self) -> None:
        self.shutdowns += 1


@dataclass
class FakeSmi:
    """Stands in for ``subprocess.run`` of `nvidia-smi` / `sudo`. Records every argv."""

    returncode: int = 0
    calls: list[list[str]] = field(default_factory=list)
    fail_when: str | None = None  # a substring of the joined argv that makes the call fail

    def __call__(self, argv: list[str]) -> int:
        self.calls.append(list(argv))
        if self.fail_when is not None and self.fail_when in " ".join(argv):
            return 1
        return self.returncode


class FakeChild:
    """A child process that exits by itself after ``exit_after_s`` of (monotonic) run time."""

    def __init__(
        self,
        clock: FakeClock,
        exit_after_s: float | None = None,
        exit_code: int = 0,
        ignore_term: bool = False,
    ) -> None:
        self.clock = clock
        self.exit_after_s = exit_after_s
        self.exit_code = exit_code
        self.ignore_term = ignore_term
        self.calls: list[str] = []
        self.paused = False
        self.finished: int | None = None
        self._born = clock.mono()

    def poll(self) -> int | None:
        if self.finished is not None:
            return self.finished
        if self.paused or self.exit_after_s is None:
            return None
        if self.clock.mono() - self._born >= self.exit_after_s:
            self.finished = self.exit_code
        return self.finished

    def pause(self) -> None:
        self.calls.append("pause")
        self.paused = True

    def resume(self) -> None:
        self.calls.append("resume")
        self.paused = False

    def terminate(self) -> None:
        self.calls.append("terminate")
        if not self.ignore_term and not self.paused:
            self.finished = -15

    def kill(self) -> None:
        self.calls.append("kill")
        self.finished = -9

    def wait(self, timeout: float) -> int | None:
        self.calls.append(f"wait:{timeout:g}")
        return self.finished


class FakeSpawn:
    """Stands in for the function that starts the user's command."""

    def __init__(self, child: FakeChild | None = None, error: Exception | None = None) -> None:
        self.child = child
        self.error = error
        self.argv: list[str] | None = None
        self.env: dict[str, str] | None = None

    def __call__(self, argv: list[str], env: dict[str, str], log_path: object) -> FakeChild:
        self.argv, self.env = list(argv), dict(env)
        if self.error is not None:
            raise self.error
        assert self.child is not None
        return self.child


class FakeCap:
    """A power-cap controller that only records what it was asked."""

    def __init__(self, log: list[str] | None = None, apply_result: bool = True) -> None:
        self.log = log if log is not None else []
        self.apply_result = apply_result
        self.applies: list[float] = []
        self.restores = 0
        self.applied = False
        self.cap_method = "none"
        self.notes: tuple[str, ...] = ()

    def apply(self, level: float) -> bool:
        self.log.append(f"cap_apply:{level}")
        self.applies.append(level)
        self.applied = self.apply_result
        self.cap_method = "nvml" if self.apply_result else "none"
        return self.apply_result

    def restore(self) -> tuple[str, ...]:
        self.log.append("cap_restore")
        self.restores += 1
        self.applied = False
        return ()


class RecordingGuard:
    """Stands in for the signal-handler guard; records when it is entered and left."""

    def __init__(self, log: list[str]) -> None:
        self.log = log

    def __enter__(self) -> RecordingGuard:
        self.log.append("guard_enter")
        return self

    def __exit__(self, *exc: object) -> None:
        self.log.append("guard_exit")
