"""Power cap with guaranteed restore (plan 04.4, TRD 6.2).

``PowerCap`` sets ``level x default limit`` (clamped to the GPU's allowed range) and puts the
ORIGINAL limit back on every exit path: normal exit, exceptions, SIGINT, SIGTERM and ``atexit``.
Before the first change it writes ``~/.thirst/restore.json`` (``{gpu_uuid: original_mW}``) so that
``thirst doctor --restore`` can undo a cap after ``kill -9`` or a power cut.

When NVML says "no permission" it tries ``sudo -n nvidia-smi``; if that fails too the job goes on
uncapped (``applied`` is False). When the GPU does not support power limits, or ``fallback_clocks``
is set, it locks the graphics clock instead (``nvidia-smi -lgc``) and resets it with ``-rgc``.
Every subprocess gets an argument list; there is never a shell.
"""

from __future__ import annotations

import atexit
import json
import logging
import math
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import FrameType, TracebackType
from typing import Any

from . import config
from .errors import GpuError
from .nvml import LimitNotSupported, LimitPermissionDenied, NvmlApi

logger = logging.getLogger(__name__)

__all__ = [
    "LimitNotSupported",
    "LimitPermissionDenied",
    "PowerCap",
    "RecoveryResult",
    "marker_present",
    "recover_from_marker",
    "run_command",
]

RESTORE_ATTEMPTS = 3
RESTORE_PAUSE_S = 0.5
COMMAND_TIMEOUT_S = 15
MIN_LOCK_MHZ = 210  # typical lowest graphics clock; the lock is [210, level x max clock]
CLOCK_KEY = "_clock_locked"

SmiRunner = Callable[[list[str]], int]
Sleeper = Callable[[float], None]


def run_command(argv: list[str]) -> int:
    """Run ``argv`` (no shell); exit code, or 124 (timeout), 126 (OS error), 127 (not found)."""
    try:
        done = subprocess.run(  # noqa: S603 - fixed argument list, never a shell
            argv, capture_output=True, timeout=COMMAND_TIMEOUT_S, check=False
        )
    except FileNotFoundError:
        return 127
    except subprocess.TimeoutExpired:
        return 124
    except OSError:
        return 126
    return done.returncode


