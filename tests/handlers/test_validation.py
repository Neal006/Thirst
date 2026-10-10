"""Request validators (plan 05.5.a, 05.6, 05.7; contract 08 §3.1, 3.2, 3.4)."""

from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

import pytest
from weather_helpers import ist

from handlers import validation
from handlers.errors import ApiError

NOW = ist(2026, 10, 9, 21, 14)
PLAN_BODY: dict[str, Any] = {
    "city": "Chennai",
    "cooling": "room_ac",
    "gpu_model": "RTX-4090",
    "gpu_count": 2,
    "work_hours": 6,
    "deadline": "2026-10-10T09:00:00+05:30",
}


def plan(**changes: Any) -> validation.PlanInput:
    return validation.plan_request({**PLAN_BODY, **changes}, NOW)


def code_of(call: Any) -> tuple[int, str]:
    with pytest.raises(ApiError) as err:
        call()
    return err.value.status, err.value.code


# /plan -------------------------------------------------------------------------------------


def test_a_valid_plan_body_gets_defaults() -> None:
    p = plan()
    assert (p.city, p.cooling, p.gpu_model, p.gpu_count, p.work_hours) == (
        "Chennai",
        "room_ac",
        "RTX-4090",
        2,
        6.0,
    )
    assert p.pausable is False and p.pausable_allowed is True
    assert p.alpha == 0.5 and p.force_now is False and p.pue_user is None and p.site_id is None
    assert p.deadline.utcoffset() == timedelta(hours=5, minutes=30)


def test_deadline_is_converted_to_ist() -> None:
    p = plan(deadline="2026-10-10T03:30:00+00:00")
    assert p.deadline.isoformat() == "2026-10-10T09:00:00+05:30"
    assert plan(deadline="2026-10-10T03:30:00Z").deadline.isoformat() == "2026-10-10T09:00:00+05:30"


def test_unknown_fields_are_ignored() -> None:
    assert plan(colour="blue", __proto__={"x": 1}).city == "Chennai"


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"city": "Atlantis"}, (400, "unknown_city")),
        ({"gpu_model": "H900"}, (400, "unknown_gpu")),
        ({"deadline": "2026-10-09T20:00:00+05:30"}, (400, "deadline_in_past")),
        ({"deadline": "2026-10-09T21:14:00+05:30"}, (400, "deadline_in_past")),
        ({"deadline": "2026-10-10T09:00:00"}, (400, "invalid_field")),
        ({"deadline": "tomorrow"}, (400, "invalid_field")),
        ({"deadline": 1760000000}, (400, "invalid_field")),
        ({"deadline": None}, (400, "invalid_field")),
        ({"cooling": "liquid"}, (400, "invalid_field")),
        ({"gpu_count": 0}, (400, "invalid_field")),
        ({"gpu_count": 4097}, (400, "invalid_field")),
        ({"gpu_count": 2.5}, (400, "invalid_field")),
        ({"gpu_count": True}, (400, "invalid_field")),
        ({"gpu_count": "2"}, (400, "invalid_field")),
        ({"work_hours": 0}, (400, "invalid_field")),
        ({"work_hours": -1}, (400, "invalid_field")),
        ({"work_hours": 48.5}, (400, "invalid_field")),
        ({"work_hours": math.nan}, (400, "invalid_field")),
        ({"work_hours": math.inf}, (400, "invalid_field")),
        ({"work_hours": "6"}, (400, "invalid_field")),
        ({"work_hours": True}, (400, "invalid_field")),
        ({"alpha": 1.5}, (400, "invalid_field")),
        ({"alpha": -0.1}, (400, "invalid_field")),
        ({"alpha": 0.55}, (400, "invalid_field")),
        ({"alpha": math.nan}, (400, "invalid_field")),
        ({"alpha": "0.5"}, (400, "invalid_field")),
        ({"pausable": "yes"}, (400, "invalid_field")),
        ({"pausable": 1}, (400, "invalid_field")),
        ({"pausable_allowed": None}, (400, "invalid_field")),
        ({"force_now": "true"}, (400, "invalid_field")),
        ({"pue": 0.9, "cooling": "evaporative"}, (400, "invalid_field")),
        ({"pue": 3.1, "cooling": "evaporative"}, (400, "invalid_field")),
        ({"pue": math.nan, "cooling": "evaporative"}, (400, "invalid_field")),
        ({"pue": "1.4", "cooling": "evaporative"}, (400, "invalid_field")),
        ({"site_id": "s_UPPERCASE"}, (400, "invalid_field")),
        ({"site_id": "s_abc"}, (400, "invalid_field")),
        ({"site_id": 5}, (400, "invalid_field")),
        ({"city": ["Chennai"]}, (400, "invalid_field")),
        ({"city": None}, (400, "invalid_field")),
    ],
)
def test_bad_plan_fields_are_rejected_with_the_documented_code(
    changes: dict[str, Any], expected: tuple[int, str]
) -> None:
    assert code_of(lambda: plan(**changes)) == expected


