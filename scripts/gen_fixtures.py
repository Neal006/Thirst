"""Write tests/fixtures/{plan,receipt,leaderboard}_response.json from the engine.

Plan steps 02.7.k and 02.8. Run with ``make fixtures`` (or ``python scripts/gen_fixtures.py``).
The frontend builds against these files, so they come from the real engine, never hand-edited.
Everything is deterministic: fixed submit time, the saved sample forecast, no wall clock.
The leaderboard sites are demo data and are labelled "(simulated)" in name and flag.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from engine import score  # noqa: E402
from engine.factors import Factors, load_factors  # noqa: E402
from engine.forecast import load_sample_rows  # noqa: E402
from engine.planner import PlanRequest, plan_from_rows  # noqa: E402
from engine.units import IST  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
SUBMIT = datetime(2026, 10, 9, 21, 14, tzinfo=IST)
DEADLINE = datetime(2026, 10, 10, 9, 0, tzinfo=IST)
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=IST)
PLAN_ID = "p_7f3a2b9c1d"
SITE_ID = "s_abcdefghij"
JOB_ID = "j_abcdefghijkl"


def build_plan(fx: Factors) -> dict[str, Any]:
    """PRD 6.1 default example: Chennai, room AC, 2 x RTX 4090, 6 h, deadline 09:00, pausable."""
    req = PlanRequest(
        city="Chennai", cooling="room_ac", pue_user=None, gpu_model="RTX-4090", gpu_count=2,
        work_hours=6.0, deadline=DEADLINE, pausable=True, alpha=0.5, submit_ts=SUBMIT,
        site_id=SITE_ID,
    )
    result = plan_from_rows(req, load_sample_rows("Chennai"), fx)
    result["plan_id"] = PLAN_ID
    return result


def receipt_from_plan(
    plan: dict[str, Any], which: str, *, shift_hours: int = 0, scale: float = 1.0,
    job_id: str = JOB_ID, method: str = "nvml_energy",
) -> dict[str, Any]:
    """A receipt that follows a plan entry, optionally shifted in time or scaled in energy."""
    entry = plan[which]
    hours = plan["forecast_snapshot"]["slots"]
    slots = []
    for h, (kwh, overlay) in enumerate(zip(entry["gpu_kwh"], entry["series_overlay"], strict=True)):
        if kwh <= 0:
            continue
        running = overlay["state"] == "run"
        hour = datetime.fromisoformat(hours[h]) + timedelta(hours=shift_hours)
        slots.append({
            "hour": hour.isoformat(),
            "run_kwh": round(kwh * scale, 6) if running else 0.0,
            "idle_kwh": 0.0 if running else round(kwh * scale, 6),
            "level": overlay["level"] or 1.0,
        })
    end = datetime.fromisoformat(slots[-1]["hour"]) + timedelta(hours=1)
    return {"job_id": job_id, "end_ts": end.isoformat(), "method": method, "slots": slots}


def receipt_response(plan: dict[str, Any], fx: Factors) -> dict[str, Any]:
    """The 200 body of ``POST /receipts`` for a job that ran one hour earlier than planned."""
    receipt = receipt_from_plan(plan, "chosen", shift_hours=-1)
    res = score.receipt_footprints(receipt, plan, (), fx)
    site = {"site_id": SITE_ID, "name": "CSE GPU Lab", "city": "Chennai", "cooling": "room_ac",
            "gpu_count": 2, "coverage_declared": 0.9, "public": True}
    view = score.site_page_view(site, [res], NOW, fx)
    return {
        "receipt_id": f"{SITE_ID}#{receipt['end_ts']}#{JOB_ID}",
        "scoring": res["scoring"],
        "absolute": res["absolute"],
        "capture": res["capture"],
        "no_room": res["no_room"],
        "flexible": res["flexible"],
        "tags": res["tags"],
        "site_score": {k: view["score"][k] for k in ("value", "badge", "provisional")},
        "url": f"/receipts/{SITE_ID}/{JOB_ID}",
    }


def demo_site(site_id: str, name: str, gpus: int, coverage: float) -> dict[str, Any]:
    return {"site_id": site_id, "name": name, "city": "Chennai", "cooling": "room_ac",
            "gpu_count": gpus, "coverage_declared": coverage, "public": True, "simulated": True}


def demo_jobs(
    plan: dict[str, Any], fx: Factors, tag: str, variants: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Score one receipt per variant; job ids follow the contract ``j_`` + 12 base32 letters."""
    out = []
    for i, variant in enumerate(variants):
        opts = dict(variant)
        which = opts.pop("which")
        job_id = f"j_{tag * 11}{'abcdefgh'[i]}"
        out.append(score.receipt_footprints(receipt_from_plan(plan, which, job_id=job_id, **opts),
                                            plan, (), fx))
    return out


def leaderboard_response(plan: dict[str, Any], fx: Factors) -> dict[str, Any]:
    """Demo sites with receipts scored by the real engine. All are labelled simulated."""
    sites = [
        demo_site("s_demoaaaaaa", "Demo Lab, Chennai (simulated)", 8, 0.9),
        demo_site("s_demobbbbbb", "Demo Lab, Bengaluru (simulated)", 4, 0.9),
        demo_site("s_democccccc", "Demo Lab, Delhi (simulated)", 12, 0.5),
        demo_site("s_demodddddd", "Demo Startup, Mumbai (simulated)", 16, 0.0),
        demo_site("s_demoeeeeee", "Demo Cluster, Pune (simulated)", 64, 0.9),
    ]
    receipts = {
        "s_demoaaaaaa": demo_jobs(plan, fx, "a", [
            {"which": "best"}, {"which": "best", "scale": 1.5},
            {"which": "chosen", "shift_hours": -1}]),
        "s_demobbbbbb": demo_jobs(plan, fx, "b", [
            {"which": "chosen", "shift_hours": -1}, {"which": "base", "scale": 0.8}]),
        "s_democccccc": demo_jobs(plan, fx, "c", [
            {"which": "base"}, {"which": "base", "scale": 0.5}]),
        "s_demoeeeeee": demo_jobs(plan, fx, "e", [{"which": "best"}]),
    }
    rows = score.leaderboard_rows(sites, receipts, "D1", NOW, fx)
    return {"division": "D1", "period": "30d", "board": "score", "generated_at": NOW.isoformat(),
            "rows": rows}


def write(name: str, data: dict[str, Any]) -> None:
    path = FIXTURES / name
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size} bytes)\n")


def main() -> int:
    fx = load_factors()
    plan = build_plan(fx)
    write("plan_response.json", plan)
    write("receipt_response.json", receipt_response(plan, fx))
    write("leaderboard_response.json", leaderboard_response(plan, fx))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
