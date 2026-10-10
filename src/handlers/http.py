"""HTTP plumbing shared by the Lambda entry points: JSON responses, body reading, errors.

``new_app`` builds a resolver whose errors are always ``{"error": code, "message": words}``:
``ApiError`` and ``EngineError`` map to their status, anything unexpected is logged with its
stack trace and answered with a generic 503, and unknown routes are a JSON 404.
"""

from __future__ import annotations

import base64
import json
import secrets
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, Response
from aws_lambda_powertools.event_handler import content_types as content_types

from engine.errors import EngineError

from . import security
from .errors import TRY_AGAIN, ApiError, error_body, from_engine

MAX_BODY_SMALL = 8 * 1024  # /plan, /sites, /explain
MAX_BODY_RECEIPT = 64 * 1024


def json_response(status: int, data: Any, cache: str = "no-store") -> Response[str]:
    body = json.dumps(data, separators=(",", ":"), allow_nan=False)
    return Response(
        status_code=status,
        content_type=content_types.APPLICATION_JSON,
        body=body,
        headers={"Cache-Control": cache},
    )


def new_id(prefix: str, size: int = 10) -> str:
    """A random id of ``size`` characters from the base32 alphabet a-z, 2-7."""
    return prefix + base64.b32encode(secrets.token_bytes(8)).decode().lower()[:size]


def read_body(app: APIGatewayHttpResolver, limit: int) -> bytes:
    """The exact request bytes (base64 decoded), refused above ``limit``."""
    raw = security.raw_body(app.current_event.raw_event)
    if len(raw) > limit:
        raise ApiError(413, "body_too_large", "Request too large.")
    return raw


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not allowed")


def parse_json(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except ValueError:
        raise ApiError(400, "invalid_field", "body: send valid JSON.") from None


def new_app(logger: Logger) -> APIGatewayHttpResolver:
    app = APIGatewayHttpResolver()

    def on_api_error(exc: ApiError) -> Response[str]:
        return json_response(exc.status, error_body(exc.code, exc.message))

    def on_engine_error(exc: EngineError) -> Response[str]:
        mapped = from_engine(exc)
        if mapped.status >= 500:
            logger.error(f"unmapped_engine_error code={exc.code}")
        return json_response(mapped.status, error_body(mapped.code, mapped.message))

    def on_unexpected(exc: Exception) -> Response[str]:
        logger.exception("unhandled_error")  # details stay in the logs, never in the response
        return json_response(503, error_body("try_again", TRY_AGAIN))

    def on_not_found(exc: Exception) -> Response[str]:
        return json_response(404, error_body("not_found", "We couldn't find that page."))

    # Registered by call rather than as decorators: Powertools' decorator is untyped.
    app.exception_handler(ApiError)(on_api_error)
    app.exception_handler(EngineError)(on_engine_error)
    app.exception_handler(Exception)(on_unexpected)
    app.not_found(on_not_found)
    return app
