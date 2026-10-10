"""Plan 04.7: receipt body, local plausibility check, terminal output, saved receipts."""

from __future__ import annotations

import json
import math
import os
import re
import stat
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from thirst import config, receipt
from thirst.errors import CliError
from thirst.ledger import SlotEnergy
from thirst.meter import GpuInfo, MeterSummary
from thirst_fakes import ist

from handlers import validation

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "receipt_response.json").read_text("utf-8")
)
SITE = "s_abcdefghij"
JOB = "j_abcdefghijkl"
PLAN = "p_abcdefghij"


def slot(hour: str, run: float, idle: float = 0.0, level: float = 1.0) -> SlotEnergy:
    return SlotEnergy(ist(hour).isoformat(), run, idle, level)


def summary(*slots: SlotEnergy, method: str = "nvml_energy", gpus: int = 2) -> MeterSummary:
    infos = tuple(GpuInfo(i, f"GPU-{i}", "NVIDIA GeForce RTX 4090", True) for i in range(gpus))
    return MeterSummary(
        slots=slots,
        run_kwh=sum(s.run_kwh for s in slots),
        idle_kwh=sum(s.idle_kwh for s in slots),
        total_mj=0.0,
        method=method,
        gpus=infos,
        driver="550.54",
        events=(),
    )


def facts(start: str = "2026-10-10 02:00:00", end: str = "2026-10-10 08:40:00", **kw: Any) -> Any:
    values: dict[str, Any] = {
        "site_id": SITE,
        "plan_id": PLAN,
        "job_id": JOB,
        "start_ts": ist(start),
        "end_ts": ist(end),
        "exit_code": 0,
        "interrupted": False,
        "overran": False,
        "cap_applied": True,
        "cap_method": "nvml",
    }
    values.update(kw)
    return receipt.JobFacts(**values)


SEVEN = tuple(
    slot(f"2026-10-10 {h:02d}:00:00", 0.5832, 0.0, 0.7) for h in range(2, 9)
)  # 7 slots, 02:00 to 08:00


# ------------------------------------------------------------ body


def test_body_has_exactly_the_contract_fields() -> None:
    body = receipt.build_body(facts(), summary(*SEVEN))

    assert set(body) == {
        "site_id", "plan_id", "job_id", "start_ts", "end_ts", "slots", "cap_applied",
        "cap_method", "method", "gpu", "exit_code", "interrupted", "overran", "cli_version",
    }  # fmt: skip
    assert body["gpu"] == {"name": "NVIDIA GeForce RTX 4090", "driver": "550.54", "count": 2}
    assert body["method"] == "nvml_energy"
    assert body["slots"][0] == {
        "hour": "2026-10-10T02:00:00+05:30",
        "run_kwh": 0.5832,
        "idle_kwh": 0.0,
        "level": 0.7,
    }


def test_body_passes_the_servers_own_validation() -> None:
    body = receipt.build_body(facts(), summary(*SEVEN))

    parsed = validation.receipt_request(json.loads(json.dumps(body)))

    assert parsed.job_id == JOB
    assert len(parsed.slots) == 7


def test_timestamps_are_whole_seconds_with_the_ist_offset() -> None:
    start = ist("2026-10-10 02:00:00").replace(microsecond=987_654)
    end = ist("2026-10-10 08:40:00").replace(microsecond=5)

    body = receipt.build_body(facts(start_ts=start, end_ts=end), summary(*SEVEN))

    assert body["start_ts"] == "2026-10-10T02:00:00+05:30"
    assert body["end_ts"] == "2026-10-10T08:40:00+05:30"


def test_end_is_pushed_after_start_for_an_instant_job() -> None:
    body = receipt.build_body(
        facts(start="2026-10-10 02:00:00", end="2026-10-10 02:00:00"), summary(*SEVEN[:1])
    )

    assert datetime.fromisoformat(body["end_ts"]) > datetime.fromisoformat(body["start_ts"])


def test_every_slot_hour_is_inside_the_job() -> None:
    body = receipt.build_body(facts(), summary(*SEVEN))
    start = datetime.fromisoformat(body["start_ts"])
    end = datetime.fromisoformat(body["end_ts"])

    for item in body["slots"]:
        hour = datetime.fromisoformat(item["hour"])
        assert start.replace(minute=0, second=0) <= hour < end


def test_a_slot_at_or_after_the_end_is_folded_into_the_previous_one() -> None:
    slots = (
        slot("2026-10-10 02:00:00", 1.0),
        slot("2026-10-10 03:00:00", 0.25, 0.1),  # job ended exactly at 03:00
    )

    body = receipt.build_body(facts(end="2026-10-10 03:00:00"), summary(*slots))

    assert len(body["slots"]) == 1
    assert body["slots"][0]["run_kwh"] == pytest.approx(1.25)
    assert body["slots"][0]["idle_kwh"] == pytest.approx(0.1)


