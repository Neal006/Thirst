"""Repository layer on moto DynamoDB (plan 05.3, contract 08 §5)."""

from __future__ import annotations

import json
import math
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from boto3.dynamodb.types import TypeSerializer
from hypothesis import given
from hypothesis import strategies as st
from weather_helpers import SUBMIT, diurnal_rows, ist, request

from engine.planner import plan_from_rows
from handlers import store
from handlers.store import (
    DuplicateJob,
    NonFiniteNumber,
    PlanRepo,
    ReceiptRepo,
    SiteExists,
    SiteRepo,
    StoreError,
    WeatherRepo,
    from_ddb,
    to_ddb,
)

NOW = ist(2026, 10, 10, 12, 0)

# to_ddb / from_ddb ----------------------------------------------------------------------------


def test_floats_become_decimals_through_their_shortest_repr() -> None:
    assert to_ddb(0.1) == Decimal("0.1")
    assert to_ddb({"a": [1.5, {"b": 2.25}]}) == {"a": [Decimal("1.5"), {"b": Decimal("2.25")}]}


def test_bool_none_int_str_bytes_are_untouched() -> None:
    assert to_ddb(True) is True
    assert to_ddb(None) is None
    assert to_ddb(7) == 7 and not isinstance(to_ddb(7), Decimal)
    assert to_ddb("x") == "x" and to_ddb(b"x") == b"x"


def test_tuples_become_lists() -> None:
    assert to_ddb((1, 2.5)) == [1, Decimal("2.5")]


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, Decimal("NaN")])
def test_non_finite_numbers_are_rejected_with_their_path(bad: Any) -> None:
    with pytest.raises(NonFiniteNumber, match=r"\$\.a\[1\]"):
        to_ddb({"a": [0, bad]})


def test_non_finite_is_a_store_error_and_a_value_error() -> None:
    assert issubclass(NonFiniteNumber, StoreError) and issubclass(NonFiniteNumber, ValueError)


def test_unstorable_types_are_rejected_not_stringified() -> None:
    with pytest.raises(TypeError, match=r"\$\.when"):
        to_ddb({"when": ist(2026, 10, 10, 1, 0)})
    with pytest.raises(TypeError):
        to_ddb({1: "int key"})


def test_numbers_outside_dynamodb_range_are_clamped_or_rejected() -> None:
    assert to_ddb(1e-200) == 0 and to_ddb(-1e-200) == 0
    with pytest.raises(StoreError):
        to_ddb(1e200)


def test_from_ddb_restores_ints_floats_and_containers() -> None:
    stored = {"n": Decimal("3"), "x": Decimal("0.85"), "l": [Decimal("1E+2")], "s": "t"}
    got = from_ddb(stored)
    assert got == {"n": 3, "x": 0.85, "l": [100], "s": "t"}
    assert type(got["n"]) is int and type(got["x"]) is float


json_values = st.recursive(
    st.none()
    | st.booleans()
    | st.integers(-(10**12), 10**12)
    | st.floats(allow_nan=False, allow_infinity=False, min_value=-1e50, max_value=1e50)
    | st.text(max_size=20),
    lambda children: (
        st.lists(children, max_size=4)
        | st.dictionaries(st.text(min_size=1, max_size=8), children, max_size=4)
    ),
    max_leaves=20,
)


def _near_zero_to_zero(value: Any) -> Any:
    if isinstance(value, float) and abs(value) < 1e-100:
        return 0
    if isinstance(value, list):
        return [_near_zero_to_zero(v) for v in value]
    if isinstance(value, dict):
        return {k: _near_zero_to_zero(v) for k, v in value.items()}
    return value


@given(json_values)
def test_round_trip_is_lossless_for_json_values(value: Any) -> None:
    assert from_ddb(to_ddb(value)) == _near_zero_to_zero(value)


# weather -------------------------------------------------------------------------------------


