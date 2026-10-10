"""Plan 04.6.c/d/e: really starting, tee-ing, pausing and stopping the user's command."""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from pathlib import Path

import pytest
from thirst import process

PYTHON = sys.executable
POSIX_ONLY = pytest.mark.skipif(os.name == "nt", reason="SIGSTOP and process groups are POSIX only")


def wait_for(path: Path, text: str, seconds: float = 10.0) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if path.exists() and text in path.read_text(encoding="utf-8", errors="replace"):
            return
        time.sleep(0.05)
    raise AssertionError(f"{text!r} never appeared in {path}")


# ------------------------------------------------------------ interrupt flag and signals


def test_interrupt_flag_starts_clear_and_wakes_waiters() -> None:
    flag = process.InterruptFlag()
    assert flag.is_set() is False
    assert flag.wait(0.01) is False

    flag.set()

    assert flag.is_set() is True
    assert flag.wait(5) is True


def test_signal_guard_sets_the_flag_and_restores_the_old_handlers() -> None:
    flag = process.InterruptFlag()
    before = signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)

    with process.SignalGuard(flag):
        handler = signal.getsignal(signal.SIGINT)
        assert callable(handler)
        handler(signal.SIGINT, None)  # type: ignore[operator]
        assert flag.is_set()  # and it did not raise KeyboardInterrupt
        term = signal.getsignal(signal.SIGTERM)
        assert callable(term)

    assert (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)) == before


def test_signal_guard_in_a_thread_does_not_crash() -> None:
    flag = process.InterruptFlag()
    errors: list[BaseException] = []

    def work() -> None:
        try:
            with process.SignalGuard(flag):
                pass
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    thread = threading.Thread(target=work)
    thread.start()
    thread.join()

    assert errors == []


# ------------------------------------------------------------ starting and stopping


def spawn(code: str, tmp_path: Path, extra_env: dict[str, str] | None = None) -> process.Child:
    env = {**os.environ, **(extra_env or {})}
    return process.spawn_child([PYTHON, "-c", code], env, tmp_path / "job.log")


def test_exit_code_is_reported(tmp_path: Path) -> None:
    child = spawn("import sys; sys.exit(3)", tmp_path)

    assert child.wait(20) == 3
    assert child.poll() == 3


def test_poll_is_none_while_running_and_wait_times_out(tmp_path: Path) -> None:
    child = spawn("import time; time.sleep(30)", tmp_path)
    try:
        assert child.poll() is None
        assert child.wait(0.2) is None
    finally:
        child.kill()
        child.wait(10)


def test_output_is_tee_d_to_the_log_file_and_the_terminal(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    child = spawn("import sys; print('to-out'); print('to-err', file=sys.stderr)", tmp_path)

    child.wait(20)

    log = (tmp_path / "job.log").read_text(encoding="utf-8")
    assert "to-out" in log and "to-err" in log
    seen = capfd.readouterr()
    assert "to-out" in seen.out
    assert "to-err" in seen.err


def test_the_environment_reaches_the_command(tmp_path: Path) -> None:
    child = spawn(
        "import os, sys; sys.exit(7 if os.environ.get('CUDA_DEVICE_ORDER') == 'PCI_BUS_ID' else 1)",
        tmp_path,
        {"CUDA_DEVICE_ORDER": "PCI_BUS_ID"},
    )

    assert child.wait(20) == 7


def test_the_command_is_not_run_through_a_shell(tmp_path: Path) -> None:
    marker = tmp_path / "pwned"
    child = process.spawn_child(
        [PYTHON, "-c", "import sys; sys.exit(0)", f"; touch {marker}"], dict(os.environ), None
    )

    child.wait(20)

    assert not marker.exists()


def test_terminate_stops_a_sleeping_command(tmp_path: Path) -> None:
    child = spawn("import time; time.sleep(60)", tmp_path)
    time.sleep(0.3)

    child.terminate()

    assert child.wait(10) is not None


def test_kill_stops_a_command_that_ignores_sigterm(tmp_path: Path) -> None:
    code = (
        "import signal, time, sys\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "print('ready', flush=True)\n"
        "time.sleep(60)\n"
    )
    child = spawn(code, tmp_path)
    wait_for(tmp_path / "job.log", "ready")

    child.kill()

    assert child.wait(10) is not None


def test_missing_command_raises_an_os_error(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        process.spawn_child(["definitely-not-a-real-program-xyz"], dict(os.environ), None)


def test_no_log_path_means_no_log_file(tmp_path: Path) -> None:
    child = process.spawn_child([PYTHON, "-c", "print('x')"], dict(os.environ), None)

    assert child.wait(20) == 0


@pytest.mark.skipif(os.name != "nt", reason="the plain child is the Windows implementation")
def test_windows_child_cannot_pause(tmp_path: Path) -> None:
    child = spawn("import time; time.sleep(30)", tmp_path)
    try:
        with pytest.raises(process.PauseUnsupported):
            child.pause()
    finally:
        child.kill()
        child.wait(10)


# ------------------------------------------------------------ POSIX pause and resume

COUNTER = (
    "import sys, time\n"
    "path = sys.argv[1]\n"
    "n = 0\n"
    "while True:\n"
    "    n += 1\n"
    "    open(path, 'w').write(str(n))\n"
    "    time.sleep(0.05)\n"
)


def count(path: Path) -> int:
    try:
        return int(path.read_text(encoding="utf-8") or 0)
    except (FileNotFoundError, ValueError):
        return 0


@POSIX_ONLY
def test_pause_really_stops_the_process_and_resume_continues_it(tmp_path: Path) -> None:
    counter = tmp_path / "count.txt"
    child = process.spawn_child([PYTHON, "-c", COUNTER, str(counter)], dict(os.environ), None)
    try:
        time.sleep(0.5)
        child.pause()
        time.sleep(0.2)
        frozen = count(counter)
        time.sleep(0.6)
        assert count(counter) == frozen  # no progress while stopped
        child.resume()
        time.sleep(0.6)
        assert count(counter) > frozen
    finally:
        child.kill()
        child.wait(10)


# A training script that cleans up on SIGTERM (checkpoint, close files). Linux kills a stopped
# process at once for a SIGTERM it does not handle, but a handled one waits for SIGCONT.
HANDLES_SIGTERM = (
    "import signal, sys\n"
    "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))\n"
) + COUNTER


@POSIX_ONLY
def test_a_stopped_process_needs_sigcont_before_sigterm(tmp_path: Path) -> None:
    counter = tmp_path / "count.txt"
    child = process.spawn_child(
        [PYTHON, "-c", HANDLES_SIGTERM, str(counter)], dict(os.environ), None
    )
    try:
        time.sleep(0.3)
        child.pause()
        child.terminate()
        assert child.wait(1.0) is None  # still stopped: it cannot handle SIGTERM
        child.resume()
        assert child.wait(10) is not None  # now the pending SIGTERM is delivered
    finally:
        child.kill()
        child.wait(10)


@POSIX_ONLY
def test_the_whole_process_group_is_paused_including_workers(tmp_path: Path) -> None:
    counter = tmp_path / "worker.txt"
    parent = (
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {COUNTER!r}, {str(counter)!r}])\n"
        "time.sleep(60)\n"
    )
    child = process.spawn_child([PYTHON, "-c", parent], dict(os.environ), None)
    try:
        time.sleep(0.8)
        child.pause()
        time.sleep(0.2)
        frozen = count(counter)
        time.sleep(0.6)
        assert count(counter) == frozen
    finally:
        child.resume()
        child.terminate()
        child.kill()
        child.wait(10)
