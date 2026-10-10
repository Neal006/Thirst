"""POST /sites and GET /sites/{id} (plan 05.6, contract 08 §3.2-3.3)."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

import api_helpers
import pytest
from api_helpers import Client

from engine.factors import load_factors
from handlers import api, store

BODY: dict[str, Any] = {
    "name": "CSE GPU Lab",
    "org": "IIT Example",
    "city": "Chennai",
    "cooling": "room_ac",
    "gpu_count": 8,
    "coverage_declared": 0.9,
}


def create(client: Client, **changes: Any) -> api_helpers.Reply:
    return client.call("POST", "/sites", {**BODY, **changes})


def stored_receipt(site_id: str, job: str, end: str, **extra: Any) -> dict[str, Any]:
    absolute = {"E_fac_kwh": 2.0, "litres": 3.0, "W_l": 4.0, "C_kg": 1.0, "person_days": 0.01}
    return {
        "site_id": site_id,
        "job_id": job,
        "end_ts": end,
        "start_ts": end,
        "plan_id": "p_aaaaaaaaaa",
        "method": "nvml_energy",
        "kwh": 1.0,
        "capture": 0.6,
        "flexible": True,
        "no_room": False,
        "scored": True,
        "slots": [],
        "absolute": {"actual": absolute},
        **extra,
    }


def test_creating_a_site_returns_the_id_the_token_and_the_division(client: Client) -> None:
    reply = create(client)
    assert reply.status == 201
    data = reply.json
    assert set(data) == {"site_id", "token", "division"}
    assert re.fullmatch(r"s_[a-z2-7]{10}", data["site_id"])
    assert data["token"] == api_helpers.token_for(data["site_id"])  # HMAC(secret, site_id)
    assert data["division"] == "D1"
    assert reply.headers["cache-control"] == "no-store"


def test_the_token_is_never_stored(client: Client) -> None:
    data = create(client).json
    item = client.tables.sites.get_item(Key={"site_id": data["site_id"]})["Item"]
    assert "token" not in item
    assert data["token"] not in str(item)
    assert item["name"] == "CSE GPU Lab" and item["simulated"] is False and item["public"] is True
    assert item["created_at"] == api_helpers.NOW.isoformat()
    assert item["division"] == "D1" and int(item["gpu_count"]) == 8


def test_each_site_gets_its_own_id_and_token(client: Client) -> None:
    a, b = create(client).json, create(client).json
    assert a["site_id"] != b["site_id"] and a["token"] != b["token"]


def test_a_colliding_id_is_retried(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    first = create(client).json["site_id"]
    ids = iter([first, first, "s_aaaaaaaaab"])
    monkeypatch.setattr(api, "_new_id", lambda prefix, size=10: next(ids))
    assert create(client).json["site_id"] == "s_aaaaaaaaab"
    stored = store.SiteRepo(client.tables.sites).get(first)
    assert stored is not None and stored["name"] == "CSE GPU Lab"


def test_division_follows_the_gpu_count_thresholds(client: Client) -> None:
    fs = load_factors().central()
    d1, d2 = int(fs["div_d1_max"]), int(fs["div_d2_max"])
    assert create(client, gpu_count=d1).json["division"] == "D1"
    assert create(client, gpu_count=d1 + 1).json["division"] == "D2"
    assert create(client, gpu_count=d2 + 1).json["division"] == "D3"


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "ab"},
        {"name": "x" * 61},
        {"name": 5},
        {"org": "o" * 81},
        {"city": "Atlantis"},
        {"cooling": "x"},
        {"gpu_count": 0},
        {"gpu_count": 100001},
        {"coverage_declared": 2},
        {"public": "yes"},
    ],
)
def test_bad_site_fields_are_400(client: Client, changes: dict[str, Any]) -> None:
    reply = create(client, **changes)
    assert reply.status == 400
    assert set(reply.json) == {"error", "message"}


def test_control_characters_are_stripped_from_names(client: Client) -> None:
    sid = create(client, name="  Lab\x00\x1b One  ").json["site_id"]
    assert store.SiteRepo(client.tables.sites).get(sid)["name"] == "Lab One"  # type: ignore[index]


def test_a_body_over_8_kb_is_413(client: Client) -> None:
    assert create(client, org="x" * 9000).status == 413


def test_get_returns_the_public_page_without_the_gpu_count(client: Client) -> None:
    sid = create(client).json["site_id"]
    reply = client.call("GET", f"/sites/{sid}")
    assert reply.status == 200 and reply.headers["cache-control"] == "no-store"
    data = reply.json
    assert set(data) == {"site", "score", "monthly_absolute", "recent_receipts"}
    assert data["site"]["name"] == "CSE GPU Lab" and data["site"]["division"] == "D1"
    assert "gpu_count" not in reply.text and "token" not in reply.text
    assert data["recent_receipts"] == []


def test_a_site_without_receipts_is_not_rated_yet(client: Client) -> None:
    sid = create(client).json["site_id"]
    score = client.call("GET", f"/sites/{sid}").json["score"]
    assert score["value"] is None and score["reason"] == "needs_flexible_receipt"
    assert score["provisional"] is True


def test_unknown_and_malformed_ids(client: Client) -> None:
    missing = client.call("GET", "/sites/s_zzzzzzzzzz")
    assert missing.status == 404 and missing.json["error"] == "site_not_found"
    for bad in ("s_short", "S_ABCDEFGHIJ", "s_abcdefgh1j", "..%2F..%2Fetc"):
        assert client.call("GET", f"/sites/{bad}").status == 400


def test_a_private_site_shows_only_name_division_and_score(client: Client) -> None:
    sid = create(client, public=False).json["site_id"]
    store.ReceiptRepo(client.tables.receipts).put_with_guard(
        stored_receipt(sid, "j_aaaaaaaaaaaa", "2026-10-09T10:00:00+05:30")
    )
    data = client.call("GET", f"/sites/{sid}").json
    assert data["recent_receipts"] == [] and data["monthly_absolute"] is None
    assert data["site"]["name"] == "CSE GPU Lab" and data["score"]["value"] is not None


def test_a_public_site_lists_its_recent_receipts(client: Client) -> None:
    sid = create(client).json["site_id"]
    repo = store.ReceiptRepo(client.tables.receipts)
    for i, end in enumerate(["2026-10-08T10:00:00+05:30", "2026-10-09T10:00:00+05:30"]):
        repo.put_with_guard(stored_receipt(sid, f"j_{'ab'[i] * 12}", end))
    data = client.call("GET", f"/sites/{sid}").json
    assert [r["job_id"] for r in data["recent_receipts"]] == ["j_" + "b" * 12, "j_" + "a" * 12]
    assert data["monthly_absolute"]["kwh"] == 2.0 and data["score"]["value"] is not None


def test_the_page_is_cached_for_twenty_seconds(client: Client) -> None:
    sid = create(client).json["site_id"]
    assert client.call("GET", f"/sites/{sid}").json["recent_receipts"] == []
    store.ReceiptRepo(client.tables.receipts).put_with_guard(
        stored_receipt(sid, "j_aaaaaaaaaaaa", "2026-10-09T10:00:00+05:30")
    )
    client.clock.advance(seconds=19)
    assert client.call("GET", f"/sites/{sid}").json["recent_receipts"] == []  # still cached
    client.clock.advance(seconds=2)
    assert len(client.call("GET", f"/sites/{sid}").json["recent_receipts"]) == 1


def test_the_cache_is_per_site(client: Client) -> None:
    a, b = create(client).json["site_id"], create(client, name="Other Lab").json["site_id"]
    assert client.call("GET", f"/sites/{a}").json["site"]["name"] == "CSE GPU Lab"
    assert client.call("GET", f"/sites/{b}").json["site"]["name"] == "Other Lab"


def test_old_receipts_leave_the_thirty_day_window(client: Client) -> None:
    sid = create(client).json["site_id"]
    store.ReceiptRepo(client.tables.receipts).put_with_guard(
        stored_receipt(sid, "j_aaaaaaaaaaaa", "2026-10-09T10:00:00+05:30")
    )
    assert len(client.call("GET", f"/sites/{sid}").json["recent_receipts"]) == 1
    client.clock.advance(days=31)
    assert client.call("GET", f"/sites/{sid}").json["recent_receipts"] == []


def test_dates_are_never_in_the_future_of_the_clock(client: Client) -> None:
    sid = create(client).json["site_id"]
    store.ReceiptRepo(client.tables.receipts).put_with_guard(
        stored_receipt(sid, "j_aaaaaaaaaaaa", (api_helpers.NOW + timedelta(hours=3)).isoformat())
    )
    assert client.call("GET", f"/sites/{sid}").json["recent_receipts"] == []


def test_new_sites_are_limited_per_day(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    """Anyone can register a site, so the number made per IST day is capped (finding: spam)."""
    monkeypatch.setattr(api, "MAX_SITES_PER_DAY", 2)
    assert [create(client, name=f"Lab {n}").status for n in range(3)] == [201, 201, 429]
    refused = create(client, name="Lab refused")
    assert refused.json["error"] == "rate_limited" and "tomorrow" in refused.json["message"]
    names = [s["name"] for s in store.SiteRepo(client.tables.sites).scan_all()]
    assert sorted(names) == ["Lab 0", "Lab 1"]  # refused sites are never stored
    client.clock.advance(days=1)
    assert create(client, name="Lab next day").status == 201


def test_a_refused_request_does_not_use_up_the_site_quota(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api, "MAX_SITES_PER_DAY", 1)
    assert create(client, name="").status == 400  # invalid: not counted
    assert create(client, name="Lab one").status == 201
