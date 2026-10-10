"""Plan 04.6: the runner state machine, driven with a fake clock, fake child and fake cap."""

from __future__ import annotations

from typing import Any

import pytest
from thirst import gpus, modelled, runner, schedule
from thirst.process import InterruptFlag
from thirst_fakes import FakeCap, FakeChild, FakeClock, FakeSpawn, RecordingGuard, ist

RTX4090 = gpus.resolve_model(["NVIDIA GeForce RTX 4090"], None)
HOUR = 3600.0


def row(hour: int, state: str, level: float) -> dict[str, Any]:
    return {"slot": f"2026-10-10T{hour:02d}:00:00+05:30", "level": level, "state": state}


def segments(*rows: dict[str, Any]) -> tuple[schedule.Segment, ...]:
    return schedule.segments_from_plan(list(rows))


class Rig:
    """Everything a Runner needs, with a clock starting at 01:00 IST."""

    def __init__(
        self,
        plan: tuple[schedule.Segment, ...],
        *,
        exit_after_s: float | None,
        exit_code: int = 0,
        ignore_term: bool = False,
        pausable: bool = True,
        with_cap: bool = True,
        start: str = "2026-10-10 01:00:00",
    ) -> None:
        self.clock = FakeClock(start)
        self.log: list[str] = []
        self.child = FakeChild(self.clock, exit_after_s, exit_code, ignore_term)
        self.spawn = FakeSpawn(self.child)
        self.cap = FakeCap(self.log) if with_cap else None
        self.meter = modelled.ModelledMeter(
            modelled.power_model(RTX4090, None), 2, wall=self.clock.wall, mono=self.clock.mono
        )
        self.flag = InterruptFlag()
        self.said: list[str] = []
        self.sleeps: list[float] = []
        self.on_sleep: Any = None
        self.plan = plan
        self.pausable = pausable

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.clock.advance(seconds)
        if self.on_sleep is not None:
            self.on_sleep(self)

    def build(self, argv: list[str] | None = None) -> runner.Runner:
        # The child's clock starts when it is spawned, so rebuild it lazily at spawn time.
        spawn = self.spawn

        def late_spawn(a: list[str], env: dict[str, str], log_path: object) -> FakeChild:
            self.child._born = self.clock.mono()  # noqa: SLF001
            return spawn(a, env, log_path)

        return runner.Runner(
            self.plan,
            argv or ["python", "train.py"],
            meter=self.meter,
            cap=self.cap,
            spawn=late_spawn,
            wall=self.clock.wall,
            mono=self.clock.mono,
            sleep=self.sleep,
            interrupt=self.flag,
            say=self.said.append,
            env={"PATH": "x"},
            log_path=None,
            guard=RecordingGuard(self.log),
            options=runner.RunnerOptions(pausable=self.pausable, tick_s=30.0),
        )


# ------------------------------------------------------------ happy path


def test_happy_path_waits_runs_pauses_and_resumes() -> None:
    plan = segments(row(3, "run", 0.85), row(4, "pause", 0.0), row(5, "run", 1.0))
    rig = Rig(plan, exit_after_s=None)

    def finish_at_six(r: Rig) -> None:
        if r.clock.wall() >= ist("2026-10-10 05:59:00"):
            r.child.finished = 0

    rig.on_sleep = finish_at_six
    run = rig.build()

    outcome = run.run()

    assert run.states == ["INIT", "WAITING", "RUNNING", "PAUSED", "RUNNING", "FINISHED"]
    assert rig.cap.applies == [0.85, 1.0]
    assert rig.child.calls == ["pause", "resume"]
    assert outcome.exit_code == 0
    assert outcome.interrupted is False
    assert outcome.overran is False
    assert outcome.started is True
    assert ist("2026-10-10 03:00:00") <= outcome.start_ts < ist("2026-10-10 03:01:00")
    assert outcome.cap_applied is True
    assert outcome.cap_method == "nvml"
    assert rig.cap.restores == 1


