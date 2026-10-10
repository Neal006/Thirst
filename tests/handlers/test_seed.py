"""scripts/seed.py: simulated demo sites, idempotent, never touching real data (plan 05.10)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

import api_helpers
import pytest
import seed

from engine import score
from engine.factors import load_factors
from handlers import api, security, store

JOBS = 4  # keep the suite quick: the real script uses 10 to 40 per site


@pytest.fixture
def seeded(tables: store.Tables) -> store.Tables:
    seed.seed(tables, api_helpers.NOW, jobs=JOBS)
    return tables


def sim_sites(tables: store.Tables) -> list[dict[str, Any]]:
    return [s for s in store.SiteRepo(tables.sites).scan_all() if s.get("simulated")]


def test_eight_fixed_sites_spread_over_the_divisions(seeded: store.Tables) -> None:
    sites = sim_sites(seeded)
    assert sorted(s["site_id"] for s in sites) == sorted(s.site_id for s in seed.SIM_SITES)
    assert len(sites) == 8
    assert Counter(s["division"] for s in sites) == {"D1": 5, "D2": 2, "D3": 1}
    fx = load_factors().central()
    assert all(score.division(s["gpu_count"], fx) == s["division"] for s in sites)


def test_site_ids_follow_the_api_id_rules_and_are_marked_simulated() -> None:
    from handlers import validation

    for sim in seed.SIM_SITES:
        assert validation.SITE_ID.fullmatch(sim.site_id), sim.site_id
        assert sim.site_id.startswith("s_sim")
        assert sim.name.endswith("(simulated)")


def test_no_real_company_names() -> None:
    banned = ("google", "amazon", "aws", "microsoft", "meta", "nvidia", "tcs", "infosys", "iit")
    for sim in seed.SIM_SITES:
        text = f"{sim.name} {sim.org}".lower()
        assert not any(word in text for word in banned), text
        assert sim.name.startswith("Demo "), sim.name


def test_receipts_are_in_the_last_30_days_and_count_per_site(seeded: store.Tables) -> None:
    repo = store.ReceiptRepo(seeded.receipts)
    for sim in seed.SIM_SITES:
        receipts = repo.last_30_days(sim.site_id, api_helpers.NOW)
        assert len(receipts) == JOBS, sim.site_id
        assert all(r["method"] == "modelled" for r in receipts)
        assert all(r["scored"] for r in receipts)


def test_receipts_look_like_the_ones_the_api_stores(
    seeded: store.Tables, client: api_helpers.Client
) -> None:
    """A seeded item has exactly the fields a real POST /receipts item has."""
    site = client.call("POST", "/sites", {"name": "Parity Lab", "city": "Chennai",
                                          "cooling": "room_ac", "gpu_count": 2}).json
    plan = client.call("POST", "/plan", {
        "site_id": site["site_id"], "gpu_model": "RTX-4090", "gpu_count": 2, "work_hours": 2,
        "deadline": "2026-10-10T20:00:00+05:30", "pausable": False, "alpha": 0.5,
    }).json
    run = [r for r in plan["chosen"]["schedule"] if r["state"] == "run"]
    end = (datetime.fromisoformat(run[-1]["slot"]) + timedelta(minutes=55)).isoformat()
    client.clock.set(datetime.fromisoformat(end) + timedelta(minutes=5))
    reply = client.post_signed("/receipts", site["site_id"], {
        "site_id": site["site_id"], "plan_id": plan["plan_id"], "job_id": "j_abcdefghijkl",
        "start_ts": run[0]["slot"], "end_ts": end, "method": "modelled",
        "slots": [{"hour": r["slot"], "run_kwh": 0.2, "idle_kwh": 0.0, "level": r["level"]}
                  for r in run],
        "cap_applied": True, "cap_method": "nvml",
        "gpu": {"name": "RTX 4090", "driver": "550", "count": 2},
        "exit_code": 0, "interrupted": False, "overran": False, "cli_version": "0.1.0",
    }, token=site["token"])
    assert reply.status == 200, reply.text
    api_item = store.ReceiptRepo(seeded.receipts).get(site["site_id"], "j_abcdefghijkl")
    seeded_item = store.ReceiptRepo(seeded.receipts).last_30_days(
        seed.SIM_SITES[0].site_id, api_helpers.NOW
    )[0]
    assert api_item is not None
    assert set(seeded_item) - {"sk"} == set(api_item) - {"sk"}


def test_scores_are_varied_and_the_board_shows_the_simulated_chip(
    seeded: store.Tables, client: api_helpers.Client, clock: api_helpers.Clock
) -> None:
    api.reset_caches()
    board = client.call("GET", "/leaderboard", query={"division": "D1"})
    assert board.status == 200, board.text
    rows = board.json["rows"]
    assert len(rows) >= 5
    assert all(r["simulated"] for r in rows)
    scores = {round(r["score"]) for r in rows if r["score"] is not None}
    assert len(scores) >= 3, scores  # varied, not all the same


def test_capture_follows_each_sites_behaviour(seeded: store.Tables) -> None:
    repo = store.ReceiptRepo(seeded.receipts)
    mean: dict[str, float] = {}
    for sim in seed.SIM_SITES:
        caps = [
            r["capture"]
            for r in repo.last_30_days(sim.site_id, api_helpers.NOW)
            if r["capture"] is not None
        ]
        if caps:
            mean[sim.profile] = sum(caps) / len(caps)
    assert mean["always_now"] < mean["follows_plan"]


def test_seeding_is_deterministic(tables: store.Tables) -> None:
    seed.seed(tables, api_helpers.NOW, jobs=JOBS)
    first = [
        (r["job_id"], r["end_ts"], r["capture"])
        for r in store.ReceiptRepo(tables.receipts).last_30_days(
            seed.SIM_SITES[0].site_id, api_helpers.NOW
        )
    ]
    seed.seed(tables, api_helpers.NOW, jobs=JOBS)
    second = [
        (r["job_id"], r["end_ts"], r["capture"])
        for r in store.ReceiptRepo(tables.receipts).last_30_days(
            seed.SIM_SITES[0].site_id, api_helpers.NOW
        )
    ]
    assert first == second and len(first) == JOBS


def test_reseeding_replaces_receipts_instead_of_piling_up(seeded: store.Tables) -> None:
    seed.seed(seeded, api_helpers.NOW, jobs=JOBS + 2)
    repo = store.ReceiptRepo(seeded.receipts)
    for sim in seed.SIM_SITES:
        assert len(repo.last_30_days(sim.site_id, api_helpers.NOW)) == JOBS + 2
    assert len(sim_sites(seeded)) == 8


def test_default_job_count_is_between_10_and_40_per_site(seeded: store.Tables) -> None:
    for sim in seed.SIM_SITES:
        assert 10 <= sim.jobs <= 40, sim.site_id


# the real lab -----------------------------------------------------------------------------


def test_the_real_lab_is_created_once_with_a_printed_token(
    tables: store.Tables, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = security.load_secret()
    out = seed.ensure_real_lab(tables, api_helpers.NOW, secret, name="Test Lab", city="Chennai",
                               cooling="room_ac", gpu_count=2)
    again = seed.ensure_real_lab(tables, api_helpers.NOW, secret, name="Test Lab", city="Chennai",
                                 cooling="room_ac", gpu_count=2)
    assert out["site_id"] == again["site_id"] and out["created"] and not again["created"]
    assert out["token"] == security.site_token(secret, out["site_id"])
    stored = store.SiteRepo(tables.sites).get(out["site_id"])
    assert stored is not None and stored["simulated"] is False
    assert "token" not in stored and out["token"] not in json.dumps(stored)


# safety --------------------------------------------------------------------------------------


def test_wipe_simulated_leaves_real_sites_and_their_receipts_alone(
    seeded: store.Tables, client: api_helpers.Client
) -> None:
    created = client.call("POST", "/sites", {"name": "Real Lab", "city": "Pune",
                                                    "cooling": "room_ac", "gpu_count": 4})
    real_id = created.json["site_id"]
    keep = {"site_id": real_id, "sk": "2026-10-09T10:00:00+05:30#j_realaaaaaaaa",
            "job_id": "j_realaaaaaaaa", "end_ts": "2026-10-09T10:00:00+05:30", "scored": True}
    seeded.receipts.put_item(Item=keep)
    removed = seed.wipe_simulated(seeded)
    assert removed == {"sites": 8, "receipts": 8 * JOBS * 2}  # receipt plus guard item each
    assert sim_sites(seeded) == []
    assert store.SiteRepo(seeded.sites).get(real_id) is not None
    assert seeded.receipts.get_item(Key={"site_id": real_id, "sk": keep["sk"]}).get("Item")


def test_wipe_then_reseed_restores_the_board(seeded: store.Tables) -> None:
    seed.wipe_simulated(seeded)
    seed.seed(seeded, api_helpers.NOW, jobs=JOBS)
    assert len(sim_sites(seeded)) == 8


def test_delete_site_removes_a_test_site_with_its_receipts(
    seeded: store.Tables, client: api_helpers.Client
) -> None:
    created = client.call("POST", "/sites", {"name": "Throwaway", "city": "Pune",
                                                    "cooling": "room_ac", "gpu_count": 4})
    sid = created.json["site_id"]
    seeded.receipts.put_item(Item={"site_id": sid, "sk": "job#j_x", "sk_receipt": "x"})
    result = seed.delete_site(seeded, sid)
    assert result == {"site": 1, "receipts": 1}
    assert store.SiteRepo(seeded.sites).get(sid) is None


def test_delete_site_refuses_the_seeded_demo_sites(seeded: store.Tables) -> None:
    with pytest.raises(seed.SeedError, match="simulated demo site"):
        seed.delete_site(seeded, seed.SIM_SITES[0].site_id)
    assert len(sim_sites(seeded)) == 8


@pytest.mark.parametrize(
    "bad", ["", "nonsense", "s_", "S_ABCDEFGHIJ", "../etc", "s_sim000001' OR 1"]
)
def test_delete_site_refuses_malformed_ids(seeded: store.Tables, bad: str) -> None:
    with pytest.raises(seed.SeedError):
        seed.delete_site(seeded, bad)


def test_delete_site_of_an_unknown_id_says_so(seeded: store.Tables) -> None:
    with pytest.raises(seed.SeedError, match="no such site"):
        seed.delete_site(seeded, "s_aaaaaaaaaa")


def test_delete_site_will_not_delete_a_site_marked_simulated(seeded: store.Tables) -> None:
    seeded.sites.put_item(Item={"site_id": "s_zzzzzzzzzz", "simulated": True, "name": "x"})
    with pytest.raises(seed.SeedError, match="simulated"):
        seed.delete_site(seeded, "s_zzzzzzzzzz")


# the command line ----------------------------------------------------------------------------


def test_main_refuses_conflicting_actions(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        seed.main(["--wipe-simulated", "--delete-site", "s_aaaaaaaaaa"])
    assert exc.value.code == 2


def test_main_wires_the_table_names_from_the_stage(
    aws: None, capsys: pytest.CaptureFixture[str]
) -> None:
    code = seed.main(["--stage", "test", "--region", "ap-south-1", "--jobs", "2", "--no-real-lab"])
    assert code == 0
    assert "8 simulated sites" in capsys.readouterr().out
    tables = store.get_tables()
    assert len(store.SiteRepo(tables.sites).scan_all()) == 8


def test_main_wipes(aws: None, capsys: pytest.CaptureFixture[str]) -> None:
    seed.main(["--stage", "test", "--region", "ap-south-1", "--jobs", "2", "--no-real-lab"])
    assert seed.main(["--stage", "test", "--region", "ap-south-1", "--wipe-simulated"]) == 0
    assert "Removed 8 simulated sites" in capsys.readouterr().out
    assert store.SiteRepo(store.get_tables().sites).scan_all() == []


def test_main_reports_a_refused_delete_with_exit_code_1(
    aws: None, capsys: pytest.CaptureFixture[str]
) -> None:
    code = seed.main(["--stage", "test", "--region", "ap-south-1", "--delete-site", "s_simaaaaaaa"])
    assert code == 1 and "simulated demo site" in capsys.readouterr().err
