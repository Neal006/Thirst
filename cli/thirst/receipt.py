"""Build, check, print and save the receipt (plan 04.7, contract 08 §3.4).

The body follows what the server accepts: at most 72 slots, every slot hour inside the job, levels
in {1.0, 0.85, 0.7}, times cut to whole seconds. The terminal output prints the SERVER's numbers
after a successful post, so the CLI and the web page always agree.
"""

from __future__ import annotations

import json
import math
import os
import secrets
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from . import __version__, config, ids
from .errors import CliError, ConfigError
from .ledger import IST, SlotEnergy, floor_hour
from .meter import MeterSummary

LEVELS = (1.0, 0.85, 0.7)
MAX_SLOTS = 72
KWH_TOLERANCE = 1.1  # same tolerance as the server (receipt_kwh_tolerance)
_BASE32 = "abcdefghijklmnopqrstuvwxyz234567"
_ONE_SECOND = timedelta(seconds=1)
_ONE_HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class JobFacts:
    site_id: str
    plan_id: str | None
    job_id: str
    start_ts: datetime
    end_ts: datetime
    exit_code: int | None
    interrupted: bool
    overran: bool
    cap_applied: bool
    cap_method: str


def new_job_id() -> str:
    """``j_`` plus 12 random characters of the base32 alphabet the server accepts."""
    return "j_" + "".join(secrets.choice(_BASE32) for _ in range(12))


# ------------------------------------------------------------ body


def _clean(value: float) -> float:
    return round(value, 9) if math.isfinite(value) and value > 0 else 0.0


def _snap(level: float) -> float:
    return min(LEVELS, key=lambda known: abs(known - level))


def _merge(into: list[Any], other: list[Any]) -> None:
    """Add ``other`` ([run, idle, level]) into ``into``; the level of the bigger energy wins."""
    if other[0] + other[1] > into[0] + into[1]:
        into[2] = other[2]
    into[0] += other[0]
    into[1] += other[1]


def _fit_slots(
    slots: Iterable[SlotEnergy], start: datetime, end: datetime
) -> list[tuple[datetime, list[Any]]]:
    first = floor_hour(start)
    last = floor_hour(end - _ONE_SECOND)
    merged: dict[datetime, list[Any]] = {}
    for item in slots:
        hour = min(max(datetime.fromisoformat(item.hour).astimezone(IST), first), last)
        entry = [_clean(item.run_kwh), _clean(item.idle_kwh), _snap(item.level)]
        if hour in merged:
            _merge(merged[hour], entry)
        else:
            merged[hour] = entry
    if not merged:
        merged[first] = [0.0, 0.0, 1.0]
    ordered = sorted(merged.items())
    while len(ordered) > MAX_SLOTS:
        (_, early), (hour, later) = ordered[0], ordered[1]
        _merge(later, early)
        ordered = [(hour, later), *ordered[2:]]
    return ordered


def build_body(facts: JobFacts, summary: MeterSummary) -> dict[str, Any]:
    """The receipt body for ``POST /receipts`` (contract 08 §3.4)."""
    start = facts.start_ts.astimezone(IST).replace(microsecond=0)
    end = facts.end_ts.astimezone(IST).replace(microsecond=0)
    if end <= start:
        end = start + _ONE_SECOND
    gpu = summary.gpus[0] if summary.gpus else None
    return {
        "site_id": facts.site_id,
        "plan_id": facts.plan_id,
        "job_id": facts.job_id,
        "start_ts": start.isoformat(),
        "end_ts": end.isoformat(),
        "slots": [
            {
                "hour": hour.isoformat(),
                "run_kwh": round(run, 9),
                "idle_kwh": round(idle, 9),
                "level": level,
            }
            for hour, (run, idle, level) in _fit_slots(summary.slots, start, end)
        ],
        "cap_applied": facts.cap_applied,
        "cap_method": facts.cap_method,
        "method": summary.method,
        "gpu": {
            "name": gpu.name if gpu else "unknown",
            "driver": summary.driver,
            "count": max(1, len(summary.gpus)),
        },
        "exit_code": facts.exit_code,
        "interrupted": facts.interrupted,
        "overran": facts.overran,
        "cli_version": __version__,
    }


