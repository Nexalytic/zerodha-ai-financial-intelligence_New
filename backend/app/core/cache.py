import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Coroutine, Dict, Generic, Optional, Tuple, TypeVar

T = TypeVar("T")

@dataclass
class CacheEntry(Generic[T]):
    value: T
    cached_at: datetime
    expires_at: datetime
    ttl_seconds: float

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def remaining_ttl(self) -> float:
        remaining = (self.expires_at - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, remaining)

class AsyncTTLCache:
    """
    Thread-safe and coroutine-safe in-memory async TTL cache.
    Guarantees concurrency safety using asyncio.Lock and per-key coalescing locks
    to prevent stampedes and race conditions.
    """

    def __init__(self, default_ttl_seconds: float = 60.0):
        self._default_ttl = float(default_ttl_seconds)
        self._store: Dict[str, CacheEntry] = {}
        self._global_lock = asyncio.Lock()
        self._key_locks: Dict[str, asyncio.Lock] = {}

    def _get_key_lock(self, key: str) -> asyncio.Lock:
        if key not in self._key_locks:
            self._key_locks[key] = asyncio.Lock()
        return self._key_locks[key]

    async def get(self, key: str) -> Tuple[Optional[Any], bool, Optional[datetime], Optional[float]]:
        """
        Retrieves a valid non-expired item from the cache.
        Returns: (value, is_hit, cached_at, ttl_remaining_seconds)
        """
        async with self._global_lock:
            entry = self._store.get(key)
            if entry is not None and not entry.is_expired:
                return entry.value, True, entry.cached_at, entry.remaining_ttl
            return None, False, None, None

    async def get_stale(self, key: str) -> Tuple[Optional[Any], Optional[datetime]]:
        """
        Retrieves an entry regardless of expiration status, preserving its original timestamp.
        Used solely for emergency stale-data fallbacks during provider outages.
        Returns: (value, cached_at)
        """
        async with self._global_lock:
            entry = self._store.get(key)
            if entry is not None:
                return entry.value, entry.cached_at
            return None, None

    async def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        """
        Stores an item in the cache with the specified TTL.
        """
        effective_ttl = float(ttl_seconds) if ttl_seconds is not None else self._default_ttl
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=effective_ttl)
        entry = CacheEntry(
            value=value,
            cached_at=now,
            expires_at=expires_at,
            ttl_seconds=effective_ttl,
        )
        async with self._global_lock:
            self._store[key] = entry

    async def invalidate(self, key: str) -> bool:
        """
        Evicts a specific key from the cache.
        """
        async with self._global_lock:
            return self._store.pop(key, None) is not None

    async def clear(self) -> None:
        """
        Clears the entire cache store and locks.
        """
        async with self._global_lock:
            self._store.clear()
            self._key_locks.clear()

    async def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Coroutine[Any, Any, T]],
        ttl_seconds: Optional[float] = None,
    ) -> Tuple[T, bool, datetime, Optional[float]]:
        """
        Coalescing fetch: checks cache, and if expired or missing, executes compute_fn
        under a per-key lock so concurrent requests for the same key share the computed result.
        Returns: (value, is_cache_hit, cached_at, ttl_remaining_seconds)
        """
        # 1. Fast path: check valid cache under global lock
        async with self._global_lock:
            entry = self._store.get(key)
            if entry is not None and not entry.is_expired:
                return entry.value, True, entry.cached_at, entry.remaining_ttl
            key_lock = self._get_key_lock(key)

        # 2. Acquire key lock to serialize in-flight requests for the same key
        async with key_lock:
            # Re-check in case another coroutine computed while we waited
            async with self._global_lock:
                entry = self._store.get(key)
                if entry is not None and not entry.is_expired:
                    return entry.value, True, entry.cached_at, entry.remaining_ttl

            # 3. Compute outside global lock
            computed_value = await compute_fn()

            # 4. Store result
            effective_ttl = float(ttl_seconds) if ttl_seconds is not None else self._default_ttl
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=effective_ttl)
            new_entry = CacheEntry(
                value=computed_value,
                cached_at=now,
                expires_at=expires_at,
                ttl_seconds=effective_ttl,
            )
            async with self._global_lock:
                self._store[key] = new_entry

            return computed_value, False, now, effective_ttl
