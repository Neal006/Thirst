"""POST /plan (plan 05.5, contract 08 §3.1)."""

from __future__ import annotations

import re
import time
from datetime import timedelta
from typing import Any

import api_helpers
import pytest
from api_helpers import Client

from handlers import api, store

BODY: dict[str, Any] = {
    "city": "Chennai",
    "cooling": "room_ac",
    "gpu_model": "RTX-4090",
    "gpu_count": 2,
    "work_hours": 6,
    "deadline": "2026-10-10T09:00:00+05:30",
    "pausable": True,
    "alpha": 0.5,
}


def plan(client: Client, **changes: Any) -> api_helpers.Reply:
    return client.call("POST", "/plan", {**BODY, **changes})


def test_a_valid_request_returns_a_stored_plan(client: Client) -> None:
    reply = plan(client)
    assert reply.status == 200
    data = reply.json
    assert re.fullmatch(r"p_[a-z2-7]{10}", data["plan_id"])
    assert data["submit_ts"] == api_helpers.NOW.isoformat()
    assert len(data["pareto"]) == 11 and len(data["series"]) == 48
    assert data["chosen"] == data["pareto"][5]  # alpha 0.5 is entry 5 of the 11 (D11)
    assert data["tags"]["forecast"] == "live"
    assert data["assumptions_url"] == "/assumptions"
    assert "forecast_snapshot" not in data  # stored, not returned
    stored = store.PlanRepo(client.tables.plans).get(data["plan_id"])
    assert stored is not None and stored["forecast_snapshot"]["city"] == "Chennai"
    assert stored["inputs"]["gpu_count"] == 2


def test_the_server_sets_the_time_and_the_id(client: Client) -> None:
    data = plan(client, submit_ts="2020-01-01T00:00:00+05:30", plan_id="p_aaaaaaaaaa").json
    assert data["submit_ts"] == api_helpers.NOW.isoformat()
    assert data["plan_id"] != "p_aaaaaaaaaa"


def test_two_requests_get_different_ids(client: Client) -> None:
    assert plan(client).json["plan_id"] != plan(client).json["plan_id"]


def test_responses_are_json_and_not_cached(client: Client) -> None:
    reply = plan(client)
    assert reply.headers["content-type"].startswith("application/json")
    assert reply.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("changes", "status", "code"),
    [
        ({"city": "Atlantis"}, 400, "unknown_city"),
        ({"gpu_model": "H900"}, 400, "unknown_gpu"),
        ({"gpu_count": 0}, 400, "invalid_field"),
        ({"gpu_count": 4097}, 400, "invalid_field"),
        ({"work_hours": 0}, 400, "invalid_field"),
        ({"work_hours": 48.5}, 400, "invalid_field"),
        ({"deadline": "2026-10-09T20:00:00+05:30"}, 400, "deadline_in_past"),
        ({"alpha": 1.5}, 400, "invalid_field"),
        ({"alpha": 0.55}, 400, "invalid_field"),
        ({"cooling": "liquid"}, 400, "invalid_field"),
        ({"site_id": "bad"}, 400, "invalid_field"),
    ],
)
def test_validation_errors_use_the_documented_codes(
    client: Client, changes: dict[str, Any], status: int, code: str
) -> None:
    reply = plan(client, **changes)
    assert reply.status == status
    assert set(reply.json) == {"error", "message"} and reply.json["error"] == code


def test_unknown_extra_fields_are_ignored(client: Client) -> None:
    assert plan(client, colour="blue", nested={"a": [1]}).status == 200


@pytest.mark.parametrize(
    "raw", [b"", b"not json", b"[1]", b'"x"', b"null", b'{"city":', b"\xff\xfe"]
)
def test_unreadable_bodies_are_400(client: Client, raw: bytes) -> None:
    reply = client.call("POST", "/plan", raw=raw)
    assert reply.status == 400 and reply.json["error"] == "invalid_field"


def test_a_body_over_8_kb_is_413(client: Client) -> None:
    reply = client.call("POST", "/plan", {**BODY, "pad": "x" * 9000})
    assert reply.status == 413 and reply.json["error"] == "body_too_large"


def test_base64_bodies_are_decoded(client: Client) -> None:
    reply = client.call("POST", "/plan", BODY, b64=True)
    assert reply.status == 200


def test_a_deadline_too_soon_names_the_earliest_finish(client: Client) -> None:
    reply = plan(client, work_hours=6, deadline="2026-10-10T00:00:00+05:30")
    assert reply.status == 422 and reply.json["error"] == "deadline_too_soon"
    assert "03:14 on 10 Oct" in reply.json["message"]


