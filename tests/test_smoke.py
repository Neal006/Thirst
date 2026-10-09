"""Smoke tests for the Phase 01 foundations: imports resolve and the skeleton is complete."""

from __future__ import annotations

import importlib
import json

import check_skeleton
import pytest

PACKAGES = (
    "engine",
    "engine.units",
    "engine.factors",
    "engine.wetbulb",
    "engine.cooling",
    "engine.grid",
    "engine.footprint",
    "engine.planner",
    "engine.score",
    "handlers",
    "handlers.api",
    "handlers.refresh",
    "handlers.explain",
    "handlers.store",
    "handlers.security",
    "handlers.validation",
    "handlers.errors",
    "thirst",
    "thirst.config",
    "thirst.client",
    "thirst.meter",
    "thirst.powercap",
    "thirst.runner",
    "thirst.sweep",
    "thirst.receipt",
)


@pytest.mark.parametrize("name", PACKAGES)
def test_imports(name: str) -> None:
    assert importlib.import_module(name) is not None


def test_skeleton_is_complete() -> None:
    assert check_skeleton.missing() == []


def test_engine_has_no_aws_imports() -> None:
    """TRD design principle 1: the engine never imports boto3 or other AWS libraries."""
    forbidden = ("boto3", "botocore", "aws_lambda_powertools")
    for path in (check_skeleton.ROOT / "src" / "engine").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for name in forbidden:
            assert f"import {name}" not in text, f"{path} imports {name}"
            assert f"from {name}" not in text, f"{path} imports from {name}"


def test_sample_forecast_is_complete() -> None:
    """The offline weather fallback (TRD §9): 6 seed cities x 96 hourly values, no gaps."""
    path = check_skeleton.ROOT / "src" / "engine" / "data" / "sample_forecast.json"
    cities = json.loads(path.read_text(encoding="utf-8"))
    assert len(cities) == 6
    for city in cities:
        hourly = city["hourly"]
        for key in ("temperature_2m", "relative_humidity_2m", "shortwave_radiation"):
            assert len(hourly[key]) == 96
            assert all(value is not None for value in hourly[key])
        assert len(hourly["time"]) == 96


def test_cli_entry_point_runs(capsys: pytest.CaptureFixture[str]) -> None:
    from thirst.__main__ import main

    assert main([]) == 0
    assert "thirst" in capsys.readouterr().out
