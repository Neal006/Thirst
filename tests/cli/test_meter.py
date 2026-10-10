"""Plan 04.3: NVML energy metering, slot bucketing, run/idle split (all with a fake NVML)."""

from __future__ import annotations

import time
from datetime import UTC

import pytest
from thirst import meter as meter_mod
from thirst.errors import GpuError
from thirst_fakes import FakeClock, FakeGpu, FakeNvml

KWH_MJ = 3_600_000_000  # 1 kWh in millijoules


def make_meter(api: FakeNvml, clock: FakeClock, indices: tuple[int, ...] = (0,)) -> meter_mod.Meter:
    return meter_mod.Meter(api, indices, wall=clock.wall, mono=clock.mono)


def tick(
    meter: meter_mod.Meter,
    clock: FakeClock,
    api: FakeNvml,
    seconds: float,
    add_mj: int,
    gpu: int = 0,
) -> None:
    """Advance the clocks, add energy to the counter, and take one sample."""
    clock.advance(seconds)
    counter = api.gpus[gpu].energy_mj
    assert counter is not None
    api.gpus[gpu].energy_mj = counter + add_mj
    meter.sample()


# ------------------------------------------------------------ energy counter


def test_energy_counter_samples_add_up(nvml_api: FakeNvml, clock: FakeClock) -> None:
    meter = make_meter(nvml_api, clock)
    meter.start(background=False)
    meter.set_state("run", 1.0)

    tick(meter, clock, nvml_api, 1, 1000)
    tick(meter, clock, nvml_api, 1, 1500)

    summary = meter.summary()
    assert summary.total_mj == 2500
    assert summary.method == "nvml_energy"
    assert summary.run_kwh == pytest.approx(2500 / KWH_MJ)
    assert summary.idle_kwh == 0


def test_counter_reset_is_ignored_and_power_times_dt_is_used(
    nvml_api: FakeNvml, clock: FakeClock
) -> None:
    nvml_api.gpus[0].energy_mj = 5000
    nvml_api.gpus[0].power_mw = 3_600_000  # 3.6 kW
    meter = make_meter(nvml_api, clock)
    meter.start(background=False)
    meter.set_state("run", 1.0)

    clock.advance(1)
    nvml_api.gpus[0].energy_mj = 100  # driver reload: the counter went backwards
    meter.sample()

    summary = meter.summary()
    assert "counter_reset" in summary.events
    assert summary.total_mj == pytest.approx(3_600_000)  # 3.6 kW x 1 s, not -4900 mJ
    assert summary.method == "nvml_energy"


def test_counter_continues_after_a_reset(nvml_api: FakeNvml, clock: FakeClock) -> None:
    nvml_api.gpus[0].energy_mj = 5000
    meter = make_meter(nvml_api, clock)
    meter.start(background=False)
    meter.set_state("run", 1.0)
    clock.advance(1)
    nvml_api.gpus[0].energy_mj = 100
    meter.sample()
    before = meter.summary().total_mj

    tick(meter, clock, nvml_api, 1, 700)

    assert meter.summary().total_mj == pytest.approx(before + 700)


# ------------------------------------------------------------ power integration


def test_without_a_counter_power_is_integrated(nvml_api: FakeNvml, clock: FakeClock) -> None:
    nvml_api.gpus[0].energy_mj = None
    nvml_api.gpus[0].power_mw = 3_600_000
    meter = make_meter(nvml_api, clock)
    meter.start(background=False)
    meter.set_state("run", 0.85)

    clock.advance(2)
    meter.sample()

    summary = meter.summary()
    assert summary.method == "nvml_power_integration"
    assert summary.total_mj == pytest.approx(7_200_000)
    assert summary.gpus[0].has_energy_counter is False


def test_one_gpu_without_a_counter_makes_the_whole_method_integration(
    clock: FakeClock,
) -> None:
    api = FakeNvml(gpus=[FakeGpu("GPU-a", energy_mj=0), FakeGpu("GPU-b", energy_mj=None)])
    meter = make_meter(api, clock, (0, 1))
    meter.start(background=False)

    assert meter.summary().method == "nvml_power_integration"


# ------------------------------------------------------------ slot bucketing


