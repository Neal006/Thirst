"""Seed the demo board into DynamoDB: the real lab and 8 simulated sites (plan step 05.10).

    python scripts/seed.py --profile thirst --stage dev            # seed (idempotent)
    python scripts/seed.py --profile thirst --stage dev --wipe-simulated
    python scripts/seed.py --profile thirst --stage dev --delete-site s_abcdefghij

Writes straight to the tables with admin credentials, not through the API. The simulated sites
are fixed (``s_sim...`` ids), so a re-run replaces their receipts. Receipts are made by the same
engine that scores real ones: plan a past job from the saved sample weather, run it the way the
site's behaviour profile says, and score it with ``score.receipt_footprints``.
"""

from __future__ import annotations

import argparse
import base64
import random
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from engine import planner, score  # noqa: E402
from engine.errors import EngineError  # noqa: E402
from engine.factors import Factors, load_factors  # noqa: E402
from engine.units import IST, floor_hour  # noqa: E402
from handlers import http, security, store, validation  # noqa: E402

SIM_PREFIX = "s_sim"
HISTORY_DAYS = 28
MIN_HISTORY_HOURS = 60  # the newest job must be over (the planning window is 48 h)
DEFAULT_REAL_LAB = ("Thirst Lab", "Chennai", "room_ac", 2)  # name, city, cooling, GPUs


class SeedError(Exception):
    """A refused or impossible request. The message is meant for the person at the terminal."""


@dataclass(frozen=True, slots=True)
class SimSite:
    site_id: str
    name: str
    org: str
    city: str
    cooling: str
    gpu_model: str
    gpu_count: int  # GPUs at the site (sets the division)
    job_gpus: int  # GPUs one job uses
    profile: str  # always_now, follows_plan, water_first, co2_first or mixed
    jobs: int
    coverage: float


# Names are invented on purpose: never a real company (Idea 12). Divisions: D1 x5, D2 x2, D3 x1.
SIM_SITES: tuple[SimSite, ...] = (
    SimSite("s_simaaaaaaa", "Demo Lab, Chennai (simulated)", "Demo University", "Chennai",
            "room_ac", "RTX-4090", 4, 2, "follows_plan", 30, 0.9),
    SimSite("s_simaaaaaab", "Demo Cluster, Hyderabad (simulated)", "Demo Institute", "Hyderabad",
            "air_chiller", "A100-PCIE-80GB", 8, 4, "mixed", 24, 0.9),
    SimSite("s_simaaaaaac", "Demo Lab, Pune (simulated)", "Demo College", "Pune",
            "room_ac", "RTX-3090", 2, 2, "always_now", 18, 0.5),
    SimSite("s_simaaaaaad", "Demo Group, Bengaluru (simulated)", "Demo Startup", "Bengaluru",
            "room_ac", "L4", 4, 4, "water_first", 22, 0.85),
    SimSite("s_simaaaaaae", "Demo Lab, Mumbai (simulated)", "Demo Research Centre", "Mumbai",
            "air_chiller", "L40S", 16, 8, "co2_first", 16, 0.7),
    SimSite("s_simaaaaaaf", "Demo Cluster, Delhi (simulated)", "Demo Supercomputing Unit", "Delhi",
            "air_chiller", "A100-SXM", 64, 16, "follows_plan", 36, 0.95),
    SimSite("s_simaaaaaag", "Demo GPU Rack, Bengaluru (simulated)", "Demo Compute Co", "Bengaluru",
            "air_chiller", "H100-PCIE", 128, 32, "mixed", 14, 0.6),
    SimSite("s_simaaaaaah", "Demo Hall, Hyderabad (simulated)", "Demo National Facility",
            "Hyderabad", "evaporative", "H100-SXM", 512, 64, "always_now", 12, 0.8),
)


# ---------------------------------------------------------------------- connection


