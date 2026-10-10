"""HTTP client for the Thirst API (plan 04.2, contract 08 §3, TRD 7.1).

Receipts are signed: ``signature = hex(HMAC_SHA256(token_ascii, ts + "." + raw_body))``. The body is
serialised once to bytes and exactly those bytes are signed and sent. Retries (1, 2, 4 s) only
happen on network errors and 5xx, never on 4xx. The token and signature are never logged.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from . import __version__
from .errors import ApiError

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_S = 5.0
READ_TIMEOUT_S = 15.0
BACKOFF_SECONDS = (1.0, 2.0, 4.0)
_SITE_ID = re.compile(r"s_[a-z2-7]{10}")
_GENERIC = "The Thirst server had a problem. Please try again in a few minutes."


@dataclass(frozen=True)
class ReceiptPost:
    """Result of posting a receipt. ``duplicate`` means the server already had this job."""

    response: dict[str, Any] | None
    duplicate: bool


def sign(token: str, timestamp: str, body: bytes) -> str:
    """Hex HMAC-SHA256 of ``timestamp + "." + body`` keyed by the token's ASCII bytes."""
    message = timestamp.encode("ascii") + b"." + body
    return hmac.new(token.encode("ascii"), message, hashlib.sha256).hexdigest()


def encode_body(payload: Mapping[str, Any]) -> bytes:
    """The single serialisation of a request body. Refuses NaN and Infinity."""
    try:
        text = json.dumps(payload, separators=(",", ":"), sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        raise ApiError(
            "Could not prepare the request: a value was missing or not a finite number.",
            code="bad_request",
        ) from None
    return text.encode("ascii")  # ensure_ascii is on, so this cannot fail


def _error_for(response: httpx.Response) -> ApiError:
    """Turn an error response into a readable ``ApiError``, using the server's own words."""
    status = response.status_code
    try:
        data = response.json()
    except ValueError:
        data = None
    if isinstance(data, dict) and isinstance(data.get("error"), str):
        message = data.get("message")
        text = message if isinstance(message, str) and message else _GENERIC
        return ApiError(text, code=data["error"], status=status)
    if status >= 500:
        return ApiError(_GENERIC, code="server_error", status=status)
    return ApiError(f"The server refused the request (HTTP {status}).", "http_error", status)


class Client:
    def __init__(
        self,
        api_url: str,
        token: str = "",
        site_id: str = "",
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._base = api_url.rstrip("/")
        self._token = token
        self._site_id = site_id
        self._sleep = sleep
        self._clock = clock
        self._http = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(READ_TIMEOUT_S, connect=CONNECT_TIMEOUT_S),
            follow_redirects=False,
        )

    def __repr__(self) -> str:
        return f"Client(api_url={self._base!r}, site_id={self._site_id!r})"

    def close(self) -> None:
        self._http.close()

    # ------------------------------------------------------------ public calls

    def post_plan(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._json_call("POST", "/plan", encode_body(payload), signed=False)

    def post_site(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._json_call("POST", "/sites", encode_body(payload), signed=False)

    def get_site(self, site_id: str) -> dict[str, Any]:
        if not _SITE_ID.fullmatch(site_id):
            raise ApiError("That is not a valid site id.", code="bad_request")
        return self._json_call("GET", f"/sites/{site_id}", None, signed=False)

    def post_receipt(self, payload: Mapping[str, Any]) -> ReceiptPost:
        """Post a signed receipt. A 409 ``duplicate_job`` is not an error: it was recorded."""
        try:
            data = self._json_call("POST", "/receipts", encode_body(payload), signed=True)
        except ApiError as err:
            if err.code == "duplicate_job":
                return ReceiptPost(response=None, duplicate=True)
            raise
        return ReceiptPost(response=data, duplicate=False)

    def get_server_time(self) -> datetime:
        """The server's clock, from the ``Date`` header of ``GET /assumptions``."""
        response = self._send("GET", "/assumptions", None, signed=False)
        header = response.headers.get("date")
        try:
            if not header:
                raise ValueError("no date")
            return parsedate_to_datetime(header)
        except (TypeError, ValueError):
            raise ApiError(
                "The server did not report its time.", code="bad_response", status=200
            ) from None

    # ------------------------------------------------------------ plumbing

    def _json_call(
        self, method: str, path: str, body: bytes | None, *, signed: bool
    ) -> dict[str, Any]:
        response = self._send(method, path, body, signed=signed)
        try:
            data = response.json()
        except ValueError:
            data = None
        if not isinstance(data, dict):
            raise ApiError(
                "The server sent a reply the CLI could not read.",
                code="bad_response",
                status=response.status_code,
            )
        return data

    def _headers(self, body: bytes | None, signed: bool) -> dict[str, str]:
        headers = {"User-Agent": f"thirst-cli/{__version__}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if signed:
            stamp = str(int(self._clock()))
            headers["X-Thirst-Timestamp"] = stamp
            headers["X-Thirst-Signature"] = sign(self._token, stamp, body or b"")
            headers["X-Thirst-Site"] = self._site_id
        return headers

    def _send(self, method: str, path: str, body: bytes | None, *, signed: bool) -> httpx.Response:
        delays = (*BACKOFF_SECONDS, None)
        for delay in delays:
            started = time.monotonic()
            try:
                response = self._http.request(
                    method, self._base + path, content=body, headers=self._headers(body, signed)
                )
            except httpx.HTTPError as exc:
                logger.info("%s %s -> network error (%s)", method, path, type(exc).__name__)
                failure = ApiError(
                    "Could not reach the Thirst server. Check your internet connection.",
                    code="network_error",
                )
            else:
                took_ms = int((time.monotonic() - started) * 1000)
                logger.info("%s %s -> %d in %d ms", method, path, response.status_code, took_ms)
                if response.status_code < 400:
                    return response
                failure = _error_for(response)
                if response.status_code < 500:
                    raise failure
            if delay is None:
                raise failure
            self._sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover
