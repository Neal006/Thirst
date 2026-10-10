"""Plan 04.3.e / TRD 6.5: the modelled meter (no GPU) and its power model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from thirst import gpus, modelled
from thirst_fakes import FakeClock

ROOT = Path(__file__).resolve().parents[2]
RTX4090 = gpus.resolve_model(["NVIDIA GeForce RTX 4090"], None)


def make(clock: FakeClock, count: int = 2) -> modelled.ModelledMeter:
    model = modelled.power_model(RTX4090, sweep=None)
    return modelled.ModelledMeter(model, count, wall=clock.wall, mono=clock.mono)


def test_defaults_match_the_engine_placeholders() -> None:
    """The CLI constants must not drift from factors.json (until the real sweep replaces both)."""
    data = json.loads((ROOT / "src" / "engine" / "data" / "factors.json").read_text("utf-8"))
    central = {f["id"]: f["value"] for f in data["factors"]}

    assert central["u_default"] == modelled.DEFAULT_U
    assert central["tau_85"] == modelled.DEFAULT_LEVELS[0.85][0]
    assert central["eps_85"] == modelled.DEFAULT_LEVELS[0.85][1]
    assert central["tau_70"] == modelled.DEFAULT_LEVELS[0.7][0]
    assert central["eps_70"] == modelled.DEFAULT_LEVELS[0.7][1]


def test_run_power_is_u_times_pmax_times_eps_times_tau(clock: FakeClock) -> None:
    meter = make(clock)
    meter.start(background=False)
    meter.set_state("run", 0.85)

    clock.advance(3600)
    meter.sample()

    watts = 0.9 * 450 * 0.88 * 0.97
    assert meter.summary().run_kwh == pytest.approx(watts * 2 / 1000)


def test_full_power_level_uses_eps_and_tau_of_one(clock: FakeClock) -> None:
    meter = make(clock, count=1)
    meter.start(background=False)
    meter.set_state("run", 1.0)

    clock.advance(3600)
    meter.sample()

    assert meter.summary().run_kwh == pytest.approx(0.9 * 450 / 1000)


def test_idle_power_is_the_gpu_idle_figure(clock: FakeClock) -> None:
    meter = make(clock, count=2)
    meter.start(background=False)
    meter.set_state("idle", 1.0)

    clock.advance(3600)
    meter.sample()

    summary = meter.summary()
    assert summary.idle_kwh == pytest.approx(45 * 2 / 1000)
    assert summary.run_kwh == 0


def test_nothing_is_modelled_while_waiting(clock: FakeClock) -> None:
    meter = make(clock)
    meter.start(background=False)

    clock.advance(600)
    meter.sample()

    assert meter.summary().slots == ()


def test_summary_is_tagged_modelled_with_no_counter(clock: FakeClock) -> None:
    meter = make(clock, count=2)
    meter.start(background=False)

    summary = meter.summary()
    assert summary.method == "modelled"
    assert len(summary.gpus) == 2
    assert all(not g.has_energy_counter for g in summary.gpus)


def test_slots_split_at_the_hour_like_the_real_meter() -> None:
    clock = FakeClock("2026-10-10 01:30:00")
    meter = make(clock, count=1)
    meter.start(background=False)
    meter.set_state("run", 1.0)

    clock.advance(3600)
    meter.sample()

    hours = [s.hour for s in meter.summary().slots]
    assert hours == ["2026-10-10T01:00:00+05:30", "2026-10-10T02:00:00+05:30"]
    first, second = meter.summary().slots
    assert first.run_kwh == pytest.approx(second.run_kwh)


def test_close_is_safe_without_nvml(clock: FakeClock) -> None:
    meter = make(clock)
    meter.start(background=False)

    meter.close()
    meter.close()


def test_a_measured_sweep_entry_replaces_the_defaults() -> None:
    sweep = {
        "gpus": {
            "RTX-4090": {
                "levels": {
                    "1.0": {"tau": 1.0, "eps": 1.0},
                    "0.85": {"tau": 0.95, "eps": 0.8},
                    "0.7": {"tau": 0.8, "eps": 0.7},
                },
                "u": 0.75,
                "p_idle_w": 30.0,
            }
        }
    }

    model = modelled.power_model(RTX4090, sweep=sweep)

    assert model.u == 0.75
    assert model.p_idle_w == 30.0
    assert model.levels[0.85] == (0.95, 0.8)


def test_placeholder_zero_sweep_entries_are_ignored() -> None:
    sweep = {
        "gpus": {
            "RTX-4090": {
                "levels": {"1.0": {"tau": 1.0, "eps": 1.0}, "0.85": {"tau": 0.0, "eps": 0.0}},
                "u": 0.0,
                "p_idle_w": 0.0,
            }
        }
    }

    model = modelled.power_model(RTX4090, sweep=sweep)

    assert model.u == modelled.DEFAULT_U
    assert model.levels[0.85] == modelled.DEFAULT_LEVELS[0.85]


def test_missing_sweep_file_means_defaults(tmp_path: Path) -> None:
    assert modelled.load_bundled_sweep(tmp_path / "nope.json") is None


def test_corrupt_sweep_file_means_defaults(tmp_path: Path) -> None:
    broken = tmp_path / "powercap_sweep.json"
    broken.write_text("{oops", encoding="utf-8")

    assert modelled.load_bundled_sweep(broken) is None