@pytest.mark.parametrize(
    "missing", ["city", "cooling", "gpu_model", "gpu_count", "work_hours", "deadline"]
)
def test_missing_required_fields_are_400(missing: str) -> None:
    body = {k: v for k, v in PLAN_BODY.items() if k != missing}
    status, code = code_of(lambda: validation.plan_request(body, NOW))
    assert status == 400 and code in {"invalid_field", "unknown_city", "unknown_gpu"}


@pytest.mark.parametrize("body", [None, [], "x", 5, [PLAN_BODY]])
def test_body_must_be_a_json_object(body: Any) -> None:
    assert code_of(lambda: validation.plan_request(body, NOW)) == (400, "invalid_field")


def test_pue_is_only_used_for_evaporative_cooling() -> None:
    assert plan(cooling="evaporative", pue=1.6).pue_user == 1.6
    assert plan(cooling="room_ac", pue=1.6).pue_user is None


def test_alpha_accepts_every_step_of_the_grid() -> None:
    assert [plan(alpha=i / 10).alpha for i in range(11)] == [i / 10 for i in range(11)]
    assert plan(alpha=0.3).alpha == 0.3  # 0.3 is not exactly 3/10 in floating point


def test_site_defaults_fill_city_and_cooling_only() -> None:
    body = {k: v for k, v in PLAN_BODY.items() if k not in ("city", "cooling")}
    site = {"site_id": "s_abcdefghij", "city": "Pune", "cooling": "evaporative"}
    p = validation.plan_request({**body, "site_id": "s_abcdefghij"}, NOW, site=site)
    assert (p.city, p.cooling, p.site_id) == ("Pune", "evaporative", "s_abcdefghij")
    # an explicit value still wins over the site default
    p2 = validation.plan_request(
        {**body, "site_id": "s_abcdefghij", "city": "Delhi"}, NOW, site=site
    )
    assert p2.city == "Delhi"


def test_without_a_site_city_and_cooling_are_required() -> None:
    body = {k: v for k, v in PLAN_BODY.items() if k not in ("city", "cooling")}
    assert code_of(lambda: validation.plan_request(body, NOW))[0] == 400


def test_to_request_uses_the_server_time_as_submit() -> None:
    req = plan(pausable=True, alpha=0.3).to_request(NOW)
    assert req.submit_ts == NOW and req.pausable is True and req.alpha == 0.3
    assert req.pausable_allowed is True and req.site_id is None


def test_force_now_reaches_the_engine_request() -> None:
    assert plan(force_now=True).to_request(NOW).force_now is True
    assert plan().to_request(NOW).force_now is False


def test_pausable_allowed_false_forces_a_non_pausable_request() -> None:
    req = plan(pausable=True, pausable_allowed=False).to_request(NOW)
    assert req.pausable_allowed is False


# /sites ------------------------------------------------------------------------------------

