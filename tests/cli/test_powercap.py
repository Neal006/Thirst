"""Plan 04.4: the power-cap controller with guaranteed restore (fake NVML, fake nvidia-smi)."""

from __future__ import annotations

import json
import logging
import signal
import subprocess
from pathlib import Path
from typing import Any

import pytest
from thirst import config, powercap
from thirst_fakes import FakeGpu, FakeNvml, FakeSmi

NO_SLEEP = lambda seconds: None  # noqa: E731


def one_gpu(**changes: Any) -> FakeNvml:
    gpu = FakeGpu("GPU-aaaa", **changes)
    return FakeNvml(gpus=[gpu])


def make_cap(api: FakeNvml, smi: FakeSmi, **options: Any) -> powercap.PowerCap:
    options.setdefault("sleep", NO_SLEEP)
    return powercap.PowerCap(api, tuple(range(api.device_count())), smi=smi, **options)


def marker() -> dict[str, Any]:
    return json.loads(config.restore_marker_path().read_text(encoding="utf-8"))


# ------------------------------------------------------------ targets


def test_target_is_level_times_default_limit(smi: FakeSmi) -> None:
    api = one_gpu()  # default 450 W
    cap = make_cap(api, smi)

    assert cap.apply(0.85) is True

    assert api.set_calls == [(0, 382_500)]
    assert cap.applied is True
    assert cap.cap_method == "nvml"


def test_target_is_clamped_up_to_the_minimum(smi: FakeSmi) -> None:
    api = one_gpu(min_limit_mw=400_000)
    cap = make_cap(api, smi)

    cap.apply(0.7)  # 315 W would be below the 400 W floor

    assert api.set_calls == [(0, 400_000)]


def test_target_is_clamped_down_to_the_maximum(smi: FakeSmi) -> None:
    api = one_gpu(default_limit_mw=450_000, max_limit_mw=420_000)
    cap = make_cap(api, smi)

    cap.apply(1.0)

    assert api.set_calls == [(0, 420_000)]


@pytest.mark.parametrize("level", [0.0, -0.5, 1.5, float("nan")])
def test_bad_levels_are_rejected(smi: FakeSmi, level: float) -> None:
    cap = make_cap(one_gpu(), smi)

    with pytest.raises(ValueError, match="level"):
        cap.apply(level)


# ------------------------------------------------------------ restore


def test_restore_goes_back_to_the_original_not_the_default(smi: FakeSmi) -> None:
    api = one_gpu(current_limit_mw=300_000, default_limit_mw=450_000)
    cap = make_cap(api, smi)
    cap.apply(0.85)

    failed = cap.restore()

    assert failed == ()
    assert api.gpus[0].current_limit_mw == 300_000
    assert api.set_calls[-1] == (0, 300_000)


def test_restore_is_idempotent(smi: FakeSmi) -> None:
    api = one_gpu(current_limit_mw=300_000)
    cap = make_cap(api, smi)
    cap.apply(0.85)

    cap.restore()
    cap.restore()

    assert api.set_calls.count((0, 300_000)) == 1


def test_restore_without_apply_touches_nothing(smi: FakeSmi) -> None:
    api = one_gpu()
    cap = make_cap(api, smi)

    assert cap.restore() == ()
    assert api.set_calls == []
    assert not config.restore_marker_path().exists()


def test_level_change_applies_again_and_restore_still_uses_the_first_original(
    smi: FakeSmi,
) -> None:
    api = one_gpu(current_limit_mw=300_000)
    cap = make_cap(api, smi)

    cap.apply(0.85)
    cap.apply(0.7)
    cap.restore()

    assert api.set_calls == [(0, 382_500), (0, 315_000), (0, 300_000)]


def test_restore_is_retried_three_times(smi: FakeSmi) -> None:
    api = one_gpu(current_limit_mw=300_000)
    cap = make_cap(api, smi)
    cap.apply(0.85)
    api.set_failures_left = 2

    failed = cap.restore()

    assert failed == ()
    assert api.gpus[0].current_limit_mw == 300_000


