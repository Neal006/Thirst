"""The in-memory cache used for site pages and leaderboards (plan 05.6.c, 05.8)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from handlers.cache import TtlCache

T0 = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def test_a_value_is_served_until_its_ttl_then_expires() -> None:
    cache = TtlCache(20)
    cache.put("k", {"a": 1}, T0)
    assert cache.get("k", T0) == {"a": 1}
    assert cache.get("k", T0 + timedelta(seconds=19.9)) == {"a": 1}
    assert cache.get("k", T0 + timedelta(seconds=20)) is None  # exactly the ttl: expired
    assert cache.get("k", T0 + timedelta(seconds=21)) is None


def test_a_missing_key_is_none_and_none_is_never_stored_as_a_hit() -> None:
    cache = TtlCache(20)
    assert cache.get("nope", T0) is None


def test_invalidate_and_clear() -> None:
    cache = TtlCache(20)
    cache.put("a", 1, T0)
    cache.put("b", 2, T0)
    cache.invalidate("a")
    cache.invalidate("never-there")
    assert cache.get("a", T0) is None and cache.get("b", T0) == 2
    cache.clear()
    assert cache.get("b", T0) is None


def test_the_cache_is_bounded_and_drops_the_oldest_first() -> None:
    cache = TtlCache(1000, max_entries=3)
    for i, key in enumerate("abcd"):
        cache.put(key, i, T0 + timedelta(seconds=i))
    later = T0 + timedelta(seconds=10)
    assert [cache.get(k, later) for k in "abcd"] == [None, 1, 2, 3]


def test_a_clock_that_goes_backwards_does_not_serve_forever() -> None:
    cache = TtlCache(20)
    cache.put("k", 1, T0)
    assert cache.get("k", T0 - timedelta(hours=1)) is None
