"""Factor sets, GPU and city data loaders (plan step 02.2).

Every constant the model uses lives in ``data/factors.json`` with a value, a low/high range, a
status and a source. ``Factors.central()/low()/high()`` give the three sets used for the savings
ranges. The *low* set means "lower footprint": factors whose increase lowers the footprint (a
better COP) take their ``high`` value there.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .errors import EngineError
from .grid import GridModel, calibrate_coal_ef, load_grid

DATA_DIR = Path(__file__).parent / "data"
LEVELS = (1.0, 0.85, 0.7)
_COAL_EF_RANGE = 0.15


@dataclass(frozen=True, slots=True)
class Factor:
    """One row of ``factors.json``."""

    id: str
    group: str
    label: str
    value: float
    low: float
    high: float
    unit: str
    status: str
    source: str
    source_url: str
    notes: str
    footprint_effect: str  # "increasing" or "decreasing"


@dataclass(frozen=True, slots=True)
class FactorSet:
    """A read-only id -> value mapping for one of the low, central or high sets."""

    values: Mapping[str, float]
    name: str

    def __getitem__(self, key: str) -> float:
        try:
            return self.values[key]
        except KeyError:
            raise KeyError(f"unknown factor: {key}") from None

    def get(self, key: str, default: float | None = None) -> float:
        if key in self.values:
            return self.values[key]
        if default is None:
            raise KeyError(f"unknown factor: {key}")
        return default


@dataclass(frozen=True, slots=True)
class GpuModel:
    id: str
    label: str
    p_max_w: float
    p_idle_w: float
    nvml_name_patterns: tuple[str, ...]
    status: str
    source_url: str


@dataclass(frozen=True, slots=True)
class GpuLevel:
    """Relative work per hour (tau) and energy per unit of work (eps) at one power-cap level."""

    tau: float
    eps: float


@dataclass(frozen=True, slots=True)
class GpuParams:
    model: GpuModel
    u: float  # average draw at 100% as a share of max power
    p_idle_w: float
    levels: Mapping[float, GpuLevel]
    measured: bool


@dataclass(frozen=True, slots=True)
class City:
    id: str
    lat: float
    lon: float
    stress_category: str
    status: str
    source: str
    source_url: str
    lookup_date: str | None


@dataclass(frozen=True, slots=True)
class Factors:
    version: str
    items: tuple[Factor, ...]
    grid: GridModel
    gpus: Mapping[str, GpuModel]
    sweep: Mapping[str, Any]

    def factor(self, factor_id: str) -> Factor:
        for item in self.items:
            if item.id == factor_id:
                return item
        raise KeyError(f"unknown factor: {factor_id}")

    def _build(self, name: str, pick: Callable[[Factor], float]) -> FactorSet:
        return FactorSet(MappingProxyType({f.id: pick(f) for f in self.items}), name)

    def central(self) -> FactorSet:
        return self._build("central", lambda f: f.value)

    def low(self) -> FactorSet:
        """Lower-footprint set: low values, except factors where more means less footprint."""
        return self._build("low", lambda f: f.low if f.footprint_effect == "increasing" else f.high)

    def high(self) -> FactorSet:
        """Higher-footprint set."""
        return self._build(
            "high", lambda f: f.high if f.footprint_effect == "increasing" else f.low
        )

    def stress_weight(self, category: str) -> float:
        try:
            return self.factor(f"stress_{category}").value
        except KeyError:
            raise EngineError(
                "invalid_field", f"Unknown water stress category: {category}"
            ) from None

    def gpu_params(self, model_id: str) -> GpuParams:
        """Power-cap parameters for a GPU: measured sweep values if present, else placeholders."""
        model = self.gpus.get(model_id)
        if model is None:
            raise EngineError("unknown_gpu", "Pick a GPU from the list.")
        measured = self.sweep.get(model_id)
        if measured is not None:
            levels = {float(k): GpuLevel(float(v["tau"]), float(v["eps"]))
                      for k, v in measured["levels"].items()}
            missing = [lv for lv in LEVELS if lv not in levels]
            if missing:
                raise ValueError(f"sweep for {model_id} lacks levels {missing}")
            return GpuParams(model, float(measured["u"]), float(measured["p_idle_w"]),
                             MappingProxyType(levels), True)
        c = self.central()
        levels = {1.0: GpuLevel(1.0, 1.0),
                  0.85: GpuLevel(c["tau_85"], c["eps_85"]),
                  0.7: GpuLevel(c["tau_70"], c["eps_70"])}
        return GpuParams(model, c["u_default"], model.p_idle_w, MappingProxyType(levels), False)

    def table(self) -> list[dict[str, Any]]:
        """Rows for ``/assumptions`` and ``ASSUMPTIONS.md``: every factor plus measured GPU rows."""
        rows: list[dict[str, Any]] = [
            {"id": f.id, "group": f.group, "label": f.label, "value": f.value, "low": f.low,
             "high": f.high, "unit": f.unit, "status": f.status, "source": f.source,
             "source_url": f.source_url, "notes": f.notes}
            for f in self.items
        ]
        for model_id, entry in sorted(self.sweep.items()):
            source = f"Thirst power-cap sweep on {entry.get('gpu_name', model_id)}"
            for level in LEVELS[1:]:
                lv = entry["levels"][str(level)]
                for key, unit in (("tau", "ratio"), ("eps", "ratio")):
                    rows.append(_measured_row(f"gpu:{model_id}:{key}_{level}",
                                              f"{key} at {int(level * 100)}% power ({model_id})",
                                              float(lv[key]), unit, source))
            rows.append(_measured_row(f"gpu:{model_id}:u", f"Average draw share ({model_id})",
                                      float(entry["u"]), "fraction", source))
            rows.append(_measured_row(f"gpu:{model_id}:p_idle_w", f"Idle power ({model_id})",
                                      float(entry["p_idle_w"]), "W", source))
        return rows


def _measured_row(row_id: str, label: str, value: float, unit: str, source: str) -> dict[str, Any]:
    return {"id": row_id, "group": "gpu", "label": label, "value": value, "low": value,
            "high": value, "unit": unit, "status": "measured", "source": source,
            "source_url": "", "notes": ""}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_gpus(path: Path | str | None = None) -> dict[str, GpuModel]:
    """GPU models keyed by id."""
    data = _read_json(Path(path) if path else DATA_DIR / "gpus.json")
    return {
        m["id"]: GpuModel(m["id"], m["label"], float(m["p_max_w"]), float(m["p_idle_w"]),
                          tuple(m["nvml_name_patterns"]), m["status"], m.get("source_url", ""))
        for m in data["models"]
    }


@lru_cache(maxsize=1)
def _default_cities() -> dict[str, City]:
    data = _read_json(DATA_DIR / "cities.json")
    return {
        c["id"]: City(c["id"], float(c["lat"]), float(c["lon"]), c["stress_category"],
                      c.get("status", "sourced"), c.get("source", ""), c.get("source_url", ""),
                      c.get("lookup_date"))
        for c in data["cities"]
    }


def load_cities() -> dict[str, City]:
    """The six seed cities keyed by id."""
    return _default_cities()


def get_city(name: str) -> City:
    try:
        return load_cities()[name]
    except KeyError:
        raise EngineError(
            "unknown_city",
            "We only have data for Chennai, Bengaluru, Hyderabad, Mumbai, Delhi and Pune "
            "right now.",
        ) from None


def _calibrated(items: list[Factor], grid: GridModel) -> list[Factor]:
    """Fill in ``ef_coal`` so that the annual mix reproduces the CEA grid factor."""
    by_id = {f.id: f for f in items}
    ef_coal = calibrate_coal_ef(grid.annual_shares, by_id["ef_gas"].value,
                                by_id["cea_grid_ef"].value)
    return [
        replace(f, value=ef_coal, low=ef_coal * (1 - _COAL_EF_RANGE),
                high=ef_coal * (1 + _COAL_EF_RANGE)) if f.id == "ef_coal" else f
        for f in items
    ]


def load_factors(
    path: Path | str | None = None,
    *,
    grid_path: Path | str | None = None,
    sweep_path: Path | str | None = None,
    gpus_path: Path | str | None = None,
) -> Factors:
    """Load all factors. The default call (no arguments) is cached for warm Lambda starts."""
    if path is None and grid_path is None and sweep_path is None and gpus_path is None:
        return _default_factors()
    return _load(path, grid_path, sweep_path, gpus_path)


@lru_cache(maxsize=1)
def _default_factors() -> Factors:
    return _load(None, None, None, None)


def _load(
    path: Path | str | None,
    grid_path: Path | str | None,
    sweep_path: Path | str | None,
    gpus_path: Path | str | None,
) -> Factors:
    factors_file = Path(path) if path else DATA_DIR / "factors.json"
    raw_bytes = factors_file.read_bytes()
    data = json.loads(raw_bytes.decode("utf-8"))
    items = [
        Factor(
            id=f["id"], group=f["group"], label=f["label"], value=float(f["value"]),
            low=float(f["low"]), high=float(f["high"]), unit=f["unit"], status=f["status"],
            source=f["source"], source_url=f["source_url"], notes=f["notes"],
            footprint_effect=f.get("footprint_effect", "increasing"),
        )
        for f in data["factors"]
    ]
    grid = load_grid(grid_path)
    sweep_file = Path(sweep_path) if sweep_path else DATA_DIR / "powercap_sweep.json"
    sweep = _read_json(sweep_file).get("gpus", {})
    version = f"{data['version']}+{hashlib.sha256(raw_bytes).hexdigest()[:12]}"
    return Factors(
        version,
        tuple(_calibrated(items, grid)),
        grid,
        MappingProxyType(load_gpus(gpus_path)),
        MappingProxyType(sweep),
    )
