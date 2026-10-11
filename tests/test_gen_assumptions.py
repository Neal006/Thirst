"""ASSUMPTIONS.md is generated from the same data as GET /assumptions (plan 07.5.b)."""

from __future__ import annotations

import gen_assumptions

from engine.factors import load_factors
from handlers.assumptions import build


def test_every_factor_city_and_gpu_is_in_the_file() -> None:
    body = build(load_factors())

    text = gen_assumptions.render(body)

    for row in body["factors"]:
        assert f"`{row['id']}`" in text
    for city in body["cities"]:
        assert f"| {city['id']} |" in text
    for gpu in body["gpus"]:
        assert f"(`{gpu['id']}`)" in text
    assert f"{len(body['factors'])} factors:" in text


def test_a_pipe_in_a_source_does_not_break_the_table() -> None:
    body = build(load_factors())
    body["factors"] = [{**body["factors"][0], "notes": "a | b"}]

    text = gen_assumptions.render(body)

    assert "a \\| b" in text


def test_the_committed_file_is_up_to_date() -> None:
    stale = "run `make assumptions` and commit ASSUMPTIONS.md"
    assert gen_assumptions.main(["--check"]) == 0, stale