def test_interval_crossing_the_hour_is_split_by_time(nvml_api: FakeNvml) -> None:
    clock = FakeClock("2026-10-10 01:59:58")
    meter = make_meter(nvml_api, clock)
    meter.start(background=False)
    meter.set_state("run", 1.0)

    tick(meter, clock, nvml_api, 4, KWH_MJ)  # 01:59:58 -> 02:00:02, 1 kWh

    slots = {s.hour: s for s in meter.summary().slots}
    assert slots["2026-10-10T01:00:00+05:30"].run_kwh == pytest.approx(0.5)
    assert slots["2026-10-10T02:00:00+05:30"].run_kwh == pytest.approx(0.5)


def test_split_is_proportional_when_uneven(nvml_api: FakeNvml) -> None:
    clock = FakeClock("2026-10-10 01:59:59")
    meter = make_meter(nvml_api, clock)
    meter.start(background=False)
    meter.set_state("run", 1.0)

    tick(meter, clock, nvml_api, 4, KWH_MJ)  # 1 s before the hour, 3 s after

    slots = {s.hour: s for s in meter.summary().slots}
    assert slots["2026-10-10T01:00:00+05:30"].run_kwh == pytest.approx(0.25)
    assert slots["2026-10-10T02:00:00+05:30"].run_kwh == pytest.approx(0.75)


def test_an_interval_spanning_three_hours_fills_the_middle_one(nvml_api: FakeNvml) -> None:
    clock = FakeClock("2026-10-10 01:30:00")
    meter = make_meter(nvml_api, clock)
    meter.start(background=False)
    meter.set_state("run", 1.0)

    tick(meter, clock, nvml_api, 3 * 3600, 6 * KWH_MJ)  # 01:30 -> 04:30

    slots = {s.hour[11:13]: s.run_kwh for s in meter.summary().slots}
    assert slots == {
        "01": pytest.approx(1.0),
        "02": pytest.approx(2.0),
        "03": pytest.approx(2.0),
        "04": pytest.approx(1.0),
    }


def test_slot_hours_are_ist_whatever_the_wall_clock_zone(nvml_api: FakeNvml) -> None:

    utc = UTC
    clock = FakeClock("2026-10-10 01:00:00")
    meter = meter_mod.Meter(
        nvml_api, (0,), wall=lambda: clock.wall().astimezone(utc), mono=clock.mono
    )
    meter.start(background=False)
    meter.set_state("run", 1.0)

    tick(meter, clock, nvml_api, 10, 1000)

    hour = meter.summary().slots[0].hour
    assert hour == "2026-10-10T01:00:00+05:30"


# ------------------------------------------------------------ run / idle split


def test_nothing_is_recorded_while_waiting(nvml_api: FakeNvml, clock: FakeClock) -> None:
    meter = make_meter(nvml_api, clock)
    meter.start(background=False)

    tick(meter, clock, nvml_api, 60, 5_000_000)

    summary = meter.summary()
    assert summary.slots == ()
    assert summary.total_mj == 0


def test_waiting_energy_does_not_leak_into_the_first_run_interval(
    nvml_api: FakeNvml, clock: FakeClock
) -> None:
    meter = make_meter(nvml_api, clock)
    meter.start(background=False)
    tick(meter, clock, nvml_api, 60, 5_000_000)  # waiting

    meter.set_state("run", 1.0)
    tick(meter, clock, nvml_api, 1, 1000)

    assert meter.summary().total_mj == 1000


def test_run_and_idle_energy_are_separate(nvml_api: FakeNvml, clock: FakeClock) -> None:
    meter = make_meter(nvml_api, clock)
    meter.start(background=False)
    meter.set_state("run", 1.0)
    tick(meter, clock, nvml_api, 1, 3000)

    meter.set_state("idle")
    tick(meter, clock, nvml_api, 1, 700)

    summary = meter.summary()
    assert summary.run_kwh == pytest.approx(3000 / KWH_MJ)
    assert summary.idle_kwh == pytest.approx(700 / KWH_MJ)
    slot = summary.slots[0]
    assert slot.run_kwh == pytest.approx(3000 / KWH_MJ)
    assert slot.idle_kwh == pytest.approx(700 / KWH_MJ)


def test_changing_state_first_credits_the_old_state(nvml_api: FakeNvml, clock: FakeClock) -> None:
    meter = make_meter(nvml_api, clock)
    meter.start(background=False)
    meter.set_state("run", 1.0)
    clock.advance(5)
    nvml_api.gpus[0].energy_mj = 9000  # energy used while still running

    meter.set_state("idle")

    assert meter.summary().run_kwh == pytest.approx(9000 / KWH_MJ)
    assert meter.summary().idle_kwh == 0


