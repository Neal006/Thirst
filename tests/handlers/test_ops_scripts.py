"""scripts/smoke.sh and bench_plan.py against a local stand-in for the API (plan 05.5, 05.12)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import bench_plan
import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
CURL = shutil.which("curl")


class Stub:
    """A fake API whose answers each test can change."""

    def __init__(self) -> None:
        self.status: dict[tuple[str, str], int] = {}
        self.cors = "http://localhost:5173"
        self.delay = 0.0
        self.seen: list[tuple[str, str, bytes, dict[str, str]]] = []

    def handler(self) -> type[BaseHTTPRequestHandler]:
        stub = self

        class H(BaseHTTPRequestHandler):
            def _reply(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                stub.seen.append((self.command, self.path, body, dict(self.headers)))
                if stub.delay:
                    import time

                    time.sleep(stub.delay)
                default = 204 if self.command == "OPTIONS" else 200
                code = stub.status.get((self.command, self.path), default)
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                if self.command == "OPTIONS" and stub.cors:
                    self.send_header("Access-Control-Allow-Origin", stub.cors)
                    self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
                    self.send_header("Access-Control-Allow-Headers", "content-type")
                payload = json.dumps({"plan_id": "p_aaaaaaaaaa"}).encode()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = do_OPTIONS = _reply  # noqa: N815

            def log_message(self, *args: Any) -> None:
                return

        return H


@pytest.fixture
def api() -> Iterator[tuple[Stub, str]]:
    stub = Stub()
    server = ThreadingHTTPServer(("127.0.0.1", 0), stub.handler())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield stub, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def smoke(
    url: str | None, origin: str = "http://localhost:5173"
) -> subprocess.CompletedProcess[str]:
    assert BASH
    args = [BASH, str(ROOT / "scripts" / "smoke.sh")]
    if url is not None:
        args.append(url)
    return subprocess.run(  # noqa: S603 - fixed script, local stub URL
        args, capture_output=True, text=True, timeout=60, env={**os.environ, "ORIGIN": origin}
    )


needs_shell = pytest.mark.skipif(not (BASH and CURL), reason="bash and curl are required")


@needs_shell
def test_smoke_passes_when_every_check_passes(api: tuple[Stub, str]) -> None:
    stub, url = api
    done = smoke(url)
    assert done.returncode == 0, done.stdout + done.stderr
    paths = [(m, p) for m, p, _, _ in stub.seen]
    assert ("GET", "/assumptions") in paths and ("POST", "/plan") in paths
    assert ("GET", "/leaderboard?division=D1") in paths and ("OPTIONS", "/plan") in paths
    assert done.stdout.count("PASS") == 4 and "FAIL" not in done.stdout


@needs_shell
def test_smoke_sends_a_plan_request_the_api_accepts(api: tuple[Stub, str]) -> None:
    from handlers import validation

    stub, url = api
    smoke(url)
    (body,) = [b for m, p, b, _ in stub.seen if (m, p) == ("POST", "/plan")]
    parsed = json.loads(body)
    from datetime import datetime, timedelta, timezone

    now = datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    inp = validation.plan_request(parsed, datetime.now(now.tzinfo))
    assert inp.deadline > datetime.now(now.tzinfo)  # a future deadline, in IST


@needs_shell
@pytest.mark.parametrize(
    ("method", "path", "label"),
    [
        ("GET", "/assumptions", "assumptions"),
        ("POST", "/plan", "plan"),
        ("GET", "/leaderboard?division=D1", "leaderboard"),
    ],
)
def test_smoke_fails_and_names_the_failing_check(
    api: tuple[Stub, str], method: str, path: str, label: str
) -> None:
    stub, url = api
    stub.status[(method, path)] = 500
    done = smoke(url)
    assert done.returncode != 0
    assert f"FAIL {label}" in done.stdout and "PASS" in done.stdout  # the others still ran


@needs_shell
def test_smoke_fails_when_cors_does_not_allow_the_origin(api: tuple[Stub, str]) -> None:
    stub, url = api
    stub.cors = "https://evil.example"
    done = smoke(url)
    assert done.returncode != 0 and "FAIL cors" in done.stdout


@needs_shell
def test_smoke_fails_on_a_wildcard_origin(api: tuple[Stub, str]) -> None:
    stub, url = api
    stub.cors = "*"
    assert smoke(url).returncode != 0


@needs_shell
def test_smoke_fails_when_nothing_is_listening() -> None:
    done = smoke("http://127.0.0.1:9")
    assert done.returncode != 0 and "FAIL" in done.stdout


@needs_shell
def test_smoke_without_an_url_prints_usage_and_exits_2() -> None:
    done = smoke(None)
    assert done.returncode == 2 and "usage" in (done.stdout + done.stderr).lower()


@needs_shell
def test_smoke_strips_a_trailing_slash(api: tuple[Stub, str]) -> None:
    stub, url = api
    assert smoke(url + "/").returncode == 0
    assert all("//" not in p for _, p, _, _ in stub.seen)


# bench_plan.py -----------------------------------------------------------------------------------


def test_percentiles_use_the_nearest_rank_method() -> None:
    data = [float(n) for n in range(1, 101)]
    assert bench_plan.percentile(data, 50) == 50.0
    assert bench_plan.percentile(data, 95) == 95.0
    assert bench_plan.percentile(data, 100) == 100.0
    assert bench_plan.percentile([7.0], 95) == 7.0
    with pytest.raises(ValueError, match="no samples"):
        bench_plan.percentile([], 50)


def test_bench_sends_one_warmup_plus_n_timed_requests(
    api: tuple[Stub, str], tmp_path: Path
) -> None:
    stub, url = api
    out = tmp_path / "bench.txt"
    result = bench_plan.run(url, n=5, out=out)
    plans = [s for s in stub.seen if (s[0], s[1]) == ("POST", "/plan")]
    assert len(plans) == 6  # 1 warm-up + 5 timed
    assert len(result.samples_ms) == 5 and result.failures == 0
    text = out.read_text(encoding="utf-8")
    for word in ("p50", "p95", "max", "n=5", url):
        assert word in text


def test_bench_passes_under_the_p95_limit_and_fails_over_it(
    api: tuple[Stub, str], tmp_path: Path
) -> None:
    stub, url = api
    assert bench_plan.run(url, n=3, out=tmp_path / "a.txt", limit_ms=2000).passed
    stub.delay = 0.05
    slow = bench_plan.run(url, n=3, out=tmp_path / "b.txt", limit_ms=10)
    assert not slow.passed and "FAIL" in (tmp_path / "b.txt").read_text(encoding="utf-8")


def test_bench_counts_errors_and_fails(api: tuple[Stub, str], tmp_path: Path) -> None:
    stub, url = api
    stub.status[("POST", "/plan")] = 503
    result = bench_plan.run(url, n=3, out=tmp_path / "c.txt")
    assert result.failures == 3 and not result.passed


def test_bench_main_exit_codes(api: tuple[Stub, str], tmp_path: Path) -> None:
    stub, url = api
    assert bench_plan.main([url, "--n", "2", "--out", str(tmp_path / "d.txt")]) == 0
    stub.status[("POST", "/plan")] = 500
    assert bench_plan.main([url, "--n", "2", "--out", str(tmp_path / "e.txt")]) == 1
    assert bench_plan.main([url, "--n", "0"]) == 2
