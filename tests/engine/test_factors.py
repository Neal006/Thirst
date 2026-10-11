from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine import factors
from engine.errors import EngineError

ROOT = Path(__file__).resolve().parents[2]
STATUSES = {"measured", "sourced", "calibrated", "placeholder", "design_choice", "definition"}
REQUIRED_KEYS = {"id", "value", "low", "high", "unit", "status", "source", "source_url", "notes"}
STRESS = {"low", "low_medium", "medium_high", "high", "extremely_high"}


@pytest.fixture(scope="module")
def fx() -> factors.Factors:
    return factors.load_factors()


def raw_factors() -> list[dict]:
    path = ROOT / "src" / "engine" / "data" / "factors.json"
    return json.loads(path.read_text(encoding="utf-8"))["factors"]


def test_every_factor_has_required_keys_and_valid_status() -> None:
    for item in raw_factors():
        assert item.keys() >= REQUIRED_KEYS, item["id"]
        assert item["status"] in STATUSES, item["id"]
        assert item["footprint_effect"] in {"increasing", "decreasing"}, item["id"]


def test_factor_ids_are_unique() -> None:
    ids = [f["id"] for f in raw_factors()]
    assert len(ids) == len(set(ids))


def test_low_value_high_are_ordered_for_every_numeric_factor(fx: factors.Factors) -> None:
    for f in fx.items:
        assert f.low <= f.value <= f.high, f.id


def test_central_low_high_sets(fx: factors.Factors) -> None:
    assert fx.central().get("wf_coal") == 3.25
    assert fx.low().get("wf_coal") == 3.0
    assert fx.high().get("wf_coal") == 3.5


def test_decreasing_factors_flip_direction_in_range_sets(fx: factors.Factors) -> None:
    """A better COP lowers the footprint, so the low-footprint set uses the high COP."""
    assert fx.low().get("cop_rated_room_ac") > fx.central().get("cop_rated_room_ac")
    assert fx.high().get("cop_rated_room_ac") < fx.central().get("cop_rated_room_ac")


def test_unknown_factor_raises_a_clear_error(fx: factors.Factors) -> None:
    with pytest.raises(KeyError, match="nope"):
        fx.central()["nope"]
    assert fx.central().get("nope", 7.0) == 7.0


def test_coal_ef_is_calibrated_to_cea_grid_factor(fx: factors.Factors) -> None:
    c = fx.central()
    assert 0.85 <= c["ef_coal"] <= 1.10
    shares = fx.grid.annual_shares
    yearly = sum(shares[k] * c[f"ef_{k}"] for k in shares)
    assert yearly == pytest.approx(0.727, abs=0.005)
    coal = fx.factor("ef_coal")
    assert coal.status == "calibrated"
    assert coal.low == pytest.approx(coal.value * 0.85)
    assert coal.high == pytest.approx(coal.value * 1.15)


def test_table_has_one_row_per_factor(fx: factors.Factors) -> None:
    rows = fx.table()
    ids = [r["id"] for r in rows]
    assert all(f.id in ids for f in fx.items)
    for row in rows:
        assert {"id", "label", "value", "low", "high", "unit", "status", "source"} <= row.keys()


def test_gpu_models_have_sane_power() -> None:
    gpus = factors.load_gpus()
    assert len(gpus) >= 10
    for g in gpus.values():
        assert g.p_max_w > 0
        assert 0 < g.p_idle_w < g.p_max_w
        assert g.nvml_name_patterns


GPU_KEYS = {
    "id",
    "label",
    "p_max_w",
    "p_idle_w",
    "nvml_name_patterns",
    "status",
    "source",
    "source_url",
    "notes",
}
GPU_STATUSES = {"sourced", "placeholder", "measured"}


def raw_gpus() -> list[dict]:
    path = ROOT / "src" / "engine" / "data" / "gpus.json"
    return json.loads(path.read_text(encoding="utf-8"))["models"]


def test_every_gpu_row_has_fields_a_source_and_a_valid_status() -> None:
    for row in raw_gpus():
        assert row.keys() >= GPU_KEYS, row["id"]
        assert row["status"] in GPU_STATUSES, row["id"]
        assert row["source"].strip(), row["id"]
        assert row["source_url"].startswith("https://"), row["id"]
        assert row["nvml_name_patterns"], row["id"]
        assert 0 < row["p_idle_w"] < row["p_max_w"], row["id"]