def forecast_row(city: str, hour: Any, temp: float = 30.0, issued: Any = NOW) -> store.ForecastRow:
    return store.ForecastRow(
        city=city,
        hour=hour,
        temp_c=temp,
        rh_pct=60.0,
        rad_wm2=100.0,
        issued=issued,
        tw=24.5,
        ci=0.71,
        ewif=2.4,
        pue_t_c=temp,
    )


def test_forecast_rows_round_trip_sorted_with_the_issue_time(tables: store.Tables) -> None:
    repo = WeatherRepo(tables.weather)
    start = ist(2026, 10, 10, 13, 0)
    rows = [forecast_row("Chennai", start + timedelta(hours=h), 25 + h) for h in (3, 0, 2, 1)]
    repo.put_forecast(rows, now=NOW)
    window = repo.window("Chennai", start, 4)
    assert [r.hour for r in window.rows] == [start + timedelta(hours=h) for h in range(4)]
    assert [r.temp_c for r in window.rows] == [25.0, 26.0, 27.0, 28.0]
    assert window.issued == NOW


def test_window_is_limited_to_the_city_and_range(tables: store.Tables) -> None:
    repo = WeatherRepo(tables.weather)
    start = ist(2026, 10, 10, 13, 0)
    repo.put_forecast([forecast_row("Chennai", start + timedelta(hours=h)) for h in range(6)], NOW)
    repo.put_forecast([forecast_row("Pune", start + timedelta(hours=h)) for h in range(6)], NOW)
    assert len(repo.window("Chennai", start, 4).rows) == 4
    assert len(repo.window("Chennai", start + timedelta(hours=4), 48).rows) == 2
    assert repo.window("Delhi", start, 4).rows == ()
    assert repo.window("Delhi", start, 4).issued is None


def test_ttl_is_the_hour_plus_ten_days(tables: store.Tables) -> None:
    repo = WeatherRepo(tables.weather)
    hour = ist(2026, 10, 10, 13, 0)
    repo.put_forecast([forecast_row("Chennai", hour)], NOW)
    item = tables.weather.get_item(Key={"city": "Chennai", "hour": hour.isoformat()})["Item"]
    assert int(item["ttl"]) == int((hour + timedelta(days=10)).timestamp())
    assert item["hour"] == "2026-10-10T13:00:00+05:30"


def test_observations_keep_the_original_forecast(tables: store.Tables) -> None:
    repo = WeatherRepo(tables.weather)
    hour = ist(2026, 10, 10, 9, 0)
    issued = NOW - timedelta(hours=3)
    repo.put_forecast([forecast_row("Chennai", hour, temp=30.0, issued=issued)], now=issued)
    repo.record_observation("Chennai", hour, temp_c=33.5, rh_pct=55.0, rad_wm2=400.0)
    item = from_ddb(
        tables.weather.get_item(Key={"city": "Chennai", "hour": hour.isoformat()})["Item"]
    )
    assert item["fc_temp"] == 30.0 and item["obs_temp"] == 33.5  # forecast survives (fairness)
    assert item["fc_issued"] == (NOW - timedelta(hours=3)).isoformat()
    window = repo.window("Chennai", hour, 1)
    assert window.rows[0].temp_c == 30.0  # planning uses the forecast, not the observation


def test_an_observation_without_a_forecast_row_creates_one(tables: store.Tables) -> None:
    repo = WeatherRepo(tables.weather)
    hour = ist(2026, 10, 10, 9, 0)
    repo.record_observation("Chennai", hour, temp_c=33.5, rh_pct=55.0, rad_wm2=400.0)
    assert [r.temp_c for r in repo.observed("Chennai", [hour])] == [33.5]
    assert repo.window("Chennai", hour, 1).rows[0].temp_c == 33.5  # falls back to observed


