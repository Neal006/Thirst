"""The server's plan, as a timeline the runner can follow (plan 04.6.a, contract 08 §3.1).

``chosen.schedule`` has one row per IST hour from the first run slot to the last: ``run`` rows with
a power-cap level, ``pause`` rows (level 0). Every run row is followed for the whole hour; the job
paces itself in the last, partial hour (decision D28). Before the first run row the CLI waits; after
the last it keeps the last level (the job ran past the plan).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .errors import CliError
from .ledger import IST

_BAD_PLAN = "The server sent a plan the CLI cannot follow. Try `thirst plan` again."
_ONE_HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class Segment:
    start: datetime
    end: datetime
    state: str  # "run" or "pause"
    level: float


@dataclass(frozen=True)
class Desired:
    """What should be happening at a moment. ``state`` is wait, run or pause."""

    state: str
    level: float
    overran: bool
    next_change: datetime | None


@dataclass(frozen=True)
class Transition:
    when: datetime
    action: str  # start, pause, resume, cap, end
    level: float


def _row(item: Any) -> tuple[datetime, str, float]:
    if not isinstance(item, Mapping):
        raise CliError(_BAD_PLAN)
    try:
        slot = datetime.fromisoformat(str(item["slot"]))
        state, level = str(item["state"]), float(item["level"])
    except (KeyError, ValueError, TypeError):
        raise CliError(_BAD_PLAN) from None
    if slot.tzinfo is None or state not in ("run", "pause", "off"):
        raise CliError(_BAD_PLAN)
    if state == "run" and not 0 < level <= 1:
        raise CliError(_BAD_PLAN)
    return slot.astimezone(IST), state, level


def segments_from_plan(rows: Sequence[Any]) -> tuple[Segment, ...]:
    """Merge the hourly rows into segments. ``off`` rows at the edges are dropped."""
    parsed = sorted(_row(item) for item in rows)
    runs = [i for i, (_, state, _) in enumerate(parsed) if state == "run"]
    if not runs:
        raise CliError(_BAD_PLAN)
    segments: list[Segment] = []
    for slot, state, level in parsed[runs[0] : runs[-1] + 1]:
        kind = "run" if state == "run" else "pause"
        level = level if kind == "run" else 0.0
        last = segments[-1] if segments else None
        if last and last.state == kind and last.level == level and last.end == slot:
            segments[-1] = Segment(last.start, slot + _ONE_HOUR, kind, level)
        else:
            segments.append(Segment(slot, slot + _ONE_HOUR, kind, level))
    return tuple(segments)


def _last_level(segments: Sequence[Segment]) -> float:
    return next(s.level for s in reversed(segments) if s.state == "run")


def desired_at(segments: Sequence[Segment], now: datetime) -> Desired:
    first, last = segments[0], segments[-1]
    if now < first.start:
        return Desired("wait", first.level, False, first.start)
    if now >= last.end:
        return Desired("run", _last_level(segments), True, None)
    for segment in segments:
        if segment.start <= now < segment.end:
            return Desired(segment.state, segment.level, False, segment.end)
    return Desired("pause", 0.0, False, None)  # a gap between rows: stay paused


def transitions(segments: Sequence[Segment]) -> tuple[Transition, ...]:
    """Every change the runner will make, in order (used by ``--dry-run``)."""
    result: list[Transition] = []
    previous: Segment | None = None
    for segment in segments:
        if previous is None:
            result.append(Transition(segment.start, "start", segment.level))
        elif segment.state == "pause":
            result.append(Transition(segment.start, "pause", 0.0))
        elif previous.state == "pause":
            result.append(Transition(segment.start, "resume", segment.level))
        else:
            result.append(Transition(segment.start, "cap", segment.level))
        previous = segment
    result.append(Transition(segments[-1].end, "end", _last_level(segments)))
    return tuple(result)


def plan_line(chosen: Mapping[str, Any]) -> str:
    """The one-line plan (PRD 6.2.4), e.g. 'Plan: start 01:00, cap 85%, done by 08:10'."""
    segments = segments_from_plan(chosen["schedule"])
    start = datetime.fromisoformat(chosen["start"]).astimezone(IST)
    finish = datetime.fromisoformat(chosen["finish"]).astimezone(IST)
    summary = str(chosen.get("level_summary") or "")
    cap = "full power (no cap)" if summary == "100%" else f"cap {summary}"
    parts = [f"start {start:%H:%M}", cap]
    parts += [f"pause {s.start:%H:%M} to {s.end:%H:%M}" for s in segments if s.state == "pause"]
    done = f"done by {finish:%H:%M}"
    if finish.date() != start.date():
        done += f" on {finish:%d %b}"
    return "Plan: " + ", ".join([*parts, done])


def compress(
    segments: Sequence[Segment], slot_seconds: float, origin: datetime
) -> tuple[Segment, ...]:
    """Squeeze every hour into ``slot_seconds`` starting at ``origin`` (hidden test flag, 4.6.h)."""
    if not slot_seconds > 0:
        raise CliError("--slot-seconds must be above 0.")
    scale = slot_seconds / 3600
    first = segments[0].start
    return tuple(
        Segment(
            origin + (s.start - first) * scale, origin + (s.end - first) * scale, s.state, s.level
        )
        for s in segments
    )