def test_gpu_ids_and_patterns_are_unique() -> None:
    rows = raw_gpus()
    ids = [r["id"] for r in rows]
    patterns = [p.lower() for r in rows for p in r["nvml_name_patterns"]]

    assert len(ids) == len(set(ids))
    assert len(patterns) == len(set(patterns))


def test_college_lab_gpus_are_present_with_their_sourced_power() -> None:
    gpus = factors.load_gpus()
    expected = {
        "RTX-3050-Laptop": 80, "RTX-3060-Laptop": 115, "RTX-4060-Laptop": 115, "RTX-3070": 220,
        "RTX-3080": 350, "RTX-4060": 115, "RTX-4070": 200, "A10": 150, "A30": 165,
        "RTX-A4000": 140, "RTX-A5000": 230, "V100-PCIE": 250, "P100-PCIE": 250,
    }
    for gpu_id, watts in expected.items():
        assert gpus[gpu_id].p_max_w == watts, gpu_id
        assert gpus[gpu_id].status == "sourced", gpu_id


def test_laptop_rows_say_why_they_use_the_top_of_the_power_range() -> None:
    laptops = [r for r in raw_gpus() if r["id"].endswith("-Laptop")]

    assert len(laptops) >= 3
    for row in laptops:
        assert "TOP of NVIDIA's stated" in row["notes"], row["id"]
        assert "GPU Subsystem Power" in row["source"], row["id"]


def test_unknown_gpu_raises_engine_error(fx: factors.Factors) -> None:
    with pytest.raises(EngineError) as err:
        fx.gpu_params("RTX-9999")
    assert err.value.code == "unknown_gpu"


def test_gpu_params_use_placeholders_without_a_sweep(fx: factors.Factors) -> None:
    p = fx.gpu_params("RTX-4090")
    assert p.measured is False
    assert p.u == 0.9
    assert p.levels[1.0].tau == 1.0
    assert p.levels[0.85].eps == 0.88
    assert p.p_idle_w == pytest.approx(45.0)


def test_gpu_params_use_measured_sweep_for_that_model_only(tmp_path: Path) -> None:
    sweep = {"gpus": {"RTX-4090": {
        "levels": {"1.0": {"tau": 1.0, "eps": 1.0}, "0.85": {"tau": 0.95, "eps": 0.8},
                   "0.7": {"tau": 0.85, "eps": 0.7}},
        "u": 0.8, "p_idle_w": 30.0}}}
    path = tmp_path / "sweep.json"
    path.write_text(json.dumps(sweep), encoding="utf-8")
    fx = factors.load_factors(sweep_path=path)

    measured = fx.gpu_params("RTX-4090")
    assert measured.measured is True
    assert (measured.u, measured.p_idle_w) == (0.8, 30.0)
    assert measured.levels[0.85].tau == 0.95
    assert fx.gpu_params("RTX-3090").measured is False

    rows = {r["id"]: r for r in fx.table()}
    assert rows["gpu:RTX-4090:tau_0.85"]["status"] == "measured"
    assert rows["tau_85"]["status"] == "placeholder"


def test_cities() -> None:
    cities = factors.load_cities()
    assert set(cities) == {"Chennai", "Bengaluru", "Hyderabad", "Mumbai", "Delhi", "Pune"}
    for c in cities.values():
        assert c.stress_category in STRESS


def test_stress_weight_comes_from_factors(fx: factors.Factors) -> None:
    assert fx.stress_weight("extremely_high") == 2.5
    assert fx.stress_weight("low") == 1.0
    with pytest.raises(EngineError):
        fx.stress_weight("moderate")


def test_unknown_city_raises_engine_error() -> None:
    with pytest.raises(EngineError) as err:
        factors.get_city("Atlantis")
    assert err.value.code == "unknown_city"


def test_factor_version_changes_with_content(tmp_path: Path) -> None:
    src = ROOT / "src" / "engine" / "data" / "factors.json"
    changed = tmp_path / "factors.json"
    changed.write_text(src.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert factors.load_factors(changed).version != factors.load_factors().version


def test_default_load_is_cached() -> None:
    assert factors.load_factors() is factors.load_factors()


def test_cli_gpu_data_is_a_byte_identical_copy() -> None:
    """Decision D19: the CLI bundles the same gpus.json as the engine."""
    engine = ROOT / "src" / "engine" / "data" / "gpus.json"
    cli = ROOT / "cli" / "thirst" / "data" / "gpus.json"
    if not cli.exists():
        pytest.skip("cli/thirst/data/gpus.json is copied in plan step 04.1")
    assert cli.read_bytes() == engine.read_bytes()
