"""POST /receipts and GET /receipts/{site}/{job} (plan 05.7, contract 08 §3.4, TRD 7.1)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import api_helpers
import pytest
from api_helpers import Client

from engine.units import floor_hour
from handlers import store

VECTORS = json.loads((Path(__file__).parents[1] / "vectors" / "hmac.json").read_text("utf-8"))
JOB = "j_abcdefghijkl"


@dataclass
class Scene:
    client: Client
    site_id: str
    token: str
    plan: dict[str, Any]

    def receipt(self, **changes: Any) -> dict[str, Any]:
        """A receipt that follows the chosen plan, with plausible energy."""
        run_rows = [r for r in self.plan["chosen"]["schedule"] if r["state"] == "run"]
        first = datetime.fromisoformat(run_rows[0]["slot"])
        last = datetime.fromisoformat(run_rows[-1]["slot"])
        body: dict[str, Any] = {
            "site_id": self.site_id,
            "plan_id": self.plan["plan_id"],
            "job_id": JOB,
            "start_ts": (first + timedelta(minutes=3)).isoformat(),
            "end_ts": (last + timedelta(minutes=55)).isoformat(),
            "slots": [
                {"hour": r["slot"], "run_kwh": 0.2, "idle_kwh": 0.0, "level": r["level"]}
                for r in run_rows
            ],
            "cap_applied": True,
            "cap_method": "nvml",
            "method": "nvml_energy",
            "gpu": {"name": "NVIDIA GeForce RTX 4090", "driver": "550.54", "count": 2},
            "exit_code": 0,
            "interrupted": False,
            "overran": False,
            "cli_version": "0.1.0",
        }
        body.update(changes)
        return body

    def finish(self, body: dict[str, Any]) -> None:
        """Move the server clock to just after the job ended."""
        self.client.clock.set(datetime.fromisoformat(body["end_ts"]) + timedelta(minutes=5))

    def post(self, body: dict[str, Any], **kw: Any) -> api_helpers.Reply:
        return self.client.post_signed("/receipts", self.site_id, body, token=self.token, **kw)


@pytest.fixture
def scene(client: Client) -> Scene:
    site = client.call(
        "POST",
        "/sites",
        {
            "name": "CSE GPU Lab",
            "city": "Chennai",
            "cooling": "room_ac",
            "gpu_count": 2,
            "coverage_declared": 0.9,
        },
    ).json
    plan = client.call(
        "POST",
        "/plan",
        {
            "site_id": site["site_id"],
            "gpu_model": "RTX-4090",
            "gpu_count": 2,
            "work_hours": 4,
            "deadline": "2026-10-10T20:00:00+05:30",
            "pausable": False,
            "alpha": 0.5,
        },
    ).json
    return Scene(client, site["site_id"], site["token"], plan)


def stored_receipts(client: Client, site_id: str) -> list[dict[str, Any]]:
    items = client.tables.receipts.query(
        KeyConditionExpression="site_id = :s", ExpressionAttributeValues={":s": site_id}
    )["Items"]
    return [i for i in items if not i["sk"].startswith("job#")]


# the happy path --------------------------------------------------------------------------


def test_a_valid_signed_receipt_is_scored(scene: Scene) -> None:
    body = scene.receipt()
    scene.finish(body)
    reply = scene.post(body)
    assert reply.status == 200, reply.text
    data = reply.json
    assert data["receipt_id"].startswith(f"{scene.site_id}#") and data["receipt_id"].endswith(JOB)
    assert set(data["scoring"]) >= {"base", "best", "actual", "J"}
    assert data["scoring"]["J"]["base"] == pytest.approx(1.0)
    assert set(data["absolute"]) >= {"base", "best", "actual", "basis"}
    assert data["tags"]["energy"] == "measured"
    assert data["capture"] is None or 0.0 <= data["capture"] <= 1.0
    assert isinstance(data["no_room"], bool) and data["flexible"] == (not data["no_room"])
    assert set(data["site_score"]) == {"value", "badge", "provisional"}
    assert data["url"] == f"/receipts/{scene.site_id}/{JOB}"
    assert "NaN" not in reply.text


def test_the_receipt_is_stored_with_a_canonical_sort_key(scene: Scene) -> None:
    body = scene.receipt()
    scene.finish(body)
    assert scene.post(body).status == 200
    (item,) = stored_receipts(scene.client, scene.site_id)
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+05:30#" + JOB, item["sk"])
    assert item["sk"] == f"{body['end_ts']}#{JOB}" and item["scored"] is True
    assert item["plan_id"] == scene.plan["plan_id"] and item["method"] == "nvml_energy"
    assert item["gpu"]["count"] == 2


def test_other_offsets_are_stored_as_ist(scene: Scene) -> None:
    body = scene.receipt()
    end = datetime.fromisoformat(body["end_ts"])
    body["end_ts"] = end.astimezone(UTC).isoformat()  # "...+00:00"
    assert body["end_ts"].endswith("+00:00")
    scene.finish({"end_ts": end.isoformat()})
    assert scene.post(body).status == 200
    (item,) = stored_receipts(scene.client, scene.site_id)
    assert item["end_ts"] == end.isoformat() and item["sk"].startswith(end.isoformat())


def test_the_same_body_as_base64_verifies_the_same_way(scene: Scene) -> None:
    body = scene.receipt()
    scene.finish(body)
    assert scene.post(body, b64=True).status == 200


def test_the_response_matches_what_get_returns_later(scene: Scene) -> None:
    body = scene.receipt()
    scene.finish(body)
    posted = scene.post(body).json
    got = scene.client.call("GET", f"/receipts/{scene.site_id}/{JOB}")
    assert got.status == 200 and got.headers["cache-control"] == "no-store"
    data = got.json
    for key in ("receipt_id", "scoring", "absolute", "capture", "no_room", "flexible", "tags"):
        assert data[key] == posted[key], key
    assert data["start_ts"] == body["start_ts"] and data["end_ts"] == body["end_ts"]
    assert data["method"] == "nvml_energy" and data["cap_applied"] is True
    assert data["cap_method"] == "nvml" and data["gpu"] == {"name": "NVIDIA GeForce RTX 4090"}
    assert [s["hour"] for s in data["slots"]] == [s["hour"] for s in body["slots"]]
    assert "gpu_count" not in got.text and '"count"' not in got.text


# signature (TRD 14) -------------------------------------------------------------------------


def test_one_changed_byte_is_a_bad_signature_and_stores_nothing(scene: Scene) -> None:
    body = scene.receipt()
    scene.finish(body)
    good = json.dumps(body).encode()
    reply = scene.client.post_signed(
        "/receipts",
        scene.site_id,
        raw=good + b" ",
        token=scene.token,
        extra={
            "x-thirst-signature": api_helpers.signature_for(
                scene.token, int(scene.client.clock().timestamp()), good
            )
        },
    )
    assert reply.status == 401 and reply.json["error"] == "bad_signature"
    assert stored_receipts(scene.client, scene.site_id) == []


@pytest.mark.parametrize("skew", [601, -601, 86_400])
def test_stale_or_future_timestamps_are_rejected(scene: Scene, skew: int) -> None:
    body = scene.receipt()
    scene.finish(body)
    stamp = int(scene.client.clock().timestamp()) + skew
    reply = scene.post(body, ts=stamp)
    assert reply.status == 401 and reply.json["error"] == "stale_timestamp"


@pytest.mark.parametrize("skew", [600, -600, 0])
def test_timestamps_inside_ten_minutes_pass(scene: Scene, skew: int) -> None:
    body = scene.receipt()
    scene.finish(body)
    assert scene.post(body, ts=int(scene.client.clock().timestamp()) + skew).status == 200


@pytest.mark.parametrize("missing", ["x-thirst-timestamp", "x-thirst-signature", "x-thirst-site"])
def test_a_missing_header_is_401(scene: Scene, missing: str) -> None:
    body = scene.receipt()
    scene.finish(body)
    raw = json.dumps(body).encode()
    stamp = int(scene.client.clock().timestamp())
    headers = {
        "x-thirst-timestamp": str(stamp),
        "x-thirst-signature": api_helpers.signature_for(scene.token, stamp, raw),
        "x-thirst-site": scene.site_id,
    }
    del headers[missing]
    reply = scene.client.call("POST", "/receipts", headers=headers, raw=raw)
    assert reply.status == 401 and reply.json["error"] == "missing_signature"


def test_another_sites_token_is_rejected(scene: Scene) -> None:
    other = scene.client.call(
        "POST",
        "/sites",
        {"name": "Other Lab", "city": "Pune", "cooling": "room_ac", "gpu_count": 1},
    ).json
    body = scene.receipt()
    scene.finish(body)
    reply = scene.client.post_signed("/receipts", scene.site_id, body, token=other["token"])
    assert reply.status == 401 and reply.json["error"] == "bad_signature"


def test_an_unknown_site_without_a_valid_signature_looks_the_same_as_a_known_one(
    scene: Scene,
) -> None:
    body = scene.receipt(site_id="s_zzzzzzzzzz")
    unknown = scene.client.post_signed("/receipts", "s_zzzzzzzzzz", body, token="00" * 32)
    known = scene.client.post_signed("/receipts", scene.site_id, body, token="00" * 32)
    assert unknown.status == known.status == 401
    assert unknown.json == known.json  # sites cannot be enumerated without the token


def test_a_validly_signed_request_for_a_deleted_site_is_404(scene: Scene) -> None:
    ghost = "s_ghostsite2"
    body = scene.receipt(site_id=ghost)
    scene.finish(body)
    reply = scene.client.post_signed("/receipts", ghost, body)  # signed with the real secret
    assert reply.status == 404 and reply.json["error"] == "site_not_found"


def test_the_shared_hmac_vectors_pass_the_signature_check(client: Client) -> None:
    # The vector site does not exist, so a request that passes the signature gets 404, not 401.
    client.clock.set(datetime.fromtimestamp(VECTORS["ts"], tz=UTC))
    body = VECTORS["body"].encode()
    headers = {
        "x-thirst-timestamp": str(VECTORS["ts"]),
        "x-thirst-signature": VECTORS["signature"],
        "x-thirst-site": VECTORS["site_id"],
    }
    assert client.call("POST", "/receipts", headers=headers, raw=body).status == 404
    tampered = client.call("POST", "/receipts", headers=headers, raw=body + b" ")
    assert tampered.status == 401 and tampered.json["error"] == "bad_signature"
    headers["x-thirst-signature"] = VECTORS["signature_trailing_space"]
    assert client.call("POST", "/receipts", headers=headers, raw=body).status == 401


def test_a_body_over_64_kb_is_413(scene: Scene) -> None:
    raw = json.dumps({"pad": "x" * 70_000}).encode()
    reply = scene.client.post_signed("/receipts", scene.site_id, raw=raw, token=scene.token)
    assert reply.status == 413 and reply.json["error"] == "body_too_large"


def test_the_body_site_must_match_the_header_site(scene: Scene) -> None:
    body = scene.receipt(site_id="s_aaaaaaaaaa")
    scene.finish(body)
    reply = scene.post(body)
    assert reply.status == 400 and reply.json["error"] == "invalid_field"


def test_unreadable_bodies_after_a_valid_signature_are_400(scene: Scene) -> None:
    for raw in (b"not json", b"[1]", b""):
        reply = scene.client.post_signed("/receipts", scene.site_id, raw=raw, token=scene.token)
        assert reply.status == 400 and reply.json["error"] == "invalid_field"


# checks on the content ------------------------------------------------------------------------


def test_energy_the_gpus_cannot_draw_over_the_job_time_is_rejected(scene: Scene) -> None:
    body = scene.receipt()
    first = datetime.fromisoformat(body["slots"][0]["hour"])
    # 30 minutes on 2 x 450 W allows at most 0.5 * 0.9 kW * 1.1 = 0.495 kWh in total
    body.update(
        start_ts=(first + timedelta(minutes=5)).isoformat(),
        end_ts=(first + timedelta(minutes=35)).isoformat(),
        slots=[{"hour": first.isoformat(), "run_kwh": 0.6, "idle_kwh": 0.0, "level": 1.0}],
    )
    scene.finish(body)
    reply = scene.post(body)
    assert reply.status == 422 and reply.json["error"] == "implausible_energy"
    assert stored_receipts(scene.client, scene.site_id) == []


def test_a_slot_hotter_than_the_gpus_allow_is_rejected(scene: Scene) -> None:
    body = scene.receipt()
    body["slots"][0]["run_kwh"] = 50.0
    scene.finish(body)
    assert scene.post(body).json["error"] == "implausible_energy"


def test_a_plan_of_another_site_is_403(scene: Scene) -> None:
    other = scene.client.call(
        "POST",
        "/sites",
        {"name": "Other Lab", "city": "Chennai", "cooling": "room_ac", "gpu_count": 2},
    ).json
    plan = scene.client.call(
        "POST",
        "/plan",
        {
            "site_id": other["site_id"],
            "gpu_model": "RTX-4090",
            "gpu_count": 2,
            "work_hours": 4,
            "deadline": "2026-10-10T20:00:00+05:30",
        },
    ).json
    body = scene.receipt(plan_id=plan["plan_id"])
    scene.finish(body)
    reply = scene.post(body)
    assert reply.status == 403 and reply.json["error"] == "plan_site_mismatch"


def test_a_plan_made_without_a_site_cannot_back_a_receipt(scene: Scene) -> None:
    plan = scene.client.call(
        "POST",
        "/plan",
        {
            "city": "Chennai",
            "cooling": "room_ac",
            "gpu_model": "RTX-4090",
            "gpu_count": 2,
            "work_hours": 4,
            "deadline": "2026-10-10T20:00:00+05:30",
        },
    ).json
    body = scene.receipt(plan_id=plan["plan_id"])
    scene.finish(body)
    assert scene.post(body).json["error"] == "plan_site_mismatch"


def test_a_missing_plan_is_404(scene: Scene) -> None:
    body = scene.receipt(plan_id="p_zzzzzzzzzz")
    scene.finish(body)
    reply = scene.post(body)
    assert reply.status == 404 and reply.json["error"] == "plan_not_found"


def test_a_repeated_job_id_is_409_and_stored_once(scene: Scene) -> None:
    body = scene.receipt()
    scene.finish(body)
    assert scene.post(body).status == 200
    again = scene.post(body)
    assert again.status == 409 and again.json["error"] == "duplicate_job"
    assert len(stored_receipts(scene.client, scene.site_id)) == 1


def test_slots_outside_the_job_are_422(scene: Scene) -> None:
    body = scene.receipt()
    end = datetime.fromisoformat(body["end_ts"])
    body["slots"].append(
        {
            "hour": (floor_hour(end) + timedelta(hours=2)).isoformat(),
            "run_kwh": 0.1,
            "idle_kwh": 0.0,
            "level": 1.0,
        }
    )
    scene.finish(body)
    reply = scene.post(body)
    assert reply.status == 422 and reply.json["error"] == "slot_out_of_range"


def test_a_job_that_starts_before_the_plan_was_made_is_422(scene: Scene) -> None:
    body = scene.receipt()
    early = datetime.fromisoformat("2026-10-09T18:30:00+05:30")  # plan made 21:14
    body.update(
        start_ts=early.isoformat(),
        slots=[
            {"hour": floor_hour(early).isoformat(), "run_kwh": 0.2, "idle_kwh": 0.0, "level": 1.0},
            *body["slots"],
        ],
    )
    scene.finish(body)
    reply = scene.post(body)
    assert reply.status == 422 and reply.json["error"] == "slot_out_of_range"


@pytest.mark.parametrize(
    "slot",
    [
        {"run_kwh": -1.0},
        {"idle_kwh": -0.1},
        {"level": 0.5},
        {"level": "1.0"},
        {"run_kwh": "0.2"},
        {"hour": "2026-10-10T03:30:00+05:30"},
    ],
)
def test_malformed_slots_are_400(scene: Scene, slot: dict[str, Any]) -> None:
    body = scene.receipt()
    body["slots"][0] = {**body["slots"][0], **slot}
    scene.finish(body)
    reply = scene.post(body)
    assert reply.status == 400 and reply.json["error"] == "invalid_field"


def test_more_than_72_slots_is_400(scene: Scene) -> None:
    body = scene.receipt()
    first = datetime.fromisoformat(body["slots"][0]["hour"])
    body["start_ts"] = first.isoformat()
    body["end_ts"] = (first + timedelta(hours=72)).isoformat()
    body["slots"] = [
        {
            "hour": (first + timedelta(hours=i)).isoformat(),
            "run_kwh": 0.01,
            "idle_kwh": 0.0,
            "level": 1.0,
        }
        for i in range(73)
    ]
    scene.finish(body)
    assert scene.post(body).status == 400


def test_a_receipt_that_ends_in_the_future_is_400(scene: Scene) -> None:
    body = scene.receipt()
    scene.client.clock.set(datetime.fromisoformat(body["end_ts"]) - timedelta(hours=1))
    reply = scene.post(body)
    assert reply.status == 400 and reply.json["error"] == "invalid_field"
    assert "future" in reply.json["message"]


def test_hours_after_the_forecast_window_are_scored_and_marked_extrapolated(scene: Scene) -> None:
    body = scene.receipt()
    start = datetime.fromisoformat("2026-10-11T21:30:00+05:30")  # slot 48 of the snapshot
    body.update(
        start_ts=start.isoformat(),
        end_ts=(start + timedelta(hours=1, minutes=10)).isoformat(),
        slots=[
            {"hour": "2026-10-11T21:00:00+05:30", "run_kwh": 0.2, "idle_kwh": 0.0, "level": 1.0},
            {"hour": "2026-10-11T22:00:00+05:30", "run_kwh": 0.2, "idle_kwh": 0.0, "level": 1.0},
        ],
    )
    scene.finish(body)
    assert scene.post(body).status == 200
    got = scene.client.call("GET", f"/receipts/{scene.site_id}/{JOB}").json
    assert [s.get("extrapolated") for s in got["slots"]] == [True, True]


def test_observed_weather_is_used_for_the_absolute_numbers(scene: Scene) -> None:
    body = scene.receipt()
    repo = store.WeatherRepo(scene.client.tables.weather)
    for slot in body["slots"]:
        repo.record_observation("Chennai", datetime.fromisoformat(slot["hour"]), 33.0, 60.0, 300.0)
    scene.finish(body)
    basis = scene.post(body).json["absolute"]["basis"]
    assert basis["observed"] == len(body["slots"]) and basis["forecast"] == 0


def test_without_observations_the_forecast_is_used(scene: Scene) -> None:
    body = scene.receipt()
    scene.finish(body)
    basis = scene.post(body).json["absolute"]["basis"]
    assert basis["observed"] == 0 and basis["forecast"] == len(body["slots"])


def test_a_modelled_receipt_is_tagged_modelled(scene: Scene) -> None:
    body = scene.receipt(method="modelled", cap_method="none", cap_applied=False)
    scene.finish(body)
    assert scene.post(body).json["tags"]["energy"] == "modelled"


# unverified receipts (D20) ------------------------------------------------------------------


def test_an_unverified_receipt_is_stored_but_never_counted(scene: Scene) -> None:
    body = scene.receipt(plan_id=None, method="unverified", cap_method="none", cap_applied=False)
    scene.finish(body)
    reply = scene.post(body)
    assert reply.status == 200, reply.text
    assert reply.json["scoring"] is None and reply.json["capture"] is None
    assert reply.json["tags"]["energy"] == "unverified"
    (item,) = stored_receipts(scene.client, scene.site_id)
    assert item["scored"] is False and item["method"] == "unverified"
    page = scene.client.call("GET", f"/sites/{scene.site_id}").json
    assert page["score"]["value"] is None and page["recent_receipts"] == []


# side effects ---------------------------------------------------------------------------------


def test_the_site_page_and_leaderboard_update_immediately(scene: Scene) -> None:
    sid = scene.site_id
    assert scene.client.call("GET", f"/sites/{sid}").json["recent_receipts"] == []
    rows = scene.client.call("GET", "/leaderboard", query={"division": "D1"}).json["rows"]
    assert [r for r in rows if r["site_id"] == sid][0]["receipts"] == 0
    body = scene.receipt()
    scene.finish(body)
    assert scene.post(body).status == 200
    page = scene.client.call("GET", f"/sites/{sid}").json  # no 20 s wait: cache was invalidated
    assert [r["job_id"] for r in page["recent_receipts"]] == [JOB]
    rows = scene.client.call("GET", "/leaderboard", query={"division": "D1"}).json["rows"]
    assert [r for r in rows if r["site_id"] == sid][0]["receipts"] == 1


def test_the_response_site_score_matches_the_site_page(scene: Scene) -> None:
    body = scene.receipt()
    scene.finish(body)
    posted = scene.post(body).json["site_score"]
    page = scene.client.call("GET", f"/sites/{scene.site_id}").json["score"]
    assert posted == {
        "value": page["value"],
        "badge": page["badge"],
        "provisional": page["provisional"],
    }


def test_logs_never_contain_the_token_or_the_signature(
    scene: Scene, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    caplog.set_level(logging.DEBUG)
    body = scene.receipt()
    scene.finish(body)
    raw = json.dumps(body).encode()
    stamp = int(scene.client.clock().timestamp())
    signature = api_helpers.signature_for(scene.token, stamp, raw)
    reply = scene.post(body, ts=stamp)
    assert reply.status == 200
    scene.post(body, ts=stamp)  # a 409 path as well
    output = capsys.readouterr().out + capsys.readouterr().err + caplog.text
    assert scene.token not in output and signature not in output
    assert JOB in output  # but the job is logged for support


def test_get_receipt_errors(scene: Scene) -> None:
    missing = scene.client.call("GET", f"/receipts/{scene.site_id}/j_zzzzzzzzzzzz")
    assert missing.status == 404 and missing.json["error"] == "receipt_not_found"
    assert scene.client.call("GET", "/receipts/bad/j_zzzzzzzzzzzz").status == 400
    assert scene.client.call("GET", f"/receipts/{scene.site_id}/bad").status == 400


def test_a_private_sites_receipt_is_not_found(client: Client) -> None:
    site = client.call(
        "POST",
        "/sites",
        {
            "name": "Private Lab",
            "city": "Chennai",
            "cooling": "room_ac",
            "gpu_count": 2,
            "public": False,
        },
    ).json
    plan = client.call(
        "POST",
        "/plan",
        {
            "site_id": site["site_id"],
            "gpu_model": "RTX-4090",
            "gpu_count": 2,
            "work_hours": 4,
            "deadline": "2026-10-10T20:00:00+05:30",
        },
    ).json
    scene = Scene(client, site["site_id"], site["token"], plan)
    body = scene.receipt()
    scene.finish(body)
    assert scene.post(body).status == 200
    reply = client.call("GET", f"/receipts/{site['site_id']}/{JOB}")
    assert reply.status == 404 and reply.json["error"] == "receipt_not_found"
