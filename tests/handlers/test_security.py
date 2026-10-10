"""Site tokens and signatures (plan 05.7, TRD 7.1, contract 08 §6 vectors)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from handlers import security
from handlers.errors import ApiError

VECTORS = json.loads((Path(__file__).parents[1] / "vectors" / "hmac.json").read_text("utf-8"))
SECRET = VECTORS["server_secret"].encode()
SITE = VECTORS["site_id"]
TOKEN = VECTORS["token"]
TS = VECTORS["ts"]
BODY = VECTORS["body"].encode()


def test_token_matches_the_shared_vector() -> None:
    assert security.site_token(SECRET, SITE) == TOKEN


def test_signature_matches_the_shared_vectors() -> None:
    assert security.sign(TOKEN, str(TS), BODY) == VECTORS["signature"]
    assert security.sign(TOKEN, str(TS), BODY + b" ") == VECTORS["signature_trailing_space"]
    assert VECTORS["signature"] != VECTORS["signature_trailing_space"]


def verify(body: bytes = BODY, sig: str | None = None, ts: Any = TS, now: int = TS) -> None:
    security.verify_signature(SECRET, SITE, str(ts), body, sig or VECTORS["signature"], now)


def test_valid_signature_passes() -> None:
    verify()


def test_one_changed_byte_is_rejected() -> None:
    with pytest.raises(ApiError) as err:
        verify(body=BODY + b" ")
    assert (err.value.status, err.value.code) == (401, "bad_signature")


def test_signature_for_another_site_is_rejected() -> None:
    with pytest.raises(ApiError) as err:
        security.verify_signature(SECRET, "s_zzzzzzzzzz", str(TS), BODY, VECTORS["signature"], TS)
    assert err.value.code == "bad_signature"


@pytest.mark.parametrize("skew", [601, -601, 100000])
def test_timestamps_outside_ten_minutes_are_stale(skew: int) -> None:
    with pytest.raises(ApiError) as err:
        verify(now=TS + skew)
    assert (err.value.status, err.value.code) == (401, "stale_timestamp")


@pytest.mark.parametrize("skew", [0, 599, -599, 600, -600])
def test_timestamps_inside_the_window_pass(skew: int) -> None:
    verify(now=TS + skew)


@pytest.mark.parametrize("ts", ["", "abc", "1.5", "-1", "1e9", " 1760030000", "١٧٦٠٠٣٠٠٠٠"])
def test_malformed_timestamps_are_stale_not_a_crash(ts: str) -> None:
    with pytest.raises(ApiError) as err:
        verify(ts=ts)
    assert err.value.status == 401


@pytest.mark.parametrize("sig", ["", "zz", "A" * 64, VECTORS["signature"][:-1], "é" * 64])
def test_malformed_signatures_are_rejected_without_crashing(sig: str) -> None:
    with pytest.raises(ApiError) as err:
        security.verify_signature(SECRET, SITE, str(TS), BODY, sig or "x", TS)
    assert err.value.status == 401


def test_uppercase_hex_of_the_right_signature_is_accepted_or_rejected_consistently() -> None:
    # The CLI always sends lowercase hex. Be strict: anything else is not our signature.
    with pytest.raises(ApiError):
        security.verify_signature(SECRET, SITE, str(TS), BODY, VECTORS["signature"].upper(), TS)


def test_missing_headers_are_reported_as_missing_signature() -> None:
    with pytest.raises(ApiError) as err:
        security.require_headers({"x-thirst-timestamp": "1"})
    assert (err.value.status, err.value.code) == (401, "missing_signature")
    assert security.require_headers(
        {"X-Thirst-Timestamp": "1", "x-thirst-signature": "ab", "X-THIRST-SITE": "s_a"}
    ) == ("1", "ab", "s_a")


def test_decode_body_handles_plain_and_base64() -> None:
    import base64

    assert security.raw_body({"body": '{"a": 1}', "isBase64Encoded": False}) == b'{"a": 1}'
    encoded = base64.b64encode(BODY).decode()
    assert security.raw_body({"body": encoded, "isBase64Encoded": True}) == BODY
    assert security.raw_body({"body": None}) == b""
    with pytest.raises(ApiError) as err:
        security.raw_body({"body": "!!!not base64!!!", "isBase64Encoded": True})
    assert err.value.status == 400


def test_empty_secret_is_refused() -> None:
    with pytest.raises(ValueError, match="secret"):
        security.site_token(b"", SITE)


def test_load_secret_reads_ssm_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class FakeSsm:
        def get_parameter(self, Name: str, WithDecryption: bool) -> dict[str, Any]:  # noqa: N803
            calls.append(Name)
            assert WithDecryption is True
            return {"Parameter": {"Value": "from-ssm"}}

    security.load_secret.cache_clear()
    monkeypatch.setenv("SERVER_SECRET_PARAM", "/thirst/server_secret")
    monkeypatch.setattr(security, "_ssm_client", lambda: FakeSsm())
    assert security.load_secret() == b"from-ssm"
    assert security.load_secret() == b"from-ssm"
    assert calls == ["/thirst/server_secret"]
    security.load_secret.cache_clear()


def test_the_vectors_file_is_what_the_generator_writes(tmp_path: Path) -> None:
    import importlib

    gen = importlib.import_module("gen_hmac_vectors")
    assert gen.build() == VECTORS