def test_missing_forecast_rows_fall_back_to_the_sample_and_say_so(
    client: Client, tables: store.Tables
) -> None:
    for item in tables.weather.scan()["Items"]:
        tables.weather.delete_item(Key={"city": item["city"], "hour": item["hour"]})
    data = plan(client).json
    assert data["tags"]["forecast"] == "cached"
    assert "forecast_cached" in data["notes"]
    assert data["forecast_age_hours"] is None


def test_a_partial_window_is_cached_and_reports_how_old_it_is(
    client: Client, tables: store.Tables
) -> None:
    for item in tables.weather.scan()["Items"]:
        if item["hour"] > "2026-10-10T08:00:00+05:30":
            tables.weather.delete_item(Key={"city": item["city"], "hour": item["hour"]})
    data = plan(client).json
    assert data["tags"]["forecast"] == "cached" and "forecast_cached" in data["notes"]
    assert data["forecast_age_hours"] == 1  # the seeded rows were issued an hour before NOW


def test_force_now_makes_chosen_the_base_plan(client: Client) -> None:
    data = plan(client, force_now=True, alpha=0.2).json
    assert data["chosen"]["schedule"] == data["base"]["schedule"]
    assert data["chosen"]["start"] == data["base"]["start"]
    assert "start_now_forced" in data["notes"]
    assert data["savings_ranges"] == {"water_pct": [0, 0], "co2_pct": [0, 0], "energy_pct": [0, 0]}


def test_pausable_not_allowed_never_pauses_and_says_why(client: Client) -> None:
    data = plan(client, pausable=True, pausable_allowed=False).json
    assert "pause_unsupported" in data["notes"]
    assert all(e["kind"] != "pausable" for e in data["pareto"])
    assert all(row["state"] != "pause" for e in data["pareto"] for row in e["schedule"])


def test_with_a_site_city_and_cooling_default_from_the_site(client: Client) -> None:
    site = client.call(
        "POST",
        "/sites",
        {"name": "Pune Lab", "city": "Pune", "cooling": "evaporative", "gpu_count": 4},
    ).json
    body = {k: v for k, v in BODY.items() if k not in ("city", "cooling")}
    api_helpers.seed_weather(client.tables, "Pune")
    reply = client.call("POST", "/plan", {**body, "site_id": site["site_id"]})
    assert reply.status == 200
    inputs = reply.json["inputs"]
    assert (inputs["city"], inputs["cooling"], inputs["site_id"]) == (
        "Pune",
        "evaporative",
        site["site_id"],
    )
    stored = store.PlanRepo(client.tables.plans).get(reply.json["plan_id"])
    assert stored is not None and stored["site_id"] == site["site_id"]


def test_without_a_site_city_and_cooling_are_required(client: Client) -> None:
    body = {k: v for k, v in BODY.items() if k not in ("city", "cooling")}
    reply = client.call("POST", "/plan", body)
    assert reply.status == 400 and reply.json["error"] == "invalid_field"


def test_an_unknown_site_is_404(client: Client) -> None:
    reply = plan(client, site_id="s_zzzzzzzzzz")
    assert reply.status == 404 and reply.json["error"] == "site_not_found"


def test_an_unexpected_failure_is_a_generic_503_without_details(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise RuntimeError("secret internal detail /var/task/handlers/api.py")

    monkeypatch.setattr(api.planner, "plan_from_rows", boom)
    reply = plan(client)
    assert reply.status == 503 and reply.json["error"] == "try_again"
    assert "secret" not in reply.text and "Traceback" not in reply.text


def test_a_storage_failure_is_a_generic_503(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self: Any, *a: Any, **k: Any) -> Any:
        raise store.NonFiniteNumber("non-finite number at $.base")

    monkeypatch.setattr(store.PlanRepo, "put", boom)
    reply = plan(client)
    assert reply.status == 503 and reply.json["error"] == "try_again"
    assert "non-finite" not in reply.text


def test_unknown_routes_and_methods_are_json_errors(client: Client) -> None:
    assert client.call("GET", "/nope").status == 404
    assert client.call("GET", "/nope").json["error"] == "not_found"
    assert client.call("GET", "/plan").status in (404, 405)


def test_a_request_takes_well_under_the_two_second_budget(client: Client) -> None:
    plan(client)  # warm-up
    started = time.perf_counter()
    for _ in range(5):
        assert plan(client).status == 200
    assert (time.perf_counter() - started) / 5 < 2.0  # PRD 8.1: p95 under 2000 ms


def test_the_clock_decides_the_window(client: Client) -> None:
    client.clock.advance(hours=1)  # one hour later: the first seeded hour is now past
    data = plan(client, deadline=(api_helpers.NOW + timedelta(hours=14)).isoformat()).json
    assert data["submit_ts"] == (api_helpers.NOW + timedelta(hours=1)).isoformat()
    assert data["series"][0]["slot"].startswith("2026-10-09T22:00")