def test_happy_path_buckets_run_idle_and_nothing_while_waiting() -> None:
    plan = segments(row(3, "run", 0.85), row(4, "pause", 0.0), row(5, "run", 1.0))
    rig = Rig(plan, exit_after_s=None)
    rig.on_sleep = lambda r: (
        setattr(r.child, "finished", 0) if r.clock.wall() >= ist("2026-10-10 05:59:00") else None
    )

    rig.build().run()

    slots = {s.hour[11:13]: s for s in rig.meter.summary().slots}
    assert sorted(slots) == ["03", "04", "05"]  # hours 01 and 02 were spent waiting
    assert slots["03"].run_kwh > 0 and slots["03"].idle_kwh == 0 and slots["03"].level == 0.85
    assert slots["04"].run_kwh == 0 and slots["04"].idle_kwh > 0
    assert slots["05"].run_kwh > 0 and slots["05"].idle_kwh == 0 and slots["05"].level == 1.0


def test_waiting_sleeps_in_chunks_of_at_most_30_seconds_and_counts_down() -> None:
    plan = segments(row(3, "run", 0.85))
    rig = Rig(plan, exit_after_s=60)

    rig.build().run()

    waits = rig.sleeps[: int(2 * HOUR / 30)]
    assert max(waits) <= 30
    countdowns = [m for m in rig.said if "starts in" in m]
    assert 10 <= len(countdowns) <= 14  # one every 10 minutes for 2 hours


def test_signal_guard_is_entered_before_the_first_cap_change() -> None:
    plan = segments(row(1, "run", 0.85))
    rig = Rig(plan, exit_after_s=60)

    rig.build().run()

    assert rig.log.index("guard_enter") < rig.log.index("cap_apply:0.85")
    assert rig.log[-1] == "guard_exit"
    assert rig.log.index("cap_restore") < rig.log.index("guard_exit")


def test_cap_is_applied_before_the_command_starts() -> None:
    plan = segments(row(1, "run", 0.85))
    rig = Rig(plan, exit_after_s=60)
    order: list[str] = []
    rig.cap.apply = lambda level: order.append("cap") or True  # type: ignore[method-assign]
    original = rig.spawn.__call__

    def spying_spawn(*args: Any) -> FakeChild:
        order.append("spawn")
        return original(*args)

    rig.spawn = spying_spawn  # type: ignore[assignment]

    rig.build().run()

    assert order == ["cap", "spawn"]


def test_child_gets_the_command_and_the_environment() -> None:
    plan = segments(row(1, "run", 1.0))
    rig = Rig(plan, exit_after_s=60)

    rig.build(["python", "-c", "pass"]).run()

    assert rig.spawn.argv == ["python", "-c", "pass"]
    assert rig.spawn.env == {"PATH": "x"}


def test_level_change_without_a_pause_changes_the_cap() -> None:
    plan = segments(row(1, "run", 0.85), row(2, "run", 0.7))
    rig = Rig(plan, exit_after_s=None)
    rig.on_sleep = lambda r: (
        setattr(r.child, "finished", 0) if r.clock.wall() >= ist("2026-10-10 02:30:00") else None
    )

    rig.build().run()

    assert rig.cap.applies == [0.85, 0.7]
    assert rig.child.calls == []


# ------------------------------------------------------------ exits


def test_child_failure_is_recorded_and_the_cap_restored() -> None:
    plan = segments(row(1, "run", 0.85), row(2, "run", 0.85))
    rig = Rig(plan, exit_after_s=120, exit_code=1)

    outcome = rig.build().run()

    assert outcome.exit_code == 1
    assert outcome.interrupted is False
    assert rig.cap.restores == 1


def test_job_finishing_early_ignores_the_rest_of_the_schedule() -> None:
    plan = segments(row(1, "run", 0.85), row(2, "pause", 0.0), row(3, "run", 1.0))
    rig = Rig(plan, exit_after_s=600)  # exits 10 minutes in, hours before the plan ends

    outcome = rig.build().run()

    assert outcome.exit_code == 0
    assert rig.child.calls == []
    assert rig.cap.applies == [0.85]
    assert [s.hour[11:13] for s in rig.meter.summary().slots] == ["01"]
    assert rig.meter.summary().idle_kwh == 0  # nothing idle-metered after the exit
    assert outcome.end_ts <= ist("2026-10-10 01:15:00")


