"""Plan 04.6 / 04.7 / 04.8: `thirst run` from the command line down to the receipt."""

from __future__ import annotations

import json
import re

import pytest
from thirst import config, outbox, powercap, receipt
from thirst.errors import ApiError, GpuError
from thirst_fakes import FakeGpu, FakeNvml, FakeSpawn, ist
from thirst_rig import SITE, CliRig, plan_response

DEADLINE = "2026-10-10 09:00"
COMMAND = ("--", "python", "train.py")


def run_args(*extra: str, command: tuple[str, ...] = COMMAND) -> list[str]:
    return ["run", "--hours", "1", "--deadline", DEADLINE, *extra, *command]


def the_job_id(rig: CliRig) -> str:
    return str(rig.api.receipts[0]["job_id"])


@pytest.fixture
def ready(rig: CliRig) -> CliRig:
    rig.register()
    return rig


# ------------------------------------------------------------ the happy path


def test_run_plans_runs_and_posts_a_receipt(ready: CliRig) -> None:
    code = ready.main(*run_args())

    assert code == 0
    assert len(ready.api.receipts) == 1
    body = ready.api.receipts[0]
    assert body["site_id"] == SITE
    assert body["plan_id"] == "p_abcdefghij"
    assert re.fullmatch(r"j_[a-z2-7]{12}", str(body["job_id"]))
    assert body["method"] == "nvml_energy"
    assert body["cap_applied"] is True and body["cap_method"] == "nvml"
    assert body["gpu"] == {"name": "NVIDIA GeForce RTX 4090", "driver": "550.54", "count": 2}
    assert body["exit_code"] == 0
    assert body["interrupted"] is False and body["overran"] is False
    run_kwh = sum(s["run_kwh"] for s in body["slots"])  # type: ignore[union-attr]
    assert run_kwh == pytest.approx(2 * 200 * 600 / 3.6e6, rel=0.02)
    assert {s["level"] for s in body["slots"]} == {0.85}  # type: ignore[union-attr]


def test_run_prints_the_plan_and_the_servers_receipt(ready: CliRig) -> None:
    ready.main(*run_args())

    assert "Plan: start 01:00, cap 85%, done by 02:00" in ready.text
    assert "Thirst receipt j_" in ready.text
    assert "You took 96% of the possible saving" in ready.text  # from the server's response


def test_run_caps_the_gpus_and_puts_the_original_limit_back(ready: CliRig) -> None:
    ready.nvml.gpus[1].current_limit_mw = 400_000

    ready.main(*run_args())

    assert ready.nvml.set_calls == [(0, 382_500), (1, 382_500), (0, 450_000), (1, 400_000)]
    assert not powercap.marker_present()


