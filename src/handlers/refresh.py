"""Hourly weather refresh from Open-Meteo (plan 05.4, TRD 9, contract 08 §5.1).

Hours that have started are stored as observations (``obs_*``) with an in-place update, so the
forecast written earlier is never overwritten: scoring compares against what the plan used.
Hours that have not started are stored as forecasts (``fc_*``) with the derived wet-bulb,
carbon and water intensities. If Open-Meteo fails, nothing is written, a warning is logged
and the function still succeeds, so the schedule does not hammer a failing API.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

from engine.errors import EngineError
from engine.factors import City, Factors, load_cities, load_factors
from engine.forecast import WeatherRow
from engine.grid import ci, ewif, hourly_shares
from engine.units import IST
from engine.wetbulb import stull_tw_checked

from . import store

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY = ("temperature_2m", "relative_humidity_2m", "shortwave_radiation")
TIMEOUT_S = 6
MAX_BYTES = 5_000_000
IST_OFFSET_SECONDS = 19800
MAX_HOURS = 400  # 3 forecast days + 1 past day is 96; refuse anything wildly larger
_COORD_TOLERANCE_DEG = 1.0  # Open-Meteo snaps to a model grid cell near the requested point

log = Logger(service="thirst")
metrics = Metrics(namespace="Thirst", service="thirst")


class PayloadError(ValueError):
    """The Open-Meteo response is not the shape we asked for."""


@dataclass(frozen=True, slots=True)
class RefreshResult:
    status: str  # "ok" or "failed"
    rows: int
    observed: int
    forecast: int
    skipped: int = 0


def build_url(cities: Mapping[str, City]) -> str:
    """One multi-location request for every seed city, in the order of ``cities``."""
    values = list(cities.values())
    lat = ",".join(str(c.lat) for c in values)
    lon = ",".join(str(c.lon) for c in values)
    return (
        f"{OPEN_METEO_URL}?latitude={lat}&longitude={lon}&hourly={','.join(HOURLY)}"
        "&timezone=Asia%2FKolkata&forecast_days=3&past_days=1"
    )


def fetch_open_meteo(opener: Callable[..., Any] = urllib.request.urlopen) -> Any:
    """GET the multi-location forecast. Raises OSError or ValueError on any problem."""
    request = urllib.request.Request(  # noqa: S310  (fixed https URL)
        build_url(load_cities()), headers={"User-Agent": "thirst-refresh/0.1"}
    )
    with opener(request, timeout=TIMEOUT_S) as response:
        if response.status != 200:
            raise OSError(f"Open-Meteo answered {response.status}")
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("Open-Meteo response too large")
    return json.loads(body)


def _hourly(entry: Mapping[str, Any], city: City) -> dict[str, list[Any]]:
    if entry.get("utc_offset_seconds") != IST_OFFSET_SECONDS:
        raise PayloadError("response is not in IST")
    try:
        if (
            abs(float(entry["latitude"]) - city.lat) > _COORD_TOLERANCE_DEG
            or abs(float(entry["longitude"]) - city.lon) > _COORD_TOLERANCE_DEG
        ):
            raise PayloadError("cities are in a different order than requested")
        hourly = entry["hourly"]
        columns = {name: hourly[name] for name in ("time", *HOURLY)}
    except (KeyError, TypeError) as err:
        raise PayloadError(f"missing field {err}") from None
    sizes = {len(c) if isinstance(c, list) else -1 for c in columns.values()}
    if len(sizes) != 1 or not 0 < next(iter(sizes)) <= MAX_HOURS:
        raise PayloadError("hourly columns have different or invalid lengths")
    return columns


def _hour(text: Any) -> datetime:
    if not isinstance(text, str):
        raise PayloadError("time must be text")
    try:
        naive = datetime.fromisoformat(text)
    except ValueError:
        raise PayloadError("time is not an ISO time") from None
    if naive.tzinfo is not None or (naive.minute, naive.second, naive.microsecond) != (0, 0, 0):
        raise PayloadError("time must be a local hour")
    return naive.replace(tzinfo=IST)


def parse_payload(
    payload: Any, cities: Mapping[str, City]
) -> tuple[dict[str, list[WeatherRow]], int]:
    """Valid rows per city and how many hours were skipped (null or implausible values)."""
    if not isinstance(payload, list) or len(payload) != len(cities):
        raise PayloadError("expected one entry per requested city")
    rows: dict[str, list[WeatherRow]] = {}
    skipped = 0
    for entry, (name, city) in zip(payload, cities.items(), strict=True):
        if not isinstance(entry, Mapping):
            raise PayloadError("entry is not an object")
        columns = _hourly(entry, city)
        city_rows: list[WeatherRow] = []
        for text, temp, rh, rad in zip(columns["time"], *(columns[h] for h in HOURLY), strict=True):
            hour = _hour(text)
            try:
                city_rows.append(WeatherRow(hour, temp, rh, rad))
            except EngineError:
                skipped += 1
        rows[name] = sorted(city_rows, key=lambda r: r.hour)
    return rows, skipped


def _forecast_rows(
    city: str, future: Sequence[WeatherRow], now: datetime, fx: Factors
) -> list[store.ForecastRow]:
    fs = fx.central()
    shares = hourly_shares(fx.grid, [r.hour.hour for r in future], [r.rad_wm2 for r in future], fs)
    return [
        store.ForecastRow(
            city=city,
            hour=r.hour,
            temp_c=r.temp_c,
            rh_pct=r.rh_pct,
            rad_wm2=r.rad_wm2,
            issued=now,
            tw=stull_tw_checked(r.temp_c, r.rh_pct)[0],
            ci=ci(s, fs),
            ewif=ewif(s, fs),
            pue_t_c=r.temp_c,
        )
        for r, s in zip(future, shares, strict=True)
    ]


def run(
    now: datetime,
    repo: store.WeatherRepo,
    fetch: Callable[[], Any],
    fx: Factors | None = None,
) -> RefreshResult:
    """Fetch, validate and store one refresh. Never raises for an upstream problem."""
    fx = fx or load_factors()
    cities = load_cities()
    try:
        by_city, skipped = parse_payload(fetch(), cities)
    except (OSError, ValueError) as err:
        log.warning(f"refresh_failed cities={','.join(cities)} reason={type(err).__name__}: {err}")
        return RefreshResult("failed", 0, 0, 0)
    started = now.replace(minute=0, second=0, microsecond=0)
    observed = forecast = 0
    for city, rows in by_city.items():
        for row in (r for r in rows if r.hour <= started):
            repo.record_observation(city, row.hour, row.temp_c, row.rh_pct, row.rad_wm2)
            observed += 1
        future = [r for r in rows if r.hour > started]
        repo.put_forecast(_forecast_rows(city, future, now, fx), now)
        forecast += len(future)
    return RefreshResult("ok", observed + forecast, observed, forecast, skipped)


def _now() -> datetime:
    return datetime.now(IST)


@metrics.log_metrics
def handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    now = _now()
    result = run(now, store.WeatherRepo(store.get_tables().weather), fetch_open_meteo)
    metrics.add_metric(name="RefreshRowsWritten", unit=MetricUnit.Count, value=result.rows)
    metrics.add_metric(
        name="RefreshFailed", unit=MetricUnit.Count, value=int(result.status == "failed")
    )
    if result.status == "ok":
        log.info(f"refresh_ok fc_issued={now.isoformat()} rows={result.rows}")
    return {"status": result.status, "rows": result.rows, "skipped": result.skipped}
