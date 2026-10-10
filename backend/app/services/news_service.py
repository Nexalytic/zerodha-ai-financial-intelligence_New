from datetime import datetime, timezone
from typing import List, Optional
from app.core.cache import AsyncTTLCache
from app.core.logging import logger
from app.providers.base import BaseNewsProvider
from app.providers.demo_news import DemoNewsProvider
from app.schemas.market_data import NewsArticle, NewsResponse

class NewsService:
    """
    Simulated news orchestration service with async TTL caching and error resilience.
    """

    def __init__(
        self,
        provider: Optional[BaseNewsProvider] = None,
        cache: Optional[AsyncTTLCache] = None,
        default_ttl_seconds: float = 300.0,
    ):
        self.provider = provider or DemoNewsProvider()
        self.cache = cache or AsyncTTLCache(default_ttl_seconds=default_ttl_seconds)
        self.default_ttl = float(default_ttl_seconds)

    def _make_symbols_key(self, symbols: List[str], limit: int) -> str:
        sorted_syms = ",".join(sorted(s.strip().upper() for s in symbols if s.strip()))
        return f"news:symbols:{sorted_syms}:{limit}"

    def _make_market_key(self, limit: int) -> str:
        return f"news:market:{limit}"

    async def get_news_for_symbols(self, symbols: List[str], limit: int = 10) -> NewsResponse:
        key = self._make_symbols_key(symbols, limit)

        # 1. Check cache
        cached_articles, is_hit, _, _ = await self.cache.get(key)
        if is_hit and cached_articles is not None:
            return NewsResponse(
                articles=cached_articles,
                total_count=len(cached_articles),
                fetched_at=datetime.now(timezone.utc),
                cache_hit=True,
                is_simulated=True,
            )

        # 2. Acquire key lock
        key_lock = self.cache._get_key_lock(key)
        async with key_lock:
            # Re-check cache
            cached_articles, is_hit, _, _ = await self.cache.get(key)
            if is_hit and cached_articles is not None:
                return NewsResponse(
                    articles=cached_articles,
                    total_count=len(cached_articles),
                    fetched_at=datetime.now(timezone.utc),
                    cache_hit=True,
                    is_simulated=True,
                )

            # 3. Query provider with resilience
            try:
                articles = await self.provider.get_news_for_symbols(symbols=symbols, limit=limit)
            except Exception as exc:
                logger.error(f"News provider failed: {exc}", exc_info=True)
                stale_articles, _ = await self.cache.get_stale(key)
                if stale_articles is not None:
                    return NewsResponse(
                        articles=stale_articles,
                        total_count=len(stale_articles),
                        fetched_at=datetime.now(timezone.utc),
                        cache_hit=False,  # Stale data is not a fresh cache hit
                        is_simulated=True,
                    )
                return NewsResponse(
                    articles=[],
                    total_count=0,
                    fetched_at=datetime.now(timezone.utc),
                    cache_hit=False,
                    is_simulated=True,
                )

            # 4. Cache and return
            await self.cache.set(key, articles, ttl_seconds=self.default_ttl)
            return NewsResponse(
                articles=articles,
                total_count=len(articles),
                fetched_at=datetime.now(timezone.utc),
                cache_hit=False,
                is_simulated=True,
            )

    async def get_market_news(self, limit: int = 10) -> NewsResponse:
        key = self._make_market_key(limit)

        cached_articles, is_hit, _, _ = await self.cache.get(key)
        if is_hit and cached_articles is not None:
            return NewsResponse(
                articles=cached_articles,
                total_count=len(cached_articles),
                fetched_at=datetime.now(timezone.utc),
                cache_hit=True,
                is_simulated=True,
            )

        key_lock = self.cache._get_key_lock(key)
        async with key_lock:
            cached_articles, is_hit, _, _ = await self.cache.get(key)
            if is_hit and cached_articles is not None:
                return NewsResponse(
                    articles=cached_articles,
                    total_count=len(cached_articles),
                    fetched_at=datetime.now(timezone.utc),
                    cache_hit=True,
                    is_simulated=True,
                )

            try:
                articles = await self.provider.get_market_news(limit=limit)
            except Exception as exc:
                logger.error(f"News provider market fetch failed: {exc}", exc_info=True)
                stale_articles, _ = await self.cache.get_stale(key)
                if stale_articles is not None:
                    return NewsResponse(
                        articles=stale_articles,
                        total_count=len(stale_articles),
                        fetched_at=datetime.now(timezone.utc),
                        cache_hit=False,
                        is_simulated=True,
                    )
                return NewsResponse(
                    articles=[],
                    total_count=0,
                    fetched_at=datetime.now(timezone.utc),
                    cache_hit=False,
                    is_simulated=True,
                )

            await self.cache.set(key, articles, ttl_seconds=self.default_ttl)
            return NewsResponse(
                articles=articles,
                total_count=len(articles),
                fetched_at=datetime.now(timezone.utc),
                cache_hit=False,
                is_simulated=True,
            )