def _watts(milliwatts: int) -> str:
    return str(max(1, int(milliwatts // 1000)))


def _pl_args(index: int, milliwatts: int) -> list[str]:
    return ["nvidia-smi", "-i", str(index), "-pl", _watts(milliwatts)]


@dataclass
class _GpuState:
    index: int
    uuid: str
    min_mw: int
    max_mw: int
    default_mw: int
    original_mw: int
    max_clock_mhz: int | None = None
    power_changed: bool = False
    clock_locked: bool = False
    method: str = "none"


@dataclass(frozen=True)
class RecoveryResult:
    restored: tuple[str, ...]
    failed: tuple[str, ...]
    manual_commands: tuple[str, ...] = ()
    note: str = ""


def marker_present() -> bool:
    return config.restore_marker_path().exists()


class PowerCap:
    def __init__(
        self,
        api: NvmlApi,
        gpu_indices: tuple[int, ...],
        *,
        smi: SmiRunner = run_command,
        marker_path: Path | None = None,
        sleep: Sleeper = time.sleep,
        handle_signals: bool = False,
        allow_sudo: bool = True,
        fallback_clocks: bool = False,
    ) -> None:
        self._api = api
        self._indices = tuple(gpu_indices)
        self._smi = smi
        self._marker = marker_path
        self._sleep = sleep
        self._handle_signals = handle_signals
        self._allow_sudo = allow_sudo
        self._fallback_clocks = fallback_clocks
        self._states: list[_GpuState] = []
        self._applied = False
        self._notes: list[str] = []
        self._old_handlers: dict[int, Any] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------ public state

    @property
    def applied(self) -> bool:
        """True when the last ``apply`` capped every GPU."""
        return self._applied

    @property
    def cap_method(self) -> str:
        """``nvml``, ``nvidia_smi``, ``clock_lock`` or ``none`` (the first GPU's method)."""
        if not self._applied or not self._states:
            return "none"
        return self._states[0].method

    @property
    def notes(self) -> tuple[str, ...]:
        return tuple(self._notes)

    def _marker_path(self) -> Path:
        return self._marker if self._marker is not None else config.restore_marker_path()

    # ------------------------------------------------------------ apply

    def apply(self, level: float) -> bool:
        """Cap every GPU to ``level`` x its default limit. Returns whether all were capped."""
        if not (isinstance(level, float | int) and math.isfinite(level) and 0 < level <= 1):
            raise ValueError(f"level must be above 0 and at most 1, not {level!r}")
        with self._lock:
            if not self._states:
                self._states = [self._read_state(i) for i in self._indices]
                self._write_marker()
            results = [self._cap_one(state, level) for state in self._states]
            self._applied = all(results)
            return self._applied

    def _read_state(self, index: int) -> _GpuState:
        low, high = self._api.limit_constraints_mw(index)
        return _GpuState(
            index=index,
            uuid=self._api.uuid(index),
            min_mw=low,
            max_mw=high,
            default_mw=self._api.default_limit_mw(index),
            original_mw=self._api.current_limit_mw(index),
        )

    def _cap_one(self, state: _GpuState, level: float) -> bool:
        target = min(max(round(level * state.default_mw), state.min_mw), state.max_mw)
        if not self._fallback_clocks:
            try:
                self._api.set_limit_mw(state.index, target)
            except LimitPermissionDenied:
                return self._cap_with_sudo(state, target)
            except LimitNotSupported:
                logger.info("GPU %d has no power limit; locking clocks instead", state.index)
            except GpuError:
                return self._give_up(state, "the driver refused the power limit")
            else:
                state.power_changed = True
                state.method = "nvml"
                return True
        return self._lock_clocks(state, level)

    def _cap_with_sudo(self, state: _GpuState, target: int) -> bool:
        if self._allow_sudo and self._smi(["sudo", "-n", *_pl_args(state.index, target)]) == 0:
            state.power_changed = True
            state.method = "nvidia_smi"
            return True
        return self._give_up(state, "setting a power limit needs root")

    def _lock_clocks(self, state: _GpuState, level: float) -> bool:
        top = state.max_clock_mhz or self._api.max_graphics_clock_mhz(state.index)
        state.max_clock_mhz = top
        argv = [
            "nvidia-smi",
            "-i",
            str(state.index),
            "-lgc",
            f"{MIN_LOCK_MHZ},{round(level * top)}",
        ]
        state.clock_locked = True  # assume locked until proven otherwise, so restore always resets
        self._write_marker()
        if self._run_with_sudo_fallback(argv):
            state.method = "clock_lock"
            return True
        state.clock_locked = False
        self._write_marker()
        return self._give_up(state, "locking the GPU clock needs root")

    def _run_with_sudo_fallback(self, argv: list[str]) -> bool:
        if self._smi(argv) == 0:
            return True
        return self._allow_sudo and self._smi(["sudo", "-n", *argv]) == 0

    def _give_up(self, state: _GpuState, reason: str) -> bool:
        state.method = "none"
        note = (
            f"GPU {state.index}: {reason}. The job runs uncapped. "
            "To allow caps, add a sudoers entry for `nvidia-smi` (see the lab setup notes)."
        )
        logger.warning(note)
        if note not in self._notes:
            self._notes.append(note)
        return False

    # ------------------------------------------------------------ marker

    def _write_marker(self) -> None:
        body: dict[str, Any] = {s.uuid: s.original_mw for s in self._states}
        locked = [s.uuid for s in self._states if s.clock_locked]
        if locked:
            body[CLOCK_KEY] = locked
        try:
            config.write_private(self._marker_path(), json.dumps(body, sort_keys=True))
        except OSError:
            logger.warning("could not write the restore marker %s", self._marker_path())
            self._notes.append("Could not write ~/.thirst/restore.json (crash safety net).")

    # ------------------------------------------------------------ restore

    def restore(self) -> tuple[str, ...]:
        """Put back the original limits. Returns the manual commands for any GPU that failed."""
        with self._lock:
            manual = self._restore_all()
            if manual:
                logger.error(
                    "Could not restore the GPU power settings. Run by hand: %s", " ; ".join(manual)
                )
            elif self._states:
                self._marker_path().unlink(missing_ok=True)
            self._applied = False
            return tuple(manual)

    def _restore_all(self) -> list[str]:
        manual: list[str] = []
        for state in self._states:
            if not (state.power_changed or state.clock_locked):
                continue
            if self._restore_one(state):
                state.power_changed = False
                state.clock_locked = False
            else:
                manual.extend(self._manual_commands(state))
        return manual

    def _restore_one(self, state: _GpuState) -> bool:
        ok = True
        if state.power_changed:
            ok = self._retry(lambda: self._put_back_limit(state))
        if state.clock_locked and ok:
            ok = self._retry(lambda: self._run_with_sudo_fallback(self._rgc(state)))
        return ok

    def _put_back_limit(self, state: _GpuState) -> bool:
        try:
            self._api.set_limit_mw(state.index, state.original_mw)
        except LimitPermissionDenied:
            argv = ["sudo", "-n", *_pl_args(state.index, state.original_mw)]
            return self._allow_sudo and self._smi(argv) == 0
        except (LimitNotSupported, GpuError):
            return False
        return True

    def _retry(self, attempt: Callable[[], bool]) -> bool:
        for number in range(RESTORE_ATTEMPTS):
            if attempt():
                return True
            if number < RESTORE_ATTEMPTS - 1:
                self._sleep(RESTORE_PAUSE_S)
        return False

    @staticmethod
    def _rgc(state: _GpuState) -> list[str]:
        return ["nvidia-smi", "-i", str(state.index), "-rgc"]

    def _manual_commands(self, state: _GpuState) -> list[str]:
        commands = []
        if state.power_changed:
            commands.append("sudo " + " ".join(_pl_args(state.index, state.original_mw)))
        if state.clock_locked:
            commands.append("sudo " + " ".join(self._rgc(state)))
        return commands

    def adopt(self, states: list[_GpuState]) -> None:
        """Use ready-made GPU states (recovery from the marker file)."""
        self._states = list(states)

    def restore_states_only(self) -> tuple[str, ...]:
        """Restore without touching the marker file (the caller owns it)."""
        with self._lock:
            return tuple(self._restore_all())

    # ------------------------------------------------------------ context manager

    def __enter__(self) -> PowerCap:
        atexit.register(self.restore)
        if self._handle_signals and threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGINT, signal.SIGTERM):
                self._old_handlers[sig] = signal.signal(sig, self._on_signal)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.restore()
        finally:
            atexit.unregister(self.restore)
            for sig, old in self._old_handlers.items():
                signal.signal(sig, old)
            self._old_handlers.clear()

    def _on_signal(self, signum: int, frame: FrameType | None) -> None:
        self.restore()
        if signum == signal.SIGINT:
            raise KeyboardInterrupt
        raise SystemExit(128 + signum)


# ------------------------------------------------------------ recovery after a crash


@dataclass
class _Recovery:
    restored: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    manual: list[str] = field(default_factory=list)


def _read_marker(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def recover_from_marker(
    api: NvmlApi,
    smi: SmiRunner = run_command,
    *,
    sleep: Sleeper = time.sleep,
    marker_path: Path | None = None,
    allow_sudo: bool = True,
) -> RecoveryResult:
    """Undo a cap left behind by a crash (``thirst doctor --restore``)."""
    path = marker_path if marker_path is not None else config.restore_marker_path()
    data = _read_marker(path)
    if data is None:
        return RecoveryResult(
            (), (), (), f"{path} is not valid. Delete it after checking nvidia-smi."
        )
    locked = set(data.get(CLOCK_KEY) or [])
    by_uuid = {api.uuid(i): i for i in range(api.device_count())}
    outcome = _Recovery()
    for uuid, original in ((k, v) for k, v in data.items() if k != CLOCK_KEY):
        index = by_uuid.get(uuid)
        if index is None or not isinstance(original, int):
            outcome.failed.append(uuid)
            continue
        state = _GpuState(index, uuid, 0, 0, 0, original, power_changed=True)
        state.clock_locked = uuid in locked
        cap = PowerCap(api, (index,), smi=smi, sleep=sleep, allow_sudo=allow_sudo)
        cap.adopt([state])
        manual = cap.restore_states_only()
        if manual:
            outcome.failed.append(uuid)
            outcome.manual.extend(manual)
        else:
            outcome.restored.append(uuid)
    if not outcome.failed:
        path.unlink(missing_ok=True)
    return RecoveryResult(tuple(outcome.restored), tuple(outcome.failed), tuple(outcome.manual), "")
