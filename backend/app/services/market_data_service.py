from datetime import datetime, timezone
from typing import Any, List, Optional
from app.core.cache import AsyncTTLCache
from app.core.config import settings
from app.core.logging import logger, sanitize_log_message
from app.providers.base import BaseMarketDataProvider
from app.providers.demo_market_data import DemoMarketDataProvider
from app.schemas.market_data import BatchQuotesResponse, Quote, QuoteStatus


def resolve_market_data_provider(settings_override: Optional[Any] = None) -> BaseMarketDataProvider:
    """
    Resolves market data provider based on application configuration.
    Strictly honors zero-cost policy:
    - If USE_MOCK_DATA is True or MARKET_DATA_PROVIDER is 'demo', DemoMarketDataProvider is used.
    - Only when USE_MOCK_DATA is False and MARKET_DATA_PROVIDER is 'alphavantage'
      is AlphaVantageMarketDataProvider selected.
    """
    from app.core import config as config_module

    cfg = settings_override or getattr(config_module, "settings", settings)
    if cfg.USE_MOCK_DATA:
        return DemoMarketDataProvider()

    provider_name = (cfg.MARKET_DATA_PROVIDER or "demo").strip().lower()
    if provider_name in ("alphavantage", "alpha_vantage"):
        from app.providers.alpha_vantage_market_data import AlphaVantageMarketDataProvider

        return AlphaVantageMarketDataProvider(
            api_key=cfg.ALPHA_VANTAGE_API_KEY,
            base_url=cfg.ALPHA_VANTAGE_BASE_URL,
        )

    return DemoMarketDataProvider()


class MarketDataService:
    """
    Market data orchestration service with concurrency-safe async TTL caching,
    stale data fallback preservation, and graceful provider failure handling.
    """

    def __init__(
        self,
        provider: Optional[BaseMarketDataProvider] = None,
        cache: Optional[AsyncTTLCache] = None,
        default_ttl_seconds: float = 60.0,
    ):
        self.provider = provider or resolve_market_data_provider()
        self.cache = cache or AsyncTTLCache(default_ttl_seconds=default_ttl_seconds)
        self.default_ttl = float(default_ttl_seconds)


    def _make_cache_key(self, symbol: str, exchange: str) -> str:
        return f"quote:{exchange.strip().upper()}:{symbol.strip().upper()}"

    async def get_quote(self, symbol: str, exchange: str = "NSE") -> Quote:
        """
        Retrieves quote for a single symbol with strict caching rules:
        - Fresh cache hit returns cache_hit=True and TTL countdown.
        - Cache miss queries provider; errors are NEVER cached.
        - On provider failure, falls back to stale cache if present (marked is_stale=True, cache_hit=False).
        - If no stale cache exists on error, returns status=ERROR with current_price=None.
        """
        norm_sym = symbol.strip().upper()
        norm_ex = exchange.strip().upper()
        key = self._make_cache_key(norm_sym, norm_ex)

        # 1. Check fresh cache
        cached_quote, is_hit, cached_at, ttl_remaining = await self.cache.get(key)
        if is_hit and cached_quote is not None:
            return cached_quote.model_copy(
                update={
                    "cache_hit": True,
                    "cached_at": cached_at,
                    "ttl_remaining_seconds": round(ttl_remaining, 2) if ttl_remaining else 0.0,
                    "is_stale": False,
                }
            )

        # 2. Acquire key-level lock to prevent stampede on missing/expired keys
        key_lock = self.cache._get_key_lock(key)
        async with key_lock:
            # Re-check in case another request resolved it while waiting
            cached_quote, is_hit, cached_at, ttl_remaining = await self.cache.get(key)
            if is_hit and cached_quote is not None:
                return cached_quote.model_copy(
                    update={
                        "cache_hit": True,
                        "cached_at": cached_at,
                        "ttl_remaining_seconds": round(ttl_remaining, 2) if ttl_remaining else 0.0,
                        "is_stale": False,
                    }
                )

            # 3. Query provider with error resilience
            try:
                fresh_quote = await self.provider.get_quote(symbol=norm_sym, exchange=norm_ex)
            except Exception as exc:
                sanitized_exc = sanitize_log_message(str(exc))
                logger.error(
                    f"Market data provider failed for {norm_sym} ({norm_ex}): {sanitized_exc}"
                )
                # Check for emergency stale cache fallback
                stale_quote, orig_cached_at = await self.cache.get_stale(key)
                if stale_quote is not None:
                    # Return stale quote preserving original timestamps
                    return stale_quote.model_copy(
                        update={
                            "is_stale": True,
                            "cache_hit": False,  # Stale data is NOT a fresh cache hit
                            "cached_at": orig_cached_at,
                            "ttl_remaining_seconds": 0.0,
                            "explanation": "Provider failed. Serving stale cached quote.",
                        }
                    )

                # No stale data exists: return explicit error quote with null price
                now = datetime.now(timezone.utc)
                is_simulated = (
                    getattr(self.provider, "IS_SIMULATED", False)
                    if hasattr(self.provider, "IS_SIMULATED")
                    else getattr(self.provider, "is_simulated", True)
                )
                return Quote(
                    symbol=norm_sym,
                    exchange=norm_ex,
                    current_price=None,
                    change=None,
                    change_percent=None,
                    status=QuoteStatus.ERROR,
                    is_simulated=is_simulated,
                    source=getattr(self.provider, "PROVIDER_NAME", "SIMULATED_DEMO_PROVIDER"),
                    generated_at=now,
                    market_as_of=None,
                    cached_at=None,
                    cache_hit=False,
                    is_stale=False,
                    explanation="Market data provider failed. Price unavailable.",
                )

            # 4. Error response from provider: do NOT cache errors, fallback to stale cache if present
            if fresh_quote.status == QuoteStatus.ERROR:
                stale_quote, orig_cached_at = await self.cache.get_stale(key)
                if stale_quote is not None:
                    return stale_quote.model_copy(
                        update={
                            "is_stale": True,
                            "cache_hit": False,
                            "cached_at": orig_cached_at,
                            "ttl_remaining_seconds": 0.0,
                            "explanation": f"Provider error: {fresh_quote.explanation or 'Price unavailable'}. Serving stale cached quote.",
                        }
                    )
                return fresh_quote.model_copy(
                    update={
                        "cache_hit": False,
                        "is_stale": False,
                    }
                )

            # 5. Success: store in cache and return
            await self.cache.set(key, fresh_quote, ttl_seconds=self.default_ttl)
            return fresh_quote.model_copy(
                update={
                    "cache_hit": False,
                    "is_stale": fresh_quote.is_stale,
                }
            )

    async def get_quotes(self, symbols: List[str], exchange: str = "NSE") -> BatchQuotesResponse:
        """
        Retrieves quotes for multiple symbols, accurately calculating per-quote
        and aggregate cache hit metrics.
        """
        norm_ex = exchange.strip().upper()
        quotes = {}
        for sym in symbols:
            cleaned = sym.strip().upper()
            if cleaned:
                quotes[cleaned] = await self.get_quote(cleaned, exchange=norm_ex)

        # Count fresh valid cache hits only (stale and errors must NOT count as cache hits)
        cache_hits_count = sum(
            1 for q in quotes.values()
            if q.cache_hit and not q.is_stale and q.status != QuoteStatus.ERROR
        )
        cache_misses_count = len(quotes) - cache_hits_count

        return BatchQuotesResponse(
            quotes=quotes,
            total_symbols=len(quotes),
            cache_hits_count=cache_hits_count,
            cache_misses_count=cache_misses_count,
            fetched_at=datetime.now(timezone.utc),
        )
