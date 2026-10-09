from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

import pytest
from weather_helpers import SUBMIT, diurnal_rows, flat_rows, request, split_window_rows

from engine.explain import explain_template
from engine.factors import Factors, load_factors
from engine.planner import plan_from_rows


@pytest.fixture(scope="module")
def fx() -> Factors:
    return load_factors()


def make(fx: Factors, **kw: Any) -> dict[str, Any]:
    rows = kw.pop("rows", None) or diurnal_rows(SUBMIT)
    kw.setdefault("deadline", SUBMIT + timedelta(hours=30))
    return plan_from_rows(request(**kw), rows, fx)


def test_text_says_what_is_modelled_and_gives_ranges(fx: Factors) -> None:
    text = explain_template(make(fx))
    assert "modelled" in text
    assert re.search(r"saves between \d+ and \d+% of stress-weighted water", text)
    assert re.search(r"between -?\d+ and -?\d+% of CO₂", text)
    assert "placeholders" in text  # default factors use the placeholder power-cap sweep


def test_every_percentage_in_the_savings_sentence_is_part_of_a_range(fx: Factors) -> None:
    text = explain_template(make(fx))
    savings = text.split("it saves ", 1)[1].split(".", 1)[0]
    singles = re.findall(r"(?<!and )(?<!between )\b-?\d+%", savings)
    assert singles == []


def test_start_now_and_later_wording(fx: Factors) -> None:
    # 6 h of work in 7 slots: only a start in slot 0 at 70% fits, so the plan starts now
    now_plan = make(fx, deadline=SUBMIT + timedelta(hours=7))
    assert explain_template(now_plan).startswith("Start now with the GPU at")
    later = explain_template(make(fx))
    assert later.startswith("Start at ")


def test_pause_is_mentioned_when_the_chosen_plan_pauses(fx: Factors) -> None:
    plan = make(fx, rows=split_window_rows(), cooling="evaporative", alpha=1.0, work_hours=6.0,
                gpu_count=2, pausable=True, deadline=SUBMIT + timedelta(hours=14))
    assert "pauses 1 time" in explain_template(plan)


def test_no_saving_is_not_dressed_up_as_a_range(fx: Factors) -> None:
    plan = make(fx, rows=flat_rows(SUBMIT), deadline=SUBMIT + timedelta(hours=6, minutes=50),
                work_hours=6.5)
    plan["chosen"]["savings_ranges"] = {"water_pct": [-3, 0], "co2_pct": [-2, 0],
                                        "energy_pct": [-1, 0]}
    assert "does not reduce your footprint" in explain_template(plan)


def test_notes_add_sentences(fx: Factors) -> None:
    plan = make(fx, rows=diurnal_rows(SUBMIT, hours=6))
    assert "saved sample" in explain_template(plan)
    plan["notes"] = ["no_room"]
    assert "little room to shift" in explain_template(plan)
