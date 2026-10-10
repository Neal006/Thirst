"""NVML energy meter (plan 04.3, TRD 6.1).

A sampler thread reads every GPU the job can see once per second. Volta and newer GPUs report a
total-energy counter (millijoules); older ones are measured by integrating power (milliwatts) over
the time between samples. Energy goes into one-hour IST slots and into "run" or "idle" by the
state the runner set. While the state is "wait" nothing is recorded.

``BaseMeter`` holds the shared lifecycle; ``Meter`` reads NVML and ``ModelledMeter`` (modelled.py)
estimates energy when there is no GPU.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .errors import GpuError
from .ledger import IST, STATES, SlotEnergy, SlotLedger
from .nvml import EnergyCounterUnsupported, NvmlApi

logger = logging.getLogger(__name__)

MJ_PER_KWH = 3_600_000_000.0
STOP_TIMEOUT_S = 2.0


@dataclass(frozen=True)
class GpuInfo:
    index: int
    uuid: str
    name: str
    has_energy_counter: bool


@dataclass(frozen=True)
class MeterSummary:
    slots: tuple[SlotEnergy, ...]
    run_kwh: float
    idle_kwh: float
    total_mj: float
    method: str
    gpus: tuple[GpuInfo, ...]
    driver: str
    events: tuple[str, ...]


class EnergyMeter(Protocol):
    """What the runner needs from a meter (NVML-backed or modelled)."""

    def start(self, *, background: bool = True) -> None: ...
    def set_state(self, state: str, level: float | None = None) -> None: ...
    def sample(self) -> None: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...
    def summary(self) -> MeterSummary: ...


def now_ist() -> datetime:
    return datetime.now(IST)


class BaseMeter:
    """Thread, state, buckets and totals. Subclasses supply the readings."""

    method = "unknown"

    def __init__(
        self,
        *,
        interval_s: float = 1.0,
        wall: Callable[[], datetime] = now_ist,
        mono: Callable[[], float] = time.monotonic,
    ) -> None:
        self._interval = interval_s
        self._wall = wall
        self._mono = mono
        self._lock = threading.RLock()
        self._ledger = SlotLedger()
        self._events: list[str] = []
        self._gpus: tuple[GpuInfo, ...] = ()
        self._driver = ""
        self._state = "wait"
        self._level = 1.0
        self._total_mj = 0.0
        self._last_mono = 0.0
        self._started = False
        self._stopped = False
        self._closed = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------ hooks for subclasses

    def _probe(self) -> tuple[tuple[GpuInfo, ...], str]:
        raise NotImplementedError

    def _read_gpu(self, info: GpuInfo, seconds: float) -> float:
        """Millijoules this GPU used in the last ``seconds`` (0.0 if it could not be read)."""
        raise NotImplementedError

    def _method(self) -> str:
        return self.method

    def _release(self) -> None:
        """Free the backend (``nvmlShutdown``)."""

    # ------------------------------------------------------------ lifecycle

    def start(self, *, background: bool = True) -> None:
        """Probe the GPUs, take the first reading, and (by default) start the 1 s sampler."""
        with self._lock:
            self._gpus, self._driver = self._probe()
            self._last_mono = self._mono()
            self._started = True
        if background:
            self._thread = threading.Thread(target=self._loop, name="thirst-meter", daemon=True)
            self._thread.start()

    def _loop(self) -> None:
        while not self._stop_event.wait(self._interval):
            try:
                self.sample()
            except Exception:  # keep metering; a lost sample is better than a dead thread
                logger.exception("meter sample failed")
                self._note("sampler_error")

    def thread_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        """Stop the thread (within 2 s) and take a last sample. Safe to call twice."""
        if not self._started or self._stopped:
            return
        self._stopped = True
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(STOP_TIMEOUT_S)
        self.sample()

    def close(self) -> None:
        """Stop, then release the backend once. Safe to call twice."""
        self.stop()
        if not self._closed:
            self._closed = True
            self._release()

    # ------------------------------------------------------------ state and sampling

    def set_state(self, state: str, level: float | None = None) -> None:
        """Credit the time so far to the old state, then switch to ``state`` and ``level``."""
        if state not in STATES:
            raise ValueError(f"state must be one of {STATES}, not {state!r}")
        with self._lock:
            if self._started and not self._stopped:
                self.sample()
            self._state = state
            if level is not None:
                self._level = level

    def sample(self) -> None:
        with self._lock:
            if not self._started:
                raise RuntimeError("start() must be called before sample()")
            now_mono = self._mono()
            seconds = max(0.0, now_mono - self._last_mono)
            self._last_mono = now_mono
            used_mj = sum(self._read_gpu(info, seconds) for info in self._gpus)
            if self._state == "wait" or used_mj <= 0:
                return
            self._total_mj += used_mj
            kwh = used_mj / MJ_PER_KWH
            self._ledger.add(self._wall(), seconds, self._state, self._level, kwh)

    def _note(self, event: str) -> None:
        with self._lock:
            if event not in self._events:
                self._events.append(event)

    def summary(self) -> MeterSummary:
        with self._lock:
            run, idle = self._ledger.totals_kwh()
            return MeterSummary(
                slots=self._ledger.slots(),
                run_kwh=run,
                idle_kwh=idle,
                total_mj=self._total_mj,
                method=self._method(),
                gpus=self._gpus,
                driver=self._driver,
                events=tuple(self._events),
            )


class Meter(BaseMeter):
    """Reads real GPUs through the ``NvmlApi`` protocol."""

    def __init__(
        self,
        api: NvmlApi,
        gpu_indices: Sequence[int],
        *,
        interval_s: float = 1.0,
        wall: Callable[[], datetime] = now_ist,
        mono: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(interval_s=interval_s, wall=wall, mono=mono)
        self._api = api
        self._indices = tuple(gpu_indices)
        self._previous_mj: dict[int, int] = {}

    def _probe_counter(self, index: int) -> bool:
        try:
            self._previous_mj[index] = self._api.total_energy_mj(index)
        except EnergyCounterUnsupported:
            return False
        return True

    def _probe(self) -> tuple[tuple[GpuInfo, ...], str]:
        infos = []
        for index in self._indices:
            counter = self._probe_counter(index)
            infos.append(GpuInfo(index, self._api.uuid(index), self._api.name(index), counter))
        return tuple(infos), self._api.driver_version()

    def _method(self) -> str:
        counters = all(info.has_energy_counter for info in self._gpus)
        return "nvml_energy" if counters else "nvml_power_integration"

    def _release(self) -> None:
        self._api.shutdown()

    def _read_gpu(self, info: GpuInfo, seconds: float) -> float:
        try:
            if not info.has_energy_counter:
                return self._api.power_mw(info.index) * seconds
            current = self._api.total_energy_mj(info.index)
            delta = current - self._previous_mj[info.index]
            self._previous_mj[info.index] = current
            if delta >= 0:
                return float(delta)
            logger.warning("GPU %d energy counter went backwards; using power x time", info.index)
            self._note("counter_reset")
            return self._api.power_mw(info.index) * seconds
        except (GpuError, EnergyCounterUnsupported):
            logger.warning("could not read GPU %d; this interval is not counted", info.index)
            self._note("sample_failed")
            return 0.0