def _total_kwh(body: Mapping[str, Any]) -> float:
    return sum(s["run_kwh"] + s["idle_kwh"] for s in body["slots"])


def plausibility_warnings(body: Mapping[str, Any], p_max_w: float) -> tuple[str, ...]:
    """Warn if the energy is more than the GPUs can physically draw (the server checks too)."""
    start = datetime.fromisoformat(body["start_ts"])
    end = datetime.fromisoformat(body["end_ts"])
    hours = (end - start).total_seconds() / 3600
    limit = body["gpu"]["count"] * p_max_w / 1000 * hours * KWH_TOLERANCE
    total = _total_kwh(body)
    if total <= limit:
        return ()
    return (
        f"The measured energy ({total:.2f} kWh) is more than {body['gpu']['count']} GPU(s) can "
        f"draw in {hours:.1f} h (about {limit:.2f} kWh). The measurement may be wrong; "
        "the server may reject this receipt.",
    )


# ------------------------------------------------------------ terminal output


def _duration(start: datetime, end: datetime) -> str:
    minutes = int((end - start).total_seconds() // 60)
    hours, rest = divmod(minutes, 60)
    if hours and rest:
        return f"{hours} h {rest} min"
    return f"{hours} h" if hours else f"{rest} min"


def _span(body: Mapping[str, Any]) -> str:
    start = datetime.fromisoformat(body["start_ts"])
    end = datetime.fromisoformat(body["end_ts"])
    stop = end.strftime("%H:%M" if end.date() == start.date() else "%d %b %H:%M")
    return f"{start.strftime('%d %b %H:%M')} to {stop} IST ({_duration(start, end)})"


def _cap_text(body: Mapping[str, Any]) -> str:
    lowest = min((s["level"] for s in body["slots"]), default=1.0)
    if body["method"] == "modelled":
        # The modelled meter assumes the plan's power level was followed (TODO 4.1.g), so say that
        # instead of "uncapped", which described the real GPU and contradicted the saving shown.
        if lowest >= 1.0:
            return "modelled at full power"
        return f"modelled at {round(lowest * 100)}% (plan level)"
    if not body["cap_applied"]:
        return "uncapped"
    return f"cap {round(lowest * 100)}%"


def _tag(body: Mapping[str, Any]) -> str:
    method = body["method"]
    if method.startswith("nvml"):
        return "measured"
    return "modelled" if method == "modelled" else "unverified"


def _row(label: str, text: str) -> str:
    return f"  {label:<9}{text}"


def _header(body: Mapping[str, Any]) -> list[str]:
    gpu = body["gpu"]
    ran = f"{_span(body)} on {gpu['count']} x {gpu['name']}, {_cap_text(body)}"
    return [f"Thirst receipt {body['job_id']}", _row("Ran", ran)]


def _saved_text(actual: Mapping[str, Any], base: Mapping[str, Any]) -> str | None:
    parts = []
    for key, name in (("litres", "water"), ("C_kg", "CO2")):
        before, after = base.get(key), actual.get(key)
        if isinstance(before, int | float) and isinstance(after, int | float) and before > 0:
            parts.append(f"{round(100 * (1 - after / before))}% {name}")
    if not parts:
        return None
    return " and ".join(parts) + " compared with starting right away (modelled)"


SMALL_KWH = 0.1  # below this, show Wh so a short job does not print "0.00 kWh"
SMALL_LITRES = 1.0
SMALL_KG = 0.1


def energy_text(kwh: float) -> str:
    return f"{kwh * 1000:.1f} Wh" if abs(kwh) < SMALL_KWH else f"{kwh:.2f} kWh"


def water_text(litres: float) -> str:
    return f"{litres * 1000:.0f} mL" if abs(litres) < SMALL_LITRES else f"{litres:.1f} L"


def carbon_text(kg: float) -> str:
    return f"{kg * 1000:.0f} g" if abs(kg) < SMALL_KG else f"{kg:.2f} kg"


def _footprint_rows(scoring: Mapping[str, Any], tag: str) -> list[str]:
    actual, base = scoring.get("actual") or {}, scoring.get("base") or {}
    rows = []
    if "E_gpu_kwh" in actual:
        rows.append(_row("Energy", f"{energy_text(actual['E_gpu_kwh'])} GPU ({tag})"))
    if "litres" in actual:
        text = f"{water_text(actual['litres'])} (modelled)"
        if "litres" in base:
            text += f"; if you had started right away: {water_text(base['litres'])}"
        rows.append(_row("Water", text))
    if "C_kg" in actual:
        text = f"{carbon_text(actual['C_kg'])} CO2 (modelled)"
        if "C_kg" in base:
            text += f"; if you had started right away: {carbon_text(base['C_kg'])}"
        rows.append(_row("Carbon", text))
    saved = _saved_text(actual, base)
    if saved:
        rows.append(_row("Saved", saved))
    return rows


def _score_text(site_score: Mapping[str, Any] | None) -> str:
    if not site_score or site_score.get("value") is None:
        return "Site score not rated yet (needs a flexible receipt)"
    badge = f" {site_score['badge']}" if site_score.get("badge") else ""
    tag = " (Provisional)" if site_score.get("provisional") else ""
    return f"Site score {site_score['value']:g}{badge}{tag}"


def format_scored(
    body: Mapping[str, Any],
    response: Mapping[str, Any],
    web_url: str = "",
    *,
    public: bool = True,
) -> str:
    """The terminal receipt from the server's scored response.

    A private site's receipts are hidden on the website (D26), so no link is printed for it.
    """
    lines = _header(body) + _footprint_rows(response.get("scoring") or {}, _tag(body))
    capture = response.get("capture")
    if response.get("no_room") or capture is None:
        lines.append(_row("Capture", "Little room to save on this job, so no capture score"))
    else:
        lines.append(_row("Capture", f"You took {round(capture * 100)}% of the possible saving"))
    lines.append(_row("Score", _score_text(response.get("site_score"))))
    if not public:
        lines.append(_row("Receipt", "Private site: receipts are kept off the website"))
    elif response.get("url"):
        lines.append(_row("Receipt", web_url.rstrip("/") + str(response["url"])))
    return "\n".join(lines) + "\n"


def format_local(body: Mapping[str, Any], *, queued: bool, note: str = "") -> str:
    """The local-only receipt (kWh from our own meter) when nothing was scored."""
    lines = _header(body)
    lines.append(_row("Energy", f"{energy_text(_total_kwh(body))} GPU ({_tag(body)})"))
    if note:
        lines.append(_row("Status", note))
    elif queued:
        lines.append(_row("Status", "Receipt queued, run `thirst sync` to post it."))
    else:
        lines.append(_row("Status", "Saved on this computer only."))
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------ files


def _path(job_id: str) -> Path:
    if not ids.JOB_ID.fullmatch(job_id):
        raise CliError("That is not a valid job id (it looks like j_abcdefghijkl).")
    return config.receipts_dir() / f"{job_id}.json"


def save_receipt(body: Mapping[str, Any], response: Mapping[str, Any] | None, status: str) -> Path:
    """Save the receipt under ``~/.thirst/receipts/``. ``status``: posted, duplicate, queued, ..."""
    path = _path(body["job_id"])
    saved = {"body": body, "response": response, "status": status}
    config.write_private(path, json.dumps(saved, indent=2, sort_keys=True, allow_nan=False))
    return path


def load_receipt(job_id: str) -> dict[str, Any]:
    path = _path(job_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CliError(f"No saved receipt for {job_id} on this computer.") from None
    except (OSError, ValueError):
        raise CliError(f"The saved receipt {path.name} is not valid. Delete it.") from None
    if not isinstance(data, dict) or not isinstance(data.get("body"), dict):
        raise CliError(f"The saved receipt {path.name} is not valid. Delete it.")
    return data


def _saved_site_is_public() -> bool:
    try:
        return config.load().public
    except ConfigError:
        return True


def render_saved(job_id: str) -> str:
    """Text for ``thirst receipt show <job_id>``."""
    saved = load_receipt(job_id)
    body, response, status = saved["body"], saved.get("response"), saved.get("status")
    web_url = os.environ.get("THIRST_WEB_URL", config.DEFAULT_WEB_URL)
    if isinstance(response, dict):
        return format_scored(body, response, web_url, public=_saved_site_is_public())
    if status == "duplicate":
        return format_local(body, queued=False, note="The server already had this receipt.")
    return format_local(body, queued=status == "queued")
