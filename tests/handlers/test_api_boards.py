"""GET /leaderboard and GET /assumptions (plan 05.8, contract 08 §3.5-3.6)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from api_helpers import Client

from engine.factors import load_cities, load_factors
from handlers import store

END = "2026-10-09T10:00:00+05:30"


def add_site(client: Client, site_id: str, name: str, gpu_count: int = 4, **extra: Any) -> None:
    store.SiteRepo(client.tables.sites).create(
        {
            "site_id": site_id,
            "name": name,
            "org": None,
            "city": "Chennai",
            "cooling": "room_ac",
            "gpu_count": gpu_count,
            "division": None,
            "coverage_declared": 0.9,
            "public": True,
            "simulated": False,
            "created_at": END,
            **extra,
        }
    )


def add_receipt(
    client: Client, site_id: str, job: str, capture: float, kwh: float = 1.0, end: str = END
) -> None:
    actual = {"E_fac_kwh": 2.0, "litres": 3.0, "W_l": 4.0, "C_kg": 1.0, "person_days": 0.01}
    store.ReceiptRepo(client.tables.receipts).put_with_guard(
        {
            "site_id": site_id,
            "job_id": job,
            "end_ts": end,
            "start_ts": end,
            "plan_id": "p_aaaaaaaaaa",
            "method": "nvml_energy",
            "kwh": kwh,
            "capture": capture,
            "flexible": True,
            "no_room": False,
            "scored": True,
            "slots": [],
            "absolute": {"actual": actual},
        }
    )


def board(client: Client, **query: str) -> Any:
    return client.call("GET", "/leaderboard", query=query or None)


# leaderboard --------------------------------------------------------------------------------


def test_default_query_is_division_d1_30_days_by_score(client: Client) -> None:
    reply = board(client)
    assert reply.status == 200 and reply.headers["cache-control"] == "no-store"
    data = reply.json
    assert (data["division"], data["period"], data["board"]) == ("D1", "30d", "score")
    assert data["rows"] == [] and data["generated_at"] == "2026-10-09T21:14:00+05:30"


@pytest.mark.parametrize(
    "query",
    [
        {"division": "D9"},
        {"division": "d1"},
        {"division": ""},
        {"period": "7d"},
        {"board": "improved"},
        {"board": "basin"},
        {"period": "30d; DROP"},
    ],
)
def test_invalid_query_values_are_400(client: Client, query: dict[str, str]) -> None:
    reply = board(client, **query)
    assert reply.status == 400 and reply.json["error"] == "invalid_field"


def test_rows_are_ranked_by_score_with_the_documented_fields(client: Client) -> None:
    add_site(client, "s_aaaaaaaaaa", "Alpha Lab")
    add_site(client, "s_bbbbbbbbbb", "Beta Lab")
    add_receipt(client, "s_aaaaaaaaaa", "j_aaaaaaaaaaaa", capture=0.9)
    add_receipt(client, "s_bbbbbbbbbb", "j_bbbbbbbbbbbb", capture=0.3)
    rows = board(client).json["rows"]
    assert [r["name"] for r in rows] == ["Alpha Lab", "Beta Lab"]
    assert [r["rank"] for r in rows] == [1, 2]
    assert rows[0]["score"] > rows[1]["score"]
    first = rows[0]
    for key in (
        "site_id",
        "simulated",
        "badge",
        "provisional",
        "A",
        "C",
        "flex_share",
        "monthly_absolute",
        "receipts",
    ):
        assert key in first, key
    assert first["receipts"] == 1
    assert set(first["monthly_absolute"]) >= {"kwh", "litres", "kg_co2", "person_days"}


def test_no_row_exposes_a_gpu_count(client: Client) -> None:
    add_site(client, "s_aaaaaaaaaa", "Alpha Lab", gpu_count=7)
    add_receipt(client, "s_aaaaaaaaaa", "j_aaaaaaaaaaaa", capture=0.9)
    text = board(client).text
    assert "gpu_count" not in text and '"gpus"' not in text


def test_an_unrated_site_is_listed_after_rated_ones(client: Client) -> None:
    add_site(client, "s_aaaaaaaaaa", "Unrated Lab")
    add_site(client, "s_bbbbbbbbbb", "Rated Lab")
    add_receipt(client, "s_bbbbbbbbbb", "j_bbbbbbbbbbbb", capture=0.5)
    rows = board(client).json["rows"]
    assert [r["name"] for r in rows] == ["Rated Lab", "Unrated Lab"]
    assert rows[1]["rank"] is None and rows[1]["score"] is None


def test_only_the_asked_division_and_only_public_sites_appear(client: Client) -> None:
    fs = load_factors().central()
    big = int(fs["div_d1_max"]) + 1
    add_site(client, "s_aaaaaaaaaa", "Small Lab", gpu_count=2)
    add_site(client, "s_bbbbbbbbbb", "Big Lab", gpu_count=big)
    add_site(client, "s_cccccccccc", "Hidden Lab", gpu_count=2, public=False)
    d1 = [r["name"] for r in board(client, division="D1").json["rows"]]
    d2 = [r["name"] for r in board(client, division="D2").json["rows"]]
    assert d1 == ["Small Lab"] and d2 == ["Big Lab"]


def test_simulated_sites_are_included_and_flagged(client: Client) -> None:
    add_site(client, "s_simaaaaaaa", "Demo Lab, Chennai (simulated)", simulated=True)
    add_receipt(client, "s_simaaaaaaa", "j_aaaaaaaaaaaa", capture=0.7)
    (row,) = board(client).json["rows"]
    assert row["simulated"] is True and row["name"].endswith("(simulated)")


def test_the_board_is_cached_for_twenty_seconds(client: Client) -> None:
    add_site(client, "s_aaaaaaaaaa", "Alpha Lab")
    assert len(board(client).json["rows"]) == 1
    add_site(client, "s_bbbbbbbbbb", "Beta Lab")
    client.clock.advance(seconds=19)
    assert len(board(client).json["rows"]) == 1  # cache hit
    client.clock.advance(seconds=2)
    assert len(board(client).json["rows"]) == 2  # expired


def test_cache_entries_are_per_division(client: Client) -> None:
    add_site(client, "s_aaaaaaaaaa", "Alpha Lab")
    assert len(board(client, division="D1").json["rows"]) == 1
    assert board(client, division="D2").json["rows"] == []


def test_receipts_outside_thirty_days_do_not_count(client: Client) -> None:
    add_site(client, "s_aaaaaaaaaa", "Alpha Lab")
    add_receipt(
        client, "s_aaaaaaaaaa", "j_aaaaaaaaaaaa", capture=0.9, end="2026-08-01T10:00:00+05:30"
    )
    (row,) = board(client).json["rows"]
    assert row["receipts"] == 0 and row["score"] is None


def test_many_sites_do_not_break_the_board(client: Client) -> None:
    for i in range(25):
        sid = f"s_{'abcdefghijklmnopqrstuvwxy'[i] * 10}"
        add_site(client, sid, f"Lab {i}")
        add_receipt(client, sid, f"j_{'abcdefghijklmnopqrstuvwxy'[i] * 12}", capture=i / 30)
    rows = board(client).json["rows"]
    assert len(rows) == 25 and [r["rank"] for r in rows] == list(range(1, 26))
    scores = [r["score"] for r in rows]
    assert scores == sorted(scores, reverse=True)


# assumptions --------------------------------------------------------------------------------


def test_assumptions_lists_factors_gpus_cities_and_sources(client: Client) -> None:
    reply = client.call("GET", "/assumptions")
    assert reply.status == 200 and reply.headers["cache-control"] == "max-age=300"
    data = reply.json
    fx = load_factors()
    assert data["version"] == fx.version
    assert len(data["factors"]) == len(fx.table())
    assert {"id", "label", "value", "unit", "status"} <= set(data["factors"][0])
    gpu = next(g for g in data["gpus"] if g["id"] == "RTX-4090")
    assert gpu["p_max_w"] == 450 and gpu["p_idle_w"] > 0 and gpu["label"]
    assert gpu["sweep_status"] in {"measured", "placeholder"}
    assert {c["id"] for c in data["cities"]} == set(load_cities())
    assert all(c["stress_weight"] > 0 and c["stress_category"] for c in data["cities"])
    assert set(data["stress_weights"]) >= {"low", "extremely_high"}
    names = {s["name"] for s in data["sources"]}
    assert {"Open-Meteo", "CEA", "WRI Aqueduct"} <= names
    assert all(s["url"].startswith("https://") and s["licence"] for s in data["sources"])


def test_assumptions_is_valid_json_without_nan(client: Client) -> None:
    text = client.call("GET", "/assumptions").text
    assert json.loads(text, parse_constant=lambda c: pytest.fail(f"bad constant {c}"))


def test_assumptions_marks_placeholder_sweeps_until_measured(client: Client) -> None:
    gpus = client.call("GET", "/assumptions").json["gpus"]
    assert {g["sweep_status"] for g in gpus} == {"placeholder"}  # no GPU box measured yet