def test_restore_failure_prints_the_manual_command_and_keeps_the_marker(
    smi: FakeSmi, caplog: pytest.LogCaptureFixture
) -> None:
    api = one_gpu(current_limit_mw=300_000)
    cap = make_cap(api, smi, allow_sudo=False)
    cap.apply(0.85)
    api.set_failures_left = 99

    with caplog.at_level(logging.ERROR):
        failed = cap.restore()

    assert failed == ("sudo nvidia-smi -i 0 -pl 300",)
    assert "sudo nvidia-smi -i 0 -pl 300" in caplog.text
    assert config.restore_marker_path().exists()


def test_a_failed_gpu_is_retried_on_the_next_restore_call(smi: FakeSmi) -> None:
    api = one_gpu(current_limit_mw=300_000)
    cap = make_cap(api, smi, allow_sudo=False)
    cap.apply(0.85)
    api.set_failures_left = 99
    assert cap.restore() != ()

    api.set_failures_left = 0

    assert cap.restore() == ()
    assert api.gpus[0].current_limit_mw == 300_000
    assert not config.restore_marker_path().exists()


def test_restore_falls_back_to_sudo_when_nvml_says_no_permission(smi: FakeSmi) -> None:
    api = one_gpu(current_limit_mw=300_000)
    api.permission_denied = True
    cap = make_cap(api, smi)
    cap.apply(0.85)  # via sudo nvidia-smi

    assert cap.restore() == ()

    assert ["sudo", "-n", "nvidia-smi", "-i", "0", "-pl", "300"] in smi.calls


# ------------------------------------------------------------ marker


def test_marker_is_written_before_the_first_change_and_removed_after_restore() -> None:
    seen: list[dict[str, Any]] = []

    class Spy(FakeNvml):
        def set_limit_mw(self, index: int, milliwatts: int) -> None:
            seen.append(marker())
            super().set_limit_mw(index, milliwatts)

    api = Spy(gpus=[FakeGpu("GPU-aaaa", current_limit_mw=300_000)])
    cap = make_cap(api, FakeSmi())

    cap.apply(0.85)

    assert seen == [{"GPU-aaaa": 300_000}]
    cap.restore()
    assert not config.restore_marker_path().exists()


def test_marker_keeps_the_first_original_across_level_changes(smi: FakeSmi) -> None:
    api = one_gpu(current_limit_mw=300_000)
    cap = make_cap(api, smi)

    cap.apply(0.85)
    cap.apply(0.7)

    assert marker() == {"GPU-aaaa": 300_000}


def test_recover_from_marker_restores_and_removes_it(smi: FakeSmi) -> None:
    api = FakeNvml(gpus=[FakeGpu("GPU-aaaa"), FakeGpu("GPU-bbbb", current_limit_mw=200_000)])
    config.write_private(config.restore_marker_path(), json.dumps({"GPU-bbbb": 330_000}))

    result = powercap.recover_from_marker(api, smi, sleep=NO_SLEEP)

    assert result.restored == ("GPU-bbbb",)
    assert result.failed == ()
    assert api.gpus[1].current_limit_mw == 330_000
    assert not config.restore_marker_path().exists()


def test_recover_reports_gpus_that_are_gone(smi: FakeSmi) -> None:
    api = one_gpu()
    config.write_private(config.restore_marker_path(), json.dumps({"GPU-zzzz": 330_000}))

    result = powercap.recover_from_marker(api, smi, sleep=NO_SLEEP)

    assert result.failed == ("GPU-zzzz",)


def test_recover_with_no_marker_does_nothing(smi: FakeSmi) -> None:
    result = powercap.recover_from_marker(one_gpu(), smi, sleep=NO_SLEEP)

    assert result.restored == () and result.failed == ()


def test_recover_ignores_a_corrupt_marker(smi: FakeSmi) -> None:
    config.write_private(config.restore_marker_path(), "{nope")

    result = powercap.recover_from_marker(one_gpu(), smi, sleep=NO_SLEEP)

    assert result.restored == ()
    assert result.failed == ()


def test_marker_present_helper() -> None:
    assert powercap.marker_present() is False
    config.write_private(config.restore_marker_path(), "{}")
    assert powercap.marker_present() is True


# ------------------------------------------------------------ permission fallbacks


def test_no_permission_falls_back_to_non_interactive_sudo(smi: FakeSmi) -> None:
    api = one_gpu()
    api.permission_denied = True
    cap = make_cap(api, smi)

    assert cap.apply(0.85) is True

    assert smi.calls == [["sudo", "-n", "nvidia-smi", "-i", "0", "-pl", "382"]]
    assert cap.cap_method == "nvidia_smi"
    assert cap.applied is True


