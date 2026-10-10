"""A fully faked CLI environment for the command tests (no network, GPU, process or real clock)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from thirst import config
from thirst.client import ReceiptPost
from thirst.context import Context
from thirst.nvml import NvmlApi
from thirst.process import InterruptFlag
from thirst_fakes import (
    FakeChild,
    FakeClock,
    FakeNvml,
    FakeSmi,
    FakeSpawn,
    RecordingGuard,
    ist,
)

TOKEN = "93ec2d429dfd3e011895ec55f2c376fed4534e588f27488ecc3bf1074433d80f"
SITE = "s_abcdefghij"
URL = "https://api.example.com"


def plan_response(
    start: str = "2026-10-10 01:00:00",
    rows: tuple[tuple[str, float], ...] = (("run", 0.85),),
    plan_id: str = "p_abcdefghij",
) -> dict[str, Any]:
    """A /plan response with one hourly schedule row per (state, level) from ``start``."""
    first = ist(start)
    schedule = [
        {
            "slot": (first + timedelta(hours=i)).isoformat(),
            "level": level,
            "state": state,
            "fraction": 1.0,
        }
        for i, (state, level) in enumerate(rows)
    ]
    levels = sorted({lv for st, lv in rows if st == "run"}, reverse=True)
    return {
        "plan_id": plan_id,
        "chosen": {
            "alpha": 0.5,
            "kind": "non_pausable",
            "start": first.isoformat(),
            "finish": (first + timedelta(hours=len(rows))).isoformat(),
            "level_summary": "/".join(f"{round(lv * 100)}%" for lv in levels),
            "schedule": schedule,
            "savings_ranges": {
                "water_pct": [14, 29],
                "co2_pct": [9, 18],
                "energy_pct": [10, 13],
            },
        },
        "notes": [],
    }


class FakeApi:
    """A scripted API client; records everything it was sent."""

    def __init__(self) -> None:
        self.plan_payloads: list[dict[str, Any]] = []
        self.receipts: list[dict[str, Any]] = []
        self.sites: list[dict[str, Any]] = []
        self.plan_result: dict[str, Any] = plan_response()
        self.plan_error: Exception | None = None
        self.receipt_error: Exception | None = None
        self.receipt_result: dict[str, Any] | None = None
        self.site_result: dict[str, Any] = {"site_id": SITE, "token": TOKEN, "division": "D1"}
        self.site_error: Exception | None = None
        self.server_time: datetime = ist("2026-10-10 01:00:00")
        self.time_error: Exception | None = None

    def post_plan(self, payload: Any) -> dict[str, Any]:
        self.plan_payloads.append(dict(payload))
        if self.plan_error is not None:
            raise self.plan_error
        return self.plan_result

    def post_site(self, payload: Any) -> dict[str, Any]:
        self.sites.append(dict(payload))
        if self.site_error is not None:
            raise self.site_error
        return self.site_result

    def get_site(self, site_id: str) -> dict[str, Any]:
        return {"site": {"site_id": site_id}}

    def post_receipt(self, payload: Any) -> ReceiptPost:
        self.receipts.append(dict(payload))
        if self.receipt_error is not None:
            raise self.receipt_error
        return ReceiptPost(response=self.receipt_result, duplicate=False)

    def get_server_time(self) -> datetime:
        if self.time_error is not None:
            raise self.time_error
        return self.server_time


class CliRig:
    """Builds a ``Context`` from fakes and runs ``thirst.__main__.main`` against it."""

    def __init__(self, home: Path) -> None:
        self.home = home
        self.clock = FakeClock("2026-10-10 01:00:00")
        self.api = FakeApi()
        self.api.receipt_result = _receipt_result()
        self.nvml = FakeNvml()
        self.child = FakeChild(self.clock, exit_after_s=600)
        self.inner_spawn = FakeSpawn(self.child)
        self.smi = FakeSmi()
        self.flag = InterruptFlag()
        self.out: list[str] = []
        self.err: list[str] = []
        self.log: list[str] = []
        self.env: dict[str, str] = {}
        self.os_name = "posix"
        self.nvml_error: Exception | None = None
        self.nvml_opens = 0
        self.workload: Any = None
        self.on_sleep: Callable[[CliRig], None] | None = None
        self.watts_per_gpu = 200.0
        self.clients: list[tuple[str, str]] = []

    # ------------------------------------------------------------ fakes wired into the context

    def sleep(self, seconds: float) -> None:
        self.clock.advance(seconds)
        for gpu in self.nvml.gpus:
            if gpu.energy_mj is not None:
                gpu.energy_mj += int(self.watts_per_gpu * seconds * 1000)
        if self.on_sleep is not None:
            self.on_sleep(self)

    def _spawn(self, argv: list[str], env: dict[str, str], log_path: object) -> FakeChild:
        self.child._born = self.clock.mono()  # noqa: SLF001
        return self.inner_spawn(argv, env, log_path)

    def _open_nvml(self) -> NvmlApi:
        self.nvml_opens += 1
        if self.nvml_error is not None:
            raise self.nvml_error
        return self.nvml

    def _make_client(self, api_url: str, token: str, site_id: str) -> FakeApi:
        self.clients.append((api_url, site_id))
        return self.api

    def _make_workload(self) -> Any:
        if self.workload is None:
            raise AssertionError("no workload configured for this test")
        return self.workload

    def context(self) -> Context:
        return Context(
            out=self.out.append,
            err=self.err.append,
            env=self.env,
            make_client=self._make_client,
            open_nvml=self._open_nvml,
            spawn=self._spawn,
            smi=self.smi,
            wall=self.clock.wall,
            mono=self.clock.mono,
            new_flag=lambda: self.flag,
            make_sleep=lambda flag: self.sleep,
            make_guard=lambda flag: RecordingGuard(self.log),
            make_workload=self._make_workload,
            os_name=self.os_name,
            meter_background=False,
        )

    # ------------------------------------------------------------ helpers for tests

    def register(self) -> None:
        config.save(config.Config(api_url=URL, site_id=SITE, token=TOKEN))

    def main(self, *argv: str) -> int:
        from thirst.__main__ import main

        return main(list(argv), context=self.context())

    @property
    def text(self) -> str:
        return "\n".join(self.out)

    @property
    def errors(self) -> str:
        return "\n".join(self.err)


def _receipt_result() -> dict[str, Any]:
    import json

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "receipt_response.json"
    return json.loads(fixture.read_text(encoding="utf-8"))
