"""Starting, pausing and stopping the user's command (plan 04.6.c to 04.6.e, TRD 6.3).

On POSIX the command runs in its own session (``start_new_session=True``), so the whole process
group, data-loader workers included, can be stopped with SIGSTOP and continued with SIGCONT. A
stopped process cannot handle SIGTERM, so it must get SIGCONT first (the runner does that).
Windows has neither; there the CLI forces non-pausable jobs and ``pause`` raises.
The command is always an argument list and never goes through a shell.
"""

from __future__ import annotations

import contextlib
import logging
import os
import signal
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from types import FrameType, TracebackType
from typing import IO, Any, Protocol

logger = logging.getLogger(__name__)

_CHUNK = 65536


class PauseUnsupported(Exception):
    """This platform cannot pause the job (Windows)."""


class Child(Protocol):
    """A running job. ``wait`` returns the exit code, or ``None`` if it did not exit in time."""

    def poll(self) -> int | None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    def wait(self, timeout: float) -> int | None: ...


class InterruptFlag:
    """Set by SIGINT or SIGTERM. The main loop does the shutdown; handlers do no work."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def set(self) -> None:
        self._event.set()

    def is_set(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float) -> bool:
        return self._event.wait(timeout)


# SIGHUP comes when an SSH session drops: without a handler the CLI dies with the GPU still capped.
_HANGUP = getattr(signal, "SIGHUP", None)  # not on Windows
_GUARDED = tuple(sig for sig in (signal.SIGINT, signal.SIGTERM, _HANGUP) if sig is not None)


class SignalGuard:
    """While active, SIGINT, SIGTERM and (POSIX) SIGHUP only set the flag. Main thread only."""

    def __init__(self, flag: InterruptFlag) -> None:
        self._flag = flag
        self._old: dict[int, Any] = {}

    def _handler(self, signum: int, frame: FrameType | None) -> None:
        self._flag.set()

    def __enter__(self) -> SignalGuard:
        if threading.current_thread() is threading.main_thread():
            for sig in _GUARDED:
                self._old[sig] = signal.signal(sig, self._handler)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        for sig, old in self._old.items():
            signal.signal(sig, old)
        self._old.clear()


def _terminal_sink(name: str) -> Callable[[bytes], None]:
    stream = getattr(sys, name)
    raw = getattr(stream, "buffer", None)

    def write(data: bytes) -> None:
        try:
            if raw is not None:
                raw.write(data)
                raw.flush()
            else:
                stream.write(data.decode("utf-8", "replace"))
                stream.flush()
        except (OSError, ValueError):  # the terminal went away; keep the job running
            pass

    return write


def _open_log(path: Path | None) -> IO[bytes] | None:
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    return os.fdopen(os.open(path, flags, 0o600), "ab")


class SubprocessChild:
    """A ``Popen`` whose output is copied to the terminal and to a log file."""

    def __init__(self, argv: list[str], env: dict[str, str], log_path: Path | None) -> None:
        self._log = _open_log(log_path)
        self._log_lock = threading.Lock()
        try:
            self._proc = subprocess.Popen(  # noqa: S603 - argument list, never a shell
                argv,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **self._popen_options(),
            )
        except BaseException:
            if self._log is not None:
                self._log.close()
            raise
        self._threads = [
            self._tee(self._proc.stdout, _terminal_sink("stdout")),
            self._tee(self._proc.stderr, _terminal_sink("stderr")),
        ]

    @staticmethod
    def _popen_options() -> dict[str, Any]:
        return {}

    def _tee(self, source: IO[bytes] | None, sink: Callable[[bytes], None]) -> threading.Thread:
        def copy() -> None:
            if source is None:
                return
            read = getattr(source, "read1", source.read)
            while True:
                try:
                    chunk = read(_CHUNK)
                except (OSError, ValueError):  # the pipe broke or was closed: nothing more to copy
                    return
                if not chunk:
                    return
                sink(chunk)
                self._write_log(chunk)

        thread = threading.Thread(target=copy, name="thirst-tee", daemon=True)
        thread.start()
        return thread

    def _write_log(self, data: bytes) -> None:
        """Append to the log. If the log fails (disk full, removed drive) stop logging, but keep
        draining the pipe: a tee thread that died would leave the job blocked on a full pipe."""
        with self._log_lock:
            if self._log is None:
                return
            try:
                self._log.write(data)
                self._log.flush()
            except (OSError, ValueError):
                log, self._log = self._log, None
                with contextlib.suppress(OSError, ValueError):
                    log.close()

    def poll(self) -> int | None:
        return self._proc.poll()

    def wait(self, timeout: float) -> int | None:
        try:
            code = self._proc.wait(timeout)
        except subprocess.TimeoutExpired:
            return None
        for thread in self._threads:
            thread.join(2.0)
        with self._log_lock:
            if self._log is not None:
                self._log.close()
                self._log = None
        return code

    def pause(self) -> None:
        raise PauseUnsupported("pausing is not supported on this system")

    def resume(self) -> None:
        raise PauseUnsupported("pausing is not supported on this system")

    def terminate(self) -> None:
        self._proc.terminate()

    def kill(self) -> None:
        self._proc.kill()


class PosixChild(SubprocessChild):
    """Own session and process group; signals go to the whole group (data-loader workers too)."""

    @staticmethod
    def _popen_options() -> dict[str, Any]:
        return {"start_new_session": True}

    def _signal_group(self, sig: int) -> None:
        try:
            os.killpg(os.getpgid(self._proc.pid), sig)
        except ProcessLookupError:
            logger.debug("process group already gone")

    def pause(self) -> None:
        self._signal_group(signal.SIGSTOP)

    def resume(self) -> None:
        self._signal_group(signal.SIGCONT)

    def terminate(self) -> None:
        self._signal_group(signal.SIGTERM)

    def kill(self) -> None:
        self._signal_group(signal.SIGKILL)


def spawn_child(argv: list[str], env: dict[str, str], log_path: Path | None) -> Child:
    """Start the user's command. Raises ``OSError`` if it cannot be started."""
    child_class = SubprocessChild if os.name == "nt" else PosixChild
    return child_class(argv, env, log_path)