def test_if_sudo_fails_too_the_job_goes_on_uncapped_with_a_warning() -> None:
    api = one_gpu()
    api.permission_denied = True
    cap = make_cap(api, FakeSmi(returncode=1))

    assert cap.apply(0.85) is False

    assert cap.applied is False
    assert cap.cap_method == "none"
    assert any("uncapped" in note for note in cap.notes)
    assert cap.restore() == ()


def test_sudo_can_be_switched_off(smi: FakeSmi) -> None:
    api = one_gpu()
    api.permission_denied = True
    cap = make_cap(api, smi, allow_sudo=False)

    assert cap.apply(0.85) is False
    assert smi.calls == []


def test_one_gpu_failing_makes_applied_false_but_caps_the_others() -> None:
    api = FakeNvml(gpus=[FakeGpu("GPU-a"), FakeGpu("GPU-b")])
    smi = FakeSmi(returncode=1)
    original = api.set_limit_mw

    def flaky(index: int, milliwatts: int) -> None:
        if index == 1:
            raise powercap.LimitPermissionDenied
        original(index, milliwatts)

    api.set_limit_mw = flaky  # type: ignore[method-assign]
    cap = make_cap(api, smi)

    assert cap.apply(0.85) is False
    assert api.gpus[0].current_limit_mw == 382_500


# ------------------------------------------------------------ clock-lock fallback


def test_unsupported_power_limit_falls_back_to_a_clock_lock(smi: FakeSmi) -> None:
    api = one_gpu(max_clock_mhz=2000)
    api.limit_unsupported = True
    cap = make_cap(api, smi, allow_sudo=False)

    assert cap.apply(0.85) is True

    assert cap.cap_method == "clock_lock"
    assert smi.calls == [["nvidia-smi", "-i", "0", "-lgc", "210,1700"]]


def test_fallback_clocks_flag_skips_the_power_limit(smi: FakeSmi) -> None:
    api = one_gpu(max_clock_mhz=2000)
    cap = make_cap(api, smi, fallback_clocks=True)

    cap.apply(0.7)

    assert api.set_calls == []
    assert smi.calls[0][-2:] == ["-lgc", "210,1400"]
    assert cap.cap_method == "clock_lock"


def test_clock_lock_is_reset_on_restore(smi: FakeSmi) -> None:
    api = one_gpu()
    cap = make_cap(api, smi, fallback_clocks=True)
    cap.apply(0.85)

    assert cap.restore() == ()

    assert ["nvidia-smi", "-i", "0", "-rgc"] in smi.calls
    assert not config.restore_marker_path().exists()


def test_clock_lock_is_recorded_in_the_marker(smi: FakeSmi) -> None:
    api = one_gpu(current_limit_mw=300_000)
    cap = make_cap(api, smi, fallback_clocks=True)

    cap.apply(0.85)

    assert marker()["_clock_locked"] == ["GPU-aaaa"]
    assert marker()["GPU-aaaa"] == 300_000


def test_recover_resets_clock_locks_too(smi: FakeSmi) -> None:
    api = one_gpu()
    body = {"GPU-aaaa": 450_000, "_clock_locked": ["GPU-aaaa"]}
    config.write_private(config.restore_marker_path(), json.dumps(body))

    result = powercap.recover_from_marker(api, smi, sleep=NO_SLEEP)

    assert result.failed == ()
    assert ["nvidia-smi", "-i", "0", "-rgc"] in smi.calls


# ------------------------------------------------------------ every exit path


def test_context_manager_restores_on_normal_exit(smi: FakeSmi) -> None:
    api = one_gpu(current_limit_mw=300_000)

    with make_cap(api, smi) as cap:
        cap.apply(0.85)
        assert api.gpus[0].current_limit_mw == 382_500

    assert api.gpus[0].current_limit_mw == 300_000


def test_context_manager_restores_when_the_body_raises(smi: FakeSmi) -> None:
    api = one_gpu(current_limit_mw=300_000)

    with pytest.raises(RuntimeError, match="boom"), make_cap(api, smi) as cap:
        cap.apply(0.85)
        raise RuntimeError("boom")

    assert api.gpus[0].current_limit_mw == 300_000


