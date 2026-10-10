import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient
from app.core.cache import AsyncTTLCache
from app.providers.base import BaseMarketDataProvider
from app.providers.demo_market_data import DemoMarketDataProvider
from app.schemas.market_data import Quote, QuoteStatus
from app.services.market_data_service import MarketDataService

class FailingMarketDataProvider(BaseMarketDataProvider):
    """Mock provider that always raises an exception to test failure resilience."""

    async def get_quote(self, symbol: str, exchange: str = "NSE") -> Quote:
        raise RuntimeError("Simulated network connection failure to market provider")

    async def get_quotes(self, symbols: list[str], exchange: str = "NSE") -> dict[str, Quote]:
        raise RuntimeError("Simulated network connection failure to market provider")

@pytest.mark.asyncio
async def test_service_single_quote_caching():
    """
    Verifies that the first call is a cache miss and subsequent call is a cache hit
    with updated cache_hit=True, cached_at, and ttl_remaining_seconds.
    """
    cache = AsyncTTLCache(default_ttl_seconds=10.0)
    service = MarketDataService(cache=cache, default_ttl_seconds=10.0)

    # First fetch (cache miss)
    quote_1 = await service.get_quote("RELIANCE", "NSE")
    assert quote_1.cache_hit is False
    assert quote_1.current_price == Decimal("2850.50")
    assert quote_1.is_stale is False

    # Second fetch (fresh cache hit)
    quote_2 = await service.get_quote("RELIANCE", "NSE")
    assert quote_2.cache_hit is True
    assert quote_2.current_price == Decimal("2850.50")
    assert quote_2.cached_at is not None
    assert quote_2.ttl_remaining_seconds > 0.0
    assert quote_2.is_stale is False

@pytest.mark.asyncio
async def test_service_mixed_batch_cache_hit_counting():
    """
    Verifies that batch requests accurately compute cache_hits_count and
    cache_misses_count across mixed cached and uncached symbols.
    """
    cache = AsyncTTLCache(default_ttl_seconds=10.0)
    service = MarketDataService(cache=cache, default_ttl_seconds=10.0)

    # Pre-cache RELIANCE
    await service.get_quote("RELIANCE", "NSE")

    # Fetch batch of RELIANCE (cached) and TCS (uncached)
    batch = await service.get_quotes(["RELIANCE", "TCS"], "NSE")

    assert batch.total_symbols == 2
    assert batch.cache_hits_count == 1
    assert batch.cache_misses_count == 1
    assert batch.quotes["RELIANCE"].cache_hit is True
    assert batch.quotes["TCS"].cache_hit is False

@pytest.mark.asyncio
async def test_service_provider_failure_not_cached_as_success():
    """
    Verifies that provider failures:
    1. Do not raise unhandled 500 exceptions.
    2. Return a Quote with status=ERROR, current_price=None, and is_stale=False.
    3. Are NEVER cached as valid success entries.
    """
    cache = AsyncTTLCache(default_ttl_seconds=10.0)
    failing_provider = FailingMarketDataProvider()
    service = MarketDataService(provider=failing_provider, cache=cache)

    quote = await service.get_quote("INFY", "NSE")

    assert quote.status == QuoteStatus.ERROR
    assert quote.current_price is None
    assert quote.cache_hit is False
    assert quote.is_stale is False
    assert "provider failed" in quote.explanation.lower()

    # Verify nothing was saved to cache
    cached_val, is_hit, _, _ = await cache.get("quote:NSE:INFY")
    assert is_hit is False
    assert cached_val is None

