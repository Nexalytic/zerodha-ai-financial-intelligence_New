import asyncio
from datetime import datetime, timezone
import pytest
from app.core.cache import AsyncTTLCache

@pytest.mark.asyncio
async def test_cache_set_and_get():
    """Verifies basic setting and retrieval of cache entries."""
    cache = AsyncTTLCache(default_ttl_seconds=10.0)
    await cache.set("test_key", {"data": 123}, ttl_seconds=5.0)

    val, hit, cached_at, ttl_rem = await cache.get("test_key")
    assert hit is True
    assert val == {"data": 123}
    assert cached_at is not None
    assert 0 < ttl_rem <= 5.0

@pytest.mark.asyncio
async def test_cache_miss_and_expiration():
    """Verifies that missing and expired keys return cache miss."""
    cache = AsyncTTLCache(default_ttl_seconds=0.05)  # 50ms TTL

    # Missing key
    val, hit, _, _ = await cache.get("missing_key")
    assert hit is False
    assert val is None

    # Expiration
    await cache.set("exp_key", "exp_value", ttl_seconds=0.05)
    val_immediate, hit_immediate, _, _ = await cache.get("exp_key")
    assert hit_immediate is True
    assert val_immediate == "exp_value"

    await asyncio.sleep(0.06)
    val_after, hit_after, _, _ = await cache.get("exp_key")
    assert hit_after is False
    assert val_after is None

@pytest.mark.asyncio
async def test_cache_stale_retrieval_preserves_timestamp():
    """Verifies that get_stale retrieves expired entries with original timestamp."""
    cache = AsyncTTLCache(default_ttl_seconds=0.05)
    await cache.set("stale_key", "historical_data", ttl_seconds=0.05)

    _, orig_cached_at = await cache.get_stale("stale_key")
    assert orig_cached_at is not None

    await asyncio.sleep(0.06)
    # Standard get misses
    _, hit, _, _ = await cache.get("stale_key")
    assert hit is False

    # Stale get returns value and original cached_at
    stale_val, preserved_time = await cache.get_stale("stale_key")
    assert stale_val == "historical_data"
    assert preserved_time == orig_cached_at

@pytest.mark.asyncio
async def test_cache_invalidation():
    """Verifies explicit cache invalidation removes key."""
    cache = AsyncTTLCache(default_ttl_seconds=10.0)
    await cache.set("inv_key", "val")

    assert await cache.invalidate("inv_key") is True
    assert await cache.invalidate("inv_key") is False

    val, hit, _, _ = await cache.get("inv_key")
    assert hit is False
    assert val is None

@pytest.mark.asyncio
async def test_cache_concurrent_safe_coalescing():
    """
    Verifies that simultaneous concurrent requests for the same key
    are safely serialized under the key lock so that compute_fn
    runs exactly once (thundering herd / stampede prevention).
    """
    cache = AsyncTTLCache(default_ttl_seconds=10.0)
    execution_counter = 0

    async def expensive_computation():
        nonlocal execution_counter
        execution_counter += 1
        await asyncio.sleep(0.02)  # Simulate small async I/O
        return {"computed": 999}

    async def worker():
        val, is_hit, cached_at, rem = await cache.get_or_compute(
            "concurrent_key", expensive_computation, ttl_seconds=5.0
        )
        return val

    # Launch 20 concurrent tasks simultaneously
    results = await asyncio.gather(*(worker() for _ in range(20)))

    # Verify every caller received the correct value
    assert len(results) == 20
    for res in results:
        assert res == {"computed": 999}

    # Verify compute_fn was executed only once
    assert execution_counter == 1
