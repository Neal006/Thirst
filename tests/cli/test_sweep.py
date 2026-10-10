"""Plan 04.5: the power-cap sweep logic, with a fake GPU (the real run needs the GPU box)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from thirst import gpus, sweep
from thirst.errors import CliError, GpuError
from thirst_fakes import FakeClock, FakeGpu, FakeNvml, FakeSmi, ist

from engine import factors

RTX4090 = gpus.resolve_model(["NVIDIA GeForce RTX 4090"], None)
TAU = {1.0: 1.0, 0.85: 0.95, 0.7: 0.8}
EPS = {1.0: 1.0, 0.85: 0.9, 0.7: 0.8}
FULL_POWER_W = 300.0
IDLE_W = 40.0
STEP_SECONDS = 0.3


class FakeWorkload:
    """A GPU job whose speed and energy follow TAU and EPS at the current power limit."""

    def __init__(self, api: FakeNvml, clock: FakeClock) -> None:
        self.api = api
        self.clock = clock
        self.warmups: list[int] = []
        self.runs: list[int] = []

    def _level(self) -> float:
        gpu = self.api.gpus[0]
        ratio = gpu.current_limit_mw / gpu.default_limit_mw
        return min(TAU, key=lambda known: abs(known - ratio))

    def _burn(self, seconds: float, watts: float) -> None:
        self.clock.advance(seconds)
        for gpu in self.api.gpus:
            gpu.energy_mj = (gpu.energy_mj or 0) + int(watts * seconds * 1000)

    def warmup(self, steps: int) -> None:
        self.warmups.append(steps)
        self._burn(steps * STEP_SECONDS, FULL_POWER_W)

    def run(self, steps: int) -> None:
        self.runs.append(steps)
        level = self._level()
        self._burn(steps * STEP_SECONDS / TAU[level], FULL_POWER_W * EPS[level] * TAU[level])

    def idle(self, seconds: float) -> None:
        self._burn(seconds, IDLE_W)


def one_gpu() -> FakeNvml:
    return FakeNvml(gpus=[FakeGpu("GPU-aaaa", energy_mj=0, current_limit_mw=450_000)])


def do_sweep(api: FakeNvml, clock: FakeClock, **options: Any) -> sweep.SweepResult:
    workload = FakeWorkload(api, clock)
    return sweep.run_sweep(
        api,
        (0,),
        RTX4090,
        workload,
        smi=FakeSmi(),
        mono=clock.mono,
        sleep=clock.sleep,
        now=lambda: ist("2026-10-09 16:40:00"),
        **options,
    )


# ------------------------------------------------------------ formulas


def test_tau_and_eps_follow_trd_6_4() -> None:
    results = {
        1.0: sweep.LevelResult(seconds=100.0, energy_mj=40_000_000.0),
        0.85: sweep.LevelResult(seconds=105.0, energy_mj=34_000_000.0),
        0.7: sweep.LevelResult(seconds=125.0, energy_mj=30_000_000.0),
    }

    levels = sweep.compute_levels(results)

    assert levels["1.0"] == {"tau": 1.0, "eps": 1.0}
    assert levels["0.85"]["tau"] == pytest.approx(100 / 105)
    assert levels["0.85"]["eps"] == pytest.approx(34 / 40)
    assert levels["0.7"]["tau"] == pytest.approx(100 / 125)
    assert levels["0.7"]["eps"] == pytest.approx(30 / 40)


def test_compute_levels_needs_the_full_power_run() -> None:
    with pytest.raises(CliError):
        sweep.compute_levels({0.85: sweep.LevelResult(1.0, 1.0)})


def test_zero_energy_at_full_power_is_an_error() -> None:
    with pytest.raises(GpuError):
        sweep.compute_levels({1.0: sweep.LevelResult(10.0, 0.0), 0.85: sweep.LevelResult(9.0, 1.0)})


# ------------------------------------------------------------ sanity gates (4.5.f)


def levels(t85: float, e85: float, t70: float, e70: float = 0.8) -> dict[str, dict[str, float]]:
    return {
        "1.0": {"tau": 1.0, "eps": 1.0},
        "0.85": {"tau": t85, "eps": e85},
        "0.7": {"tau": t70, "eps": e70},
    }


def test_sensible_numbers_pass_the_gates() -> None:
    assert sweep.gate_failures(levels(0.95, 0.9, 0.8)) == ()


@pytest.mark.parametrize(
    ("given", "expected_fragment"),
    [
        (levels(0.69, 0.9, 0.6), "tau"),  # tau_85 below 0.7
        (levels(1.01, 0.9, 0.8), "tau"),  # tau_85 above 1.0
        (levels(0.95, 0.59, 0.8), "eps"),  # eps_85 below 0.6
        (levels(0.95, 1.06, 0.8), "eps"),  # eps_85 above 1.05
        (levels(0.8, 0.9, 0.85), "70%"),  # tau_70 above tau_85
    ],
)
def test_nonsense_numbers_fail_a_gate(given: dict[str, Any], expected_fragment: str) -> None:
    failures = sweep.gate_failures(given)

    assert failures
    assert any(expected_fragment in message for message in failures)


def test_gate_edges_are_inclusive() -> None:
    assert sweep.gate_failures(levels(0.7, 0.6, 0.7)) == ()
    assert sweep.gate_failures(levels(1.0, 1.05, 0.9)) == ()


# ------------------------------------------------------------ the whole sweep


def test_run_sweep_measures_tau_eps_u_and_idle(clock: FakeClock) -> None:
    api = one_gpu()

    result = do_sweep(api, clock, steps=300, warmup=30, idle_seconds=60)

    entry = result.entry
    assert entry["levels"]["0.85"]["tau"] == pytest.approx(0.95, rel=1e-3)
    assert entry["levels"]["0.85"]["eps"] == pytest.approx(0.9, rel=1e-3)
    assert entry["levels"]["0.7"]["tau"] == pytest.approx(0.8, rel=1e-3)
    assert entry["levels"]["0.7"]["eps"] == pytest.approx(0.8, rel=1e-3)
    assert entry["p_idle_w"] == pytest.approx(IDLE_W, rel=1e-3)
    assert entry["u"] == pytest.approx(FULL_POWER_W / 450, rel=1e-3)
    assert result.gate_failures == ()


def test_entry_records_gpu_driver_date_workload_steps_and_raw(clock: FakeClock) -> None:
    result = do_sweep(one_gpu(), clock, steps=300, warmup=30, idle_seconds=60)

    entry = result.entry
    assert entry["gpu_name"] == "NVIDIA GeForce RTX 4090"
    assert entry["driver"] == "550.54"
    assert entry["measured_at"].startswith("2026-10-09T16:40")
    assert "resnet18" in entry["workload"] and "300" in entry["workload"]
    assert entry["runs"] == 1
    assert entry["steps"] == 300
    assert [r["level"] for r in entry["raw"]] == [1.0, 0.85, 0.7]
    assert all(r["steps"] == 300 and r["seconds"] > 0 for r in entry["raw"])


def test_warmup_is_not_part_of_the_timed_run(clock: FakeClock) -> None:
    api = one_gpu()
    workload = FakeWorkload(api, clock)

    result = sweep.run_sweep(
        api, (0,), RTX4090, workload, smi=FakeSmi(), mono=clock.mono, sleep=clock.sleep,
        now=lambda: ist("2026-10-09 16:40:00"), steps=300, warmup=30, idle_seconds=10,
    )  # fmt: skip

    assert workload.warmups == [30, 30, 30]
    assert workload.runs == [300, 300, 300]
    assert result.entry["raw"][0]["seconds"] == pytest.approx(300 * STEP_SECONDS)


def test_the_cap_is_restored_after_every_level_and_at_the_end(clock: FakeClock) -> None:
    api = one_gpu()
    api.gpus[0].current_limit_mw = 400_000  # not the default

    do_sweep(api, clock, idle_seconds=10)

    assert api.gpus[0].current_limit_mw == 400_000
    assert [mw for _, mw in api.set_calls].count(400_000) == 3  # one restore per level


def test_the_settle_pause_happens_after_applying_each_cap(clock: FakeClock) -> None:
    api = one_gpu()
    sleeps: list[float] = []
    workload = FakeWorkload(api, clock)

    sweep.run_sweep(
        api, (0,), RTX4090, workload, smi=FakeSmi(), mono=clock.mono,
        sleep=lambda s: (sleeps.append(s), clock.sleep(s))[0],
        now=lambda: ist("2026-10-09 16:40:00"), idle_seconds=10, settle_seconds=5,
    )  # fmt: skip

    assert sleeps.count(5) >= 3


def test_a_gpu_without_an_energy_counter_cannot_be_swept(clock: FakeClock) -> None:
    api = FakeNvml(gpus=[FakeGpu("GPU-aaaa", energy_mj=None)])

    with pytest.raises(GpuError) as err:
        do_sweep(api, clock)

    assert "energy counter" in err.value.message


def test_a_cap_that_cannot_be_set_stops_the_sweep(clock: FakeClock) -> None:
    api = one_gpu()
    api.permission_denied = True
    workload = FakeWorkload(api, clock)

    with pytest.raises(GpuError) as err:
        sweep.run_sweep(
            api, (0,), RTX4090, workload, smi=FakeSmi(returncode=1), mono=clock.mono,
            sleep=clock.sleep, now=lambda: ist("2026-10-09 16:40:00"),
        )  # fmt: skip

    assert "power cap" in err.value.message
    assert workload.runs == []


def test_failing_gates_are_reported_not_hidden(
    clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(TAU, 0.85, 0.5)  # a nonsense measurement

    result = do_sweep(one_gpu(), clock)

    assert result.gate_failures


# ------------------------------------------------------------ the output file


def entry_for(result: sweep.SweepResult) -> dict[str, Any]:
    return result.entry


def test_merge_replaces_this_gpu_and_keeps_the_others() -> None:
    existing = {"gpus": {"RTX-3090": {"u": 0.5}, "RTX-4090": {"u": 0.1, "runs": 1}}}

    merged = sweep.merge_sweep(existing, "RTX-4090", {"u": 0.9, "runs": 1})

    assert merged["gpus"]["RTX-4090"] == {"u": 0.9, "runs": 1}
    assert merged["gpus"]["RTX-3090"] == {"u": 0.5}
    assert existing["gpus"]["RTX-4090"]["u"] == 0.1  # the input is not changed


def test_merge_into_an_empty_file() -> None:
    assert sweep.merge_sweep({"gpus": {}}, "RTX-4090", {"u": 1})["gpus"] == {"RTX-4090": {"u": 1}}


def test_write_creates_the_file_and_the_engine_can_load_it(
    tmp_path: Path, clock: FakeClock
) -> None:
    result = do_sweep(one_gpu(), clock)
    target = tmp_path / "powercap_sweep.json"

    sweep.write_result(target, RTX4090.id, result.entry)

    data = json.loads(target.read_text(encoding="utf-8"))
    assert set(data["gpus"]["RTX-4090"]["levels"]) == {"1.0", "0.85", "0.7"}
    params = factors.load_factors(sweep_path=target).gpu_params("RTX-4090")
    assert params.measured is True
    assert params.levels[0.85].tau == pytest.approx(0.95, rel=1e-3)
    assert params.u == pytest.approx(FULL_POWER_W / 450, rel=1e-3)


def test_second_run_for_another_gpu_keeps_the_first(tmp_path: Path, clock: FakeClock) -> None:
    target = tmp_path / "powercap_sweep.json"
    result = do_sweep(one_gpu(), clock)
    sweep.write_result(target, "RTX-3090", {"u": 0.5, "levels": {}})

    sweep.write_result(target, "RTX-4090", result.entry)

    assert set(json.loads(target.read_text(encoding="utf-8"))["gpus"]) == {"RTX-3090", "RTX-4090"}


def test_rerunning_the_same_gpu_replaces_its_entry(tmp_path: Path, clock: FakeClock) -> None:
    target = tmp_path / "powercap_sweep.json"
    sweep.write_result(target, "RTX-4090", {"u": 0.1, "levels": {}})

    sweep.write_result(target, "RTX-4090", {"u": 0.2, "levels": {}})

    assert json.loads(target.read_text(encoding="utf-8"))["gpus"]["RTX-4090"]["u"] == 0.2


def test_a_corrupt_existing_file_is_a_plain_error_and_is_not_overwritten(tmp_path: Path) -> None:
    target = tmp_path / "powercap_sweep.json"
    target.write_text("{oops", encoding="utf-8")

    with pytest.raises(CliError) as err:
        sweep.write_result(target, "RTX-4090", {"u": 1})

    assert "not valid" in err.value.message
    assert target.read_text(encoding="utf-8") == "{oops"


def test_write_leaves_no_temp_files(tmp_path: Path) -> None:
    sweep.write_result(tmp_path / "powercap_sweep.json", "RTX-4090", {"u": 1})

    assert [p.name for p in tmp_path.iterdir()] == ["powercap_sweep.json"]


# ------------------------------------------------------------ the real workload


def test_parse_levels_accepts_percentages() -> None:
    assert sweep.parse_levels("100,85,70") == (1.0, 0.85, 0.7)


@pytest.mark.parametrize("text", ["", "100,abc", "0,85", "150", "100,100"])
def test_parse_levels_rejects_nonsense(text: str) -> None:
    with pytest.raises(CliError):
        sweep.parse_levels(text)


def test_levels_must_include_full_power() -> None:
    with pytest.raises(CliError) as err:
        sweep.parse_levels("85,70")

    assert "100" in err.value.message


def test_torch_missing_is_a_plain_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "torch", None)

    with pytest.raises(GpuError) as err:
        sweep.TorchResnetWorkload()

    assert "torch" in err.value.message
    assert "pip install" in err.value.message
