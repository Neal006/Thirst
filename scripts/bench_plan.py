"""Benchmark POST /plan latency against a deployed API (plan step 05.5, PRD 8.1).

    python scripts/bench_plan.py "$API"                # 1 warm-up + 50 sequential requests
    python scripts/bench_plan.py "$API" --n 20 --out docs/bench_plan.txt

Prints p50, p95 and max in milliseconds, saves them to ``docs/bench_plan.txt`` and exits 1 when
the p95 is not under 2000 ms or any request fails. Standard library only.
"""

from __future__ import annotations

import argparse
import http.client
import json
import math
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))
LIMIT_MS = 2000.0
DEFAULT_N = 50
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "docs" / "bench_plan.txt"
TIMEOUT_S = 30


@dataclass(frozen=True, slots=True)
class Result:
    url: str
    samples_ms: tuple[float, ...]
    failures: int
    limit_ms: float

    @property
    def p95(self) -> float:
        return percentile(self.samples_ms, 95) if self.samples_ms else math.inf

    @property
    def passed(self) -> bool:
        return self.failures == 0 and bool(self.samples_ms) and self.p95 < self.limit_ms


def percentile(samples: Sequence[float], p: float) -> float:
    """Nearest-rank percentile: the smallest value with at least p% of the samples at or below."""
    if not samples:
        raise ValueError("no samples")
    ordered = sorted(samples)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def _body() -> bytes:
    deadline = datetime.now(IST) + timedelta(hours=30)
    return json.dumps(
        {
            "city": "Chennai",
            "cooling": "room_ac",
            "gpu_model": "RTX-4090",
            "gpu_count": 2,
            "work_hours": 4,
            "deadline": deadline.isoformat(timespec="seconds"),
            "pausable": False,
            "alpha": 0.5,
        }
    ).encode()


def _post_plan(url: str) -> float | None:
    """Milliseconds for one POST /plan, or None if it failed."""
    request = urllib.request.Request(  # noqa: S310 - the URL is the operator's own stack output
        f"{url}/plan", data=_body(), headers={"content-type": "application/json"}, method="POST"
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as reply:  # noqa: S310
            reply.read()
            ok = reply.status == 200
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
        return None
    return (time.perf_counter() - started) * 1000 if ok else None


def render(result: Result) -> str:
    n = len(result.samples_ms)
    lines = [
        f"POST /plan latency  {datetime.now(IST).isoformat(timespec='seconds')}",
        f"url={result.url}  n={n}  failures={result.failures}",
    ]
    if n:
        lines.append(
            f"p50={percentile(result.samples_ms, 50):.0f} ms  p95={result.p95:.0f} ms  "
            f"max={max(result.samples_ms):.0f} ms"
        )
    verdict = "PASS" if result.passed else "FAIL"
    lines.append(f"{verdict}: p95 limit is {result.limit_ms:.0f} ms and no request may fail")
    return "\n".join(lines) + "\n"


def run(
    url: str, n: int = DEFAULT_N, out: Path | None = None, limit_ms: float = LIMIT_MS
) -> Result:
    """One warm-up request, then ``n`` timed ones in a row. Writes the report to ``out``."""
    base = url.rstrip("/")
    _post_plan(base)  # warm-up: not counted, it pays for the cold start
    samples: list[float] = []
    failures = 0
    for _ in range(n):
        took = _post_plan(base)
        if took is None:
            failures += 1
        else:
            samples.append(took)
    result = Result(base, tuple(samples), failures, limit_ms)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(result), encoding="utf-8")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark POST /plan (plan step 05.5).")
    parser.add_argument("url", help="the ApiUrl stack output")
    parser.add_argument("--n", type=int, default=DEFAULT_N, help="timed requests (default 50)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if args.n < 1:
        print("error: --n must be at least 1", file=sys.stderr)
        return 2
    result = run(args.url, args.n, args.out)
    print(render(result), end="")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