def test_unknown_state_is_rejected(nvml_api: FakeNvml, clock: FakeClock) -> None:
    meter = make_meter(nvml_api, clock)

    with pytest.raises(ValueError, match="state"):
        meter.set_state("sleeping")


def test_slot_level_is_the_level_that_used_the_most_energy(
    nvml_api: FakeNvml, clock: FakeClock
) -> None:
    meter = make_meter(nvml_api, clock)
    meter.start(background=False)
    meter.set_state("run", 0.85)
    tick(meter, clock, nvml_api, 10, 1000)
    meter.set_state("run", 0.7)
    tick(meter, clock, nvml_api, 10, 9000)

    assert meter.summary().slots[0].level == 0.7


def test_idle_only_slot_keeps_the_last_level(nvml_api: FakeNvml, clock: FakeClock) -> None:
    meter = make_meter(nvml_api, clock)
    meter.start(background=False)
    meter.set_state("run", 0.85)
    meter.set_state("idle")
    tick(meter, clock, nvml_api, 10, 1000)

    assert meter.summary().slots[0].level == 0.85


# ------------------------------------------------------------ several GPUs and probing


def test_energy_of_all_selected_gpus_is_summed(clock: FakeClock) -> None:
    api = FakeNvml(gpus=[FakeGpu("GPU-a"), FakeGpu("GPU-b"), FakeGpu("GPU-c")])
    meter = make_meter(api, clock, (0, 2))  # GPU 1 is not visible to the job
    meter.start(background=False)
    meter.set_state("run", 1.0)

    clock.advance(1)
    for index, added in enumerate((100, 999_999, 300)):
        api.gpus[index].energy_mj = added
    meter.sample()

    assert meter.summary().total_mj == 400


def test_probe_reports_name_uuid_driver_and_counter(nvml_api: FakeNvml, clock: FakeClock) -> None:
    meter = make_meter(nvml_api, clock, (0, 1))
    meter.start(background=False)

    summary = meter.summary()
    assert [g.uuid for g in summary.gpus] == ["GPU-aaaa", "GPU-bbbb"]
    assert summary.gpus[0].name == "NVIDIA GeForce RTX 4090"
    assert summary.gpus[0].has_energy_counter is True
    assert summary.driver == "550.54"


def test_a_failed_read_is_recorded_not_raised(nvml_api: FakeNvml, clock: FakeClock) -> None:
    meter = make_meter(nvml_api, clock)
    meter.start(background=False)
    meter.set_state("run", 1.0)

    def broken(index: int) -> int:
        raise GpuError("driver hiccup")

    nvml_api.total_energy_mj = broken  # type: ignore[method-assign]
    clock.advance(1)
    meter.sample()

    assert "sample_failed" in meter.summary().events


def test_sample_before_start_is_an_error(nvml_api: FakeNvml, clock: FakeClock) -> None:
    meter = make_meter(nvml_api, clock)

    with pytest.raises(RuntimeError):
        meter.sample()


# ------------------------------------------------------------ the thread


def test_background_thread_samples_and_stops_within_two_seconds(nvml_api: FakeNvml) -> None:
    meter = meter_mod.Meter(nvml_api, (0,), interval_s=0.01)
    meter.start()
    meter.set_state("run", 1.0)
    for step in range(1, 6):
        nvml_api.gpus[0].energy_mj = step * 1000
        time.sleep(0.03)

    began = time.monotonic()
    meter.stop()

    assert time.monotonic() - began < 2.0
    assert meter.thread_alive() is False
    assert meter.summary().total_mj > 0


def test_close_shuts_nvml_down_once(nvml_api: FakeNvml, clock: FakeClock) -> None:
    meter = make_meter(nvml_api, clock)
    meter.start(background=False)

    meter.close()
    meter.close()

    assert nvml_api.shutdowns == 1


def test_stop_takes_a_final_sample(nvml_api: FakeNvml, clock: FakeClock) -> None:
    meter = make_meter(nvml_api, clock)
    meter.start(background=False)
    meter.set_state("run", 1.0)
    clock.advance(1)
    nvml_api.gpus[0].energy_mj = 4000

    meter.stop()

    assert meter.summary().total_mj == 4000