SITE_BODY: dict[str, Any] = {
    "name": "CSE GPU Lab",
    "city": "Chennai",
    "cooling": "room_ac",
    "gpu_count": 8,
    "coverage_declared": 0.5,
}


def test_a_valid_site_body_gets_defaults() -> None:
    s = validation.site_request(SITE_BODY)
    assert (s.name, s.org, s.city, s.cooling, s.gpu_count) == (
        "CSE GPU Lab",
        None,
        "Chennai",
        "room_ac",
        8,
    )
    assert s.public is True and s.coverage_declared == 0.5


def test_site_name_is_trimmed_and_control_characters_are_stripped() -> None:
    s = validation.site_request({**SITE_BODY, "name": "  Lab\x00 \x1b[31mOne‮\n  "})
    assert s.name == "Lab [31mOne"
    assert "\x00" not in s.name and "‮" not in s.name and "\n" not in s.name


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "ab"},
        {"name": "  a  "},
        {"name": "x" * 61},
        {"name": ""},
        {"name": 5},
        {"name": "\x00\x01\x02\x03"},
        {"org": "o" * 81},
        {"org": 3},
        {"city": "Atlantis"},
        {"cooling": "x"},
        {"gpu_count": 0},
        {"gpu_count": 100001},
        {"gpu_count": 1.5},
        {"gpu_count": True},
        {"coverage_declared": 1.1},
        {"coverage_declared": -0.1},
        {"coverage_declared": math.nan},
        {"coverage_declared": "0.5"},
        {"public": "yes"},
        {"public": 1},
    ],
)
def test_bad_site_fields_are_400(changes: dict[str, Any]) -> None:
    status, _ = code_of(lambda: validation.site_request({**SITE_BODY, **changes}))
    assert status == 400


def test_site_optional_fields() -> None:
    s = validation.site_request({**SITE_BODY, "org": "  IIT  ", "public": False})
    assert s.org == "IIT" and s.public is False
    assert validation.site_request({**SITE_BODY, "org": "   "}).org is None
    assert (
        validation.site_request(
            {k: v for k, v in SITE_BODY.items() if k != "coverage_declared"}
        ).coverage_declared
        == 0.0
    )


@pytest.mark.parametrize("good", ["s_abcdefghij", "s_a2b3c4d5e6", "s_simaaaaaaa"])
def test_site_id_format(good: str) -> None:
    assert validation.site_id(good) == good


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "s_",
        "s_abcdefghi",
        "s_abcdefghijk",
        "S_abcdefghij",
        "s_abcdefgh1j",
        "../../etc/passwd",
        "s_abcdefghij\n",
        None,
        5,
    ],
)
def test_malformed_site_ids_are_400(bad: Any) -> None:
    assert code_of(lambda: validation.site_id(bad))[0] == 400


# /receipts ---------------------------------------------------------------------------------


def receipt_body(**changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "site_id": "s_abcdefghij",
        "plan_id": "p_abcdefghij",
        "job_id": "j_abcdefghijkl",
        "start_ts": "2026-10-10T01:10:00+05:30",
        "end_ts": "2026-10-10T03:20:00+05:30",
        "slots": [
            {"hour": "2026-10-10T01:00:00+05:30", "run_kwh": 0.4, "idle_kwh": 0.0, "level": 0.85},
            {"hour": "2026-10-10T02:00:00+05:30", "run_kwh": 0.5, "idle_kwh": 0.01, "level": 0.85},
            {"hour": "2026-10-10T03:00:00+05:30", "run_kwh": 0.1, "idle_kwh": 0.0, "level": 0.7},
        ],
        "cap_applied": True,
        "cap_method": "nvml",
        "method": "nvml_energy",
        "gpu": {"name": "NVIDIA GeForce RTX 4090", "driver": "550.54", "count": 2},
        "exit_code": 0,
        "interrupted": False,
        "overran": False,
        "cli_version": "0.1.0",
    }
    body.update(changes)
    return body