def test_observed_returns_only_rows_with_observations(tables: store.Tables) -> None:
    repo = WeatherRepo(tables.weather)
    start = ist(2026, 10, 10, 7, 0)
    repo.put_forecast([forecast_row("Chennai", start + timedelta(hours=h)) for h in range(5)], NOW)
    repo.record_observation("Chennai", start + timedelta(hours=1), 31.0, 50.0, 300.0)
    repo.record_observation("Chennai", start + timedelta(hours=2), 32.0, 50.0, 300.0)
    hours = [start + timedelta(hours=h) for h in range(5)]
    got = repo.observed("Chennai", hours)
    assert [r.hour for r in got] == hours[1:3]
    assert repo.observed("Chennai", []) == []


def test_corrupt_stored_weather_is_skipped_not_fatal(tables: store.Tables) -> None:
    repo = WeatherRepo(tables.weather)
    start = ist(2026, 10, 10, 13, 0)
    repo.put_forecast([forecast_row("Chennai", start + timedelta(hours=h)) for h in range(3)], NOW)
    tables.weather.update_item(
        Key={"city": "Chennai", "hour": (start + timedelta(hours=1)).isoformat()},
        UpdateExpression="SET fc_temp = :t",
        ExpressionAttributeValues={":t": Decimal("999")},
    )
    assert [r.hour for r in repo.window("Chennai", start, 3).rows] == [
        start,
        start + timedelta(hours=2),
    ]


def test_naive_hours_are_refused(tables: store.Tables) -> None:
    with pytest.raises(StoreError, match="timezone"):
        WeatherRepo(tables.weather).put_forecast(
            [forecast_row("Chennai", SUBMIT.replace(tzinfo=None))], NOW
        )


# sites ---------------------------------------------------------------------------------------

SITE = {
    "site_id": "s_abcdefghij",
    "name": "CSE GPU Lab",
    "org": None,
    "city": "Chennai",
    "cooling": "room_ac",
    "gpu_count": 8,
    "division": "D1",
    "coverage_declared": 0.5,
    "public": True,
    "simulated": False,
    "created_at": "2026-10-10T12:00:00+05:30",
}


def test_site_round_trip_and_missing(tables: store.Tables) -> None:
    repo = SiteRepo(tables.sites)
    repo.create(SITE)
    got = repo.get("s_abcdefghij")
    assert got is not None and got["name"] == "CSE GPU Lab" and got["coverage_declared"] == 0.5
    assert got["gpu_count"] == 8 and got["org"] is None
    assert repo.get("s_zzzzzzzzzz") is None


def test_a_token_is_never_stored(tables: store.Tables) -> None:
    with pytest.raises(StoreError, match="token"):
        SiteRepo(tables.sites).create({**SITE, "token": "abc"})
    assert "token" not in tables.sites.scan()["Items"]


def test_creating_the_same_site_twice_is_refused(tables: store.Tables) -> None:
    repo = SiteRepo(tables.sites)
    repo.create(SITE)
    with pytest.raises(SiteExists):
        repo.create({**SITE, "name": "Other"})
    stored = repo.get("s_abcdefghij")
    assert stored is not None and stored["name"] == "CSE GPU Lab"


def test_scan_all_follows_every_page(tables: store.Tables) -> None:
    repo = SiteRepo(tables.sites)
    for i in range(7):
        repo.create({**SITE, "site_id": f"s_aaaaaaaaa{'abcdefg'[i]}"})
    assert len(repo.scan_all(page_size=2)) == 7
    assert len(repo.scan_all()) == 7


def test_site_delete(tables: store.Tables) -> None:
    repo = SiteRepo(tables.sites)
    repo.create(SITE)
    repo.delete("s_abcdefghij")
    assert repo.get("s_abcdefghij") is None
    repo.delete("s_abcdefghij")  # deleting twice is fine


# plans ---------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine_plan() -> dict[str, Any]:
    req = request(pausable=True, deadline=SUBMIT + timedelta(hours=30))
    result = plan_from_rows(req, diurnal_rows(SUBMIT))
    return {**result, "plan_id": "p_abcdefghij"}


def item_size(item: dict[str, Any]) -> int:
    return len(json.dumps(TypeSerializer().serialize(item), default=str))


