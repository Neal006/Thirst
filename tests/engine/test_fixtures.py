"""The committed API fixtures must match what the engine produces today (run `make fixtures`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import gen_fixtures
import pytest

from engine.factors import Factors, load_factors

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def fx() -> Factors:
    return load_factors()


@pytest.fixture(scope="module")
def plan(fx: Factors) -> dict[str, Any]:
    return gen_fixtures.build_plan(fx)


def on_disk(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def normalised(data: Any) -> Any:
    return json.loads(json.dumps(data))


def test_plan_fixture_is_up_to_date(plan: dict[str, Any]) -> None:
    assert on_disk("plan_response.json") == normalised(plan), "run `make fixtures`"


def test_receipt_fixture_is_up_to_date(fx: Factors, plan: dict[str, Any]) -> None:
    expected = gen_fixtures.receipt_response(plan, fx)
    assert on_disk("receipt_response.json") == normalised(expected), "run `make fixtures`"


def test_leaderboard_fixture_is_up_to_date(fx: Factors, plan: dict[str, Any]) -> None:
    expected = gen_fixtures.leaderboard_response(plan, fx)
    assert on_disk("leaderboard_response.json") == normalised(expected), "run `make fixtures`"


def test_plan_fixture_has_the_contract_shape() -> None:
    plan = on_disk("plan_response.json")
    assert plan["plan_id"] == "p_7f3a2b9c1d"
    assert len(plan["pareto"]) == 11
    assert plan["chosen"] == plan["pareto"][5]
    assert len(plan["series"]) == 48
    assert set(plan["tags"]) == {"energy", "water", "co2", "tau", "forecast"}
    assert plan["assumptions_url"] == "/assumptions"


def test_leaderboard_fixture_never_exposes_gpu_counts_and_marks_demo_data() -> None:
    board = on_disk("leaderboard_response.json")
    assert "gpu_count" not in json.dumps(board)
    assert board["rows"], "the board needs rows for the frontend"
    assert all(row["simulated"] and "(simulated)" in row["name"] for row in board["rows"])
    ranks = [row["rank"] for row in board["rows"]]
    assert ranks == sorted(r for r in ranks if r is not None) + [None] * ranks.count(None)