def connect(profile: str | None, stage: str, region: str) -> store.Tables:
    import boto3

    resource = boto3.Session(profile_name=profile, region_name=region).resource("dynamodb")
    return store.Tables(
        **{name: resource.Table(f"thirst-{stage}-{name}") for name in store.TABLE_SPECS}
    )


def _secret(profile: str | None, region: str, param: str) -> bytes:
    import boto3

    ssm = boto3.Session(profile_name=profile, region_name=region).client("ssm")
    return str(ssm.get_parameter(Name=param, WithDecryption=True)["Parameter"]["Value"]).encode()


# ---------------------------------------------------------------------- simulation


def _job_id(rng: random.Random) -> str:
    return "j_" + base64.b32encode(rng.randbytes(8)).decode().lower()[:12]


def _entry(result: Mapping[str, Any], profile: str, rng: random.Random) -> Mapping[str, Any]:
    """The plan entry the site's operators actually followed."""
    pareto: Sequence[Mapping[str, Any]] = result["pareto"]
    chosen: Mapping[str, Any] = result["chosen"]
    base: Mapping[str, Any] = result["base"]
    if profile == "always_now":
        return base
    if profile == "follows_plan":
        return chosen
    if profile == "water_first":
        return pareto[-1]
    if profile == "co2_first":
        return pareto[0]
    return rng.choice([base, chosen])


def _slots(
    entry: Mapping[str, Any], first_hour: datetime, rng: random.Random, max_hour_kwh: float
) -> list[dict[str, Any]]:
    """Receipt slots from an entry's per-hour GPU energy (small measurement noise)."""
    plan = {row["slot"]: row for row in entry["schedule"]}
    out: list[dict[str, Any]] = []
    for i, kwh in enumerate(entry["gpu_kwh"]):
        if kwh <= 0:
            continue
        hour = (first_hour + timedelta(hours=i)).isoformat()
        row = plan.get(hour, {"state": "run", "level": 1.0})
        energy = min(kwh * rng.uniform(0.97, 1.03), max_hour_kwh)
        paused = row["state"] == "pause"
        out.append(
            {
                "hour": hour,
                "run_kwh": 0.0 if paused else energy,
                "idle_kwh": energy if paused else 0.0,
                "level": 0.7 if paused or row["level"] <= 0 else row["level"],
            }
        )
    return out


def _item(
    sim: SimSite,
    rng: random.Random,
    result: Mapping[str, Any],
    entry: Mapping[str, Any],
    first_hour: datetime,
    fx: Factors,
) -> dict[str, Any]:
    gpu = fx.gpus[sim.gpu_model]
    max_hour_kwh = sim.job_gpus * gpu.p_max_w / 1000 * fx.central()["receipt_kwh_tolerance"]
    slots = _slots(entry, first_hour, rng, max_hour_kwh * 0.98)
    start = datetime.fromisoformat(slots[0]["hour"]) + timedelta(minutes=rng.randint(0, 9))
    end = datetime.fromisoformat(slots[-1]["hour"]) + timedelta(minutes=rng.randint(40, 59))
    job_id = _job_id(rng)
    doc = {"job_id": job_id, "end_ts": end.isoformat(), "method": "modelled", "slots": slots}
    scored = score.receipt_footprints(doc, result, (), fx)
    capped = any(s["level"] < 1.0 for s in slots)
    return {
        "site_id": sim.site_id,
        "job_id": job_id,
        "plan_id": None,
        "start_ts": start.isoformat(),
        "end_ts": end.isoformat(),
        "slots": slots,
        "method": "modelled",
        "cap_applied": capped,
        "cap_method": "nvml" if capped else "none",
        "gpu": {"name": sim.gpu_model, "driver": "simulated", "count": sim.job_gpus},
        "scoring": scored["scoring"],
        "absolute": scored["absolute"],
        "capture": scored["capture"],
        "no_room": bool(scored["no_room"]),
        "flexible": bool(scored["flexible"]),
        "scored": True,
        "kwh": scored["kwh"],
        "tags": dict(scored["tags"]),
        "extrapolated_hours": scored["extrapolated_hours"],
        "factor_version_mismatch": bool(scored["factor_version_mismatch"]),
        "exit_code": 0,
        "interrupted": False,
        "overran": False,
        "cli_version": "simulated",
        "created_at": end.isoformat(),
    }