def test_plan_round_trip_restores_every_stored_part(
    tables: store.Tables, engine_plan: dict[str, Any]
) -> None:
    repo = PlanRepo(tables.plans)
    repo.put(engine_plan, site_id="s_abcdefghij")
    got = repo.get("p_abcdefghij")
    assert got is not None
    assert got["site_id"] == "s_abcdefghij" and got["submit_ts"] == engine_plan["submit_ts"]
    assert got["pareto"] == engine_plan["pareto"]
    assert got["forecast_snapshot"] == engine_plan["forecast_snapshot"]
    assert got["base"]["gpu_kwh"] == pytest.approx(engine_plan["base"]["gpu_kwh"])
    assert got["best"]["gpu_kwh"] == pytest.approx(engine_plan["best"]["gpu_kwh"])
    assert got["inputs"]["gpu_model"] == engine_plan["inputs"]["gpu_model"]
    assert got["factor_version"] == engine_plan["factor_version"]
    assert got["notes"] == engine_plan["notes"] and got["tags"] == engine_plan["tags"]


def test_plans_stored_before_notes_existed_still_load(
    tables: store.Tables, engine_plan: dict[str, Any]
) -> None:
    PlanRepo(tables.plans).put(engine_plan, site_id=None)
    tables.plans.update_item(
        Key={"plan_id": "p_abcdefghij"}, UpdateExpression="REMOVE notes, tags"
    )
    got = PlanRepo(tables.plans).get("p_abcdefghij")
    assert got is not None and got["notes"] == [] and got["tags"] == {}


def test_a_stored_plan_scores_a_receipt_like_the_original(
    tables: store.Tables, engine_plan: dict[str, Any]
) -> None:
    from engine import score

    PlanRepo(tables.plans).put(engine_plan, site_id=None)
    stored = PlanRepo(tables.plans).get("p_abcdefghij")
    assert stored is not None
    hour = engine_plan["forecast_snapshot"]["slots"][3]
    receipt = {
        "job_id": "j_aaaaaaaaaaaa",
        "end_ts": NOW.isoformat(),
        "method": "nvml_energy",
        "slots": [{"hour": hour, "run_kwh": 0.5, "idle_kwh": 0.0, "level": 0.7}],
    }
    a = score.receipt_footprints(receipt, engine_plan, ())
    b = score.receipt_footprints(receipt, stored, ())
    assert b["capture"] == pytest.approx(a["capture"], abs=1e-6)
    assert b["scoring"]["J"]["actual"] == pytest.approx(a["scoring"]["J"]["actual"], rel=1e-6)


def test_plan_items_are_small_and_compressed(
    tables: store.Tables, engine_plan: dict[str, Any]
) -> None:
    PlanRepo(tables.plans).put(engine_plan, site_id=None)
    item = tables.plans.get_item(Key={"plan_id": "p_abcdefghij"})["Item"]
    assert isinstance(item["pareto_gz"].value, bytes)
    assert isinstance(item["forecast_snapshot_gz"].value, bytes)
    assert "pareto" not in item and "forecast_snapshot" not in item
    assert item_size(item) < 100_000  # the hard DynamoDB limit is 400 KB


def test_plan_ttl_is_submit_plus_fourteen_days(
    tables: store.Tables, engine_plan: dict[str, Any]
) -> None:
    PlanRepo(tables.plans).put(engine_plan, site_id=None)
    item = tables.plans.get_item(Key={"plan_id": "p_abcdefghij"})["Item"]
    submit = ist(2026, 10, 9, 21, 14)
    assert int(item["ttl"]) == int((submit + timedelta(days=14)).timestamp())


def test_missing_plan_is_none(tables: store.Tables) -> None:
    assert PlanRepo(tables.plans).get("p_zzzzzzzzzz") is None


def test_putting_a_plan_without_an_id_is_refused(
    tables: store.Tables, engine_plan: dict[str, Any]
) -> None:
    with pytest.raises(StoreError, match="plan_id"):
        PlanRepo(tables.plans).put({**engine_plan, "plan_id": ""}, site_id=None)


