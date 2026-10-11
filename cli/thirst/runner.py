"""The runner: wait, cap, start, pause, resume, finish (plan 04.6, TRD 6.2 and 6.3).

State machine::

    INIT -> WAITING -> RUNNING <-> PAUSED -> FINISHED
                 any state -> INTERRUPTED (Ctrl-C or SIGTERM) | FAILED (unexpected error)

The wall clock decides what should be happening (``schedule.desired_at``), so after a suspend or a
clock jump the runner resyncs to the current slot instead of replaying missed transitions. On every
exit path the child is continued (if stopped) and then terminated, the meter stops, and the power
cap is restored. Nothing here talks to a GPU: the meter, the cap and the process are injected.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from .meter import EnergyMeter
from .process import Child, InterruptFlag, PauseUnsupported
from .schedule import Desired, Segment, desired_at

logger = logging.getLogger(__name__)

OVERRAN_MESSAGE = "Job ran past the plan; deadline may be missed"
_LAUNCHERS = {"torchrun", "deepspeed", "mpirun", "mpiexec", "srun", "horovodrun"}
_DISTRIBUTED_MODULES = {"torch.distributed.run", "torch.distributed.launch"}
_INTERNAL_ERROR = "The run stopped because of an internal error. Details are in the log."
_KILL_WAIT_S = 5.0
_RESTORE_BY_HAND = ("thirst doctor --restore",)


class CapController(Protocol):
    applied: bool
    cap_method: str
    notes: tuple[str, ...]

    def apply(self, level: float) -> bool: ...
    def restore(self) -> tuple[str, ...]: ...


Spawn = Callable[[list[str], dict[str, str], Path | None], Child]


@dataclass(frozen=True)
class RunnerOptions:
    pausable: bool = True
    tick_s: float = 1.0
    grace_s: float = 10.0
    wait_chunk_s: float = 30.0
    countdown_s: float = 600.0
    clock_jump_s: float = 300.0
    meter_background: bool = True


@dataclass(frozen=True)
class RunOutcome:
    started: bool
    start_ts: datetime | None
    end_ts: datetime | None
    exit_code: int | None
    interrupted: bool
    overran: bool
    cap_applied: bool
    cap_method: str
    events: tuple[str, ...]
    notes: tuple[str, ...]
    restore_failures: tuple[str, ...]
    error: str | None


@dataclass(frozen=True)
class PausableDecision:
    """``pausable``: what to ask the planner. ``allowed`` False becomes ``pausable_allowed``."""

    pausable: bool
    allowed: bool
    reason: str


# ------------------------------------------------------------ distributed jobs (D15)


def _base(arg: str) -> str:
    name = re.split(r"[\\/]", arg)[-1].lower()
    return re.sub(r"\.(exe|cmd|bat|py)$", "", name)


def _is_distributed_command(argv: Sequence[str]) -> bool:
    if not argv:
        return False
    first = _base(argv[0])
    if first in _LAUNCHERS or (first == "accelerate" and "launch" in argv[1:3]):
        return True
    return any(
        flag == "-m" and nxt in _DISTRIBUTED_MODULES
        for flag, nxt in zip(argv, argv[1:], strict=False)
    )


def _world_size(env: Mapping[str, str]) -> int:
    try:
        return int(env.get("WORLD_SIZE", "1"))
    except ValueError:
        return 1


def pausable_decision(
    requested: bool, argv: Sequence[str], env: Mapping[str, str], os_name: str
) -> PausableDecision:
    """Pausing is forced off for distributed launchers, WORLD_SIZE > 1 and Windows (D15)."""
    reason = ""
    if os_name == "nt":
        reason = "Pausing is not available on Windows, so the job will run without pauses."
    elif _is_distributed_command(argv) or _world_size(env) > 1:
        reason = (
            "This looks like a distributed job; pausing could break its network connections, "
            "so the job will run without pauses."
        )
    if not reason:
        return PausableDecision(requested, True, "")
    return PausableDecision(False, False, reason if requested else "")


# ------------------------------------------------------------ the runner


class Runner:
    def __init__(
        self,
        plan: Sequence[Segment],
        argv: list[str],
        *,
        meter: EnergyMeter,
        cap: CapController | None,
        spawn: Spawn,
        wall: Callable[[], datetime],
        mono: Callable[[], float],
        sleep: Callable[[float], Any],
        interrupt: InterruptFlag,
        say: Callable[[str], Any],
        env: dict[str, str],
        log_path: Path | None,
        guard: AbstractContextManager[Any],
        options: RunnerOptions | None = None,
    ) -> None:
        self._plan = tuple(plan)
        self._argv = argv
        self._meter = meter
        self._cap = cap
        self._spawn = spawn
        self._wall = wall
        self._mono = mono
        self._sleep = sleep
        self._interrupt = interrupt
        self._say = say
        self._env = env
        self._log_path = log_path
        self._guard = guard
        self._opt = options or RunnerOptions()
        self._pausable = self._opt.pausable
        self.states: list[str] = []
        self._events: list[str] = []
        self._notes: list[str] = []
        self._child: Child | None = None
        self._paused = False  # the child is stopped (SIGSTOP), whatever state the runner is in
        self._level = 1.0
        self._cap_ok = True
        self._started = False
        self._start_ts: datetime | None = None
        self._end_ts: datetime | None = None
        self._exit_code: int | None = None
        self._interrupted = False
        self._overran = False
        self._error: str | None = None
        self._cap_applied = False
        self._cap_method = "none"
        self._restore_failures: tuple[str, ...] = ()
        self._enter("INIT")

    # ------------------------------------------------------------ public

    def run(self) -> RunOutcome:
        with self._guard:  # signal handlers are in place before the first cap change
            try:
                if self._wait_for_start() and self._start():
                    self._supervise()
            except Exception as exc:  # noqa: BLE001 - every failure must still restore the cap
                self._fail(_INTERNAL_ERROR, exc)
            finally:
                self._finish()
        return self._outcome()

    # ------------------------------------------------------------ states

    def _enter(self, state: str) -> None:
        if not self.states or self.states[-1] != state:
            self.states.append(state)

    def _event(self, name: str) -> None:
        if name not in self._events:
            self._events.append(name)

    def _fail(self, message: str, exc: BaseException) -> None:
        logger.error("runner failed: %s", exc, exc_info=exc)
        self._error = message
        self._enter("FAILED")

    # ------------------------------------------------------------ waiting

    def _wait_for_start(self) -> bool:
        """Sleep until the plan's first run slot. False if interrupted first."""
        next_countdown = self._mono()
        while True:
            if self._interrupt.is_set():
                self._interrupted = True
                self._enter("INTERRUPTED")
                return False
            wanted = desired_at(self._plan, self._wall())
            if wanted.state != "wait":
                return True
            self._enter("WAITING")
            if self._mono() >= next_countdown:
                self._say_countdown(wanted)
                next_countdown = self._mono() + self._opt.countdown_s
            seconds = (
                (wanted.next_change - self._wall()).total_seconds() if wanted.next_change else 0
            )
            self._sleep(max(0.01, min(self._opt.wait_chunk_s, seconds)))

    def _say_countdown(self, wanted: Desired) -> None:
        if wanted.next_change is None:
            return
        minutes = max(0, int((wanted.next_change - self._wall()).total_seconds() // 60))
        hours, rest = divmod(minutes, 60)
        self._say(
            f"Waiting for the planned start: starts in {hours} h {rest} min "
            f"(at {wanted.next_change:%H:%M} IST)."
        )

    # ------------------------------------------------------------ starting

    def _first_level(self, wanted: Desired) -> float:
        if wanted.state == "run":
            return wanted.level
        return next(s.level for s in self._plan if s.state == "run")

    def _start(self) -> bool:
        """Cap, meter, then the command. False (with ``error`` set) if it cannot be started."""
        self._level = self._first_level(desired_at(self._plan, self._wall()))
        if self._cap is not None:
            self._cap_ok = self._cap.apply(self._level) and self._cap_ok
        self._meter.start(background=self._opt.meter_background)
        self._meter.set_state("run", self._level)
        try:
            self._child = self._spawn(self._argv, self._env, self._log_path)
        except OSError as exc:
            self._fail(f"Could not start '{self._argv[0]}': {exc.strerror or exc}.", exc)
            return False
        self._started = True
        self._start_ts = self._wall()
        self._enter("RUNNING")
        return True

    # ------------------------------------------------------------ supervising

    def _supervise(self) -> None:
        child = self._child
        if child is None:
            return
        last_wall, last_mono = self._wall(), self._mono()
        while True:
            if self._interrupt.is_set():
                self._interrupted = True
                return
            code = child.poll()
            if code is not None:
                self._exit_code = code
                self._enter("FINISHED")
                return
            now, tick = self._wall(), self._mono()
            if abs((now - last_wall).total_seconds() - (tick - last_mono)) > self._opt.clock_jump_s:
                logger.warning("clock_jump: the wall clock moved; resyncing to the current slot")
                self._event("clock_jump")
            last_wall, last_mono = now, tick
            self._follow(desired_at(self._plan, now), child)
            self._sleep(self._opt.tick_s)

    def _follow(self, wanted: Desired, child: Child) -> None:
        if wanted.overran and not self._overran:
            self._overran = True
            self._say(OVERRAN_MESSAGE)
        state = self.states[-1]
        if wanted.state == "pause" and not self._pausable:
            self._event("pause_ignored")
        elif wanted.state == "pause" and state == "RUNNING":
            self._pause(child)
        elif wanted.state == "run" and state == "PAUSED":
            self._resume(child, wanted.level)
        elif wanted.state == "run" and state == "RUNNING" and wanted.level != self._level:
            self._change_level(wanted.level)

    def _pause(self, child: Child) -> None:
        try:
            child.pause()
        except PauseUnsupported:
            self._pausable = False
            self._event("pause_failed")
            return
        self._paused = True
        self._meter.set_state("idle")
        self._enter("PAUSED")

    def _resume(self, child: Child, level: float) -> None:
        self._set_cap(level)
        self._meter.set_state("run", level)
        child.resume()
        self._paused = False
        self._enter("RUNNING")

    def _change_level(self, level: float) -> None:
        self._set_cap(level)
        self._meter.set_state("run", level)

    def _set_cap(self, level: float) -> None:
        self._level = level
        if self._cap is not None:
            self._cap_ok = self._cap.apply(level) and self._cap_ok

    # ------------------------------------------------------------ shutdown

    def _finish(self) -> None:
        """Always runs: stop the child, stop the meter, restore the cap. Never raises."""
        self._stop_child()
        if self._interrupted:
            self._enter("INTERRUPTED")
        self._safely(self._meter.stop)
        if self._cap is not None:
            self._cap_applied = bool(self._cap.applied) and self._cap_ok
            self._cap_method = self._cap.cap_method if self._cap_applied else "none"
            self._notes.extend(self._cap.notes)
            restored = self._safely(self._cap.restore)
            # None: restore itself crashed, so nothing says the limit is back. Scripts must notice.
            self._restore_failures = _RESTORE_BY_HAND if restored is None else tuple(restored)
        self._end_ts = self._wall() if self._started else None

    def _stop_child(self) -> None:
        child = self._child
        if child is None:
            return
        try:
            code = child.poll()
            if code is None:
                if self._paused:  # also after an error moved the state on to FAILED
                    child.resume()  # SIGCONT first: a stopped process cannot handle SIGTERM
                    self._paused = False
                child.terminate()
                code = child.wait(self._opt.grace_s)
                if code is None:
                    child.kill()
                    code = child.wait(_KILL_WAIT_S)
            self._exit_code = code if self._exit_code is None else self._exit_code
        except Exception:  # noqa: BLE001 - keep going so the cap is still restored
            logger.exception("could not stop the job cleanly")

    @staticmethod
    def _safely(action: Callable[[], Any]) -> Any:
        try:
            return action()
        except Exception:  # noqa: BLE001
            logger.exception("shutdown step failed")
            return None

    def _outcome(self) -> RunOutcome:
        return RunOutcome(
            started=self._started,
            start_ts=self._start_ts,
            end_ts=self._end_ts,
            exit_code=self._exit_code,
            interrupted=self._interrupted,
            overran=self._overran,
            cap_applied=self._cap_applied,
            cap_method=self._cap_method,
            events=tuple(self._events),
            notes=tuple(self._notes),
            restore_failures=tuple(self._restore_failures),
            error=self._error,
        )


def os_name() -> str:
    """The platform name used by ``pausable_decision`` (``nt`` on Windows)."""
    return os.name