def test_job_running_past_the_plan_keeps_the_last_level_and_is_flagged() -> None:
    plan = segments(row(1, "run", 0.85))
    rig = Rig(plan, exit_after_s=None)
    rig.on_sleep = lambda r: (
        setattr(r.child, "finished", 0) if r.clock.wall() >= ist("2026-10-10 03:00:00") else None
    )

    outcome = rig.build().run()

    assert outcome.overran is True
    assert outcome.exit_code == 0
    assert rig.cap.applies == [0.85]  # no change after the plan ended
    assert sum("Job ran past the plan; deadline may be missed" in m for m in rig.said) == 1


# ------------------------------------------------------------ interruption


def test_ctrl_c_while_paused_continues_then_terminates_and_restores() -> None:
    plan = segments(row(1, "run", 0.85), row(2, "pause", 0.0), row(3, "run", 0.85))
    rig = Rig(plan, exit_after_s=None)

    def interrupt_in_the_pause(r: Rig) -> None:
        if r.clock.wall() >= ist("2026-10-10 02:30:00"):
            r.flag.set()

    rig.on_sleep = interrupt_in_the_pause

    outcome = rig.build().run()

    # SIGCONT before SIGTERM, then the 10 s grace wait; no SIGKILL needed
    assert rig.child.calls == ["pause", "resume", "terminate", "wait:10"]
    assert outcome.interrupted is True
    assert outcome.started is True
    assert rig.cap.restores == 1


def test_a_child_that_ignores_sigterm_is_killed_after_the_grace_period() -> None:
    plan = segments(row(1, "run", 1.0))
    rig = Rig(plan, exit_after_s=None, ignore_term=True)
    rig.on_sleep = lambda r: r.flag.set() if r.clock.wall() >= ist("2026-10-10 01:05:00") else None

    outcome = rig.build().run()

    assert rig.child.calls[:3] == ["terminate", "wait:10", "kill"]
    assert outcome.interrupted is True
    assert rig.cap.restores == 1


def test_ctrl_c_while_waiting_starts_nothing_and_posts_no_receipt() -> None:
    plan = segments(row(5, "run", 0.85))
    rig = Rig(plan, exit_after_s=None)
    rig.on_sleep = lambda r: r.flag.set() if r.clock.wall() >= ist("2026-10-10 02:00:00") else None

    outcome = rig.build().run()

    assert outcome.started is False
    assert outcome.interrupted is True
    assert rig.spawn.argv is None
    assert rig.cap.applies == []
    assert outcome.start_ts is None


# ------------------------------------------------------------ failures


def test_command_that_cannot_start_is_a_plain_error_and_the_cap_is_restored() -> None:
    plan = segments(row(1, "run", 0.85))
    rig = Rig(plan, exit_after_s=None)
    rig.spawn = FakeSpawn(error=FileNotFoundError(2, "No such file or directory"))

    outcome = rig.build(["no-such-program"]).run()

    assert outcome.error is not None
    assert "no-such-program" in outcome.error
    assert "Traceback" not in outcome.error
    assert rig.cap.restores == 1
    assert outcome.exit_code is None


def test_an_unexpected_error_stops_the_child_and_restores_the_cap() -> None:
    plan = segments(row(1, "run", 0.85))
    rig = Rig(plan, exit_after_s=None)

    def explode(r: Rig) -> None:
        if r.clock.wall() >= ist("2026-10-10 01:02:00"):
            raise RuntimeError("meter broke")

    rig.on_sleep = explode

    outcome = rig.build().run()

    assert outcome.error is not None
    assert "meter broke" not in outcome.error  # no internals in the user message
    assert "terminate" in rig.child.calls
    assert rig.cap.restores == 1


# ------------------------------------------------------------ cap variants


def test_without_a_cap_controller_the_job_is_uncapped() -> None:
    plan = segments(row(1, "run", 0.85))
    rig = Rig(plan, exit_after_s=60, with_cap=False)

    outcome = rig.build().run()

    assert outcome.cap_applied is False
    assert outcome.cap_method == "none"
    assert outcome.exit_code == 0


def test_a_cap_that_could_not_be_applied_is_reported_honestly() -> None:
    plan = segments(row(1, "run", 0.85))
    rig = Rig(plan, exit_after_s=60)
    rig.cap.apply_result = False
    rig.cap.notes = ("GPU 0: setting a power limit needs root. The job runs uncapped.",)

    outcome = rig.build().run()

    assert outcome.cap_applied is False
    assert outcome.cap_method == "none"
    assert any("uncapped" in n for n in outcome.notes)


