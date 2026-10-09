"""Plain-words explanation of a plan, built from the plan JSON without any AI (plan 02.7.l).

Used by the CLI and by the ``/explain`` fallback. Savings are always shown as ranges, and every
sentence says what is modelled (TRD section 10).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

_WHEN = "%a %d %b %H:%M"


def _clock(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime(_WHEN)


def _range(pair: list[int]) -> str:
    return f"between {pair[0]} and {pair[1]}%"


def _pauses(schedule: list[dict[str, Any]]) -> int:
    states = [row["state"] for row in schedule]
    previous = ["run", *states]
    return sum(1 for a, b in zip(previous, states, strict=False) if b == "pause" and a != "pause")


def _start_sentence(plan: Mapping[str, Any], chosen: Mapping[str, Any]) -> str:
    level = chosen["level_summary"]
    when = "now" if chosen["start"] == plan["submit_ts"] else f"at {_clock(chosen['start'])}"
    text = f"Start {when} with the GPU at {level} of its power limit."
    gaps = _pauses(chosen["schedule"])
    if gaps:
        times = "time" if gaps == 1 else "times"
        text += f" The job pauses {gaps} {times} and the GPUs idle in between."
    return text


def _saving_sentence(chosen: Mapping[str, Any]) -> str:
    ranges = chosen["savings_ranges"]
    if max(r[1] for r in ranges.values()) <= 0:
        return "Compared with starting now, this plan does not reduce your footprint."
    return (
        "Compared with starting now, it saves "
        f"{_range(ranges['water_pct'])} of stress-weighted water, "
        f"{_range(ranges['co2_pct'])} of CO₂ and "
        f"{_range(ranges['energy_pct'])} of facility energy."
    )


def explain_template(plan: Mapping[str, Any]) -> str:
    """Three to six short sentences describing ``plan`` (the output of ``planner.plan``)."""
    chosen = plan["chosen"]
    notes = plan.get("notes", [])
    tags = plan.get("tags", {})
    sentences = [
        _start_sentence(plan, chosen),
        f"It finishes by {_clock(chosen['finish'])}, before your deadline.",
        _saving_sentence(chosen),
        "Energy is modelled from your GPU type; water and CO₂ are modelled from that energy.",
    ]
    if "no_room" in notes:
        sentences.append(
            "There is little room to shift this job, so any saving comes from the power cap."
        )
    if tags.get("tau") == "placeholder":
        sentences.append(
            "The power-cap factors are placeholders until they are measured on your GPU."
        )
    if tags.get("forecast") == "cached":
        sentences.append("The weather forecast is a saved sample, not live data.")
    return " ".join(sentences)
