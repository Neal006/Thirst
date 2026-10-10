"""Hourly weather refresh (plan 05.4, TRD 9)."""

from __future__ import annotations

import copy
import http.client
import io
import json
import logging
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from weather_helpers import ist

from engine.factors import load_cities, load_factors
from engine.forecast import SAMPLE_PATH
from engine.grid import ci, ewif, hourly_shares
from engine.wetbulb import stull_tw_checked
from handlers import refresh, store
from handlers.store import WeatherRepo, from_ddb

SAMPLE: list[dict[str, Any]] = json.loads(Path(SAMPLE_PATH).read_text(encoding="utf-8"))
NOW = ist(2026, 10, 9, 12, 0)  # the sample covers 2026-10-08 00:00 to 2026-10-11 23:00
PAST_HOURS = 37  # 10-08 00:00 .. 10-09 12:00 inclusive: hours that have started
FUTURE_HOURS = 59
CITY_ORDER = list(load_cities())


def payload() -> list[dict[str, Any]]:
    return copy.deepcopy(SAMPLE)


def run(repo: WeatherRepo, data: Any = None, now: datetime = NOW) -> refresh.RefreshResult:
    return refresh.run(now, repo, lambda: payload() if data is None else data)


def all_items(tables: store.Tables) -> list[dict[str, Any]]:
    return [from_ddb(i) for i in tables.weather.scan()["Items"]]


# request ----------------------------------------------------------------------------------


def test_url_asks_for_the_six_cities_in_order() -> None:
    url = refresh.build_url(load_cities())
    parts = urlparse(url)
    query = parse_qs(parts.query)
    assert parts.netloc == "api.open-meteo.com" and parts.path == "/v1/forecast"
    cities = list(load_cities().values())
    assert query["latitude"] == [",".join(str(c.lat) for c in cities)]
    assert query["longitude"] == [",".join(str(c.lon) for c in cities)]
    assert query["hourly"] == ["temperature_2m,relative_humidity_2m,shortwave_radiation"]
    assert query["timezone"] == ["Asia/Kolkata"]
    assert query["forecast_days"] == ["3"] and query["past_days"] == ["1"]


# writing rows -----------------------------------------------------------------------------


def test_started_hours_are_observations_and_later_hours_are_forecasts(
    tables: store.Tables,
) -> None:
    result = run(WeatherRepo(tables.weather))
    assert result.status == "ok"
    assert (result.observed, result.forecast) == (6 * PAST_HOURS, 6 * FUTURE_HOURS)
    assert result.rows == 6 * 96
    items = {(i["city"], i["hour"]): i for i in all_items(tables)}
    assert len(items) == 6 * 96
    past = items[("Chennai", "2026-10-09T12:00:00+05:30")]  # the current hour has started
    future = items[("Chennai", "2026-10-09T13:00:00+05:30")]
    assert "obs_temp" in past and "fc_temp" not in past
    assert "fc_temp" in future and "obs_temp" not in future
    assert future["fc_issued"] == NOW.isoformat()


def test_values_match_the_open_meteo_response(tables: store.Tables) -> None:
    run(WeatherRepo(tables.weather))
    chennai = SAMPLE[0]["hourly"]
    k = chennai["time"].index("2026-10-09T15:00")
    item = from_ddb(
        tables.weather.get_item(Key={"city": "Chennai", "hour": "2026-10-09T15:00:00+05:30"})[
            "Item"
        ]
    )
    assert item["fc_temp"] == chennai["temperature_2m"][k]
    assert item["fc_rh"] == chennai["relative_humidity_2m"][k]
    assert item["fc_rad"] == chennai["shortwave_radiation"][k]


def test_every_city_gets_its_own_rows(tables: store.Tables) -> None:
    run(WeatherRepo(tables.weather))
    by_city: dict[str, int] = {}
    for item in all_items(tables):
        by_city[item["city"]] = by_city.get(item["city"], 0) + 1
    assert by_city == {name: 96 for name in CITY_ORDER}
    delhi = SAMPLE[CITY_ORDER.index("Delhi")]["hourly"]["temperature_2m"][40]
    got = tables.weather.get_item(Key={"city": "Delhi", "hour": "2026-10-09T16:00:00+05:30"})
    assert float(got["Item"]["fc_temp"]) == delhi


def test_ttl_is_the_hour_plus_ten_days(tables: store.Tables) -> None:
    run(WeatherRepo(tables.weather))
    for item in all_items(tables):
        hour = datetime.fromisoformat(item["hour"])
        assert item["ttl"] == int((hour + timedelta(days=10)).timestamp())