def simulate_receipts(
    sim: SimSite, now: datetime, jobs: int | None = None, fx: Factors | None = None
) -> list[dict[str, Any]]:
    """``jobs`` receipts spread over the last 28 days. The same inputs give the same receipts."""
    fx = fx or load_factors()
    count = sim.jobs if jobs is None else jobs
    rng = random.Random(sim.site_id)  # noqa: S311 - a repeatable simulation, not security
    newest = floor_hour(now) - timedelta(hours=MIN_HISTORY_HOURS)
    bin_hours = (HISTORY_DAYS * 24 - MIN_HISTORY_HOURS) / max(count, 1)
    receipts = []
    for k in range(count):
        submit = newest - timedelta(hours=int(k * bin_hours + rng.uniform(0, bin_hours * 0.4)))
        work = round(rng.uniform(1.0, 6.0), 1)
        req = planner.PlanRequest(
            city=sim.city,
            cooling=sim.cooling,
            pue_user=None,
            gpu_model=sim.gpu_model,
            gpu_count=sim.job_gpus,
            work_hours=work,
            deadline=submit + timedelta(hours=work * 1.6 + 3 + rng.uniform(0, 6)),
            pausable=rng.random() < 0.5,
            alpha=0.5,
            submit_ts=submit,
            site_id=sim.site_id,
        )
        try:
            result = planner.plan_from_rows(req, (), fx)
        except EngineError as err:  # a seed that cannot plan is a bug, not data to skip
            raise SeedError(f"{sim.site_id}: job {k} could not be planned: {err.message}") from err
        entry = _entry(result, sim.profile, rng)
        receipts.append(_item(sim, rng, result, entry, floor_hour(submit), fx))
    return receipts


# ---------------------------------------------------------------------- writes


def _site_item(sim: SimSite, now: datetime, fx: Factors) -> dict[str, Any]:
    return {
        "site_id": sim.site_id,
        "name": sim.name,
        "org": sim.org,
        "city": sim.city,
        "cooling": sim.cooling,
        "gpu_count": sim.gpu_count,
        "division": score.division(sim.gpu_count, fx.central()),
        "coverage_declared": sim.coverage,
        "public": True,
        "simulated": True,
        "created_at": now.isoformat(),
    }


def seed(tables: store.Tables, now: datetime, jobs: int | None = None) -> dict[str, int]:
    """Write the 8 simulated sites with fresh receipts. Re-running replaces them."""
    fx = load_factors()
    sites, receipts_repo = store.SiteRepo(tables.sites), store.ReceiptRepo(tables.receipts)
    written = 0
    for sim in SIM_SITES:
        batch = simulate_receipts(sim, now, jobs, fx)  # first, so a failure leaves data intact
        receipts_repo.delete_site(sim.site_id)
        sites.delete(sim.site_id)
        sites.create(_site_item(sim, now, fx))
        for item in batch:
            receipts_repo.put_with_guard(item)
        written += len(batch)
    return {"sites": len(SIM_SITES), "receipts": written}


def ensure_real_lab(
    tables: store.Tables,
    now: datetime,
    secret: bytes,
    *,
    name: str,
    city: str,
    cooling: str,
    gpu_count: int,
    org: str | None = None,
) -> dict[str, Any]:
    """The team's own site (not simulated). Created once; the token can be shown again."""
    repo = store.SiteRepo(tables.sites)
    for site in repo.scan_all():
        if not site.get("simulated") and site.get("name") == name:
            token = security.site_token(secret, site["site_id"])
            return {"site_id": site["site_id"], "created": False, "token": token}
    site_id = http.new_id("s_")
    repo.create(
        {
            "site_id": site_id,
            "name": name,
            "org": org,
            "city": city,
            "cooling": cooling,
            "gpu_count": gpu_count,
            "division": score.division(gpu_count, load_factors().central()),
            "coverage_declared": 0.0,
            "public": True,
            "simulated": False,
            "created_at": now.isoformat(),
        }
    )
    return {"site_id": site_id, "created": True, "token": security.site_token(secret, site_id)}