def test_quota_counts_up_to_the_limit_then_refuses(tables: store.Tables) -> None:
    repo = PlanRepo(tables.plans)
    day = ist(2026, 10, 10, 12, 0)
    assert [repo.bump_quota(day, 3) for _ in range(5)] == [True, True, True, False, False]
    assert repo.bump_quota(day + timedelta(days=1), 3) is True  # a new day starts again
    item = tables.plans.get_item(Key={"plan_id": "quota#2026-10-10"})["Item"]
    assert int(item["n"]) == 3
    assert int(item["ttl"]) > int(day.timestamp())


# receipts ------------------------------------------------------------------------------------


def make_receipt(job: str, end: str, site: str = "s_abcdefghij", **extra: Any) -> dict[str, Any]:
    return {
        "site_id": site,
        "job_id": job,
        "end_ts": end,
        "start_ts": end,
        "plan_id": "p_abcdefghij",
        "method": "nvml_energy",
        "kwh": 1.5,
        "capture": 0.8,
        "scored": True,
        "slots": [{"hour": end, "run_kwh": 1.5, "idle_kwh": 0.0, "level": 0.85}],
        **extra,
    }


def test_receipt_round_trip_through_the_guard(tables: store.Tables) -> None:
    repo = ReceiptRepo(tables.receipts)
    receipt = make_receipt("j_aaaaaaaaaaaa", "2026-10-10T08:10:00+05:30")
    repo.put_with_guard(receipt)
    got = repo.get("s_abcdefghij", "j_aaaaaaaaaaaa")
    assert got is not None and got["capture"] == 0.8 and got["slots"][0]["level"] == 0.85
    assert repo.get("s_abcdefghij", "j_bbbbbbbbbbbb") is None
    assert repo.get("s_other00000", "j_aaaaaaaaaaaa") is None


def test_the_sort_key_is_end_ts_hash_job_and_the_guard_points_at_it(tables: store.Tables) -> None:
    repo = ReceiptRepo(tables.receipts)
    repo.put_with_guard(make_receipt("j_aaaaaaaaaaaa", "2026-10-10T08:10:00+05:30"))
    keys = sorted(i["sk"] for i in tables.receipts.scan()["Items"])
    assert keys == ["2026-10-10T08:10:00+05:30#j_aaaaaaaaaaaa", "job#j_aaaaaaaaaaaa"]
    guard = tables.receipts.get_item(Key={"site_id": "s_abcdefghij", "sk": "job#j_aaaaaaaaaaaa"})
    assert guard["Item"]["sk_receipt"] == "2026-10-10T08:10:00+05:30#j_aaaaaaaaaaaa"


def test_a_repeated_job_id_is_refused_and_nothing_extra_is_written(tables: store.Tables) -> None:
    repo = ReceiptRepo(tables.receipts)
    repo.put_with_guard(make_receipt("j_aaaaaaaaaaaa", "2026-10-10T08:10:00+05:30"))
    with pytest.raises(DuplicateJob):
        repo.put_with_guard(make_receipt("j_aaaaaaaaaaaa", "2026-10-10T09:10:00+05:30"))
    assert tables.receipts.scan()["Count"] == 2  # still the one receipt and its guard


def test_the_same_job_id_on_another_site_is_not_a_duplicate(tables: store.Tables) -> None:
    repo = ReceiptRepo(tables.receipts)
    repo.put_with_guard(make_receipt("j_aaaaaaaaaaaa", "2026-10-10T08:10:00+05:30"))
    repo.put_with_guard(
        make_receipt("j_aaaaaaaaaaaa", "2026-10-10T08:10:00+05:30", site="s_other00000")
    )