def test_a_slot_before_the_start_hour_is_folded_into_the_first() -> None:
    slots = (slot("2026-10-10 00:00:00", 0.4), slot("2026-10-10 02:00:00", 1.0))

    body = receipt.build_body(facts(start="2026-10-10 02:10:00"), summary(*slots))

    assert [s["hour"] for s in body["slots"]] == ["2026-10-10T02:00:00+05:30"]
    assert body["slots"][0]["run_kwh"] == pytest.approx(1.4)


def test_more_than_72_slots_are_merged_to_fit_the_server_limit() -> None:
    one_hour = timedelta(hours=1)
    start = ist("2026-10-10 01:30:00")
    first = start.replace(minute=0)
    slots = tuple(SlotEnergy((first + i * one_hour).isoformat(), 1.0, 0.0, 1.0) for i in range(73))

    body = receipt.build_body(facts(start_ts=start, end_ts=start + 72 * one_hour), summary(*slots))

    assert len(body["slots"]) == 72
    assert sum(s["run_kwh"] for s in body["slots"]) == pytest.approx(73.0)
    validation.receipt_request(json.loads(json.dumps(body)))


def test_non_finite_and_negative_energy_is_cleaned() -> None:
    slots = (slot("2026-10-10 02:00:00", math.nan, -1.0), slot("2026-10-10 03:00:00", 1.0))

    body = receipt.build_body(facts(), summary(*slots))

    assert body["slots"][0]["run_kwh"] == 0.0
    assert body["slots"][0]["idle_kwh"] == 0.0
    json.dumps(body, allow_nan=False)


def test_levels_are_snapped_to_the_allowed_set() -> None:
    body = receipt.build_body(
        facts(),
        summary(
            slot("2026-10-10 02:00:00", 1.0, 0.0, 0.8499), slot("2026-10-10 03:00:00", 1.0, 0, 0.99)
        ),
    )

    assert [s["level"] for s in body["slots"]] == [0.85, 1.0]


def test_a_job_with_no_energy_still_gets_one_zero_slot() -> None:
    body = receipt.build_body(facts(), summary())

    assert len(body["slots"]) == 1
    assert body["slots"][0]["run_kwh"] == 0.0
    assert body["slots"][0]["hour"] == "2026-10-10T02:00:00+05:30"


def test_flags_and_exit_code_are_carried() -> None:
    body = receipt.build_body(
        facts(exit_code=None, interrupted=True, overran=True, cap_applied=False, cap_method="none"),
        summary(*SEVEN),
    )

    assert body["exit_code"] is None
    assert body["interrupted"] is True
    assert body["overran"] is True
    assert body["cap_applied"] is False
    assert body["cap_method"] == "none"


def test_modelled_method_and_plan_less_unverified_pass_through() -> None:
    body = receipt.build_body(facts(plan_id=None), summary(*SEVEN, method="modelled"))

    assert body["method"] == "modelled"
    assert body["plan_id"] is None


def test_cli_version_is_the_package_version() -> None:
    import thirst

    assert receipt.build_body(facts(), summary(*SEVEN))["cli_version"] == thirst.__version__


# ------------------------------------------------------------ ids


def test_job_ids_match_the_server_pattern_and_differ() -> None:
    ids = {receipt.new_job_id() for _ in range(50)}

    assert len(ids) == 50
    assert all(re.fullmatch(r"j_[a-z2-7]{12}", i) for i in ids)


# ------------------------------------------------------------ plausibility


def test_energy_within_the_physical_limit_has_no_warning() -> None:
    body = receipt.build_body(facts(), summary(*SEVEN))

    assert receipt.plausibility_warnings(body, p_max_w=450) == ()


def test_energy_above_the_physical_limit_warns() -> None:
    slots = (slot("2026-10-10 02:00:00", 500.0),)
    body = receipt.build_body(facts(), summary(*slots))

    warnings = receipt.plausibility_warnings(body, p_max_w=450)

    assert len(warnings) == 1
    assert "more than" in warnings[0]


def test_limit_is_gpus_times_pmax_times_hours_times_1_1() -> None:
    hours = 6 + 40 / 60
    limit = 2 * 0.450 * hours * 1.1
    just_under = (slot("2026-10-10 02:00:00", limit * 0.99),)
    just_over = (slot("2026-10-10 02:00:00", limit * 1.01),)

    ok = receipt.build_body(facts(), summary(*just_under))
    bad = receipt.build_body(facts(), summary(*just_over))

    assert receipt.plausibility_warnings(ok, p_max_w=450) == ()
    assert receipt.plausibility_warnings(bad, p_max_w=450) != ()


# ------------------------------------------------------------ terminal output

