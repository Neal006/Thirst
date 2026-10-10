from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from engine import units
from engine.errors import EngineError

IST = units.IST


def ist(*args: int) -> datetime:
    return datetime(*args, tzinfo=IST)


def test_ist_is_plus_0530() -> None:
    assert units.IST.utcoffset(None) == timedelta(hours=5, minutes=30)


def test_floor_hour_drops_minutes_and_seconds() -> None:
    assert units.floor_hour(ist(2026, 10, 9, 21, 14, 33)) == ist(2026, 10, 9, 21)


def test_floor_hour_converts_other_zones_to_ist() -> None:
    utc = datetime(2026, 10, 9, 15, 44, tzinfo=UTC)  # 21:14 IST
    floored = units.floor_hour(utc)
    assert floored == ist(2026, 10, 9, 21)
    assert floored.utcoffset() == timedelta(hours=5, minutes=30)


def test_slot0_capacity_is_remaining_share_of_the_hour() -> None:
    assert units.slot0_capacity(ist(2026, 10, 9, 21, 14)) == pytest.approx(46 / 60)
    assert units.slot0_capacity(ist(2026, 10, 9, 21, 0)) == 1.0
    assert units.slot0_capacity(ist(2026, 10, 9, 21, 59, 59)) == pytest.approx(1 / 3600)


def test_slot_starts_are_hourly_increasing_and_ist() -> None:
    slots = units.slot_starts(ist(2026, 10, 9, 21, 14), 48)
    assert len(slots) == 48
    assert slots[0] == ist(2026, 10, 9, 21)
    assert all(b - a == timedelta(hours=1) for a, b in zip(slots, slots[1:], strict=False))
    assert all(s.utcoffset() == timedelta(hours=5, minutes=30) for s in slots)


def test_energy_conversions() -> None:
    assert units.mj_to_kwh(3_600_000_000) == 1.0
    assert units.w_h_to_kwh(400, 6) == pytest.approx(2.4)


def test_naive_datetime_is_rejected() -> None:
    naive = datetime(2026, 10, 9, 21, 14)
    for fn in (units.ensure_ist, units.floor_hour, units.slot0_capacity):
        with pytest.raises(ValueError, match="timezone"):
            fn(naive)


def test_deadline_slots_counts_whole_slots_from_floor_hour() -> None:
    submit = ist(2026, 10, 9, 21, 14)
    # deadline 09:00 next day: slots 21:00..08:00 end by 09:00 -> 12 whole slots
    assert units.deadline_slots(submit, ist(2026, 10, 10, 9, 0)) == (12, False)
    # a deadline that is not on the hour only counts slots that end before it
    assert units.deadline_slots(submit, ist(2026, 10, 10, 9, 30)) == (12, False)


def test_deadline_slots_is_capped_at_48() -> None:
    submit = ist(2026, 10, 9, 21, 14)
    assert units.deadline_slots(submit, ist(2026, 10, 14, 9, 0)) == (48, True)
    assert units.deadline_slots(submit, ist(2026, 10, 11, 21, 0)) == (48, False)


def test_deadline_slots_never_negative() -> None:
    submit = ist(2026, 10, 9, 21, 14)
    assert units.deadline_slots(submit, ist(2026, 10, 9, 20, 0)) == (0, False)


def test_engine_error_carries_code_and_message() -> None:
    err = EngineError("deadline_too_soon", "Needs until 05:00.")
    assert err.code == "deadline_too_soon"
    assert str(err) == "Needs until 05:00."