def receipt(**changes: Any) -> validation.ReceiptInput:
    return validation.receipt_request(receipt_body(**changes))


def test_a_valid_receipt_is_parsed_and_end_ts_is_canonical() -> None:
    r = receipt()
    assert r.job_id == "j_abcdefghijkl" and r.plan_id == "p_abcdefghij" and len(r.slots) == 3
    assert r.end_ts.isoformat() == "2026-10-10T03:20:00+05:30"
    assert r.canonical_end == "2026-10-10T03:20:00+05:30"
    assert r.method == "nvml_energy" and r.cap_method == "nvml" and r.gpu_count == 2


def test_z_and_other_offsets_are_normalised_to_ist() -> None:
    r = receipt(
        start_ts="2026-10-09T19:40:00Z",
        end_ts="2026-10-09T21:50:00+00:00",
        slots=[{"hour": "2026-10-09T19:30:00Z", "run_kwh": 1, "idle_kwh": 0, "level": 1}],
    )
    assert r.canonical_end == "2026-10-10T03:20:00+05:30"
    assert r.canonical_start == "2026-10-10T01:10:00+05:30"
    assert r.slots[0]["hour"] == "2026-10-10T01:00:00+05:30"
    assert r.slots[0]["level"] == 1.0  # ints are accepted and stored as floats


def test_a_slot_that_is_not_on_an_ist_hour_is_rejected() -> None:
    # 20:00 UTC is 01:30 IST: a different slot grid than the engine's
    slot = {"hour": "2026-10-09T20:00:00Z", "run_kwh": 1, "idle_kwh": 0, "level": 1}
    assert code_of(lambda: receipt(slots=[slot])) == (400, "invalid_field")


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"job_id": "j_short"}, (400, "invalid_field")),
        ({"job_id": "J_ABCDEFGHIJKL"}, (400, "invalid_field")),
        ({"job_id": 5}, (400, "invalid_field")),
        ({"plan_id": "x"}, (400, "invalid_field")),
        ({"plan_id": None, "method": "nvml_energy"}, (400, "invalid_field")),
        ({"start_ts": "2026-10-10T04:00:00+05:30"}, (400, "invalid_field")),
        ({"start_ts": "2026-10-06T01:00:00+05:30"}, (400, "invalid_field")),  # about 98 h
        ({"start_ts": "bad"}, (400, "invalid_field")),
        ({"end_ts": "2026-10-10T03:20:00"}, (400, "invalid_field")),
        ({"slots": []}, (400, "invalid_field")),
        ({"slots": "x"}, (400, "invalid_field")),
        ({"cap_applied": "yes"}, (400, "invalid_field")),
        ({"cap_method": "magic"}, (400, "invalid_field")),
        ({"method": "magic"}, (400, "invalid_field")),
        ({"gpu": {"name": "x", "driver": "y"}}, (400, "invalid_field")),
        ({"gpu": {"name": "x", "driver": "y", "count": 0}}, (400, "invalid_field")),
        ({"gpu": "x"}, (400, "invalid_field")),
        ({"exit_code": "0"}, (400, "invalid_field")),
        ({"interrupted": "no"}, (400, "invalid_field")),
        ({"cli_version": "v" * 40}, (400, "invalid_field")),
    ],
)
def test_bad_receipt_fields(changes: dict[str, Any], expected: tuple[int, str]) -> None:
    assert code_of(lambda: receipt(**changes)) == expected


