"""Plan 04.8 and friends: register, plan, sync, receipt show, doctor, sweep, error handling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from thirst import config, outbox, powercap, receipt
from thirst.errors import ApiError, GpuError
from thirst_fakes import FakeGpu, FakeNvml, FakeSmi, ist
from thirst_rig import SITE, TOKEN, URL, CliRig, plan_response

DEADLINE = "2026-10-10 09:00"


# ------------------------------------------------------------ register


def register_args(*extra: str) -> list[str]:
    return [
        "register", "--api-url", URL, "--name", "CSE GPU Lab", "--city", "Chennai",
        "--cooling", "room_ac", "--gpus", "4", *extra,
    ]  # fmt: skip


def test_register_creates_the_site_and_saves_the_config(rig: CliRig) -> None:
    code = rig.main(*register_args("--org", "IIT", "--coverage", "0.8"))

    assert code == 0
    assert rig.api.sites == [
        {
            "name": "CSE GPU Lab",
            "city": "Chennai",
            "cooling": "room_ac",
            "gpu_count": 4,
            "coverage_declared": 0.8,
            "public": True,
            "org": "IIT",
        }
    ]
    saved = config.load()
    assert (saved.api_url, saved.site_id, saved.token) == (URL, SITE, TOKEN)
    assert SITE in rig.text
    assert "public" in rig.text.lower()  # the "site names are public" warning


def test_register_never_prints_the_token(rig: CliRig) -> None:
    rig.main(*register_args())

    assert TOKEN not in rig.text
    assert TOKEN not in rig.errors


def test_register_private_site(rig: CliRig) -> None:
    rig.main(*register_args("--private"))

    assert rig.api.sites[0]["public"] is False


def test_register_needs_an_api_url(rig: CliRig, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "DEFAULT_API_URL", "")
    args = [a for a in register_args() if a not in ("--api-url", URL)]

    code = rig.main(*args)

    assert code == 3
    assert "THIRST_API_URL" in rig.errors
    assert rig.api.sites == []


def test_register_uses_the_hosted_api_by_default(
    rig: CliRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "DEFAULT_API_URL", URL)
    args = [a for a in register_args() if a not in ("--api-url", URL)]

    assert rig.main(*args) == 0
    assert config.load().api_url == URL


def test_register_reads_the_api_url_from_the_environment(rig: CliRig) -> None:
    rig.env["THIRST_API_URL"] = URL
    args = [a for a in register_args() if a not in ("--api-url", URL)]

    assert rig.main(*args) == 0
    assert config.load().api_url == URL


def test_register_will_not_overwrite_an_existing_site_without_force(rig: CliRig) -> None:
    rig.register()

    code = rig.main(*register_args())

    assert code == 3
    assert "--force" in rig.errors
    assert rig.api.sites == []


def test_register_force_replaces_the_config(rig: CliRig) -> None:
    rig.register()
    rig.api.site_result = {"site_id": "s_bbbbbbbbbb", "token": "ab" * 32, "division": "D1"}

    assert rig.main(*register_args("--force")) == 0
    assert config.load().site_id == "s_bbbbbbbbbb"


def test_register_api_error_is_plain_and_saves_nothing(rig: CliRig) -> None:
    rig.api.site_error = ApiError("We only have data for Chennai, ...", "unknown_city", 400)

    code = rig.main(*register_args())

    assert code == 4
    assert "We only have data for Chennai" in rig.errors
    assert "Traceback" not in rig.errors
    assert not (rig.home / "config.toml").exists()


def test_register_rejects_a_bad_coverage_before_calling_the_server(rig: CliRig) -> None:
    code = rig.main(*register_args("--coverage", "1.5"))

    assert code == 2
    assert rig.api.sites == []


# ------------------------------------------------------------ plan


def plan_args(*extra: str) -> list[str]:
    return ["plan", "--hours", "6", "--deadline", DEADLINE, *extra]


def test_plan_prints_the_one_line_plan_and_savings(rig: CliRig) -> None:
    rig.register()

    code = rig.main(*plan_args("--gpu-model", "RTX-4090", "--gpus", "2"))

    assert code == 0
    assert "Plan: start 01:00, cap 85%, done by 02:00" in rig.text
    assert "14 to 29%" in rig.text and "9 to 18%" in rig.text and "10 to 13%" in rig.text
    assert rig.nvml_opens == 0  # nothing needed the GPU


def test_plan_sends_the_site_and_the_job(rig: CliRig) -> None:
    rig.register()

    rig.main(*plan_args("--gpu-model", "RTX-4090", "--gpus", "2", "--alpha", "0.3", "--pausable"))

    assert rig.api.plan_payloads == [
        {
            "site_id": SITE,
            "gpu_model": "RTX-4090",
            "gpu_count": 2,
            "work_hours": 6.0,
            "deadline": "2026-10-10T09:00:00+05:30",
            "pausable": True,
            "pausable_allowed": True,
            "alpha": 0.3,
        }
    ]
    assert rig.clients == [(URL, SITE)]


def test_plan_json_prints_the_raw_response(rig: CliRig) -> None:
    rig.register()

    rig.main(*plan_args("--gpu-model", "RTX-4090", "--gpus", "1", "--json"))

    assert json.loads(rig.text) == rig.api.plan_result


def test_plan_detects_the_gpu_with_nvml_when_not_given(rig: CliRig) -> None:
    rig.register()

    rig.main(*plan_args())

    payload = rig.api.plan_payloads[0]
    assert payload["gpu_model"] == "RTX-4090"
    assert payload["gpu_count"] == 2
    assert rig.nvml.shutdowns == 1  # NVML was closed again


def test_plan_without_a_gpu_asks_for_the_flags(rig: CliRig) -> None:
    rig.register()
    rig.nvml_error = GpuError("No NVIDIA GPU was found on this machine.")

    code = rig.main(*plan_args())

    assert code == 5
    assert "--gpu-model" in rig.errors
    assert rig.api.plan_payloads == []


def test_plan_needs_the_config(rig: CliRig) -> None:
    code = rig.main(*plan_args("--gpu-model", "RTX-4090", "--gpus", "1"))

    assert code == 3
    assert "Run `thirst register` first" in rig.errors


def test_plan_with_a_bad_alpha_is_a_usage_error(rig: CliRig) -> None:
    rig.register()

    code = rig.main(*plan_args("--gpu-model", "RTX-4090", "--gpus", "1", "--alpha", "0.55"))

    assert code == 2
    assert "alpha" in rig.errors
    assert rig.api.plan_payloads == []


def test_plan_api_error_is_shown_in_plain_words(rig: CliRig) -> None:
    rig.register()
    rig.api.plan_error = ApiError(
        "This job needs until 12:00 at full power.", "deadline_too_soon", 422
    )

    code = rig.main(*plan_args("--gpu-model", "RTX-4090", "--gpus", "1"))

    assert code == 4
    assert "This job needs until 12:00" in rig.errors


def test_plan_forces_non_pausable_on_windows(rig: CliRig) -> None:
    rig.register()
    rig.os_name = "nt"

    rig.main(*plan_args("--gpu-model", "RTX-4090", "--gpus", "1", "--pausable"))

    payload = rig.api.plan_payloads[0]
    assert payload["pausable"] is False
    assert payload["pausable_allowed"] is False
    assert "Windows" in rig.text


def test_plan_shows_the_pause_in_the_plan_line(rig: CliRig) -> None:
    rig.register()
    rig.api.plan_result = plan_response(rows=(("run", 0.85), ("pause", 0.0), ("run", 0.85)))

    rig.main(*plan_args("--gpu-model", "RTX-4090", "--gpus", "1", "--pausable"))

    assert "pause 02:00 to 03:00" in rig.text


# ------------------------------------------------------------ sync and receipts


JOB = "j_aaaaaaaaaaaa"


def queued_body(job: str = JOB) -> dict[str, Any]:
    return {"job_id": job, "site_id": SITE}


def test_sync_posts_queued_receipts(rig: CliRig) -> None:
    rig.register()
    outbox.enqueue(queued_body())
    outbox.enqueue(queued_body("j_bbbbbbbbbbbb"))

    code = rig.main("sync")

    assert code == 0
    assert [r["job_id"] for r in rig.api.receipts] == [JOB, "j_bbbbbbbbbbbb"]
    assert outbox.pending() == []
    assert "2" in rig.text and "posted" in rig.text.lower()


def test_sync_with_nothing_queued(rig: CliRig) -> None:
    rig.register()

    assert rig.main("sync") == 0
    assert "Nothing to send" in rig.text


def test_sync_reports_when_the_server_is_unreachable(rig: CliRig) -> None:
    rig.register()
    outbox.enqueue(queued_body())
    rig.api.receipt_error = ApiError("Could not reach the Thirst server.", "network_error", 0)

    code = rig.main("sync")

    assert code == 4
    assert "Could not reach" in rig.errors
    assert outbox.pending() == [JOB]


def test_sync_reports_rejected_receipts(rig: CliRig) -> None:
    rig.register()
    outbox.enqueue(queued_body())
    rig.api.receipt_error = ApiError("end_ts: more than 30 days old.", "invalid_field", 400)

    code = rig.main("sync")

    assert code == 4
    assert "more than 30 days old" in rig.text + rig.errors
    assert outbox.pending() == []


def test_receipt_show_prints_a_saved_receipt(rig: CliRig) -> None:
    body = {
        "site_id": SITE, "plan_id": "p_abcdefghij", "job_id": JOB,
        "start_ts": "2026-10-10T02:00:00+05:30", "end_ts": "2026-10-10T03:00:00+05:30",
        "slots": [
            {"hour": "2026-10-10T02:00:00+05:30", "run_kwh": 1.0, "idle_kwh": 0.0, "level": 1.0}
        ],
        "cap_applied": False, "cap_method": "none", "method": "nvml_energy",
        "gpu": {"name": "NVIDIA GeForce RTX 4090", "driver": "550", "count": 1},
    }  # fmt: skip
    receipt.save_receipt(body, None, status="queued")

    code = rig.main("receipt", "show", JOB)

    assert code == 0
    assert "Thirst receipt " + JOB in rig.text
    assert "thirst sync" in rig.text


def test_receipt_show_unknown_job(rig: CliRig) -> None:
    code = rig.main("receipt", "show", JOB)

    assert code == 2
    assert "No saved receipt" in rig.errors


# ------------------------------------------------------------ doctor


def test_doctor_all_good(rig: CliRig) -> None:
    rig.register()

    code = rig.main("doctor")

    assert code == 0
    assert "FAIL" not in rig.text
    for topic in ("Python", "Config", "API", "clock", "GPU", "energy counter", "power cap"):
        assert topic in rig.text
    assert TOKEN not in rig.text


def test_doctor_without_config_or_gpu_gives_hints(rig: CliRig) -> None:
    rig.nvml_error = GpuError("No NVIDIA GPU was found on this machine.")

    code = rig.main("doctor")

    assert code == 1
    assert rig.text.count("[FAIL]") >= 2  # config and GPU
    assert "thirst register" in rig.text
    assert "No NVIDIA GPU" in rig.text
    assert "Traceback" not in rig.text


def test_doctor_reports_an_unreachable_api(rig: CliRig) -> None:
    rig.register()
    rig.api.time_error = ApiError("Could not reach the Thirst server.", "network_error", 0)

    code = rig.main("doctor")

    assert code == 1
    assert "[FAIL] API" in rig.text
    assert "Could not reach the Thirst server." in rig.text


def test_doctor_flags_a_clock_that_is_off(rig: CliRig) -> None:
    rig.register()
    rig.api.server_time = ist("2026-10-10 01:05:00")  # 5 minutes ahead of the fake clock

    code = rig.main("doctor")

    assert code == 1
    assert "clock" in rig.text.lower() and "300" in rig.text


def test_doctor_small_clock_differences_are_fine(rig: CliRig) -> None:
    rig.register()
    rig.api.server_time = ist("2026-10-10 01:00:30")

    assert rig.main("doctor") == 0


def test_doctor_cap_permission_check_does_not_change_the_limit(rig: CliRig) -> None:
    rig.register()
    rig.nvml.gpus[0].current_limit_mw = 300_000

    rig.main("doctor")

    assert rig.nvml.gpus[0].current_limit_mw == 300_000
    assert rig.nvml.set_calls == [(0, 300_000)]  # "set the current limit to itself"


def test_doctor_without_cap_permission_suggests_sudo_and_checks_it(rig: CliRig) -> None:
    rig.register()
    rig.nvml.permission_denied = True
    rig.smi.returncode = 1

    code = rig.main("doctor")

    assert code == 1
    assert "sudo" in rig.text
    assert ["sudo", "-n", "nvidia-smi", "-L"] in rig.smi.calls


def test_doctor_accepts_sudo_when_nvml_has_no_permission(rig: CliRig) -> None:
    rig.register()
    rig.nvml.permission_denied = True

    assert rig.main("doctor") == 0
    assert "sudo" in rig.text


def test_doctor_names_the_leftover_restore_marker(rig: CliRig) -> None:
    rig.register()
    config.write_private(config.restore_marker_path(), json.dumps({"GPU-aaaa": 300_000}))

    code = rig.main("doctor")

    assert code == 1
    assert "doctor --restore" in rig.text


def test_doctor_reports_a_gpu_without_an_energy_counter(rig: CliRig) -> None:
    rig.register()
    rig.nvml.gpus[0].energy_mj = None

    rig.main("doctor")

    assert "power integration" in rig.text


def test_doctor_reports_an_unknown_gpu_model(rig: CliRig) -> None:
    rig.register()
    rig.nvml = FakeNvml(gpus=[FakeGpu("GPU-x", name="Mystery GPU 9000")])

    code = rig.main("doctor")

    assert code == 1
    assert "--gpu-model" in rig.text


def test_doctor_restore_puts_the_cap_back(rig: CliRig) -> None:
    rig.nvml.gpus[1].current_limit_mw = 382_500
    config.write_private(config.restore_marker_path(), json.dumps({"GPU-bbbb": 450_000}))

    code = rig.main("doctor", "--restore")

    assert code == 0
    assert rig.nvml.gpus[1].current_limit_mw == 450_000
    assert not powercap.marker_present()
    assert "GPU-bbbb" in rig.text


def test_doctor_restore_with_nothing_to_do(rig: CliRig) -> None:
    assert rig.main("doctor", "--restore") == 0
    assert "Nothing to restore" in rig.text


def test_doctor_restore_failure_prints_the_manual_command(rig: CliRig) -> None:
    config.write_private(config.restore_marker_path(), json.dumps({"GPU-bbbb": 450_000}))
    rig.nvml.set_failures_left = 99
    rig.smi = FakeSmi(returncode=1)

    code = rig.main("doctor", "--restore")

    assert code == 5
    assert "sudo nvidia-smi -i 1 -pl 450" in rig.errors
    assert powercap.marker_present()


# ------------------------------------------------------------ sweep


class FakeSweepWorkload:
    def __init__(self, rig: CliRig, tau85: float = 0.95) -> None:
        self.rig = rig
        self.tau85 = tau85

    def _level(self) -> float:
        gpu = self.rig.nvml.gpus[0]
        ratio = gpu.current_limit_mw / gpu.default_limit_mw
        return min((1.0, 0.85, 0.7), key=lambda known: abs(known - ratio))

    def _burn(self, seconds: float, watts: float) -> None:
        self.rig.clock.advance(seconds)
        for gpu in self.rig.nvml.gpus:
            gpu.energy_mj = (gpu.energy_mj or 0) + int(watts * seconds * 1000)

    def warmup(self, steps: int) -> None:
        self._burn(steps * 0.3, 300)

    def run(self, steps: int) -> None:
        tau = {1.0: 1.0, 0.85: self.tau85, 0.7: 0.8}[self._level()]
        eps = {1.0: 1.0, 0.85: 0.9, 0.7: 0.8}[self._level()]
        self._burn(steps * 0.3 / tau, 300 * eps * tau)

    def idle(self, seconds: float) -> None:
        self._burn(seconds, 40)


def sweep_rig(rig: CliRig, **kw: Any) -> None:
    rig.nvml = FakeNvml(gpus=[FakeGpu("GPU-aaaa", energy_mj=0)])
    rig.workload = FakeSweepWorkload(rig, **kw)


def test_sweep_writes_the_measured_numbers(rig: CliRig, tmp_path: Path) -> None:
    sweep_rig(rig)
    out = tmp_path / "powercap_sweep.json"

    code = rig.main("sweep", "--idle-seconds", "10", "--out", str(out))

    assert code == 0
    entry = json.loads(out.read_text(encoding="utf-8"))["gpus"]["RTX-4090"]
    assert entry["levels"]["0.85"]["tau"] == pytest.approx(0.95, rel=1e-3)
    assert "85%: tau 0.950, eps 0.900" in rig.text
    assert rig.nvml.gpus[0].current_limit_mw == 450_000  # the cap is back


def test_sweep_keeps_other_gpus_in_the_file(rig: CliRig, tmp_path: Path) -> None:
    sweep_rig(rig)
    out = tmp_path / "powercap_sweep.json"
    out.write_text(json.dumps({"gpus": {"RTX-3090": {"u": 0.5}}}), encoding="utf-8")

    rig.main("sweep", "--idle-seconds", "10", "--out", str(out))

    assert set(json.loads(out.read_text(encoding="utf-8"))["gpus"]) == {"RTX-3090", "RTX-4090"}


def test_sweep_that_fails_the_gates_does_not_overwrite_the_good_file(
    rig: CliRig, tmp_path: Path
) -> None:
    sweep_rig(rig, tau85=0.5)
    out = tmp_path / "powercap_sweep.json"

    code = rig.main("sweep", "--idle-seconds", "10", "--out", str(out))

    assert code == 5
    assert not out.exists()
    assert (tmp_path / "powercap_sweep.rejected.json").exists()
    assert "tau at 85%" in rig.errors + rig.text


def test_sweep_without_a_gpu(rig: CliRig, tmp_path: Path) -> None:
    rig.nvml_error = GpuError("No NVIDIA GPU was found on this machine.")

    code = rig.main("sweep", "--out", str(tmp_path / "x.json"))

    assert code == 5
    assert "No NVIDIA GPU" in rig.errors


def test_sweep_levels_option(rig: CliRig, tmp_path: Path) -> None:
    sweep_rig(rig)
    out = tmp_path / "s.json"

    rig.main("sweep", "--levels", "100,85", "--idle-seconds", "10", "--out", str(out))

    levels = json.loads(out.read_text(encoding="utf-8"))["gpus"]["RTX-4090"]["levels"]
    assert set(levels) == {"1.0", "0.85"}


# ------------------------------------------------------------ main()


def test_unexpected_errors_become_a_plain_message(
    rig: CliRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig.register()

    def boom(*args: Any) -> None:
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr("thirst.commands.cmd_sync", boom)

    code = rig.main("sync")

    assert code == 1
    assert "secret internal detail" not in rig.errors
    assert "--verbose" in rig.errors


def test_ctrl_c_in_a_quick_command_exits_130(rig: CliRig, monkeypatch: pytest.MonkeyPatch) -> None:
    rig.register()

    def interrupted(*args: Any) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("thirst.commands.cmd_sync", interrupted)

    assert rig.main("sync") == 130


def test_no_command_prints_the_help_and_exits_cleanly(rig: CliRig) -> None:
    code = rig.main()

    assert code == 0
    assert "usage: thirst" in rig.text
    assert "register" in rig.text and "doctor" in rig.text


def test_unknown_command_is_a_usage_error(rig: CliRig) -> None:
    assert rig.main("frobnicate") == 2


def test_help_exits_cleanly(rig: CliRig) -> None:
    assert rig.main("--help") == 0


# ------------------------------------------------------------ H1: register refuses cleartext


@pytest.mark.parametrize(
    "url",
    ["http://api.example.com", "https://user:pw@api.example.com", "ftp://x.example.com"],
)
def test_register_refuses_a_cleartext_url_before_any_request(rig: CliRig, url: str) -> None:
    args = register_args()
    args[args.index(URL)] = url

    code = rig.main(*args)

    assert code == 3
    assert "https" in rig.errors
    assert rig.api.sites == []
    assert rig.clients == []
    assert not (rig.home / "config.toml").exists()


def test_register_refuses_a_cleartext_url_from_the_environment(rig: CliRig) -> None:
    rig.env["THIRST_API_URL"] = "http://api.example.com"
    args = [a for a in register_args() if a not in ("--api-url", URL)]

    assert rig.main(*args) == 3
    assert rig.api.sites == []


def test_register_allows_http_to_loopback(rig: CliRig) -> None:
    args = register_args()
    args[args.index(URL)] = "http://127.0.0.1:8000"

    assert rig.main(*args) == 0
    assert rig.clients[0][0] == "http://127.0.0.1:8000"