GOLDEN = """\
Thirst receipt j_abcdefghijkl
  Ran      10 Oct 02:00 to 08:40 IST (6 h 40 min) on 2 x NVIDIA GeForce RTX 4090, cap 70%
  Energy   3.89 kWh GPU (measured)
  Water    16.7 L (modelled); if you had started right away: 21.0 L
  Carbon   4.85 kg CO2 (modelled); if you had started right away: 6.13 kg
  Saved    21% water and 21% CO2 compared with starting right away (modelled)
  Capture  You took 96% of the possible saving
  Score    Site score 97.4 platinum (Provisional)
  Receipt  /receipts/s_abcdefghij/j_abcdefghijkl
"""


def test_scored_receipt_matches_the_golden_text() -> None:
    body = receipt.build_body(facts(), summary(*SEVEN))

    assert receipt.format_scored(body, FIXTURE) == GOLDEN


def test_the_server_numbers_are_printed_not_local_estimates() -> None:
    body = receipt.build_body(facts(), summary(*SEVEN))
    changed = json.loads(json.dumps(FIXTURE))
    changed["scoring"]["actual"]["E_gpu_kwh"] = 9.0

    assert "9.00 kWh GPU (measured)" in receipt.format_scored(body, changed)


def test_no_room_is_explained() -> None:
    body = receipt.build_body(facts(), summary(*SEVEN))
    changed = {**FIXTURE, "capture": None, "no_room": True}

    text = receipt.format_scored(body, changed)

    assert "Capture  Little room to save on this job" in text
    assert "None" not in text


def test_unrated_site_score_is_explained() -> None:
    body = receipt.build_body(facts(), summary(*SEVEN))
    changed = {**FIXTURE, "site_score": {"value": None, "badge": None, "provisional": True}}

    assert "not rated yet" in receipt.format_scored(body, changed)


def test_uncapped_runs_say_so() -> None:
    body = receipt.build_body(facts(cap_applied=False, cap_method="none"), summary(*SEVEN))

    assert "uncapped" in receipt.format_scored(body, FIXTURE)


def test_web_url_prefix_is_used_when_given() -> None:
    body = receipt.build_body(facts(), summary(*SEVEN))

    text = receipt.format_scored(body, FIXTURE, web_url="https://thirst.example.com/")

    assert "https://thirst.example.com/receipts/s_abcdefghij/j_abcdefghijkl" in text


def test_local_receipt_shows_kwh_only_and_says_how_to_sync() -> None:
    body = receipt.build_body(facts(), summary(*SEVEN))

    text = receipt.format_local(body, queued=True)

    assert "4.08 kWh" in text  # 7 x 0.5832
    assert "(measured)" in text
    assert "Receipt queued, run `thirst sync`" in text
    assert "Water" not in text


def test_modelled_local_receipt_is_tagged_modelled() -> None:
    body = receipt.build_body(facts(), summary(*SEVEN, method="modelled"))

    assert "(modelled)" in receipt.format_local(body, queued=False)


def test_rejected_receipt_text_names_the_reason() -> None:
    body = receipt.build_body(facts(), summary(*SEVEN))

    text = receipt.format_local(body, queued=False, note="This energy is too high.")

    assert "This energy is too high." in text
    assert "queued" not in text


# ------------------------------------------------------------ saved receipts


def test_save_and_load_round_trip() -> None:
    body = receipt.build_body(facts(), summary(*SEVEN))

    path = receipt.save_receipt(body, FIXTURE, status="posted")

    assert path == config.receipts_dir() / f"{JOB}.json"
    saved = receipt.load_receipt(JOB)
    assert saved["body"] == body
    assert saved["response"] == FIXTURE
    assert saved["status"] == "posted"


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_saved_receipts_are_private() -> None:
    body = receipt.build_body(facts(), summary(*SEVEN))

    path = receipt.save_receipt(body, None, status="queued")

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_show_rebuilds_the_scored_text_from_disk() -> None:
    body = receipt.build_body(facts(), summary(*SEVEN))
    receipt.save_receipt(body, FIXTURE, status="posted")

    assert receipt.render_saved(JOB) == GOLDEN


def test_show_of_a_queued_receipt_explains_the_state() -> None:
    body = receipt.build_body(facts(), summary(*SEVEN))
    receipt.save_receipt(body, None, status="queued")

    assert "thirst sync" in receipt.render_saved(JOB)


def test_show_unknown_job_is_a_plain_error() -> None:
    with pytest.raises(CliError) as err:
        receipt.render_saved("j_aaaaaaaaaaaa")

    assert "No saved receipt" in err.value.message


def test_show_refuses_a_job_id_that_could_escape_the_folder() -> None:
    with pytest.raises(CliError):
        receipt.render_saved("../../secret")


def test_corrupt_saved_receipt_is_a_plain_error() -> None:
    config.receipts_dir().mkdir(parents=True)
    (config.receipts_dir() / f"{JOB}.json").write_text("{bad", encoding="utf-8")

    with pytest.raises(CliError) as err:
        receipt.render_saved(JOB)

    assert "not valid" in err.value.message