def wipe_simulated(tables: store.Tables) -> dict[str, int]:
    """Remove the sites marked ``simulated`` and their receipts. Nothing else is touched."""
    sites, receipts = store.SiteRepo(tables.sites), store.ReceiptRepo(tables.receipts)
    removed = {"sites": 0, "receipts": 0}
    for site in sites.scan_all():
        if site.get("simulated") is True:
            removed["receipts"] += receipts.delete_site(site["site_id"])
            sites.delete(site["site_id"])
            removed["sites"] += 1
    return removed


def delete_site(tables: store.Tables, site_id: str) -> dict[str, int]:
    """Delete one test site with its receipts and guards. Refuses the seeded demo sites."""
    if not validation.SITE_ID.fullmatch(site_id):
        raise SeedError(f"{site_id!r} is not a site id (like s_abcdefghij).")
    if site_id.startswith(SIM_PREFIX):
        raise SeedError(f"{site_id} is a simulated demo site; use --wipe-simulated to remove them.")
    repo = store.SiteRepo(tables.sites)
    site = repo.get(site_id)
    if site is None:
        raise SeedError(f"no such site: {site_id}")
    if site.get("simulated"):
        raise SeedError(f"{site_id} is marked simulated; use --wipe-simulated to remove them.")
    count = store.ReceiptRepo(tables.receipts).delete_site(site_id)
    repo.delete(site_id)
    return {"site": 1, "receipts": count}


# ---------------------------------------------------------------------- command line


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Seed the Thirst demo board (plan step 05.10).")
    p.add_argument("--profile", default=None, help="AWS profile, e.g. thirst")
    p.add_argument("--stage", default="dev")
    p.add_argument("--region", default="ap-south-1")
    p.add_argument("--jobs", type=int, default=None, help="receipts per site (default 10 to 40)")
    p.add_argument("--no-real-lab", action="store_true", help="skip the team's own site")
    p.add_argument("--secret-param", default="/thirst/server_secret")
    action = p.add_mutually_exclusive_group()
    action.add_argument("--wipe-simulated", action="store_true")
    action.add_argument("--delete-site", metavar="SITE_ID")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.jobs is not None and not 1 <= args.jobs <= 40:
        print("error: --jobs must be between 1 and 40", file=sys.stderr)
        return 2
    now = datetime.now(IST)
    try:
        tables = connect(args.profile, args.stage, args.region)
        if args.wipe_simulated:
            gone = wipe_simulated(tables)
            print(f"Removed {gone['sites']} simulated sites and {gone['receipts']} items.")
            print("The demo board is now empty: run the seed again before the demo.")
            return 0
        if args.delete_site:
            gone = delete_site(tables, args.delete_site)
            print(f"Deleted {args.delete_site} and {gone['receipts']} receipt items.")
            return 0
        done = seed(tables, now, args.jobs)
        print(f"Seeded {done['sites']} simulated sites with {done['receipts']} receipts.")
        if not args.no_real_lab:
            name, city, cooling, gpus = DEFAULT_REAL_LAB
            secret = _secret(args.profile, args.region, args.secret_param)
            lab = ensure_real_lab(
                tables, now, secret, name=name, city=city, cooling=cooling, gpu_count=gpus
            )
            state = "created" if lab["created"] else "exists"
            print(f"Real lab {name}: site_id={lab['site_id']} ({state})")
            print(f"Token for the CLI config (keep it private): {lab['token']}")
    except SeedError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