def test_derived_values_come_from_the_engine(tables: store.Tables) -> None:
    run(WeatherRepo(tables.weather))
    fx = load_factors()
    fs = fx.central()
    got = from_ddb(
        tables.weather.get_item(Key={"city": "Chennai", "hour": "2026-10-09T15:00:00+05:30"})[
            "Item"
        ]
    )
    assert got["tw"] == pytest.approx(stull_tw_checked(got["fc_temp"], got["fc_rh"])[0], abs=1e-6)
    assert got["pue_inputs"] == {"t_c": got["fc_temp"]}
    assert 0.3 < got["ci"] < 1.1 and 0.5 < got["ewif"] < 6.0  # kg/kWh and L/kWh, India scale
    future = sorted(
        (i for i in all_items(tables) if i["city"] == "Chennai" and "fc_temp" in i),
        key=lambda i: i["hour"],
    )
    shares = hourly_shares(
        fx.grid,
        [datetime.fromisoformat(i["hour"]).hour for i in future],
        [i["fc_rad"] for i in future],
        fs,
    )
    k = [i["hour"] for i in future].index("2026-10-09T15:00:00+05:30")
    assert got["ci"] == pytest.approx(ci(shares[k], fs), abs=1e-6)
    assert got["ewif"] == pytest.approx(ewif(shares[k], fs), abs=1e-6)


# the fairness rule ------------------------------------------------------------------------


def test_the_original_forecast_survives_when_the_hour_is_observed(tables: store.Tables) -> None:
    repo = WeatherRepo(tables.weather)
    run(repo, now=ist(2026, 10, 9, 11, 0))  # 13:00 is a forecast hour
    first = from_ddb(
        tables.weather.get_item(Key={"city": "Chennai", "hour": "2026-10-09T13:00:00+05:30"})[
            "Item"
        ]
    )
    changed = payload()
    hourly = changed[0]["hourly"]
    k = hourly["time"].index("2026-10-09T13:00")
    hourly["temperature_2m"][k] += 4.0  # the analysis differs from what was forecast
    run(repo, changed, now=ist(2026, 10, 9, 13, 5))  # 13:00 has now started
    after = from_ddb(
        tables.weather.get_item(Key={"city": "Chennai", "hour": "2026-10-09T13:00:00+05:30"})[
            "Item"
        ]
    )
    assert after["fc_temp"] == first["fc_temp"]  # the forecast the plan used is unchanged
    assert after["fc_issued"] == first["fc_issued"]
    assert after["obs_temp"] == first["fc_temp"] + 4.0
    assert after["tw"] == first["tw"]


def test_later_runs_replace_the_forecast_of_future_hours(tables: store.Tables) -> None:
    repo = WeatherRepo(tables.weather)
    run(repo)
    changed = payload()
    hourly = changed[0]["hourly"]
    k = hourly["time"].index("2026-10-10T10:00")
    hourly["temperature_2m"][k] = 40.0
    later = NOW + timedelta(hours=1)
    run(repo, changed, now=later)
    item = from_ddb(
        tables.weather.get_item(Key={"city": "Chennai", "hour": "2026-10-10T10:00:00+05:30"})[
            "Item"
        ]
    )
    assert item["fc_temp"] == 40.0 and item["fc_issued"] == later.isoformat()


def test_running_twice_does_not_duplicate_rows(tables: store.Tables) -> None:
    repo = WeatherRepo(tables.weather)
    run(repo)
    run(repo)
    assert len(all_items(tables)) == 6 * 96


# failures ---------------------------------------------------------------------------------


def broken(mutate: Any) -> list[dict[str, Any]]:
    data = payload()
    return mutate(data)


BAD_PAYLOADS = {
    "not a list": {"error": True},
    "five cities": payload()[:5],
    "wrong order": list(reversed(payload())),
    "wrong offset": broken(lambda d: [{**e, "utc_offset_seconds": 0} for e in d]),
    "no hourly": broken(lambda d: [{k: v for k, v in e.items() if k != "hourly"} for e in d]),
    "missing variable": broken(
        lambda d: [
            {**e, "hourly": {k: v for k, v in e["hourly"].items() if k != "shortwave_radiation"}}
            for e in d
        ]
    ),
    "uneven lengths": broken(
        lambda d: [{**e, "hourly": {**e["hourly"], "temperature_2m": [1.0]}} for e in d]
    ),
    "time is not text": broken(
        lambda d: [{**e, "hourly": {**e["hourly"], "time": [5] * 96}} for e in d]
    ),
    "bad time": broken(
        lambda d: [{**e, "hourly": {**e["hourly"], "time": ["soon"] * 96}} for e in d]
    ),
}


