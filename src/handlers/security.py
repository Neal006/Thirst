"""Site tokens and HMAC signature checks (plan 05.7, TRD 7.1, contract 08 §6).

token     = hex(HMAC_SHA256(server_secret, site_id))
signature = hex(HMAC_SHA256(token_as_ascii, timestamp + "." + raw_body))

Nothing here logs the token, the signature or the secret.
"""

from __future__ import annotations

import base64
import binascii
import functools
import hashlib
import hmac
import os
import re
from collections.abc import Mapping
from typing import Any

from .errors import ApiError

MAX_SKEW_SECONDS = 600
_TS = re.compile(r"[0-9]{1,12}")
_SIG = re.compile(r"[0-9a-f]{64}")
_HEADERS = ("x-thirst-timestamp", "x-thirst-signature", "x-thirst-site")

_BAD_SIGNATURE = "This receipt could not be verified. Run `thirst doctor`."
_STALE = "Your computer clock is more than 10 minutes off."


def _mac(key: bytes, message: bytes) -> str:
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def site_token(secret: bytes, site_id: str) -> str:
    if not secret:
        raise ValueError("server secret must not be empty")
    return _mac(secret, site_id.encode("utf-8"))


def sign(token: str, timestamp: str, body: bytes) -> str:
    return _mac(token.encode("ascii"), timestamp.encode("ascii") + b"." + body)


def verify_signature(
    secret: bytes, site_id: str, timestamp: str, body: bytes, signature: str, now: int
) -> None:
    """Raise ApiError(401) unless the timestamp is fresh and the signature is ours."""
    if not _TS.fullmatch(timestamp) or abs(now - int(timestamp)) > MAX_SKEW_SECONDS:
        raise ApiError(401, "stale_timestamp", _STALE)
    expected = sign(site_token(secret, site_id), timestamp, body)
    # Both sides are ASCII hex, so compare_digest never sees a non-ASCII str (it would raise).
    if not _SIG.fullmatch(signature) or not hmac.compare_digest(
        expected.encode("ascii"), signature.encode("ascii")
    ):
        raise ApiError(401, "bad_signature", _BAD_SIGNATURE)


def require_headers(headers: Mapping[str, str]) -> tuple[str, str, str]:
    """(timestamp, signature, site) from the request headers, matched case-insensitively."""
    lowered = {str(k).lower(): v for k, v in headers.items()}
    values = [lowered.get(name) for name in _HEADERS]
    if not all(isinstance(v, str) and v for v in values):
        raise ApiError(401, "missing_signature", _BAD_SIGNATURE)
    timestamp, signature, site = values
    return str(timestamp), str(signature), str(site)


def raw_body(event: Mapping[str, Any]) -> bytes:
    """The exact bytes the client signed. HTTP API may base64-encode the body (D21)."""
    body = event.get("body")
    if body is None:
        return b""
    if event.get("isBase64Encoded"):
        try:
            return base64.b64decode(body, validate=True)
        except (binascii.Error, ValueError):
            raise ApiError(400, "invalid_field", "body: could not be decoded.") from None
    return str(body).encode("utf-8")


def _ssm_client() -> Any:
    import boto3

    return boto3.client("ssm")


@functools.lru_cache(maxsize=1)
def load_secret() -> bytes:
    """The server secret from SSM, read once per cold start."""
    name = os.environ["SERVER_SECRET_PARAM"]
    value = _ssm_client().get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]
    return str(value).encode("utf-8")
