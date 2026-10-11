"""Plan 04.6.a / 04.8.b: the POST /plan request the CLI builds, checked against the real server."""

from __future__ import annotations

import json
import math
from typing import Any

import pytest
from thirst import planning
from thirst.errors import CliError
from thirst_fakes import ist

from handlers import validation

SITE = "s_abcdefghij"
NOW = ist("2026-10-09 21:00:00")


def request(**changes: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "site_id": SITE,
        "gpu_model": "RTX-4090",
        "gpu_count": 2,
        "work_hours": 6.0,
        "deadline": ist("2026-10-10 09:00:00"),
        "pausable": True,
        "pausable_allowed": True,
        "alpha": 0.5,
        "force_now": False,
    }
    values.update(changes)
    return planning.build_plan_request(**values)


def test_deadline_without_a_zone_is_taken_as_ist() -> None:
    assert planning.parse_deadline("2026-10-10 09:00") == ist("2026-10-10 09:00:00")
    assert planning.parse_deadline("2026-10-10T09:00") == ist("2026-10-10 09:00:00")


def test_deadline_with_an_offset_keeps_the_same_instant() -> None:
    parsed = planning.parse_deadline("2026-10-10T03:30:00+00:00")

    assert parsed == ist("2026-10-10 09:00:00")
    assert parsed.utcoffset() == ist("2026-10-10 09:00:00").utcoffset()


@pytest.mark.parametrize("text", ["", "tomorrow", "2026-13-40 99:99", "09:00"])
def test_a_bad_deadline_is_a_plain_error(text: str) -> None:
    with pytest.raises(CliError) as err:
        planning.parse_deadline(text)

    assert "deadline" in err.value.message.lower()
    assert "2026-10-10 09:00" in err.value.message  # shows the expected format


def test_request_has_the_fields_the_server_expects() -> None:
    body = request()

    assert body == {
        "site_id": SITE,
        "gpu_model": "RTX-4090",
        "gpu_count": 2,
        "work_hours": 6.0,
        "deadline": "2026-10-10T09:00:00+05:30",
        "pausable": True,
        "pausable_allowed": True,
        "alpha": 0.5,
    }


def test_force_now_is_sent_only_when_asked() -> None:
    assert "force_now" not in request()
    assert request(force_now=True)["force_now"] is True


def test_forced_non_pausable_says_so_to_the_server() -> None:
    body = request(pausable=False, pausable_allowed=False)

    assert body["pausable"] is False
    assert body["pausable_allowed"] is False


def test_request_is_accepted_by_the_servers_own_validation() -> None:
    site = {"site_id": SITE, "city": "Chennai", "cooling": "room_ac"}

    parsed = validation.plan_request(json.loads(json.dumps(request())), NOW, site)

    assert parsed.gpu_model == "RTX-4090"
    assert parsed.site_id == SITE
    assert parsed.work_hours == 6.0


def test_force_now_request_is_accepted_by_the_server() -> None:
    site = {"site_id": SITE, "city": "Chennai", "cooling": "room_ac"}

    parsed = validation.plan_request(json.loads(json.dumps(request(force_now=True))), NOW, site)

    assert parsed.force_now is True


@pytest.mark.parametrize("alpha", [0.55, -0.1, 1.1, 0.123, math.nan])
def test_alpha_must_be_on_the_tenths_grid(alpha: float) -> None:
    with pytest.raises(CliError) as err:
        request(alpha=alpha)

    assert "alpha" in err.value.message


@pytest.mark.parametrize("alpha", [0.0, 0.1, 0.3, 0.7, 1.0])
def test_alpha_on_the_grid_is_rounded_cleanly(alpha: float) -> None:
    assert request(alpha=alpha)["alpha"] == round(alpha, 1)


@pytest.mark.parametrize("hours", [0, -1, 48.5, math.nan, math.inf])
def test_work_hours_must_be_above_zero_and_at_most_48(hours: float) -> None:
    with pytest.raises(CliError) as err:
        request(work_hours=hours)

    assert "hours" in err.value.message


def test_gpu_count_must_be_at_least_one() -> None:
    with pytest.raises(CliError):
        request(gpu_count=0)


# ------------------------------------------------------------ reading the server's plan (TODO 4.2)


def good_plan() -> dict[str, Any]:
    return {
        "plan_id": "p_abcdefghij",
        "chosen": {
            "start": "2026-10-10T01:00:00+05:30",
            "finish": "2026-10-10T02:00:00+05:30",
            "level_summary": "85%",
            "schedule": [],
            "savings_ranges": {"water_pct": [14, 29], "co2_pct": [9.5, 18]},
        },
        "notes": [],
    }


def test_a_good_plan_passes_unchanged() -> None:
    plan = good_plan()

    assert planning.checked_plan(plan) is plan


@pytest.mark.parametrize(
    "spoil",
    [
        lambda p: p.pop("plan_id"),
        lambda p: p.update(chosen="nope"),
        lambda p: p["chosen"].update(start="tomorrow"),
        lambda p: p["chosen"].update(finish="2026-10-10T02:00:00"),  # no time zone
        lambda p: p["chosen"].update(schedule=None),
        lambda p: p["chosen"]["savings_ranges"].update(water_pct=[14]),
        lambda p: p["chosen"]["savings_ranges"].update(co2_pct=["9", 18]),
        lambda p: p["chosen"]["savings_ranges"].update(co2_pct=[math.nan, 18]),
        lambda p: p.update(notes="none"),
    ],
)
def test_a_broken_plan_is_one_plain_error(spoil: Any) -> None:
    plan = good_plan()
    spoil(plan)

    with pytest.raises(CliError) as err:
        planning.checked_plan(plan)

    assert "cannot read" in err.value.message


def test_a_plan_that_is_not_an_object_is_refused() -> None:
    with pytest.raises(CliError):
        planning.checked_plan(["not", "a", "plan"])
