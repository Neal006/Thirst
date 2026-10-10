"""A tiny bounded in-memory cache for one Lambda instance (plan 05.6.c, 05.8).

Each warm instance keeps its own copy, so the time-to-live is the worst-case staleness.
The caller passes the clock in, which keeps the class free of hidden time and easy to test.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Hashable
from datetime import datetime
from typing import Any

DEFAULT_MAX_ENTRIES = 256


class TtlCache:
    def __init__(self, ttl_seconds: float, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._items: OrderedDict[Hashable, tuple[datetime, Any]] = OrderedDict()

    def get(self, key: Hashable, now: datetime) -> Any | None:
        """The cached value, or None when missing, expired, or stored in the future."""
        entry = self._items.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        age = (now - stored_at).total_seconds()
        if age < 0 or age >= self._ttl:
            del self._items[key]
            return None
        return value

    def put(self, key: Hashable, value: Any, now: datetime) -> None:
        self._items[key] = (now, value)
        self._items.move_to_end(key)
        while len(self._items) > self._max:
            self._items.popitem(last=False)

    def invalidate(self, key: Hashable) -> None:
        self._items.pop(key, None)

    def clear(self) -> None:
        self._items.clear()