def test_run_starts_the_command_as_given_with_pci_order(ready: CliRig) -> None:
    ready.main(*run_args(command=("--", "python", "-c", "print('a; b')")))

    assert ready.inner_spawn.argv == ["python", "-c", "print('a; b')"]
    assert ready.inner_spawn.env is not None
    assert ready.inner_spawn.env["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"


def test_run_saves_the_receipt_locally(ready: CliRig) -> None:
    ready.main(*run_args())

    saved = receipt.load_receipt(the_job_id(ready))
    assert saved["status"] == "posted"
    assert saved["body"]["site_id"] == SITE
    assert saved["response"] == ready.api.receipt_result


def test_run_installs_the_signal_guard(ready: CliRig) -> None:
    ready.main(*run_args())

    # once around the run itself, once while the receipt is written to disk
    assert ready.log == ["guard_enter", "guard_exit", "guard_enter", "guard_exit"]


def test_run_exits_with_the_commands_exit_code(ready: CliRig) -> None:
    ready.child.exit_code = 3

    code = ready.main(*run_args())

    assert code == 3
    assert ready.api.receipts[0]["exit_code"] == 3


def test_a_command_killed_by_a_signal_maps_to_a_shell_style_code(ready: CliRig) -> None:
    ready.child.exit_code = -9

    assert ready.main(*run_args()) == 137


def test_the_receipt_is_posted_even_when_the_job_failed(ready: CliRig) -> None:
    ready.child.exit_code = 1

    ready.main(*run_args())

    assert len(ready.api.receipts) == 1


# ------------------------------------------------------------ now and dry-run


def test_now_asks_the_server_for_the_base_schedule(ready: CliRig) -> None:
    ready.main(*run_args("--now"))

    assert ready.api.plan_payloads[0]["force_now"] is True


def test_without_now_force_now_is_not_sent(ready: CliRig) -> None:
    ready.main(*run_args())

    assert "force_now" not in ready.api.plan_payloads[0]


def test_dry_run_prints_the_transitions_and_starts_nothing(ready: CliRig) -> None:
    ready.api.plan_result = plan_response(rows=(("run", 0.85), ("pause", 0.0), ("run", 1.0)))

    code = ready.main(*run_args("--dry-run", "--pausable"))

    assert code == 0
    assert ready.inner_spawn.argv is None
    assert ready.nvml.set_calls == []
    assert ready.api.receipts == []
    for expected in ("Dry run", "01:00", "start", "02:00", "pause", "03:00", "resume", "04:00"):
        assert expected in ready.text


def test_dry_run_does_not_need_a_gpu_when_the_flags_say_what_it_is(ready: CliRig) -> None:
    ready.nvml_error = GpuError("No NVIDIA GPU was found on this machine.")

    code = ready.main(*run_args("--dry-run", "--gpu-model", "RTX-4090", "--gpus", "2"))

    assert code == 0
    assert ready.nvml_opens == 0


# ------------------------------------------------------------ interrupt and failure


def test_ctrl_c_stops_the_job_posts_the_receipt_and_exits_130(ready: CliRig) -> None:
    ready.child.exit_after_s = None
    ready.on_sleep = lambda r: (
        r.flag.set() if r.clock.wall() >= ist("2026-10-10 01:05:00") else None
    )

    code = ready.main(*run_args())

    assert code == 130
    body = ready.api.receipts[0]
    assert body["interrupted"] is True
    assert "terminate" in ready.child.calls
    assert ready.nvml.gpus[0].current_limit_mw == 450_000  # the cap is back


def test_ctrl_c_while_waiting_posts_no_receipt_and_changes_no_cap(ready: CliRig) -> None:
    ready.api.plan_result = plan_response(start="2026-10-10 05:00:00")
    ready.on_sleep = lambda r: (
        r.flag.set() if r.clock.wall() >= ist("2026-10-10 02:00:00") else None
    )

    code = ready.main(*run_args())

    assert code == 130
    assert ready.api.receipts == []
    assert ready.nvml.set_calls == []
    assert ready.inner_spawn.argv is None
    assert "Nothing was started" in ready.text


def test_a_command_that_cannot_start_is_reported_and_the_cap_restored(ready: CliRig) -> None:
    ready.inner_spawn = FakeSpawn(error=FileNotFoundError(2, "No such file or directory"))

    code = ready.main(*run_args(command=("--", "no-such-program")))

    assert code == 2
    assert "no-such-program" in ready.errors
    assert ready.api.receipts == []
    assert ready.nvml.gpus[0].current_limit_mw == 450_000


def test_a_failed_cap_restore_is_loud_and_changes_the_exit_code(ready: CliRig) -> None:
    ready.child.exit_after_s = None

    def break_restore(r: CliRig) -> None:
        r.nvml.set_failures_left = 99
        if r.clock.wall() >= ist("2026-10-10 01:02:00"):
            r.child.finished = 0

    ready.on_sleep = break_restore

    code = ready.main(*run_args())

    assert code == 5
    assert "sudo nvidia-smi -i 0 -pl 450" in ready.errors
    assert powercap.marker_present()
    assert len(ready.api.receipts) == 1  # the receipt is still posted


# ------------------------------------------------------------ receipts that cannot be posted


def test_receipt_is_queued_when_the_server_is_down(ready: CliRig) -> None:
    ready.api.receipt_error = ApiError("Could not reach the Thirst server.", "network_error", 0)

    code = ready.main(*run_args())

    assert code == 0  # the job itself succeeded
    job_id = the_job_id(ready)
    assert outbox.pending() == [job_id]
    assert "Receipt queued, run `thirst sync`" in ready.text
    assert receipt.load_receipt(job_id)["status"] == "queued"
    queued = json.loads((config.outbox_dir() / f"{job_id}.json").read_text(encoding="utf-8"))
    assert queued["job_id"] == job_id


def test_a_rejected_receipt_is_explained_and_not_queued(ready: CliRig) -> None:
    msg = "This energy is more than your GPUs can draw. Receipt rejected."
    ready.api.receipt_error = ApiError(msg, "implausible_energy", 422)

    code = ready.main(*run_args())

    assert code == 0
    assert msg in ready.text
    assert outbox.pending() == []
    assert receipt.load_receipt(the_job_id(ready))["status"] == "rejected"


def test_implausible_energy_warns_and_is_still_posted(ready: CliRig) -> None:
    ready.watts_per_gpu = 50_000.0

    ready.main(*run_args())

    assert "more than" in ready.text + ready.errors
    assert len(ready.api.receipts) == 1


def test_a_duplicate_receipt_is_reported_as_already_recorded(ready: CliRig) -> None:
    ready.api.receipt_duplicate = True

    code = ready.main(*run_args())

    assert code == 0
    assert "already recorded" in ready.text
    assert outbox.pending() == []
    assert receipt.load_receipt(the_job_id(ready))["status"] == "duplicate"


def test_a_401_keeps_the_receipt_queued_and_says_what_to_fix(ready: CliRig) -> None:
    ready.api.receipt_error = ApiError("Too old.", "stale_timestamp", 401)

    code = ready.main(*run_args())

    assert code == 0
    assert outbox.pending() == [the_job_id(ready)]
    assert "clock" in ready.text
    assert receipt.load_receipt(the_job_id(ready))["status"] == "queued"


def test_the_receipt_is_on_disk_before_the_first_network_attempt(ready: CliRig) -> None:
    seen: dict[str, object] = {}

    def spy() -> None:
        seen["outbox"] = outbox.pending()
        seen["receipts"] = list(config.receipts_dir().glob("*.json"))

    ready.api.on_receipt = spy

    ready.main(*run_args())

    assert seen["outbox"] == [the_job_id(ready)]
    assert len(seen["receipts"]) == 1  # type: ignore[arg-type]
    assert outbox.pending() == []  # the server took it, so it left the outbox


def test_ctrl_c_while_posting_keeps_the_receipt_for_sync(ready: CliRig) -> None:
    ready.api.receipt_error = KeyboardInterrupt()

    code = ready.main(*run_args())

    assert code == 130
    assert outbox.pending() == [the_job_id(ready)]
    assert "thirst sync" in ready.errors
    assert receipt.load_receipt(the_job_id(ready))["status"] == "pending"


def test_an_outbox_write_error_still_prints_and_posts_the_receipt(
    ready: CliRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_: object) -> object:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(outbox, "enqueue", broken)

    code = ready.main(*run_args())

    assert code == 0
    assert "Thirst receipt j_" in ready.text
    assert len(ready.api.receipts) == 1


def test_an_outbox_write_error_with_the_server_down_is_said_out_loud(
    ready: CliRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_: object) -> object:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(outbox, "enqueue", broken)
    ready.api.receipt_error = ApiError("Could not reach the Thirst server.", "network_error", 0)

    code = ready.main(*run_args())

    assert code == 0
    assert "could not be saved to the outbox" in ready.text
    assert "Thirst receipt j_" in ready.text  # the numbers are still on screen
    assert "queued, run" not in ready.text


def test_a_local_copy_write_error_does_not_lose_the_receipt(
    ready: CliRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: object) -> object:
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(receipt, "save_receipt", broken)

    code = ready.main(*run_args())

    assert code == 0
    assert len(ready.api.receipts) == 1
    assert "Thirst receipt j_" in ready.text
    assert outbox.pending() == []


# ------------------------------------------------------------ pausing and the plan's timeline


def test_a_pausable_plan_pauses_and_meters_the_idle_hour(ready: CliRig) -> None:
    ready.api.plan_result = plan_response(rows=(("run", 0.85), ("pause", 0.0), ("run", 0.85)))
    ready.child.exit_after_s = None
    ready.on_sleep = lambda r: (
        setattr(r.child, "finished", 0) if r.clock.wall() >= ist("2026-10-10 03:30:00") else None
    )

    ready.main(*run_args("--pausable", "--hours", "2"))

    assert ready.child.calls == ["pause", "resume"]
    slots = {str(s["hour"])[11:13]: s for s in ready.api.receipts[0]["slots"]}  # type: ignore[union-attr]
    assert slots["01"]["run_kwh"] > 0 and slots["01"]["idle_kwh"] == 0
    assert slots["02"]["idle_kwh"] > 0 and slots["02"]["run_kwh"] == 0
    assert slots["03"]["run_kwh"] > 0


def test_a_job_running_past_the_plan_is_flagged(ready: CliRig) -> None:
    ready.child.exit_after_s = 5400  # 90 minutes; the plan covers one hour

    ready.main(*run_args())

    assert ready.api.receipts[0]["overran"] is True
    assert "Job ran past the plan; deadline may be missed" in ready.text


def test_distributed_launchers_are_planned_as_non_pausable(ready: CliRig) -> None:
    ready.main(*run_args("--pausable", command=("--", "torchrun", "train.py")))

    payload = ready.api.plan_payloads[0]
    assert payload["pausable"] is False
    assert payload["pausable_allowed"] is False
    assert "distributed" in ready.text


def test_slot_seconds_squeezes_the_plan_and_posts_no_receipt(ready: CliRig) -> None:
    ready.api.plan_result = plan_response(rows=(("run", 0.85), ("pause", 0.0), ("run", 1.0)))
    ready.child.exit_after_s = None
    ready.on_sleep = lambda r: (
        setattr(r.child, "finished", 0) if r.clock.wall() >= ist("2026-10-10 01:03:30") else None
    )

    code = ready.main(*run_args("--pausable", "--slot-seconds", "60"))

    assert code == 0
    assert ready.child.calls == ["pause", "resume"]
    assert ready.api.receipts == []
    assert "test run" in ready.text.lower()


# ------------------------------------------------------------ cap variants


def test_no_cap_flag_never_touches_the_power_limit(ready: CliRig) -> None:
    ready.main(*run_args("--no-cap"))

    assert ready.nvml.set_calls == []
    assert not powercap.marker_present()
    body = ready.api.receipts[0]
    assert body["cap_applied"] is False and body["cap_method"] == "none"


def test_without_permission_the_job_runs_uncapped_and_says_so(ready: CliRig) -> None:
    ready.nvml.permission_denied = True
    ready.smi.returncode = 1

    code = ready.main(*run_args())

    assert code == 0
    body = ready.api.receipts[0]
    assert body["cap_applied"] is False and body["cap_method"] == "none"
    assert "uncapped" in ready.text


def test_fallback_clocks_uses_a_clock_lock(ready: CliRig) -> None:
    ready.main(*run_args("--fallback-clocks"))

    assert ready.nvml.set_calls == []
    assert ["nvidia-smi", "-i", "0", "-lgc", "210,2142"] in ready.smi.calls
    assert ["nvidia-smi", "-i", "0", "-rgc"] in ready.smi.calls
    assert ready.api.receipts[0]["cap_method"] == "clock_lock"


# ------------------------------------------------------------ modelled mode (no GPU)


def test_modelled_run_needs_no_gpu_and_is_tagged_modelled(ready: CliRig) -> None:
    ready.nvml_error = GpuError("No NVIDIA GPU was found on this machine.")

    code = ready.main(*run_args("--modelled", "--gpu-model", "RTX-4090", "--gpus", "2"))

    assert code == 0
    assert ready.nvml_opens == 0
    body = ready.api.receipts[0]
    assert body["method"] == "modelled"
    assert body["cap_applied"] is False and body["cap_method"] == "none"
    assert body["gpu"]["count"] == 2  # type: ignore[index]
    assert sum(s["run_kwh"] for s in body["slots"]) > 0  # type: ignore[union-attr]
    assert ready.nvml.set_calls == []


def test_modelled_run_needs_the_gpu_flags(ready: CliRig) -> None:
    code = ready.main(*run_args("--modelled"))

    assert code == 2
    assert "--gpu-model" in ready.errors
    assert ready.api.plan_payloads == []


# ------------------------------------------------------------ bad setups


def test_run_without_a_config_asks_to_register(rig: CliRig) -> None:
    code = rig.main(*run_args())

    assert code == 3
    assert "Run `thirst register` first" in rig.errors


def test_run_without_a_gpu_suggests_modelled(ready: CliRig) -> None:
    ready.nvml_error = GpuError(
        "No NVIDIA GPU was found on this machine. Use `--modelled` to estimate energy."
    )

    code = ready.main(*run_args())

    assert code == 5
    assert "--modelled" in ready.errors
    assert ready.api.plan_payloads == []


def test_run_refuses_to_start_over_a_leftover_cap_marker(ready: CliRig) -> None:
    config.write_private(config.restore_marker_path(), json.dumps({"GPU-aaaa": 300_000}))

    code = ready.main(*run_args())

    assert code == 5
    assert "thirst doctor --restore" in ready.errors
    assert ready.api.plan_payloads == []
    assert ready.inner_spawn.argv is None
    assert json.loads(config.restore_marker_path().read_text("utf-8")) == {"GPU-aaaa": 300_000}


def test_the_marker_does_not_matter_for_a_run_that_changes_no_cap(ready: CliRig) -> None:
    config.write_private(config.restore_marker_path(), json.dumps({"GPU-aaaa": 300_000}))

    assert ready.main(*run_args("--no-cap")) == 0


def test_the_command_must_come_after_double_dash(ready: CliRig) -> None:
    code = ready.main("run", "--hours", "1", "--deadline", DEADLINE)

    assert code == 2
    assert "--" in ready.errors
    assert ready.api.plan_payloads == []


def test_an_empty_command_after_double_dash_is_refused(ready: CliRig) -> None:
    assert ready.main(*run_args(command=("--",))) == 2


def test_an_unknown_gpu_name_asks_for_gpu_model(ready: CliRig) -> None:
    ready.nvml = FakeNvml(gpus=[FakeGpu("GPU-x", name="Mystery GPU 9000")])

    code = ready.main(*run_args())

    assert code == 2
    assert "--gpu-model" in ready.errors


def test_gpu_model_overrides_the_detected_name(ready: CliRig) -> None:
    ready.nvml = FakeNvml(gpus=[FakeGpu("GPU-x", name="Mystery GPU 9000", energy_mj=0)])

    code = ready.main(*run_args("--gpu-model", "RTX-3090"))

    assert code == 0
    assert ready.api.plan_payloads[0]["gpu_model"] == "RTX-3090"


def test_gpus_flag_that_disagrees_with_the_visible_gpus_is_refused(ready: CliRig) -> None:
    code = ready.main(*run_args("--gpus", "5"))

    assert code == 2
    assert "CUDA_VISIBLE_DEVICES" in ready.errors or "GPUs" in ready.errors


def test_cuda_visible_devices_limits_the_measured_gpus(ready: CliRig) -> None:
    ready.env["CUDA_VISIBLE_DEVICES"] = "GPU-bbbb"
    ready.nvml = FakeNvml(gpus=[FakeGpu("GPU-aaaa", energy_mj=0), FakeGpu("GPU-bbbb", energy_mj=0)])

    ready.main(*run_args())

    assert ready.api.plan_payloads[0]["gpu_count"] == 1
    assert ready.nvml.set_calls[0] == (1, 382_500)
    assert ready.inner_spawn.env is not None
    assert ready.inner_spawn.env["CUDA_VISIBLE_DEVICES"] == "GPU-bbbb"


def test_plan_api_errors_stop_the_run_before_anything_changes(ready: CliRig) -> None:
    ready.api.plan_error = ApiError(
        "This job needs until 12:00 at full power.", "deadline_too_soon", 422
    )

    code = ready.main(*run_args())

    assert code == 4
    assert ready.nvml.set_calls == []
    assert ready.inner_spawn.argv is None


def test_the_site_token_is_never_printed(ready: CliRig) -> None:
    from thirst_rig import TOKEN

    ready.api.receipt_error = ApiError("Could not reach the Thirst server.", "network_error", 0)
    ready.main(*run_args())

    assert TOKEN not in ready.text + ready.errors
