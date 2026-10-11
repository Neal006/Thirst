"""Deterministic rule‑based parser for free‑form job sentences.

Extracts:
- work_hours (float) – number before "hour(s)" or "hr(s)"
- gpu_count (int) – leading number before an "x" (e.g. "2 x 4090")
- city (str) – first recognized city name from the engine data
- workload (str) – simple keyword match (lora, training, inference, finetune)

Returns a dict with the extracted values (or ``None``) and a sorted ``found`` list.
"""

import re
from typing import Any

from engine.factors import load_cities


def parse_job_sentence(text: str) -> dict[str, Any]:
    """Parse *text* and return extracted parameters.

    The implementation is deliberately simple and deterministic – no ML, only regexes and
    known city names. The return shape matches the contract used by the frontend component
    and the unit tests.
    """
    result: dict[str, Any] = {
        "work_hours": None,
        "gpu_count": None,
        "city": None,
        "workload": None,
        "found": [],
    }

    # GPU count – number before an "x" (e.g. "2 x 4090")
    m = re.search(r"(?P<g>\d+)\s*[xX]\s*\d+", text)
    if m:
        result["gpu_count"] = int(m.group("g"))
        result["found"].append("gpu_count")

    # work hours – number followed by "hour" or "hr"
    m = re.search(r"(?P<h>\d+(?:\.\d+)?)\s*(?:hours?|hrs?)", text, re.IGNORECASE)
    if m:
        result["work_hours"] = float(m.group("h"))
        result["found"].append("work_hours")

    # city – first matching known city name
    for city in load_cities():
        if re.search(r"\b" + re.escape(city) + r"\b", text, re.IGNORECASE):
            result["city"] = city
            result["found"].append("city")
            break

    # workload – simple keyword detection
    workload_keywords = ["lora", "training", "inference", "finetune", "fine‑tune"]
    for kw in workload_keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE):
            result["workload"] = kw
            result["found"].append("workload")
            break

    # deduplicate while preserving order
    seen = set()
    ordered = []
    for x in result["found"]:
        if x not in seen:
            ordered.append(x)
            seen.add(x)
    result["found"] = ordered
    return result
