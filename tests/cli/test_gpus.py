"""Plan 04.3 test 6 (D25): GPU selection by UUID, child environment, GPU model mapping."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import thirst
from thirst import gpus
from thirst.errors import CliError, GpuError
from thirst_fakes import FakeGpu, FakeNvml

ROOT = Path(__file__).resolve().parents[2]


def three_gpus() -> FakeNvml:
    """NVML (PCI bus) order is A, B, C. CUDA's default "fastest first" order would differ."""
    return FakeNvml(
        gpus=[FakeGpu("GPU-aaaa-1111"), FakeGpu("GPU-bbbb-2222"), FakeGpu("GPU-cccc-3333")]
    )


# ------------------------------------------------------------ child environment


def test_child_environment_sets_pci_bus_order_by_default() -> None:
    env = gpus.child_environment({"PATH": "x"})

    assert env["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"
    assert env["PATH"] == "x"


def test_child_environment_respects_a_user_choice() -> None:
    env = gpus.child_environment({"CUDA_DEVICE_ORDER": "FASTEST_FIRST"})

    assert env["CUDA_DEVICE_ORDER"] == "FASTEST_FIRST"


def test_child_environment_does_not_modify_its_input() -> None:
    base = {"PATH": "x"}

    gpus.child_environment(base)

    assert base == {"PATH": "x"}


def test_child_environment_asks_python_not_to_buffer_the_tee() -> None:
    assert gpus.child_environment({})["PYTHONUNBUFFERED"] == "1"
    assert gpus.child_environment({"PYTHONUNBUFFERED": "0"})["PYTHONUNBUFFERED"] == "0"


# ------------------------------------------------------------ selection


def test_without_the_variable_all_gpus_are_measured() -> None:
    assert gpus.select_gpu_indices(three_gpus(), {}) == (0, 1, 2)


def test_numeric_indices_map_to_pci_order_when_the_child_uses_pci_order() -> None:
    env = gpus.child_environment({"CUDA_VISIBLE_DEVICES": "2,0"})

    assert gpus.select_gpu_indices(three_gpus(), env) == (2, 0)


def test_uuids_map_to_the_right_nvml_handle_regardless_of_order() -> None:
    env = {
        "CUDA_VISIBLE_DEVICES": "GPU-cccc-3333,GPU-aaaa-1111",
        "CUDA_DEVICE_ORDER": "FASTEST_FIRST",
    }

    assert gpus.select_gpu_indices(three_gpus(), env) == (2, 0)


def test_a_unique_uuid_prefix_works_like_cuda() -> None:
    env = {"CUDA_VISIBLE_DEVICES": "GPU-bbbb", "CUDA_DEVICE_ORDER": "PCI_BUS_ID"}

    assert gpus.select_gpu_indices(three_gpus(), env) == (1,)


def test_numeric_indices_with_fastest_first_order_are_refused() -> None:
    env = {"CUDA_VISIBLE_DEVICES": "1", "CUDA_DEVICE_ORDER": "FASTEST_FIRST"}

    with pytest.raises(GpuError) as err:
        gpus.select_gpu_indices(three_gpus(), env)

    assert "PCI_BUS_ID" in err.value.message


def test_an_unknown_uuid_is_an_error() -> None:
    env = {"CUDA_VISIBLE_DEVICES": "GPU-zzzz"}

    with pytest.raises(GpuError) as err:
        gpus.select_gpu_indices(three_gpus(), env)

    assert "GPU-zzzz" in err.value.message


def test_an_out_of_range_index_is_an_error() -> None:
    env = gpus.child_environment({"CUDA_VISIBLE_DEVICES": "7"})

    with pytest.raises(GpuError) as err:
        gpus.select_gpu_indices(three_gpus(), env)

    assert "7" in err.value.message


def test_an_empty_variable_means_no_gpus_and_is_an_error() -> None:
    with pytest.raises(GpuError):
        gpus.select_gpu_indices(three_gpus(), {"CUDA_VISIBLE_DEVICES": ""})


def test_mig_devices_are_not_supported() -> None:
    with pytest.raises(GpuError) as err:
        gpus.select_gpu_indices(three_gpus(), {"CUDA_VISIBLE_DEVICES": "MIG-1234"})

    assert "MIG" in err.value.message


def test_duplicates_are_measured_once() -> None:
    env = gpus.child_environment({"CUDA_VISIBLE_DEVICES": "1,1,0"})

    assert gpus.select_gpu_indices(three_gpus(), env) == (1, 0)


def test_garbage_entries_are_an_error() -> None:
    with pytest.raises(GpuError):
        gpus.select_gpu_indices(three_gpus(), {"CUDA_VISIBLE_DEVICES": "abc"})


# ------------------------------------------------------------ model mapping


def test_bundled_gpus_json_is_the_engine_copy() -> None:
    """Decision D19: the CLI bundles byte-identical gpus.json. Engine tests check the same file."""
    engine = ROOT / "src" / "engine" / "data" / "gpus.json"
    bundled = Path(thirst.__file__).parent / "data" / "gpus.json"

    assert bundled.read_bytes() == engine.read_bytes()


def test_models_load_from_the_bundled_file() -> None:
    models = gpus.load_gpu_models()

    assert len(models) >= 10
    assert all(m.p_max_w > 0 and m.id for m in models)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("NVIDIA GeForce RTX 4090", "RTX-4090"),
        ("nvidia geforce rtx 4090", "RTX-4090"),
        ("NVIDIA GeForce RTX 3090", "RTX-3090"),
    ],
)
def test_known_names_map_to_model_ids(name: str, expected: str) -> None:
    assert gpus.match_model(name).id == expected


def test_unknown_name_is_a_plain_error_that_lists_ids_and_the_override() -> None:
    with pytest.raises(CliError) as err:
        gpus.match_model("Some Future GPU 9000")

    assert "--gpu-model" in err.value.message
    assert "RTX-4090" in err.value.message


def test_every_bundled_pattern_maps_back_to_its_own_model() -> None:
    data = json.loads((Path(thirst.__file__).parent / "data" / "gpus.json").read_text("utf-8"))

    for model in data["models"]:
        for pattern in model["nvml_name_patterns"]:
            assert gpus.match_model(f"NVIDIA {pattern}").id == model["id"]


def test_override_wins_and_must_exist() -> None:
    assert gpus.resolve_model(["Whatever"], "RTX-3090").id == "RTX-3090"
    with pytest.raises(CliError):
        gpus.resolve_model(["NVIDIA GeForce RTX 4090"], "RTX-0000")


def test_mixed_models_are_refused_without_an_override() -> None:
    with pytest.raises(CliError) as err:
        gpus.resolve_model(["NVIDIA GeForce RTX 4090", "NVIDIA GeForce RTX 3090"], None)

    assert "different" in err.value.message


def test_same_model_on_all_gpus_resolves() -> None:
    names = ["NVIDIA GeForce RTX 4090"] * 3

    assert gpus.resolve_model(names, None).id == "RTX-4090"


def test_l4_is_not_confused_with_l40s() -> None:
    assert gpus.match_model("NVIDIA L40S").id == "L40S"
    assert gpus.match_model("NVIDIA L4").id == "L4"
