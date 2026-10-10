"""Everything the commands touch outside themselves, bundled so tests can swap each piece.

``default_context`` wires the real thing (stdout, the HTTP client, real NVML, real processes).
Tests build a ``Context`` with fakes: no network, no GPU, no real child process, no real clock.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from .client import Client, ReceiptPost
from .meter import now_ist
from .nvml import NvmlApi, open_nvml
from .powercap import SmiRunner, run_command
from .process import InterruptFlag, SignalGuard, spawn_child
from .runner import Spawn
from .sweep import TorchResnetWorkload, Workload


class ApiClient(Protocol):
    """The part of ``Client`` the commands use."""

    def post_plan(self, payload: Mapping[str, Any]) -> dict[str, Any]: ...
    def post_site(self, payload: Mapping[str, Any]) -> dict[str, Any]: ...
    def get_site(self, site_id: str) -> dict[str, Any]: ...
    def post_receipt(self, payload: Mapping[str, Any]) -> ReceiptPost: ...
    def get_server_time(self) -> datetime: ...


@dataclass(frozen=True)
class Context:
    out: Callable[[str], Any]
    err: Callable[[str], Any]
    env: Mapping[str, str]
    make_client: Callable[[str, str, str], ApiClient]  # (api_url, token, site_id)
    open_nvml: Callable[[], NvmlApi]
    spawn: Spawn
    smi: SmiRunner
    wall: Callable[[], datetime]
    mono: Callable[[], float]
    new_flag: Callable[[], InterruptFlag]
    make_sleep: Callable[[InterruptFlag], Callable[[float], Any]]
    make_guard: Callable[[InterruptFlag], AbstractContextManager[Any]]
    make_workload: Callable[[], Workload]
    os_name: str
    meter_background: bool = True


def _client(api_url: str, token: str, site_id: str) -> ApiClient:
    return Client(api_url, token=token, site_id=site_id)


def default_context(out: Callable[[str], Any], err: Callable[[str], Any]) -> Context:
    return Context(
        out=out,
        err=err,
        env=os.environ,
        make_client=_client,
        open_nvml=open_nvml,
        spawn=spawn_child,
        smi=run_command,
        wall=now_ist,
        mono=time.monotonic,
        new_flag=InterruptFlag,
        make_sleep=lambda flag: flag.wait,
        make_guard=SignalGuard,
        make_workload=TorchResnetWorkload,
        os_name=os.name,
    )


def stdout_writer() -> Callable[[str], Any]:
    """Line writer for stdout that never crashes on a console that cannot show a character."""

    def write(text: str) -> None:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe = text.encode(encoding, "replace").decode(encoding, "replace")
        sys.stdout.write(safe + "\n")
        sys.stdout.flush()

    return write


def stderr_writer() -> Callable[[str], Any]:
    def write(text: str) -> None:
        encoding = getattr(sys.stderr, "encoding", None) or "utf-8"
        safe = text.encode(encoding, "replace").decode(encoding, "replace")
        sys.stderr.write(safe + "\n")
        sys.stderr.flush()

    return write
