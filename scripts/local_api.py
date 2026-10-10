"""Run the real API Lambdas locally on in-memory DynamoDB (moto), no AWS account or SAM needed.

    python scripts/local_api.py            # http://127.0.0.1:3000, live Open-Meteo weather
    python scripts/local_api.py --offline  # skip Open-Meteo; /plan uses the bundled sample forecast

State lives in memory and is gone when the process stops, and the server secret is new on every
start, so run `thirst register --force` again after a restart. The web dev server
(`VITE_API_URL=http://127.0.0.1:3000`) and the CLI (`THIRST_API_URL=...`) can both point here.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import os
import secrets
import sys
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

REGION = "ap-south-1"
STAGE = "local"
SECRET_PARAM = "/thirst/server_secret"  # noqa: S105  (an SSM parameter name, not a secret)
ALLOWED_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}
CORS_HEADERS = "content-type, x-thirst-timestamp, x-thirst-signature, x-thirst-site"


class _Context:
    function_name = "thirst-local-api"
    memory_limit_in_mb = 512
    invoked_function_arn = f"arn:aws:lambda:{REGION}:123456789012:function:thirst-local-api"
    aws_request_id = "local"

    @staticmethod
    def get_remaining_time_in_millis() -> int:
        return 10_000


def _set_env() -> None:
    from handlers import store

    os.environ.update(
        {
            "AWS_ACCESS_KEY_ID": "testing",
            "AWS_SECRET_ACCESS_KEY": "testing",
            "AWS_SESSION_TOKEN": "testing",
            "AWS_DEFAULT_REGION": REGION,
            "SERVER_SECRET_PARAM": SECRET_PARAM,
            "POWERTOOLS_METRICS_NAMESPACE": "ThirstLocal",
            "POWERTOOLS_LOG_LEVEL": os.environ.get("POWERTOOLS_LOG_LEVEL", "WARNING"),
        }
    )
    for name, spec in store.TABLE_SPECS.items():
        os.environ[spec.env] = f"thirst-{STAGE}-{name}"


def _bootstrap(offline: bool) -> None:
    import boto3
    import seed

    from engine.units import IST
    from handlers import refresh, store

    ddb = boto3.client("dynamodb", region_name=REGION)
    for name, spec in store.TABLE_SPECS.items():
        ddb.create_table(
            TableName=f"thirst-{STAGE}-{name}", BillingMode="PAY_PER_REQUEST", **spec.create_args()
        )
    boto3.client("ssm", region_name=REGION).put_parameter(
        Name=SECRET_PARAM, Value=secrets.token_urlsafe(32), Type="SecureString"
    )
    tables = store.get_tables()
    now = datetime.now(IST)
    if offline:
        print("weather: offline, /plan will use the bundled sample forecast")
    else:
        result = refresh.run(now, store.WeatherRepo(tables.weather), refresh.fetch_open_meteo)
        print(f"weather: Open-Meteo refresh {result.status}, {result.rows} rows")
    done = seed.seed(tables, now)
    print(f"seed: {done['sites']} simulated sites, {done['receipts']} receipts")


def _event(method: str, raw_path: str, headers: dict[str, str], body: bytes) -> dict[str, Any]:
    parts = urlsplit(raw_path)
    query = {}
    for pair in filter(None, parts.query.split("&")):
        key, _, value = pair.partition("=")
        query[key] = value
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": parts.path,
        "rawQueryString": parts.query,
        "headers": headers,
        "queryStringParameters": query or None,
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "local",
            "domainName": "127.0.0.1",
            "http": {
                "method": method,
                "path": parts.path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": headers.get("user-agent", ""),
            },
            "requestId": f"local-{time.time_ns()}",
            "stage": "$default",
            "time": "",
            "timeEpoch": int(time.time() * 1000),
        },
        "body": base64.b64encode(body).decode() if body else None,
        "isBase64Encoded": bool(body),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "thirst-local"

    def _cors(self) -> None:
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", CORS_HEADERS)
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        from handlers import api, explain

        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        headers = {k.lower(): v for k, v in self.headers.items()}
        path = urlsplit(self.path).path
        fn = explain.handler if path == "/explain" else api.handler
        with self.server.lock:  # type: ignore[attr-defined]
            result = fn(_event(method, self.path, headers, body), _Context())
        payload = result.get("body") or ""
        data = base64.b64decode(payload) if result.get("isBase64Encoded") else payload.encode()
        self.send_response(int(result["statusCode"]))
        for key, value in (result.get("headers") or {}).items():
            self.send_header(key, str(value))
        for key, values in (result.get("multiValueHeaders") or {}).items():
            for value in values:
                self.send_header(key, str(value))
        self._cors()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(f"{self.command} {self.path} -> {args[1] if len(args) > 1 else ''}\n")


def main() -> int:
    import threading

    from moto import mock_aws

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--port", type=int, default=3000)
    p.add_argument("--offline", action="store_true", help="skip the Open-Meteo refresh")
    args = p.parse_args()

    _set_env()
    with mock_aws():
        _bootstrap(args.offline)
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
        server.lock = threading.Lock()  # type: ignore[attr-defined]
        print(f"Thirst local API on http://127.0.0.1:{args.port}  (Ctrl-C to stop)")
        with contextlib.suppress(KeyboardInterrupt):
            server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
