"""The ``GET /assumptions`` payload (plan 05.8, contract 08 §3.6).

Everything comes from the engine's loaded data, so the page can never disagree with the model.
The licence strings are summaries for the credits page; plan step 07.5 re-checks them at release.
"""

from __future__ import annotations

from typing import Any

from engine.factors import Factors, load_cities

STRESS_CATEGORIES = ("low", "low_medium", "medium_high", "high", "extremely_high")

SOURCES: tuple[dict[str, str], ...] = (
    {
        "name": "Open-Meteo",
        "url": "https://open-meteo.com/",
        "licence": "CC BY 4.0 (free for non-commercial use, attribution required)",
        "used_for": "hourly temperature, humidity and sunshine forecast and observations",
    },
    {
        "name": "CEA",
        "url": "https://cea.nic.in/",
        "licence": "Government of India publication, cited",
        "used_for": "grid carbon intensity (CO2 baseline database, direct combustion basis)",
    },
    {
        "name": "CSEP",
        "url": "https://csep.org/",
        "licence": "Published open data, cited",
        "used_for": "hourly national generation mix (Electricity and Carbon Tracker)",
    },
    {
        "name": "Ember",
        "url": "https://ember-energy.org/",
        "licence": "CC BY 4.0",
        "used_for": "annual generation mix",
    },
    {
        "name": "MoEFCC",
        "url": "https://powermin.gov.in/",
        "licence": "Government of India notification, cited",
        "used_for": "water use limits of coal power plants",
    },
    {
        "name": "WRI Aqueduct",
        "url": "https://www.wri.org/aqueduct",
        "licence": "CC BY 4.0",
        "used_for": "baseline water stress category of each city",
    },
    {
        "name": "NREL (Macknick et al. 2012)",
        "url": "https://doi.org/10.1088/1748-9326/7/4/045802",
        "licence": "Journal article, cited",
        "used_for": "water consumption of non-coal generation",
    },
    {
        "name": "NVIDIA",
        "url": "https://www.nvidia.com/",
        "licence": "Manufacturer datasheets, cited",
        "used_for": "GPU maximum and idle power",
    },
)


def build(fx: Factors) -> dict[str, Any]:
    gpus = [
        {
            "id": model.id,
            "label": model.label,
            "p_max_w": model.p_max_w,
            "p_idle_w": model.p_idle_w,
            "sweep_status": "measured" if model.id in fx.sweep else "placeholder",
        }
        for model in sorted(fx.gpus.values(), key=lambda m: m.label)
    ]
    cities = [
        {
            "id": city.id,
            "stress_category": city.stress_category,
            "stress_weight": fx.stress_weight(city.stress_category),
            "status": city.status,
        }
        for city in load_cities().values()
    ]
    return {
        "version": fx.version,
        "factors": fx.table(),
        "gpus": gpus,
        "cities": cities,
        "stress_weights": {c: fx.stress_weight(c) for c in STRESS_CATEGORIES},
        "sources": [dict(s) for s in SOURCES],
    }