@pytest.mark.parametrize("name", list(BAD_PAYLOADS))
def test_a_bad_response_writes_nothing_and_warns(
    tables: store.Tables, caplog: pytest.LogCaptureFixture, name: str
) -> None:
    caplog.set_level(logging.WARNING)
    result = run(WeatherRepo(tables.weather), BAD_PAYLOADS[name])
    assert result.status == "failed" and result.rows == 0
    assert all_items(tables) == []
    assert any("refresh_failed" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError("no route"),
        urllib.error.HTTPError("u", 500, "boom", {}, None),  # type: ignore[arg-type]
        TimeoutError("timed out"),
        json.JSONDecodeError("bad", "x", 0),
        ConnectionResetError("reset"),
    ],
)
def test_an_unreachable_open_meteo_writes_nothing_and_does_not_raise(
    tables: store.Tables, caplog: pytest.LogCaptureFixture, error: Exception
) -> None:
    def fetch() -> Any:
        raise error

    caplog.set_level(logging.WARNING)
    result = refresh.run(NOW, WeatherRepo(tables.weather), fetch)
    assert result.status == "failed"
    assert all_items(tables) == []
    warning = next(r.getMessage() for r in caplog.records if "refresh_failed" in r.getMessage())
    assert "Chennai" in warning  # the city list is logged


def test_missing_values_skip_only_that_hour(tables: store.Tables) -> None:
    data = payload()
    hourly = data[0]["hourly"]
    k = hourly["time"].index("2026-10-09T15:00")
    hourly["temperature_2m"][k] = None
    hourly["relative_humidity_2m"][k + 1] = 250  # impossible humidity
    result = run(WeatherRepo(tables.weather), data)
    assert result.status == "ok" and result.rows == 6 * 96 - 2
    present = {(i["city"], i["hour"]) for i in all_items(tables)}
    assert ("Chennai", "2026-10-09T15:00:00+05:30") not in present
    assert ("Chennai", "2026-10-09T16:00:00+05:30") not in present
    assert ("Chennai", "2026-10-09T17:00:00+05:30") in present


def test_one_city_with_only_bad_values_does_not_stop_the_others(tables: store.Tables) -> None:
    data = payload()
    data[1]["hourly"]["temperature_2m"] = [None] * 96
    result = run(WeatherRepo(tables.weather), data)
    assert result.status == "ok" and result.rows == 5 * 96
    assert {i["city"] for i in all_items(tables)} == set(CITY_ORDER) - {CITY_ORDER[1]}


# fetching ---------------------------------------------------------------------------------


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def test_fetch_reads_json_with_the_six_second_timeout() -> None:
    seen: dict[str, Any] = {}

    def opener(request: Any, timeout: float) -> FakeResponse:
        seen["url"], seen["timeout"] = request.full_url, timeout
        return FakeResponse(json.dumps(SAMPLE).encode())

    assert refresh.fetch_open_meteo(opener) == SAMPLE
    assert seen["timeout"] == 6 and seen["url"].startswith("https://api.open-meteo.com/v1/forecast")


def test_fetch_refuses_a_huge_or_invalid_body() -> None:
    huge = FakeResponse(b" " * (refresh.MAX_BYTES + 10))
    with pytest.raises(ValueError, match="too large"):
        refresh.fetch_open_meteo(lambda r, timeout: huge)
    with pytest.raises(ValueError):
        refresh.fetch_open_meteo(lambda r, timeout: FakeResponse(b"<html>"))


def test_fetch_refuses_a_non_200_status() -> None:
    odd = FakeResponse(b"[]")
    odd.status = 204
    with pytest.raises(OSError, match="204"):
        refresh.fetch_open_meteo(lambda r, timeout: odd)


# handler ----------------------------------------------------------------------------------


def test_the_handler_writes_rows_and_reports_them(
    tables: store.Tables, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(refresh, "fetch_open_meteo", lambda *a, **k: payload())
    monkeypatch.setattr(refresh, "_now", lambda: NOW)
    out = refresh.handler({}, None)
    assert out["status"] == "ok" and out["rows"] == 6 * 96
    assert len(all_items(tables)) == 6 * 96
    assert "RefreshRowsWritten" in capsys.readouterr().out


def test_the_handler_succeeds_even_when_open_meteo_is_down(
    tables: store.Tables, monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(*a: Any, **k: Any) -> Any:
        raise urllib.error.URLError("down")

    monkeypatch.setattr(refresh, "fetch_open_meteo", down)
    monkeypatch.setattr(refresh, "_now", lambda: NOW)
    out = refresh.handler({}, None)  # no exception: the schedule must not retry-hammer the API
    assert out["status"] == "failed" and out["rows"] == 0


@pytest.mark.parametrize(
    "error",
    [
        http.client.IncompleteRead(b"par", 100),  # a body cut short mid-transfer
        http.client.RemoteDisconnected("closed"),
        TimeoutError("slow"),
        json.JSONDecodeError("bad", "x", 0),
    ],
)
def test_a_broken_download_is_a_failed_refresh_not_a_crash(
    tables: store.Tables, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def broken(*a: Any, **k: Any) -> Any:
        raise error

    monkeypatch.setattr(refresh, "fetch_open_meteo", broken)
    monkeypatch.setattr(refresh, "_now", lambda: NOW)
    assert refresh.handler({}, None)["status"] == "failed"
    assert all_items(tables) == []
