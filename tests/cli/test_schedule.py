"""The plan's schedule as the runner follows it (plan 04.6.a, contract 08 §3.1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from thirst import schedule
from thirst.errors import CliError
from thirst_fakes import ist

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "plan_response.json").read_text("utf-8")
)


def row(
    hour: int, state: str, level: float, fraction: float = 1.0, day: int = 10
) -> dict[str, Any]:
    return {
        "slot": f"2026-10-{day:02d}T{hour:02d}:00:00+05:30",
        "level": level,
        "state": state,
        "fraction": fraction,
    }


PAUSABLE = [
    row(1, "run", 0.85),
    row(2, "run", 0.85),
    row(3, "pause", 0.0),
    row(4, "pause", 0.0),
    row(5, "run", 1.0),
    row(6, "run", 1.0, 0.5),
]


def test_adjacent_rows_with_the_same_state_and_level_are_merged() -> None:
    segments = schedule.segments_from_plan(PAUSABLE)

    assert [(s.state, s.level) for s in segments] == [("run", 0.85), ("pause", 0.0), ("run", 1.0)]
    assert segments[0].start == ist("2026-10-10 01:00:00")
    assert segments[0].end == ist("2026-10-10 03:00:00")
    assert segments[-1].end == ist("2026-10-10 07:00:00")  # the partial last slot runs on its own


def test_real_server_fixture_parses() -> None:
    segments = schedule.segments_from_plan(FIXTURE["chosen"]["schedule"])

    assert len(segments) == 1
    assert segments[0].level == 0.7


def test_off_rows_in_the_middle_count_as_a_pause_and_at_the_edges_are_dropped() -> None:
    rows = [row(0, "off", 0.0), row(1, "run", 1.0), row(2, "off", 0.0), row(3, "run", 1.0)]

    segments = schedule.segments_from_plan(rows)

    assert [(s.state, s.start.hour) for s in segments] == [("run", 1), ("pause", 2), ("run", 3)]


@pytest.mark.parametrize(
    "bad",
    [
        [],
        [row(1, "pause", 0.0)],
        [{"slot": "nope", "level": 1.0, "state": "run"}],
        [{"slot": "2026-10-10T01:00:00+05:30", "level": 1.0, "state": "dance"}],
        [{"slot": "2026-10-10T01:00:00", "level": 1.0, "state": "run"}],
        [row(1, "run", 0.0)],
        [row(1, "run", 1.5)],
        ["x"],
    ],
)
def test_unusable_schedules_are_a_plain_error(bad: list[Any]) -> None:
    with pytest.raises(CliError) as err:
        schedule.segments_from_plan(bad)

    assert "plan" in err.value.message.lower()


def test_desired_before_the_first_slot_is_wait() -> None:
    segments = schedule.segments_from_plan(PAUSABLE)

    wanted = schedule.desired_at(segments, ist("2026-10-10 00:20:00"))

    assert wanted.state == "wait"
    assert wanted.next_change == ist("2026-10-10 01:00:00")
    assert wanted.overran is False


def test_desired_inside_segments() -> None:
    segments = schedule.segments_from_plan(PAUSABLE)

    first = schedule.desired_at(segments, ist("2026-10-10 01:00:00"))
    paused = schedule.desired_at(segments, ist("2026-10-10 03:30:00"))
    last = schedule.desired_at(segments, ist("2026-10-10 06:59:59"))

    assert (first.state, first.level) == ("run", 0.85)
    assert paused.state == "pause"
    assert paused.next_change == ist("2026-10-10 05:00:00")
    assert (last.state, last.level, last.overran) == ("run", 1.0, False)


def test_desired_after_the_plan_keeps_the_last_level_and_flags_overrun() -> None:
    segments = schedule.segments_from_plan(PAUSABLE)

    wanted = schedule.desired_at(segments, ist("2026-10-10 07:00:00"))

    assert (wanted.state, wanted.level, wanted.overran) == ("run", 1.0, True)
    assert wanted.next_change is None


def test_segment_end_is_exclusive() -> None:
    segments = schedule.segments_from_plan(PAUSABLE)

    assert schedule.desired_at(segments, ist("2026-10-10 02:59:59")).state == "run"
    assert schedule.desired_at(segments, ist("2026-10-10 03:00:00")).state == "pause"


def test_transitions_list_start_pause_resume_and_end() -> None:
    segments = schedule.segments_from_plan(PAUSABLE)

    actions = [(t.when.hour, t.action, t.level) for t in schedule.transitions(segments)]

    assert actions == [(1, "start", 0.85), (3, "pause", 0.0), (5, "resume", 1.0), (7, "end", 1.0)]


def test_level_change_without_a_pause_is_a_cap_change() -> None:
    segments = schedule.segments_from_plan([row(1, "run", 0.85), row(2, "run", 0.7)])

    actions = [t.action for t in schedule.transitions(segments)]

    assert actions == ["start", "cap", "end"]


def test_plan_line_names_start_cap_pauses_and_finish() -> None:
    chosen = {
        "start": "2026-10-10T01:00:00+05:30",
        "finish": "2026-10-10T08:10:00+05:30",
        "level_summary": "85%",
        "schedule": [row(1, "run", 0.85), row(2, "pause", 0.0), row(3, "run", 0.85)],
    }

    assert schedule.plan_line(chosen) == (
        "Plan: start 01:00, cap 85%, pause 02:00 to 03:00, done by 08:10"
    )


def test_plan_line_without_a_pause_and_with_a_next_day_finish() -> None:
    chosen = {
        "start": "2026-10-10T22:00:00+05:30",
        "finish": "2026-10-11T03:30:00+05:30",
        "level_summary": "70%",
        "schedule": [row(22, "run", 0.7), row(23, "run", 0.7)],
    }

    assert schedule.plan_line(chosen) == "Plan: start 22:00, cap 70%, done by 03:30 on 11 Oct"


def test_plan_line_says_full_power_for_100_percent() -> None:
    chosen = {
        "start": "2026-10-10T01:00:00+05:30",
        "finish": "2026-10-10T03:00:00+05:30",
        "level_summary": "100%",
        "schedule": [row(1, "run", 1.0)],
    }

    assert "full power" in schedule.plan_line(chosen)


def test_plan_line_for_the_real_fixture() -> None:
    line = schedule.plan_line(FIXTURE["chosen"])

    assert line == "Plan: start 02:00, cap 70%, done by 08:40"


def test_compress_maps_each_hour_to_the_test_slot_length() -> None:
    segments = schedule.segments_from_plan(PAUSABLE)
    origin = ist("2026-10-20 12:00:00")

    short = schedule.compress(segments, 60, origin)

    assert short[0].start == origin
    assert short[0].end == origin + (segments[0].end - segments[0].start) / 60
    assert [(s.state, s.level) for s in short] == [(s.state, s.level) for s in segments]
    assert short[-1].end == ist("2026-10-20 12:06:00")  # 6 hourly rows become 6 minutes
    for before, after in zip(short, short[1:], strict=False):
        assert before.end == after.start


def test_compress_rejects_a_non_positive_slot_length() -> None:
    with pytest.raises(CliError):
        schedule.compress(schedule.segments_from_plan(PAUSABLE), 0, ist("2026-10-20 12:00:00"))
