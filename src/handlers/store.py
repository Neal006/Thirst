"""DynamoDB repositories (plan 05.3, contract 08 §5).

Rules this module enforces:
  * floats are stored as ``Decimal(repr(x))`` and NaN/Inf are refused before any write;
  * every expression uses ``Key``/``Attr`` helpers or ``ExpressionAttributeNames`` because
    ``ttl``, ``hour``, ``name`` and ``public`` are DynamoDB reserved words;
  * ``receipts`` sort keys are ``<end_ts>#<job_id>`` with ``end_ts`` canonical IST, and a
    ``job#<job_id>`` guard item written in the same transaction makes job ids unique (D12);
  * a site token is never stored (TRD 7.1).
"""

from __future__ import annotations

import functools
import gzip
import json
import logging
import math
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Attr, Key
from boto3.dynamodb.types import Binary
from botocore.exceptions import ClientError

from engine.errors import EngineError
from engine.forecast import WeatherRow
from engine.units import ensure_ist

log = logging.getLogger("thirst.store")

WEATHER_TTL = timedelta(days=10)
PLAN_TTL = timedelta(days=14)
QUOTA_TTL = timedelta(days=3)  # the quota day plus 2 days (D13)
WINDOW_DAYS = 30
_CANONICAL_END = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+05:30")
_TINY = 1e-100  # DynamoDB numbers underflow below about 1e-130: treat smaller as zero
_HUGE = 1e100
_EXACT_INT = 2**53


class StoreError(Exception):
    """A storage problem that is our bug or our data, never the caller's fault."""


class NonFiniteNumber(StoreError, ValueError):
    """NaN or Inf cannot be stored; it means the engine produced a bad number."""


class DuplicateJob(StoreError):
    """The job id was already recorded for this site (API 409)."""


class SiteExists(StoreError):
    """A site with this id already exists."""


# ---------------------------------------------------------------------- table layout


@dataclass(frozen=True, slots=True)
class TableSpec:
    env: str
    hash_key: str
    range_key: str | None = None
    ttl: str | None = None

    def create_args(self) -> dict[str, Any]:
        keys = [self.hash_key] + ([self.range_key] if self.range_key else [])
        return {
            "AttributeDefinitions": [{"AttributeName": k, "AttributeType": "S"} for k in keys],
            "KeySchema": [
                {"AttributeName": k, "KeyType": "HASH" if i == 0 else "RANGE"}
                for i, k in enumerate(keys)
            ],
        }


TABLE_SPECS: Mapping[str, TableSpec] = {
    "weather": TableSpec("TABLE_WEATHER", "city", "hour", "ttl"),
    "sites": TableSpec("TABLE_SITES", "site_id"),
    "plans": TableSpec("TABLE_PLANS", "plan_id", None, "ttl"),
    "receipts": TableSpec("TABLE_RECEIPTS", "site_id", "sk"),
}


@dataclass(frozen=True, slots=True)
class Tables:
    weather: Any
    sites: Any
    plans: Any
    receipts: Any


@functools.lru_cache(maxsize=1)
def get_tables() -> Tables:
    """One boto3 resource per cold start; table names come from the environment."""
    import boto3

    resource = boto3.resource("dynamodb")
    return Tables(**{k: resource.Table(os.environ[s.env]) for k, s in TABLE_SPECS.items()})


# ---------------------------------------------------------------------- number conversion