def test_last_30_days_returns_only_receipts_in_the_window_never_guards(
    tables: store.Tables,
) -> None:
    repo = ReceiptRepo(tables.receipts)
    # the window is now - 30 days < end <= now, the same rule the engine's site score uses
    inside = [
        "2026-10-10T08:10:00+05:30",
        "2026-09-15T08:10:00+05:30",
        "2026-09-10T12:00:01+05:30",
        "2026-10-10T12:00:00+05:30",
    ]
    outside = [
        "2026-09-10T12:00:00+05:30",
        "2026-08-01T00:00:00+05:30",
        "2026-10-10T12:00:01+05:30",
    ]
    for i, end in enumerate(inside + outside):
        repo.put_with_guard(make_receipt(f"j_{'abcdefgh'[i] * 12}", end))
    repo.put_with_guard(
        make_receipt("j_zzzzzzzzzzzz", "2026-10-10T07:00:00+05:30", site="s_other00000")
    )
    got = repo.last_30_days("s_abcdefghij", NOW)
    assert sorted(r["end_ts"] for r in got) == sorted(inside)
    assert all("sk_receipt" not in r for r in got)


def test_the_guard_sorts_after_every_timestamp(tables: store.Tables) -> None:
    # 'j' > '2', so a range query between two ISO timestamps can never return a guard (05.2.b)
    assert "job#j_aaaaaaaaaaaa" > "2999-12-31T23:59:59+05:30~"


def test_last_30_days_follows_pages(tables: store.Tables) -> None:
    repo = ReceiptRepo(tables.receipts)
    for i in range(7):
        repo.put_with_guard(
            make_receipt(f"j_{'abcdefg'[i] * 12}", f"2026-10-0{i + 1}T08:10:00+05:30")
        )
    assert len(repo.last_30_days("s_abcdefghij", NOW, page_size=2)) == 7


@pytest.mark.parametrize(
    "end", ["2026-10-10T08:10:00Z", "2026-10-10T08:10:00", "2026-10-10T08:10+05:30", "x"]
)
def test_only_canonical_end_timestamps_are_accepted(tables: store.Tables, end: str) -> None:
    with pytest.raises(StoreError, match="end_ts"):
        ReceiptRepo(tables.receipts).put_with_guard(make_receipt("j_aaaaaaaaaaaa", end))


def test_delete_site_removes_receipts_and_guards(tables: store.Tables) -> None:
    repo = ReceiptRepo(tables.receipts)
    for i in range(3):
        repo.put_with_guard(make_receipt(f"j_{'abc'[i] * 12}", f"2026-10-0{i + 1}T08:10:00+05:30"))
    repo.put_with_guard(
        make_receipt("j_zzzzzzzzzzzz", "2026-10-05T08:10:00+05:30", site="s_other00000")
    )
    assert repo.delete_site("s_abcdefghij") == 6
    assert repo.last_30_days("s_abcdefghij", NOW) == []
    assert repo.get("s_other00000", "j_zzzzzzzzzzzz") is not None


def test_a_deleted_job_id_can_be_used_again(tables: store.Tables) -> None:
    repo = ReceiptRepo(tables.receipts)
    repo.put_with_guard(make_receipt("j_aaaaaaaaaaaa", "2026-10-10T08:10:00+05:30"))
    repo.delete_site("s_abcdefghij")
    repo.put_with_guard(make_receipt("j_aaaaaaaaaaaa", "2026-10-10T08:10:00+05:30"))


def test_non_finite_receipt_values_are_refused_before_writing(tables: store.Tables) -> None:
    bad = make_receipt("j_aaaaaaaaaaaa", "2026-10-10T08:10:00+05:30", kwh=math.nan)
    with pytest.raises(NonFiniteNumber):
        ReceiptRepo(tables.receipts).put_with_guard(bad)
    assert tables.receipts.scan()["Count"] == 0


def test_get_tables_reads_names_from_the_environment(aws: None) -> None:
    t = store.get_tables()
    assert t.sites.name == "thirst-test-sites" and t.receipts.name == "thirst-test-receipts"
    assert store.get_tables() is t  # one resource per cold start
