"""Plan 04.2: HTTP client, HMAC signing, retries, error mapping, idempotent receipt posting."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from thirst import client as client_mod
from thirst.errors import ApiError

from handlers import security

VECTORS = json.loads(
    (Path(__file__).resolve().parents[1] / "vectors" / "hmac.json").read_text(encoding="utf-8")
)
TOKEN = VECTORS["token"]
SITE = VECTORS["site_id"]
SECRET = VECTORS["server_secret"].encode()
NOW = VECTORS["ts"]
BASE = "https://api.example.com"


class Server:
    """A scripted fake server: replies in order, records every request."""

    def __init__(self, *replies: Any) -> None:
        self.replies = list(replies)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply


def reply(status: int, payload: Any = None, **kwargs: Any) -> httpx.Response:
    return httpx.Response(status, json=payload if payload is not None else {}, **kwargs)


def make_client(
    server: Server, sleeps: list[float] | None = None, clock: Callable[[], float] | None = None
) -> client_mod.Client:
    record = [] if sleeps is None else sleeps
    return client_mod.Client(
        BASE,
        token=TOKEN,
        site_id=SITE,
        transport=httpx.MockTransport(server),
        sleep=record.append,
        clock=clock or (lambda: float(NOW)),
    )


RECEIPT = {"job_id": "j_aaaaaaaaaaaa", "site_id": SITE, "slots": [{"hour": "x", "run_kwh": 1.5}]}


# ---------------------------------------------------------------- signing


def test_sign_matches_the_shared_vector() -> None:
    body = VECTORS["body"].encode()

    assert client_mod.sign(TOKEN, str(VECTORS["ts"]), body) == VECTORS["signature"]


def test_sign_differs_when_the_body_has_a_trailing_space() -> None:
    body = (VECTORS["body"] + " ").encode()
    signature = client_mod.sign(TOKEN, str(VECTORS["ts"]), body)

    assert signature == VECTORS["signature_trailing_space"]
    assert signature != VECTORS["signature"]


def test_receipt_is_signed_over_the_exact_bytes_sent() -> None:
    server = Server(reply(200, {"capture": 0.5}))

    make_client(server).post_receipt(RECEIPT)

    sent = server.requests[0]
    assert sent.headers["x-thirst-signature"] == client_mod.sign(
        TOKEN, sent.headers["x-thirst-timestamp"], sent.content
    )
    assert json.loads(sent.content) == RECEIPT


def test_signature_verifies_against_the_real_server_check() -> None:
    server = Server(reply(200, {}))

    make_client(server).post_receipt(RECEIPT)

    sent = server.requests[0]
    security.verify_signature(
        SECRET,
        SITE,
        sent.headers["x-thirst-timestamp"],
        sent.content,
        sent.headers["x-thirst-signature"],
        now=NOW,
    )


def test_a_body_changed_after_signing_would_fail_the_server_check() -> None:
    server = Server(reply(200, {}))
    make_client(server).post_receipt(RECEIPT)
    sent = server.requests[0]

    with pytest.raises(Exception, match="could not be verified"):
        security.verify_signature(
            SECRET,
            SITE,
            sent.headers["x-thirst-timestamp"],
            sent.content + b" ",
            sent.headers["x-thirst-signature"],
            now=NOW,
        )


def test_headers_follow_the_contract() -> None:
    server = Server(reply(200, {}))

    make_client(server).post_receipt(RECEIPT)

    headers = server.requests[0].headers
    assert headers["x-thirst-timestamp"] == str(NOW)
    assert headers["x-thirst-site"] == SITE
    assert headers["content-type"] == "application/json"
    assert headers["user-agent"].startswith("thirst-cli/")
    assert server.requests[0].url == httpx.URL(f"{BASE}/receipts")


def test_plan_and_site_requests_are_not_signed_and_never_carry_the_token() -> None:
    server = Server(reply(200, {"plan_id": "p_x"}), reply(201, {"site_id": SITE, "token": TOKEN}))
    client = make_client(server)

    client.post_plan({"work_hours": 1})
    client.post_site({"name": "Lab"})

    for request in server.requests:
        assert "x-thirst-signature" not in request.headers
        assert TOKEN not in str(dict(request.headers))


# ---------------------------------------------------------------- timeouts and retries


def test_timeouts_are_5s_connect_and_15s_read() -> None:
    server = Server(reply(200, {}))

    make_client(server).post_plan({})

    timeout = server.requests[0].extensions["timeout"]
    assert timeout["connect"] == 5
    assert timeout["read"] == 15


def test_server_errors_are_retried_with_backoff_then_succeed() -> None:
    server = Server(
        reply(503, {"error": "try_again", "message": "x"}), reply(500), reply(200, {"ok": 1})
    )
    sleeps: list[float] = []

    result = make_client(server, sleeps).post_plan({})

    assert result == {"ok": 1}
    assert len(server.requests) == 3
    assert sleeps == [1, 2]


def test_gives_up_after_three_retries() -> None:
    server = Server(reply(503, {"error": "try_again", "message": "Something went wrong."}))
    sleeps: list[float] = []

    with pytest.raises(ApiError) as err:
        make_client(server, sleeps).post_plan({})

    assert len(server.requests) == 4
    assert sleeps == [1, 2, 4]
    assert err.value.status == 503
    assert err.value.code == "try_again"


def test_network_errors_are_retried_and_reported_in_plain_words() -> None:
    server = Server(httpx.ConnectError("boom with secret-looking detail"))
    sleeps: list[float] = []

    with pytest.raises(ApiError) as err:
        make_client(server, sleeps).post_plan({})

    assert len(server.requests) == 4
    assert err.value.code == "network_error"
    assert err.value.status == 0
    assert "internet" in err.value.message
    assert "secret-looking" not in err.value.message
    assert "Traceback" not in err.value.message


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 413, 422, 429])
def test_client_errors_are_never_retried(status: int) -> None:
    server = Server(reply(status, {"error": "invalid_field", "message": "work_hours: too big"}))
    sleeps: list[float] = []

    with pytest.raises(ApiError) as err:
        make_client(server, sleeps).post_plan({})

    assert len(server.requests) == 1
    assert sleeps == []
    assert err.value.status == status
    assert err.value.message == "work_hours: too big"


def test_each_retry_gets_a_fresh_timestamp_and_a_matching_signature() -> None:
    server = Server(reply(503), reply(200, {}))
    ticks = iter([1000.0, 1002.0])

    make_client(server, clock=lambda: next(ticks)).post_receipt(RECEIPT)

    first, second = server.requests
    assert first.headers["x-thirst-timestamp"] == "1000"
    assert second.headers["x-thirst-timestamp"] == "1002"
    assert first.content == second.content
    assert second.headers["x-thirst-signature"] == client_mod.sign(TOKEN, "1002", second.content)


# ---------------------------------------------------------------- error mapping


def test_error_envelope_becomes_a_readable_message() -> None:
    body = {"error": "deadline_too_soon", "message": "This job needs until 09:00."}
    server = Server(reply(422, body))

    with pytest.raises(ApiError) as err:
        make_client(server).post_plan({})

    assert (err.value.code, err.value.status) == ("deadline_too_soon", 422)
    assert err.value.message == "This job needs until 09:00."
    assert err.value.exit_code == 4


def test_non_json_error_bodies_get_a_generic_message() -> None:
    gateway = httpx.Response(502, text="<html>Bad gateway</html>")
    server = Server(gateway)

    with pytest.raises(ApiError) as err:
        make_client(server, []).post_plan({})

    assert err.value.status == 502
    assert "<html>" not in err.value.message
    assert "try again" in err.value.message.lower()


def test_rate_limit_message_is_plain() -> None:
    server = Server(reply(429, {"error": "rate_limited", "message": "Too many today."}))

    with pytest.raises(ApiError) as err:
        make_client(server).post_site({})

    assert err.value.code == "rate_limited"


def test_a_2xx_that_is_not_json_is_an_error() -> None:
    server = Server(httpx.Response(200, text="ok"))

    with pytest.raises(ApiError) as err:
        make_client(server).post_plan({})

    assert err.value.code == "bad_response"


def test_non_finite_numbers_are_refused_before_sending() -> None:
    server = Server(reply(200, {}))

    with pytest.raises(ApiError):
        make_client(server).post_receipt({**RECEIPT, "slots": [{"run_kwh": float("nan")}]})
    assert server.requests == []


# ---------------------------------------------------------------- receipts


def test_duplicate_job_is_reported_as_already_recorded() -> None:
    server = Server(reply(409, {"error": "duplicate_job", "message": "Already recorded."}))

    outcome = make_client(server).post_receipt(RECEIPT)

    assert outcome.duplicate is True
    assert outcome.response is None


def test_normal_receipt_returns_the_scored_response() -> None:
    server = Server(reply(200, {"capture": 0.86}))

    outcome = make_client(server).post_receipt(RECEIPT)

    assert outcome.duplicate is False
    assert outcome.response == {"capture": 0.86}


def test_bad_signature_error_keeps_the_server_hint() -> None:
    message = "This receipt could not be verified. Run `thirst doctor`."
    server = Server(reply(401, {"error": "bad_signature", "message": message}))

    with pytest.raises(ApiError) as err:
        make_client(server).post_receipt(RECEIPT)

    assert err.value.message == message


# ---------------------------------------------------------------- other calls


def test_get_site_and_register_paths() -> None:
    server = Server(reply(200, {"site": {}}), reply(201, {"site_id": SITE, "token": TOKEN}))
    client = make_client(server)

    client.get_site(SITE)
    created = client.post_site({"name": "Lab"})

    assert server.requests[0].method == "GET"
    assert server.requests[0].url.path == f"/sites/{SITE}"
    assert created["token"] == TOKEN


def test_get_site_refuses_an_id_that_could_change_the_path() -> None:
    server = Server(reply(200, {}))

    with pytest.raises(ApiError):
        make_client(server).get_site("../../etc")
    assert server.requests == []


def test_server_time_comes_from_the_date_header() -> None:
    date = "Fri, 10 Oct 2025 04:00:00 GMT"
    server = Server(httpx.Response(200, json={}, headers={"Date": date}))

    when = make_client(server).get_server_time()

    assert when == datetime(2025, 10, 10, 4, 0, tzinfo=UTC)
    assert server.requests[0].url.path == "/assumptions"


def test_missing_date_header_is_an_error() -> None:
    server = Server(httpx.Response(200, json={}))

    with pytest.raises(ApiError):
        make_client(server).get_server_time()


# ---------------------------------------------------------------- secrets


def test_logging_never_contains_the_token_or_signature(caplog: pytest.LogCaptureFixture) -> None:
    server = Server(reply(200, {"ok": True}))
    caplog.set_level(logging.DEBUG)

    make_client(server).post_receipt(RECEIPT)

    signature = server.requests[0].headers["x-thirst-signature"]
    assert TOKEN not in caplog.text
    assert signature not in caplog.text
    assert "/receipts" in caplog.text
    assert "200" in caplog.text


def test_client_repr_hides_the_token() -> None:
    assert TOKEN not in repr(make_client(Server(reply(200))))
