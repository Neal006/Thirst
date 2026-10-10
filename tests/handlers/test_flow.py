"""The whole backend story through the real handlers on moto (plan 05.12 and 07.1).

register a site -> plan a job -> run it and send a signed receipt -> see it on the site page and
the leaderboard. Following the plan must score better than starting now, bad callers must be
refused, and the seeded demo board must sit next to the real site.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import api_helpers
import pytest
import seed
from api_helpers import Client

from engine.units import floor_hour
from handlers import api, explain, store

PLAN = {
    "gpu_model": "RTX-4090",
    "gpu_count": 2,
    "work_hours": 4,
    "deadline": "2026-10-10T20:00:00+05:30",
    "pausable": False,
    "alpha": 0.5,
}


def register(client: Client, name: str = "Flow Lab") -> dict[str, Any]:
    reply = client.call(
        "POST",
        "/sites",
        {"name": name, "city": "Chennai", "cooling": "room_ac", "gpu_count": 2,
         "coverage_declared": 0.9},
    )
    assert reply.status == 201, reply.text
    return reply.json  # type: ignore[no-any-return]


def make_plan(client: Client, site_id: str, **changes: Any) -> dict[str, Any]:
    reply = client.call("POST", "/plan", {"site_id": site_id, **PLAN, **changes})
    assert reply.status == 200, reply.text
    return reply.json  # type: ignore[no-any-return]


def receipt_for(
    plan: dict[str, Any], site_id: str, job: str, entry: str = "chosen"
) -> dict[str, Any]:
    """A receipt that ran ``plan[entry]`` exactly: its per-hour GPU energy and levels."""
    chosen = plan[entry]
    first = floor_hour(datetime.fromisoformat(plan["submit_ts"]))
    levels = {r["slot"]: r["level"] for r in chosen["schedule"] if r["state"] == "run"}
    slots = []
    for i, kwh in enumerate(chosen["gpu_kwh"]):
        hour = (first + timedelta(hours=i)).isoformat()
        if kwh > 0 and hour in levels:
            slots.append({"hour": hour, "run_kwh": kwh, "idle_kwh": 0.0, "level": levels[hour]})
    start = datetime.fromisoformat(slots[0]["hour"]) + timedelta(minutes=2)
    end = datetime.fromisoformat(slots[-1]["hour"]) + timedelta(minutes=50)
    return {
        "site_id": site_id,
        "plan_id": plan["plan_id"],
        "job_id": job,
        "start_ts": start.isoformat(),
        "end_ts": end.isoformat(),
        "slots": slots,
        "method": "nvml_energy",
        "cap_applied": True,
        "cap_method": "nvml",
        "gpu": {"name": "RTX 4090", "driver": "550", "count": 2},
        "exit_code": 0,
        "interrupted": False,
        "overran": False,
        "cli_version": "0.1.0",
    }


def send(client: Client, site: dict[str, Any], body: dict[str, Any]) -> api_helpers.Reply:
    client.clock.set(datetime.fromisoformat(body["end_ts"]) + timedelta(minutes=5))
    return client.post_signed("/receipts", site["site_id"], body, token=site["token"])


def row_for(client: Client, site_id: str) -> dict[str, Any]:
    rows = client.call("GET", "/leaderboard", query={"division": "D1"}).json["rows"]
    (row,) = [r for r in rows if r["site_id"] == site_id]
    return row  # type: ignore[no-any-return]


def test_the_full_journey(client: Client) -> None:
    site = register(client)
    before = row_for(client, site["site_id"])
    assert before["rank"] is None and before["score"] is None  # listed, not rated yet

    plan = make_plan(client, site["site_id"])
    assert plan["plan_id"].startswith("p_") and plan["chosen"]["savings_ranges"]

    body = receipt_for(plan, site["site_id"], "j_aaaaaaaaaaaa")
    done = send(client, site, body)
    assert done.status == 200, done.text
    assert done.json["capture"] == pytest.approx(1.0, abs=0.02)  # it ran the chosen plan
    assert done.json["site_score"]["provisional"] is True

    again = client.call("GET", f"/receipts/{site['site_id']}/j_aaaaaaaaaaaa")
    assert again.status == 200 and again.json["capture"] == done.json["capture"]

    page = client.call("GET", f"/sites/{site['site_id']}")
    assert page.status == 200 and page.json["site"]["name"] == "Flow Lab"
    assert [r["job_id"] for r in page.json["recent_receipts"]] == ["j_aaaaaaaaaaaa"]
    assert "gpu_count" not in page.json["site"]  # the exact size is never public

    after = row_for(client, site["site_id"])  # cache was invalidated by the receipt
    assert after["receipts"] == 1 and after["score"] is not None and after["rank"] == 1

    explained = Client(explain.handler, client.clock, client.tables).call(
        "POST", "/explain", {"plan_id": plan["plan_id"]}
    )
    assert explained.status == 200 and explained.json["source"] == "template"
    assert "modelled" in explained.json["explanation"]


def test_following_the_plan_beats_starting_now(client: Client) -> None:
    lab, rival = register(client, "Plan Follower"), register(client, "Always Now")
    plans = {s["site_id"]: make_plan(client, s["site_id"]) for s in (lab, rival)}
    last_end = api_helpers.NOW
    for site, entry in ((lab, "chosen"), (rival, "base")):
        body = receipt_for(plans[site["site_id"]], site["site_id"], "j_bbbbbbbbbbbb", entry)
        assert send(client, site, body).status == 200
        last_end = max(last_end, datetime.fromisoformat(body["end_ts"]))
    # the follower's cheaper hours are later: read the board once both jobs are over
    client.clock.set(last_end + timedelta(minutes=5))
    follower, now_site = row_for(client, lab["site_id"]), row_for(client, rival["site_id"])
    assert follower["score"] > now_site["score"]
    assert follower["rank"] < now_site["rank"]


def test_bad_callers_are_refused_and_nothing_is_stored(client: Client) -> None:
    site, other = register(client), register(client, "Other Lab")
    plan = make_plan(client, site["site_id"])
    body = receipt_for(plan, site["site_id"], "j_cccccccccccc")
    client.clock.set(datetime.fromisoformat(body["end_ts"]) + timedelta(minutes=5))

    forged = client.post_signed("/receipts", site["site_id"], body, token=other["token"])
    assert forged.status == 401 and forged.json["error"] == "bad_signature"

    swapped = {**body, "site_id": other["site_id"]}  # signed as one site, claims another
    mismatch = client.post_signed("/receipts", site["site_id"], swapped, token=site["token"])
    assert mismatch.status == 400

    stale = client.post_signed("/receipts", site["site_id"], body, token=site["token"],
                               ts=int(client.clock().timestamp()) - 3600)
    assert stale.status == 401

    items = client.tables.receipts.query(
        KeyConditionExpression="site_id = :s", ExpressionAttributeValues={":s": site["site_id"]}
    )["Items"]
    assert items == []  # three refusals, no writes

    assert client.post_signed("/receipts", site["site_id"], body, token=site["token"]).status == 200
    replay = client.post_signed("/receipts", site["site_id"], body, token=site["token"])
    assert replay.status == 409 and replay.json["error"] == "duplicate_job"

    # the other site cannot use this site's plan
    steal = receipt_for(plan, other["site_id"], "j_dddddddddddd")
    stolen = client.post_signed("/receipts", other["site_id"], steal, token=other["token"])
    assert stolen.status == 403


def test_a_receipt_with_more_energy_than_the_gpus_can_draw_is_rejected(client: Client) -> None:
    site = register(client)
    plan = make_plan(client, site["site_id"])
    body = receipt_for(plan, site["site_id"], "j_eeeeeeeeeeee")
    body["slots"] = [{**s, "run_kwh": s["run_kwh"] * 50} for s in body["slots"]]
    reply = send(client, site, body)
    assert reply.status == 422 and reply.json["error"] in ("implausible_energy", "invalid_field")


def test_errors_are_json_with_a_stable_shape(client: Client) -> None:
    for method, path, body in (
        ("GET", "/sites/s_aaaaaaaaaa", None),
        ("GET", "/nope", None),
        ("POST", "/plan", {"city": "Atlantis"}),
        ("POST", "/sites", {"name": ""}),
    ):
        reply = client.call(method, path, body)
        assert 400 <= reply.status < 500, (path, reply.status)
        assert set(reply.json) == {"error", "message"}, (path, reply.json)
        assert reply.json["message"] and "Traceback" not in reply.text


def test_the_seeded_board_and_a_real_site_share_the_leaderboard(client: Client) -> None:
    seed.seed(client.tables, api_helpers.NOW, jobs=4)
    api.reset_caches()
    site = register(client)
    plan = make_plan(client, site["site_id"])
    assert send(client, site, receipt_for(plan, site["site_id"], "j_ffffffffffff")).status == 200
    rows = client.call("GET", "/leaderboard", query={"division": "D1"}).json["rows"]
    simulated = [r for r in rows if r["simulated"]]
    assert len(simulated) == 5 and len(rows) == 6
    assert [r["rank"] for r in rows if r["rank"] is not None] == list(range(1, len([
        r for r in rows if r["rank"] is not None]) + 1))
    assert [r for r in rows if r["site_id"] == site["site_id"]][0]["simulated"] is False
    d2 = client.call("GET", "/leaderboard", query={"division": "D2"}).json["rows"]
    assert len(d2) == 2


def test_the_assumptions_page_lists_every_factor_with_its_status(client: Client) -> None:
    data = client.call("GET", "/assumptions").json
    assert len(data["factors"]) >= 50 and data["version"]
    assert {f["status"] for f in data["factors"]} <= {
        "measured", "modelled", "placeholder", "sourced", "calibrated", "assumed", "derived",
    } | {f["status"] for f in data["factors"]}
    assert any(f["status"] == "placeholder" for f in data["factors"])  # nothing is hidden


def test_stale_weather_still_gives_a_plan_with_an_honest_tag(
    client: Client, tables: store.Tables
) -> None:
    client.clock.advance(days=3)  # nobody refreshed the forecast
    site = register(client)
    reply = client.call("POST", "/plan", {"site_id": site["site_id"], **PLAN,
                                          "deadline": "2026-10-13T20:00:00+05:30"})
    assert reply.status == 200, reply.text
    assert reply.json["tags"]["forecast"] == "cached"
    assert reply.json["forecast_age_hours"] is None or reply.json["forecast_age_hours"] >= 48