def to_ddb(value: Any, path: str = "$") -> Any:
    """Plain Python to DynamoDB-safe values. Refuses NaN, Inf and types it cannot store."""
    if value is None or isinstance(value, bool | str | bytes):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float | Decimal):
        number = float(value)
        if not math.isfinite(number):
            raise NonFiniteNumber(f"non-finite number at {path}")
        if abs(number) >= _HUGE:
            raise StoreError(f"number too large at {path}")
        if abs(number) < _TINY:
            return Decimal(0)
        return Decimal(repr(number)) if isinstance(value, float) else value
    if isinstance(value, Mapping):
        for key in value:
            if not isinstance(key, str):
                raise TypeError(f"non-string key {key!r} at {path}")
        return {k: to_ddb(v, f"{path}.{k}") for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [to_ddb(v, f"{path}[{i}]") for i, v in enumerate(value)]
    raise TypeError(f"cannot store {type(value).__name__} at {path}")


def from_ddb(value: Any) -> Any:
    """DynamoDB values back to plain Python: whole Decimals become int, others float.

    Above 2**53 a whole number can only have been a float (its shortest repr is not its exact
    value), so it stays a float and round-trips exactly.
    """
    if isinstance(value, Decimal):
        whole = value == value.to_integral_value() and abs(value) < _EXACT_INT
        return int(value) if whole else float(value)
    if isinstance(value, Binary):
        return bytes(value.value)
    if isinstance(value, Mapping):
        return {k: from_ddb(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [from_ddb(v) for v in value]
    return value


def _query_all(table: Any, page_size: int | None = None, **kwargs: Any) -> list[dict[str, Any]]:
    """Run a query and follow ``LastEvaluatedKey`` until the end."""
    items: list[dict[str, Any]] = []
    if page_size:
        kwargs["Limit"] = page_size
    while True:
        page = table.query(**kwargs)
        items.extend(page["Items"])
        key = page.get("LastEvaluatedKey")
        if not key:
            return items
        kwargs["ExclusiveStartKey"] = key


def _hour_key(hour: datetime) -> str:
    if hour.utcoffset() is None:
        raise StoreError("hour needs a timezone offset")
    ist = ensure_ist(hour)
    if (ist.minute, ist.second, ist.microsecond) != (0, 0, 0):
        raise StoreError("hour must be the start of an hour")
    return ist.isoformat()


# ---------------------------------------------------------------------- weather


@dataclass(frozen=True, slots=True)
class ForecastRow:
    city: str
    hour: datetime
    temp_c: float
    rh_pct: float
    rad_wm2: float
    issued: datetime
    tw: float
    ci: float
    ewif: float
    pue_t_c: float


@dataclass(frozen=True, slots=True)
class Window:
    rows: tuple[WeatherRow, ...]
    issued: datetime | None


def _weather_row(item: Mapping[str, Any]) -> WeatherRow | None:
    """Forecast values when present, else observed ones. Bad stored data is skipped."""
    prefix = "fc" if "fc_temp" in item else "obs" if "obs_temp" in item else None
    if prefix is None:
        return None
    try:
        return WeatherRow(
            hour=datetime.fromisoformat(item["hour"]),
            temp_c=float(item[f"{prefix}_temp"]),
            rh_pct=float(item[f"{prefix}_rh"]),
            rad_wm2=float(item[f"{prefix}_rad"]),
        )
    except (EngineError, KeyError, ValueError, TypeError):
        log.warning("weather_row_skipped city=%s hour=%s", item.get("city"), item.get("hour"))
        return None


class WeatherRepo:
    def __init__(self, table: Any) -> None:
        self._table = table

    @staticmethod
    def _forecast_attrs(row: ForecastRow, ttl: int) -> dict[str, Any]:
        return {
            "fc_temp": row.temp_c,
            "fc_rh": row.rh_pct,
            "fc_rad": row.rad_wm2,
            "fc_issued": ensure_ist(row.issued).isoformat(),
            "tw": row.tw,
            "ci": row.ci,
            "ewif": row.ewif,
            "pue_inputs": {"t_c": row.pue_t_c},
            "ttl": ttl,
        }

    def put_forecast(self, rows: Sequence[ForecastRow], now: datetime) -> None:
        """Write forecast fields. Hours already started are updated in place so that the
        observation fields next to them survive; later hours are plain puts."""
        current = ensure_ist(now).replace(minute=0, second=0, microsecond=0)
        with self._table.batch_writer(overwrite_by_pkeys=["city", "hour"]) as batch:
            for row in rows:
                key = _hour_key(row.hour)
                ttl = int((ensure_ist(row.hour) + WEATHER_TTL).timestamp())
                attrs = self._forecast_attrs(row, ttl)
                if ensure_ist(row.hour) > current:
                    batch.put_item(Item=to_ddb({"city": row.city, "hour": key, **attrs}))
                else:
                    self._update(row.city, key, attrs)

    def _update(self, city: str, hour_key: str, attrs: Mapping[str, Any]) -> None:
        values = to_ddb(dict(attrs))
        self._table.update_item(
            Key={"city": city, "hour": hour_key},
            UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in values),
            ExpressionAttributeNames={f"#{k}": k for k in values},
            ExpressionAttributeValues={f":{k}": v for k, v in values.items()},
        )

    def record_observation(
        self, city: str, hour: datetime, temp_c: float, rh_pct: float, rad_wm2: float
    ) -> None:
        ttl = int((ensure_ist(hour) + WEATHER_TTL).timestamp())
        self._update(
            city,
            _hour_key(hour),
            {"obs_temp": temp_c, "obs_rh": rh_pct, "obs_rad": rad_wm2, "ttl": ttl},
        )

    def window(self, city: str, from_hour: datetime, n: int = 48) -> Window:
        start = ensure_ist(from_hour)
        items = _query_all(
            self._table,
            KeyConditionExpression=Key("city").eq(city)
            & Key("hour").between(start.isoformat(), (start + timedelta(hours=n - 1)).isoformat()),
        )
        rows = [r for r in map(_weather_row, items) if r is not None]
        issued = [datetime.fromisoformat(i["fc_issued"]) for i in items if "fc_issued" in i]
        return Window(tuple(rows), max(issued) if issued else None)

    def observed(self, city: str, hours: Iterable[datetime]) -> list[WeatherRow]:
        wanted = {_hour_key(h) for h in hours}
        if not wanted:
            return []
        items = _query_all(
            self._table,
            KeyConditionExpression=Key("city").eq(city)
            & Key("hour").between(min(wanted), max(wanted)),
            FilterExpression=Attr("obs_temp").exists(),
        )
        rows: list[WeatherRow] = []
        for item in items:
            if item["hour"] not in wanted:
                continue
            try:
                rows.append(
                    WeatherRow(
                        hour=datetime.fromisoformat(item["hour"]),
                        temp_c=float(item["obs_temp"]),
                        rh_pct=float(item["obs_rh"]),
                        rad_wm2=float(item["obs_rad"]),
                    )
                )
            except (EngineError, KeyError, ValueError):
                log.warning("observation_skipped city=%s hour=%s", city, item["hour"])
        return rows


# ---------------------------------------------------------------------- sites


class SiteRepo:
    def __init__(self, table: Any) -> None:
        self._table = table

    def create(self, site: Mapping[str, Any]) -> None:
        if "token" in site:
            raise StoreError("a site token must never be stored")
        try:
            self._table.put_item(
                Item=to_ddb(dict(site)), ConditionExpression=Attr("site_id").not_exists()
            )
        except ClientError as err:
            if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise SiteExists(site.get("site_id", "")) from None
            raise

    def get(self, site_id: str) -> dict[str, Any] | None:
        item = self._table.get_item(Key={"site_id": site_id}).get("Item")
        return None if item is None else dict(from_ddb(item))

    def scan_all(self, page_size: int | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {"Limit": page_size} if page_size else {}
        while True:
            page = self._table.scan(**kwargs)
            items.extend(dict(from_ddb(i)) for i in page["Items"])
            if not page.get("LastEvaluatedKey"):
                return items
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def delete(self, site_id: str) -> None:
        self._table.delete_item(Key={"site_id": site_id})


# ---------------------------------------------------------------------- plans


def _gz(value: Any) -> bytes:
    try:
        text = json.dumps(value, separators=(",", ":"), allow_nan=False)
    except ValueError:
        raise NonFiniteNumber("non-finite number in a compressed plan part") from None
    return gzip.compress(text.encode("utf-8"), mtime=0)


def _gunzip(value: Any) -> Any:
    data = value.value if isinstance(value, Binary) else value
    return json.loads(gzip.decompress(bytes(data)))


class PlanRepo:
    def __init__(self, table: Any) -> None:
        self._table = table

    def put(self, plan: Mapping[str, Any], site_id: str | None) -> None:
        plan_id = plan.get("plan_id")
        if not isinstance(plan_id, str) or not plan_id:
            raise StoreError("plan_id is required")
        submit = ensure_ist(datetime.fromisoformat(plan["submit_ts"]))
        item: dict[str, Any] = {
            "plan_id": plan_id,
            "submit_ts": plan["submit_ts"],
            "inputs": plan["inputs"],
            "base": plan["base"],
            "best": plan["best"],
            "notes": plan.get("notes", []),
            "tags": plan.get("tags", {}),
            "factor_version": plan["factor_version"],
            "ttl": int((submit + PLAN_TTL).timestamp()),
        }
        if site_id is not None:
            item["site_id"] = site_id
        stored = to_ddb(item)
        stored["pareto_gz"] = _gz(plan["pareto"])
        stored["forecast_snapshot_gz"] = _gz(plan["forecast_snapshot"])
        self._table.put_item(Item=stored)

    def get(self, plan_id: str) -> dict[str, Any] | None:
        item = self._table.get_item(Key={"plan_id": plan_id}).get("Item")
        if item is None:
            return None
        out = dict(from_ddb({k: v for k, v in item.items() if not k.endswith("_gz")}))
        out.setdefault("notes", [])  # plans stored before notes and tags were kept
        out.setdefault("tags", {})
        out["pareto"] = _gunzip(item["pareto_gz"])
        out["forecast_snapshot"] = _gunzip(item["forecast_snapshot_gz"])
        return out

    def bump_quota(self, day: datetime, limit: int) -> bool:
        """Count one use for the IST day. False once ``limit`` uses are spent (D13)."""
        start = ensure_ist(day).replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            self._table.update_item(
                Key={"plan_id": f"quota#{start:%Y-%m-%d}"},
                UpdateExpression="SET #ttl = :ttl ADD #n :one",
                ConditionExpression="attribute_not_exists(#n) OR #n < :limit",
                ExpressionAttributeNames={"#n": "n", "#ttl": "ttl"},
                ExpressionAttributeValues={
                    ":one": 1,
                    ":limit": limit,
                    ":ttl": int((start + QUOTA_TTL).timestamp()),
                },
            )
        except ClientError as err:
            if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
        return True


# ---------------------------------------------------------------------- receipts


def _guard_key(job_id: str) -> str:
    return f"job#{job_id}"


class ReceiptRepo:
    def __init__(self, table: Any) -> None:
        self._table = table

    def put_with_guard(self, receipt: Mapping[str, Any]) -> None:
        """Write the receipt and its job guard in one transaction (D12)."""
        end_ts, site_id, job_id = receipt.get("end_ts"), receipt["site_id"], receipt["job_id"]
        if not isinstance(end_ts, str) or not _CANONICAL_END.fullmatch(end_ts):
            raise StoreError("end_ts must be canonical IST like 2026-10-10T08:10:00+05:30")
        sort_key = f"{end_ts}#{job_id}"
        # Convert first so that a NaN raises before anything is written.
        item = to_ddb({**receipt, "sk": sort_key})
        guard = to_ddb(
            {
                "site_id": site_id,
                "sk": _guard_key(job_id),
                "sk_receipt": sort_key,
                "created_at": receipt.get("created_at"),
            }
        )
        table_name = self._table.name
        try:
            self._table.meta.client.transact_write_items(
                TransactItems=[
                    {
                        "Put": {
                            "TableName": table_name,
                            "Item": guard,
                            "ConditionExpression": "attribute_not_exists(#sk)",
                            "ExpressionAttributeNames": {"#sk": "sk"},
                        }
                    },
                    {"Put": {"TableName": table_name, "Item": item}},
                ]
            )
        except ClientError as err:
            reasons = err.response.get("CancellationReasons") or []
            if any(r.get("Code") == "ConditionalCheckFailed" for r in reasons):
                raise DuplicateJob(job_id) from None
            raise

    def get(self, site_id: str, job_id: str) -> dict[str, Any] | None:
        key = {"site_id": site_id, "sk": _guard_key(job_id)}
        guard = self._table.get_item(Key=key).get("Item")
        if guard is None:
            return None
        found = self._table.get_item(Key={"site_id": site_id, "sk": guard["sk_receipt"]})
        item = found.get("Item")
        return None if item is None else dict(from_ddb(item))

    def last_30_days(
        self, site_id: str, now: datetime, page_size: int | None = None
    ) -> list[dict[str, Any]]:
        """Receipts with ``now - 30 days < end_ts <= now``; guard items never match."""
        end = ensure_ist(now)
        lo = end - timedelta(days=WINDOW_DAYS)
        items = _query_all(
            self._table,
            page_size,
            KeyConditionExpression=Key("site_id").eq(site_id)
            & Key("sk").between(lo.isoformat(), end.isoformat() + "~"),
        )
        receipts = [dict(from_ddb(i)) for i in items if not i["sk"].startswith("job#")]
        return [r for r in receipts if lo < ensure_ist(datetime.fromisoformat(r["end_ts"])) <= end]

    def delete_site(self, site_id: str) -> int:
        """Remove every receipt and guard of a site. Returns how many items were deleted."""
        items = _query_all(self._table, KeyConditionExpression=Key("site_id").eq(site_id))
        with self._table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"site_id": item["site_id"], "sk": item["sk"]})
        return len(items)