def test_atexit_hook_is_registered_inside_and_removed_after(
    smi: FakeSmi, monkeypatch: pytest.MonkeyPatch
) -> None:
    registered: list[Any] = []
    unregistered: list[Any] = []
    monkeypatch.setattr(powercap.atexit, "register", lambda fn: registered.append(fn) or fn)
    monkeypatch.setattr(powercap.atexit, "unregister", unregistered.append)
    api = one_gpu(current_limit_mw=300_000)

    with make_cap(api, smi) as cap:
        cap.apply(0.85)
        assert len(registered) == 1
        registered[0]()  # what the interpreter would do at exit if we never got to __exit__
        assert api.gpus[0].current_limit_mw == 300_000

    assert unregistered == registered


@pytest.mark.parametrize(
    ("sig", "expected"),
    [(signal.SIGINT, KeyboardInterrupt), (signal.SIGTERM, SystemExit)],
)
def test_signals_restore_then_stop_the_program(
    smi: FakeSmi, sig: signal.Signals, expected: type[BaseException]
) -> None:
    api = one_gpu(current_limit_mw=300_000)
    before_int = signal.getsignal(signal.SIGINT)
    before_term = signal.getsignal(signal.SIGTERM)

    with make_cap(api, smi, handle_signals=True) as cap:
        cap.apply(0.85)
        handler = signal.getsignal(sig)
        assert callable(handler)
        with pytest.raises(expected):
            handler(sig, None)  # type: ignore[operator]
        assert api.gpus[0].current_limit_mw == 300_000

    assert signal.getsignal(signal.SIGINT) == before_int
    assert signal.getsignal(signal.SIGTERM) == before_term


def test_signal_handlers_are_not_touched_by_default(smi: FakeSmi) -> None:
    before = signal.getsignal(signal.SIGINT)

    with make_cap(one_gpu(), smi):
        assert signal.getsignal(signal.SIGINT) == before


# ------------------------------------------------------------ subprocess safety


def test_default_smi_runs_a_list_without_a_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run(argv: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(powercap.subprocess, "run", fake_run)
    monkeypatch.setattr(powercap.shutil, "which", lambda name: None)

    assert powercap.run_command(["nvidia-smi", "-i", "0", "-pl", "300"]) == 0

    assert captured["argv"] == ["nvidia-smi", "-i", "0", "-pl", "300"]
    assert captured["kwargs"].get("shell", False) is False
    assert captured["kwargs"]["timeout"] > 0


def test_nvidia_smi_and_sudo_run_by_their_full_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    # TODO 4.2: a bare name is looked up in PATH, which a writable directory could hijack.
    captured: dict[str, Any] = {}

    def fake_run(argv: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, 0)

    paths = {"nvidia-smi": "/usr/bin/nvidia-smi", "sudo": "/usr/bin/sudo"}
    monkeypatch.setattr(powercap.subprocess, "run", fake_run)
    monkeypatch.setattr(powercap.shutil, "which", paths.get)

    powercap.run_command(["sudo", "-n", "nvidia-smi", "-i", "0", "-pl", "300"])

    assert captured["argv"] == [
        "/usr/bin/sudo",
        "-n",
        "/usr/bin/nvidia-smi",
        "-i",
        "0",
        "-pl",
        "300",
    ]


def test_only_known_tools_are_resolved(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(powercap.shutil, "which", lambda name: f"/bin/{name}")

    assert powercap.absolute_argv(["nvidia-smi", "-i", "300", "-pl", "sudo-ish"]) == [
        "/bin/nvidia-smi",
        "-i",
        "300",
        "-pl",
        "sudo-ish",
    ]


def test_missing_nvidia_smi_is_a_failure_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(argv: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError

    monkeypatch.setattr(powercap.subprocess, "run", fake_run)

    assert powercap.run_command(["nvidia-smi", "-pl", "1"]) != 0


def test_a_hanging_command_times_out_as_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(argv: Any, **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(argv, 1)

    monkeypatch.setattr(powercap.subprocess, "run", fake_run)

    assert powercap.run_command(["sudo", "-n", "nvidia-smi"]) != 0


def test_marker_path_is_under_the_thirst_home(thirst_home: Path) -> None:
    assert config.restore_marker_path() == thirst_home / "restore.json"