def slot_with(**changes: Any) -> dict[str, Any]:
    return {
        "hour": "2026-10-10T02:00:00+05:30",
        "run_kwh": 0.5,
        "idle_kwh": 0.0,
        "level": 0.85,
        **changes,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"run_kwh": -0.1},
        {"idle_kwh": -1},
        {"run_kwh": math.nan},
        {"idle_kwh": math.inf},
        {"run_kwh": "1"},
        {"run_kwh": True},
        {"level": 0.5},
        {"level": "1.0"},
        {"level": None},
        {"hour": "2026-10-10T02:30:00+05:30"},
        {"hour": "2026-10-10T02:00:00"},
        {"hour": "x"},
        {"hour": 5},
    ],
)
def test_bad_slots_are_400(changes: dict[str, Any]) -> None:
    status, code = code_of(lambda: receipt(slots=[slot_with(**changes)]))
    assert (status, code) == (400, "invalid_field")


@pytest.mark.parametrize("key", ["hour", "run_kwh", "idle_kwh", "level"])
def test_slot_missing_keys_is_400(key: str) -> None:
    slot = {k: v for k, v in slot_with().items() if k != key}
    assert code_of(lambda: receipt(slots=[slot])) == (400, "invalid_field")


def test_slots_outside_the_job_are_422() -> None:
    before = slot_with(hour="2026-10-10T00:00:00+05:30")
    after = slot_with(hour="2026-10-10T04:00:00+05:30")
    assert code_of(lambda: receipt(slots=[before])) == (422, "slot_out_of_range")
    assert code_of(lambda: receipt(slots=[after])) == (422, "slot_out_of_range")
    # the hour containing start_ts (01:00 for a 01:10 start) is allowed
    assert receipt(slots=[slot_with(hour="2026-10-10T01:00:00+05:30")]).slots


def test_more_than_72_slots_is_rejected() -> None:
    start = ist(2026, 10, 7, 0, 0)
    slots = [slot_with(hour=(start + timedelta(hours=h)).isoformat()) for h in range(73)]
    assert (
        code_of(
            lambda: receipt(
                start_ts=start.isoformat(),
                end_ts=(start + timedelta(hours=73)).isoformat(),
                slots=slots,
            )
        )[0]
        == 400
    )


def test_unverified_receipts_may_have_no_plan() -> None:
    r = receipt(plan_id=None, method="unverified")
    assert r.plan_id is None and r.method == "unverified"


def test_duplicate_slot_hours_are_rejected() -> None:
    assert code_of(lambda: receipt(slots=[slot_with(), slot_with()]))[0] == 400


# inputs that used to escape as a 503 (review fixes) -------------------------------------------


@pytest.mark.parametrize("value", [10**400, -(10**400)])
def test_a_huge_integer_is_a_400_not_an_overflow(value: int) -> None:
    assert code_of(lambda: validation._number(value, "work_hours", 0, 48)) == (
        400,
        "invalid_field",
    )


@pytest.mark.parametrize(
    "value",
    ["9999-12-31T23:59:59-05:00", "0001-01-01T00:00:00+05:30", "0001-01-01T00:00:00+14:00"],
)
def test_a_time_at_the_edge_of_the_calendar_is_a_400(value: str) -> None:
    assert code_of(lambda: validation._aware(value, "deadline")) == (400, "invalid_field")


def test_fractional_seconds_are_cut_from_receipt_times() -> None:
    r = receipt(start_ts="2026-10-10T01:10:00.25+05:30", end_ts="2026-10-10T03:20:00.5+05:30")
    assert r.canonical_start == "2026-10-10T01:10:00+05:30"
    assert r.canonical_end == "2026-10-10T03:20:00+05:30"


def test_a_slot_that_starts_at_the_end_time_is_refused() -> None:
    slots = [
        slot_with(hour="2026-10-10T01:00:00+05:30"),
        slot_with(hour="2026-10-10T03:00:00+05:30"),
    ]
    assert code_of(lambda: receipt(end_ts="2026-10-10T03:00:00+05:30", slots=slots)) == (
        422,
        "slot_out_of_range",
    )
    ok = [slot_with(hour="2026-10-10T01:00:00+05:30"), slot_with(hour="2026-10-10T02:00:00+05:30")]
    assert len(receipt(end_ts="2026-10-10T03:00:00+05:30", slots=ok).slots) == 2