def test_a_pause_is_ignored_when_the_job_is_not_pausable() -> None:
    plan = segments(row(1, "run", 0.85), row(2, "pause", 0.0), row(3, "run", 0.85))
    rig = Rig(plan, exit_after_s=None, pausable=False)
    rig.on_sleep = lambda r: (
        setattr(r.child, "finished", 0) if r.clock.wall() >= ist("2026-10-10 03:30:00") else None
    )

    outcome = rig.build().run()

    assert rig.child.calls == []
    assert "pause_ignored" in outcome.events
    assert outcome.exit_code == 0


# ------------------------------------------------------------ clock


def test_a_clock_jump_resyncs_to_the_current_slot_without_replaying_transitions() -> None:
    plan = segments(row(1, "run", 0.85), row(2, "pause", 0.0), row(3, "run", 1.0))
    rig = Rig(plan, exit_after_s=None)
    jumped: list[bool] = []

    def jump_once(r: Rig) -> None:
        if not jumped and r.clock.wall() >= ist("2026-10-10 01:30:00"):
            jumped.append(True)
            r.clock.jump_wall(1.5 * HOUR)  # suspend: 01:30 becomes 03:00
        if r.clock.wall() >= ist("2026-10-10 03:30:00"):
            r.child.finished = 0

    rig.on_sleep = jump_once

    outcome = rig.build().run()

    assert "clock_jump" in outcome.events
    assert rig.child.calls == []  # the pause was skipped, not replayed
    assert rig.cap.applies == [0.85, 1.0]


def test_small_clock_differences_are_not_jumps() -> None:
    plan = segments(row(1, "run", 0.85))
    rig = Rig(plan, exit_after_s=300)

    outcome = rig.build().run()

    assert "clock_jump" not in outcome.events


# ------------------------------------------------------------ pausable decision (D15)


@pytest.mark.parametrize(
    "argv",
    [
        ["torchrun", "--nproc_per_node=2", "train.py"],
        ["/usr/bin/torchrun", "train.py"],
        ["accelerate", "launch", "train.py"],
        ["deepspeed", "train.py"],
        ["mpirun", "-n", "4", "python", "train.py"],
        ["mpiexec", "-n", "4", "python", "train.py"],
        ["srun", "python", "train.py"],
        ["python", "-m", "torch.distributed.run", "train.py"],
        ["python", "-m", "torch.distributed.launch", "train.py"],
        ["C:\\tools\\torchrun.exe", "train.py"],
    ],
)
def test_distributed_launchers_force_non_pausable(argv: list[str]) -> None:
    decision = runner.pausable_decision(True, argv, {}, "posix")

    assert decision.pausable is False
    assert decision.allowed is False
    assert "distributed" in decision.reason


def test_world_size_above_one_forces_non_pausable() -> None:
    decision = runner.pausable_decision(True, ["python", "train.py"], {"WORLD_SIZE": "4"}, "posix")

    assert decision.pausable is False
    assert decision.allowed is False


def test_world_size_one_or_garbage_does_not() -> None:
    for value in ("1", "", "many"):
        decision = runner.pausable_decision(
            True, ["python", "x.py"], {"WORLD_SIZE": value}, "posix"
        )
        assert decision.pausable is True


def test_windows_forces_non_pausable() -> None:
    decision = runner.pausable_decision(True, ["python", "train.py"], {}, "nt")

    assert decision.pausable is False
    assert decision.allowed is False
    assert "Windows" in decision.reason


def test_a_single_process_job_on_posix_keeps_the_users_choice() -> None:
    wanted = runner.pausable_decision(True, ["python", "train.py"], {}, "posix")
    not_wanted = runner.pausable_decision(False, ["python", "train.py"], {}, "posix")

    assert (wanted.pausable, wanted.allowed) == (True, True)
    assert (not_wanted.pausable, not_wanted.allowed) == (False, True)
    assert wanted.reason == ""


def test_a_forced_decision_is_silent_when_pausing_was_not_asked_for() -> None:
    decision = runner.pausable_decision(False, ["torchrun", "x.py"], {}, "posix")

    assert decision.allowed is False
    assert decision.reason == ""  # nothing to tell the user: they did not ask to pause
