"""Helpers shared by the API tests: HTTP API events, independent HMAC signing, seeding."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from weather_helpers import SUBMIT, diurnal_rows

SECRET = "test-secret-not-for-prod"  # noqa: S105  (the published test value)
NOW = SUBMIT  # 2026-10-09 21:14 IST: the clock the API tests run at


def token_for(site_id: str, secret: str = SECRET) -> str:
    """Computed here with hashlib, not with the code under test."""
    return hmac.new(secret.encode(), site_id.encode(), hashlib.sha256).hexdigest()


def signature_for(token: str, timestamp: int | str, body: bytes) -> str:
    return hmac.new(
        token.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256
    ).hexdigest()


def event(
    method: str,
    path: str,
    body: Any = None,
    headers: dict[str, str] | None = None,
    query: dict[str, str] | None = None,
    *,
    raw: bytes | None = None,
    b64: bool = False,
) -> dict[str, Any]:
    """An API Gateway HTTP API (payload 2.0) event."""
    if raw is None and body is not None:
        raw = json.dumps(body).encode()
    text = None
    if raw is not None:
        text = base64.b64encode(raw).decode() if b64 else raw.decode("utf-8", "surrogateescape")
    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "&".join(f"{k}={v}" for k, v in (query or {}).items()),
        "headers": {"content-type": "application/json", **(headers or {})},
        "queryStringParameters": query or None,
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api",
            "domainName": "api.example.com",
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "203.0.113.9",
                "userAgent": "pytest",
            },
            "requestId": "req-1",
            "stage": "$default",
            "time": "09/Oct/2026:15:44:00 +0000",
            "timeEpoch": 1791560640000,
        },
        "body": text,
        "isBase64Encoded": b64 and text is not None,
    }


@dataclass(frozen=True)
class Reply:
    status: int
    headers: dict[str, str]
    text: str

    @property
    def json(self) -> Any:
        return json.loads(self.text)


def to_reply(result: dict[str, Any]) -> Reply:
    headers = {k.lower(): v for k, v in (result.get("headers") or {}).items()}
    for key, values in (result.get("multiValueHeaders") or {}).items():
        headers.setdefault(key.lower(), values[-1])
    return Reply(int(result["statusCode"]), headers, result.get("body") or "")


class Clock:
    """A settable stand-in for ``api._now`` so tests control the server time."""

    def __init__(self, start: datetime) -> None:
        self.current = start

    def __call__(self) -> datetime:
        return self.current

    def set(self, value: datetime) -> None:
        self.current = value

    def advance(self, **delta: float) -> None:
        self.current += timedelta(**delta)


class FakeContext:
    function_name = "thirst-test-api"
    memory_limit_in_mb = 512
    invoked_function_arn = "arn:aws:lambda:ap-south-1:123456789012:function:thirst-test-api"
    aws_request_id = "req-1"

    @staticmethod
    def get_remaining_time_in_millis() -> int:
        return 10_000


class Client:
    """Invokes the real Lambda handler with HTTP API events."""

    def __init__(self, handler: Any, clock: Clock, tables: Any) -> None:
        self.handler, self.clock, self.tables = handler, clock, tables

    def call(
        self,
        method: str,
        path: str,
        body: Any = None,
        headers: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
        *,
        raw: bytes | None = None,
        b64: bool = False,
    ) -> Reply:
        evt = event(method, path, body, headers, query, raw=raw, b64=b64)
        return to_reply(self.handler(evt, FakeContext()))

    def post_signed(
        self,
        path: str,
        site_id: str,
        body: Any = None,
        *,
        raw: bytes | None = None,
        ts: int | None = None,
        token: str | None = None,
        b64: bool = False,
        extra: dict[str, str] | None = None,
    ) -> Reply:
        payload = raw if raw is not None else json.dumps(body).encode()
        stamp = int(self.clock().timestamp()) if ts is None else ts
        key = token or token_for(site_id)
        headers = {
            "x-thirst-timestamp": str(stamp),
            "x-thirst-signature": signature_for(key, stamp, payload),
            "x-thirst-site": site_id,
            **(extra or {}),
        }
        return self.call("POST", path, headers=headers, raw=payload, b64=b64)


def seed_weather(
    tables: Any, city: str = "Chennai", start: datetime | None = None, hours: int = 72
) -> None:
    """Forecast rows in the weather table from the diurnal test weather."""
    from handlers.store import ForecastRow, WeatherRepo

    first = start or SUBMIT
    rows = [
        ForecastRow(
            city=city,
            hour=r.hour,
            temp_c=r.temp_c,
            rh_pct=r.rh_pct,
            rad_wm2=r.rad_wm2,
            issued=NOW - timedelta(hours=1),
            tw=r.temp_c - 5,
            ci=0.7,
            ewif=2.4,
            pue_t_c=r.temp_c,
        )
        for r in diurnal_rows(first)[:hours]
    ]
    WeatherRepo(tables.weather).put_forecast(rows, NOW - timedelta(hours=1))