@pytest.mark.asyncio
async def test_service_stale_fallback_preserves_original_timestamps():
    """
    Verifies that if a provider fails after a quote was previously cached and expired:
    1. The service returns the stale quote with is_stale=True.
    2. cache_hit is False (not counted as a fresh cache hit).
    3. Original generated_at and cached_at timestamps are preserved intact.
    4. In a batch query, stale fallback counts as a cache miss (requirement 3).
    """
    cache = AsyncTTLCache(default_ttl_seconds=0.05)  # 50ms TTL
    healthy_provider = DemoMarketDataProvider()

    # Step 1: Pre-populate cache using healthy provider
    service_healthy = MarketDataService(provider=healthy_provider, cache=cache, default_ttl_seconds=0.05)
    orig_quote = await service_healthy.get_quote("TCS", "NSE")
    assert orig_quote.current_price == Decimal("3920.00")
    orig_generated_at = orig_quote.generated_at

    # Wait for TTL to expire
    await asyncio.sleep(0.06)

    # Step 2: Now query using a service attached to failing provider but sharing same cache
    failing_service = MarketDataService(
        provider=FailingMarketDataProvider(), cache=cache, default_ttl_seconds=0.05
    )
    fallback_quote = await failing_service.get_quote("TCS", "NSE")

    # Verifications
    assert fallback_quote.current_price == Decimal("3920.00")
    assert fallback_quote.is_stale is True
    assert fallback_quote.cache_hit is False  # Must NOT be counted as fresh cache hit
    assert fallback_quote.generated_at == orig_generated_at  # Timestamp preserved
    assert fallback_quote.cached_at is not None  # Preserved

    # Batch verification: stale quotes must NOT be counted as cache hits
    batch = await failing_service.get_quotes(["TCS"], "NSE")
    assert batch.cache_hits_count == 0
    assert batch.cache_misses_count == 1
    assert batch.quotes["TCS"].is_stale is True

@pytest.mark.asyncio
async def test_market_data_api_single_quote(client: AsyncClient):
    """Verifies GET /api/v1/market-data/quote endpoint."""
    response = await client.get("/api/v1/market-data/quote?symbol=RELIANCE&exchange=NSE")
    assert response.status_code == 200

    data = response.json()
    assert data["symbol"] == "RELIANCE"
    assert data["exchange"] == "NSE"
    assert data["current_price"] == "2850.50"
    assert data["status"] == "AVAILABLE"
    assert data["is_simulated"] is True
    assert data["market_as_of"] is None
    assert "Simulated market quote" in data["disclaimer"]

@pytest.mark.asyncio
async def test_market_data_api_unknown_symbol(client: AsyncClient):
    """Verifies unknown symbol returns 200 with current_price=null and UNAVAILABLE status."""
    response = await client.get("/api/v1/market-data/quote?symbol=XYZ_UNKNOWN&exchange=NSE")
    assert response.status_code == 200

    data = response.json()
    assert data["symbol"] == "XYZ_UNKNOWN"
    assert data["current_price"] is None
    assert data["status"] == "UNAVAILABLE"
    assert data["is_simulated"] is True
    assert data["market_as_of"] is None
    assert "not found in demo market universe" in data["explanation"]

@pytest.mark.asyncio
async def test_market_data_api_batch_quotes(client: AsyncClient):
    """Verifies GET /api/v1/market-data/quotes batch endpoint."""
    response = await client.get("/api/v1/market-data/quotes?symbols=RELIANCE,TCS,UNKNOWN_SYM")
    assert response.status_code == 200

    data = response.json()
    assert data["total_symbols"] == 3
    assert "RELIANCE" in data["quotes"]
    assert "TCS" in data["quotes"]
    assert "UNKNOWN_SYM" in data["quotes"]
    assert data["quotes"]["RELIANCE"]["current_price"] == "2850.50"
    assert data["quotes"]["UNKNOWN_SYM"]["current_price"] is None
    assert data["quotes"]["UNKNOWN_SYM"]["status"] == "UNAVAILABLE"

@pytest.mark.asyncio
async def test_market_data_api_missing_param_returns_422_envelope(client: AsyncClient):
    """Verifies missing required query parameter returns centralized 422 error envelope."""
    response = await client.get("/api/v1/market-data/quote")
    assert response.status_code == 422

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "timestamp" in data

@pytest.mark.asyncio
async def test_news_api_endpoint(client: AsyncClient):
    """Verifies GET /api/v1/news endpoint returns simulated articles with correct attribution."""
    response = await client.get("/api/v1/news?symbols=RELIANCE&limit=5")
    assert response.status_code == 200

    data = response.json()
    assert data["is_simulated"] is True
    assert "Simulated financial news" in data["disclaimer"]
    assert len(data["articles"]) >= 1

    article = data["articles"][0]
    assert article["is_simulated"] is True
    assert article["source"] == "Simulated Demo Financial News Engine"
    assert "RELIANCE" in article["related_symbols"]
