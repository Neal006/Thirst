"""ApiError and the engine-error mapping (plan 05.5.e, contract 08 §4)."""

from __future__ import annotations

import pytest

from engine.errors import EngineError
from handlers.errors import ApiError, error_body, from_engine


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("invalid_field", 400),
        ("unknown_city", 400),
        ("unknown_gpu", 400),
        ("deadline_too_soon", 422),
        ("implausible_energy", 422),
        ("slot_out_of_range", 422),
    ],
)
def test_engine_codes_map_to_the_documented_status(code: str, status: int) -> None:
    err = from_engine(EngineError(code, "plain words"))
    assert (err.status, err.code, err.message) == (status, code, "plain words")


def test_an_unknown_engine_code_is_a_server_error_not_a_leak() -> None:
    err = from_engine(EngineError("something_new", "internal detail"))
    assert err.status == 503
    assert err.code == "try_again"
    assert "internal detail" not in err.message


def test_error_body_has_exactly_error_and_message() -> None:
    assert error_body("bad_signature", "x") == {"error": "bad_signature", "message": "x"}


def test_api_error_is_an_exception_with_fields() -> None:
    with pytest.raises(ApiError) as caught:
        raise ApiError(404, "site_not_found", "We couldn't find that site.")
    assert caught.value.status == 404
    assert caught.value.code == "site_not_found"
