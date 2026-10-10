import logging
from datetime import datetime, timezone
from decimal import Decimal
import httpx
import pytest
from app.core.cache import AsyncTTLCache
from app.core.config import Settings
from app.core.logging import sanitize_log_message
from app.providers.alpha_vantage_market_data import AlphaVantageMarketDataProvider
from app.providers.demo_market_data import DemoMarketDataProvider
from app.schemas.market_data import QuoteStatus
from app.services.market_data_service import MarketDataService, resolve_market_data_provider


MOCK_AV_SUCCESS_PAYLOAD = {
    "Global Quote": {
        "01. symbol": "RELIANCE.NSE",
        "02. open": "2840.0000",
        "03. high": "2870.0000",
        "04. low": "2835.0000",
        "05. price": "2850.5000",
        "06. volume": "1234567",
        "07. latest trading day": "2026-10-09",
        "08. previous close": "2835.3000",
        "09. change": "15.2000",
        "10. change percent": "0.5361%",
    }
}


@pytest.mark.asyncio
async def test_alpha_vantage_successful_quote_parsing():
    """
    Verifies that a valid Alpha Vantage Global Quote response is accurately parsed
    into a Quote with Decimal precision, correct timestamps, and is_simulated=False.
    """
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json=MOCK_AV_SUCCESS_PAYLOAD)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(
            api_key="test-api-key",
            http_client=client,
        )

        quote = await provider.get_quote("RELIANCE", "NSE")

        # Provenance and simulation assertions
        assert quote.symbol == "RELIANCE"
        assert quote.exchange == "NSE"
        assert quote.is_simulated is False
        assert quote.source == "ALPHA_VANTAGE"
        assert quote.status == QuoteStatus.AVAILABLE
        assert "Alpha Vantage" in quote.disclaimer
        assert quote.explanation is None

        # Price and metric precision assertions
        assert quote.current_price == Decimal("2850.5000")
        assert quote.change == Decimal("15.2000")
        assert quote.change_percent == Decimal("0.5361")

        # Timestamp assertions
        assert quote.market_as_of == datetime(2026, 10, 9, tzinfo=timezone.utc)
        assert quote.generated_at is not None
        assert quote.cache_hit is False


@pytest.mark.asyncio
async def test_alpha_vantage_symbol_formatting():
    """
    Verifies that symbols are formatted with proper exchange suffixes when appropriate:
    - Dot already present -> unchanged
    - Exchange BSE/NSE -> suffix appended
    - US / blank exchange -> symbol unchanged
    """
    requested_urls = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, json=MOCK_AV_SUCCESS_PAYLOAD)

    transport = httpx.MockTransport(handle_request)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(
            api_key="test-key",
            http_client=client,
        )

        # 1. NSE exchange appends .NSE
        await provider.get_quote("RELIANCE", "NSE")
        assert "symbol=RELIANCE.NSE" in requested_urls[-1]

        # 2. BSE exchange appends .BSE
        await provider.get_quote("TCS", "BSE")
        assert "symbol=TCS.BSE" in requested_urls[-1]

        # 3. Already qualified symbol keeps dot suffix
        await provider.get_quote("INFY.BSE", "NSE")
        assert "symbol=INFY.BSE" in requested_urls[-1]

        # 4. US / empty exchange leaves US tickers without dot
        await provider.get_quote("IBM", "US")
        assert "symbol=IBM" in requested_urls[-1]


@pytest.mark.asyncio
async def test_alpha_vantage_missing_api_key_no_network_call(monkeypatch):
    """
    Verifies that when no API key is configured, the provider returns QuoteStatus.UNAVAILABLE
    with current_price=None, is_simulated=False, and makes zero network calls.
    Deterministic regardless of local .env configuration via monkeypatch.
    """
    from app.core import config
    monkeypatch.setattr(config.settings, "ALPHA_VANTAGE_API_KEY", None)

    call_count = 0

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=MOCK_AV_SUCCESS_PAYLOAD)

    transport = httpx.MockTransport(handle_request)
    async with httpx.AsyncClient(transport=transport) as client:
        # None key with settings.ALPHA_VANTAGE_API_KEY patched to None
        provider = AlphaVantageMarketDataProvider(api_key=None, http_client=client)
        quote = await provider.get_quote("RELIANCE")

        assert call_count == 0  # No HTTP call made
        assert quote.status == QuoteStatus.UNAVAILABLE
        assert quote.current_price is None
        assert quote.is_simulated is False
        assert quote.source == "ALPHA_VANTAGE"
        assert "not configured" in quote.explanation

        # Placeholder / demo key
        provider_demo = AlphaVantageMarketDataProvider(api_key="demo", http_client=client)
        quote_demo = await provider_demo.get_quote("RELIANCE")
        assert call_count == 0
        assert quote_demo.status == QuoteStatus.UNAVAILABLE
        assert quote_demo.current_price is None


@pytest.mark.asyncio
async def test_alpha_vantage_empty_json_payload():
    """
    Verifies that an empty JSON response payload ({}) is classified as UNAVAILABLE
    with an explicit empty-payload explanation, without falsely claiming 'symbol not found'.
    """
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json={})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(api_key="test-key", http_client=client)
        quote = await provider.get_quote("RELIANCE", "NSE")

        assert quote.symbol == "RELIANCE"
        assert quote.exchange == "NSE"
        assert quote.current_price is None
        assert quote.status == QuoteStatus.UNAVAILABLE
        assert quote.is_simulated is False
        assert quote.source == "ALPHA_VANTAGE"
        assert "empty response payload" in quote.explanation.lower()


@pytest.mark.asyncio
async def test_alpha_vantage_unrecognized_json_structure():
    """
    Verifies that non-empty JSON without 'Global Quote', 'Note', or 'Error Message'
    is classified as UNAVAILABLE with an unrecognized-structure explanation.
    """
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"bestMatches": [], "meta": "search_result"})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(api_key="test-key", http_client=client)
        quote = await provider.get_quote("RELIANCE", "NSE")

        assert quote.symbol == "RELIANCE"
        assert quote.current_price is None
        assert quote.status == QuoteStatus.UNAVAILABLE
        assert quote.is_simulated is False
        assert "unrecognized response without quote data" in quote.explanation.lower()


@pytest.mark.asyncio
async def test_alpha_vantage_unknown_symbol_returns_null_price():
    """
    Verifies that an unknown symbol returning empty Global Quote is handled safely
    without price fabrication (current_price=None, UNAVAILABLE, 'not found' explanation).
    """
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"Global Quote": {}})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(api_key="test-key", http_client=client)
        quote = await provider.get_quote("UNKNOWN_SYM", "NSE")

        assert quote.symbol == "UNKNOWN_SYM"
        assert quote.current_price is None
        assert quote.status == QuoteStatus.UNAVAILABLE
        assert quote.is_simulated is False
        assert "not found" in quote.explanation
        assert "No price fabricated" in quote.explanation


@pytest.mark.asyncio
async def test_alpha_vantage_rate_limit_notice():
    """
    Verifies that Alpha Vantage rate-limit notices with 'Note' key
    return QuoteStatus.UNAVAILABLE with current_price=None and clear explanation.
    """
    rate_limit_payload = {
        "Note": "Thank you for using Alpha Vantage! Our standard API call frequency is 5 calls per minute and 500 calls per day."
    }
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json=rate_limit_payload)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(api_key="test-key", http_client=client)
        quote = await provider.get_quote("RELIANCE", "NSE")

        assert quote.current_price is None
        assert quote.status == QuoteStatus.UNAVAILABLE
        assert quote.is_simulated is False
        assert "rate limit exceeded" in quote.explanation.lower()


@pytest.mark.asyncio
async def test_alpha_vantage_information_rate_limit_notice():
    """
    Verifies that Alpha Vantage rate-limit notices with 'Information' key (e.g. daily/tier caps)
    return QuoteStatus.UNAVAILABLE with current_price=None and clear explanation.
    """
    rate_limit_payload = {
        "Information": "Thank you for using Alpha Vantage! Please visit https://www.alphavantage.co/premium/ to upgrade."
    }
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json=rate_limit_payload)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(api_key="test-key", http_client=client)
        quote = await provider.get_quote("RELIANCE", "NSE")

        assert quote.current_price is None
        assert quote.status == QuoteStatus.UNAVAILABLE
        assert quote.is_simulated is False
        assert "rate limit exceeded" in quote.explanation.lower()


@pytest.mark.asyncio
async def test_alpha_vantage_api_error_message():
    """
    Verifies that Alpha Vantage API error responses ('Error Message' key)
    return QuoteStatus.ERROR with current_price=None and safe explanation.
    """
    error_payload = {
        "Error Message": "Invalid API call. Please check the documentation."
    }
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json=error_payload)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(api_key="test-key", http_client=client)
        quote = await provider.get_quote("BAD_CALL", "NSE")

        assert quote.current_price is None
        assert quote.status == QuoteStatus.ERROR
        assert quote.is_simulated is False
        assert "api error" in quote.explanation.lower()


@pytest.mark.asyncio
async def test_alpha_vantage_malformed_and_missing_price():
    """
    Verifies that malformed payloads (non-JSON, missing price, invalid decimal)
    strictly return null prices and appropriate error statuses without raising.
    """
    # 1. Non-JSON response
    transport_non_json = httpx.MockTransport(
        lambda req: httpx.Response(200, text="<html>502 Bad Gateway</html>")
    )
    async with httpx.AsyncClient(transport=transport_non_json) as client:
        provider = AlphaVantageMarketDataProvider(api_key="test-key", http_client=client)
        quote = await provider.get_quote("INFY", "NSE")
        assert quote.current_price is None
        assert quote.status == QuoteStatus.ERROR
        assert quote.is_simulated is False

    # 2. Missing "05. price" key
    transport_missing_price = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"Global Quote": {"01. symbol": "INFY"}})
    )
    async with httpx.AsyncClient(transport=transport_missing_price) as client:
        provider = AlphaVantageMarketDataProvider(api_key="test-key", http_client=client)
        quote = await provider.get_quote("INFY", "NSE")
        assert quote.current_price is None
        assert quote.status == QuoteStatus.UNAVAILABLE

    # 3. Invalid decimal string
    transport_bad_decimal = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"Global Quote": {"05. price": "NOT_A_NUMBER"}})
    )
    async with httpx.AsyncClient(transport=transport_bad_decimal) as client:
        provider = AlphaVantageMarketDataProvider(api_key="test-key", http_client=client)
        quote = await provider.get_quote("INFY", "NSE")
        assert quote.current_price is None
        assert quote.status == QuoteStatus.ERROR


@pytest.mark.asyncio
async def test_alpha_vantage_network_timeout_and_http_error():
    """
    Verifies that HTTP 500 status and timeout exceptions return QuoteStatus.ERROR
    with current_price=None and never crash the service.
    """
    # HTTP 500
    transport_500 = httpx.MockTransport(
        lambda req: httpx.Response(500, text="Internal Server Error")
    )
    async with httpx.AsyncClient(transport=transport_500) as client:
        provider = AlphaVantageMarketDataProvider(api_key="test-key", http_client=client)
        quote = await provider.get_quote("TCS", "NSE")
        assert quote.current_price is None
        assert quote.status == QuoteStatus.ERROR
        assert quote.is_simulated is False

    # Timeout
    def timeout_handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Request timed out", request=req)

    transport_timeout = httpx.MockTransport(timeout_handler)
    async with httpx.AsyncClient(transport=transport_timeout) as client:
        provider = AlphaVantageMarketDataProvider(api_key="test-key", http_client=client)
        quote = await provider.get_quote("TCS", "NSE")
        assert quote.current_price is None
        assert quote.status == QuoteStatus.ERROR
        assert quote.is_simulated is False


@pytest.mark.asyncio
async def test_alpha_vantage_batch_quotes():
    """Verifies that get_quotes batches multiple symbols accurately."""
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json=MOCK_AV_SUCCESS_PAYLOAD)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(api_key="test-key", http_client=client)
        quotes = await provider.get_quotes(["RELIANCE", "TCS"], "NSE")

        assert len(quotes) == 2
        assert "RELIANCE" in quotes
        assert "TCS" in quotes
        assert quotes["RELIANCE"].current_price == Decimal("2850.5000")
        assert quotes["TCS"].current_price == Decimal("2850.5000")


@pytest.mark.asyncio
async def test_alpha_vantage_secret_redaction_and_leak_prevention(caplog):
    """
    Security test: verifies that the raw API key and URLs containing apikey
    never appear in logs, error explanations, or exception strings.
    """
    secret_key = "CONFIDENTIAL_ALPHA_KEY_98765"

    def failing_handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"Connection to {req.url} failed", request=req)

    transport = httpx.MockTransport(failing_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(
            api_key=secret_key,
            http_client=client,
        )

        caplog.set_level(logging.DEBUG)
        quote = await provider.get_quote("RELIANCE", "NSE")

        # 1. Secret must never be in explanation
        assert secret_key not in (quote.explanation or "")

        # 2. Secret must never be in captured logs
        log_records = [r.getMessage() for r in caplog.records]
        log_dump = "\n".join(log_records)
        assert secret_key not in log_dump
        assert f"apikey={secret_key}" not in log_dump

        # 3. Direct test of sanitize_log_message utility
        dirty = f"https://www.alphavantage.co/query?symbol=TCS&apikey={secret_key}"
        cleaned = sanitize_log_message(dirty, secret=secret_key)
        assert secret_key not in cleaned
        assert "apikey=[REDACTED]" in cleaned


def test_provider_selection_behavior():
    """
    Verifies that resolve_market_data_provider strictly honors configuration:
    - USE_MOCK_DATA=True always forces DemoMarketDataProvider (₹0 policy)
    - USE_MOCK_DATA=False and MARKET_DATA_PROVIDER='alphavantage' selects AlphaVantageMarketDataProvider
    - Default settings return DemoMarketDataProvider
    """
    # 1. Default settings -> Demo
    default_provider = resolve_market_data_provider()
    assert isinstance(default_provider, DemoMarketDataProvider)

    # 2. Custom isolated settings: mock=True with alphavantage provider -> Demo (zero cost master switch)
    mock_forced_settings = Settings(
        USE_MOCK_DATA=True,
        MARKET_DATA_PROVIDER="alphavantage",
    )
    # Monkeypatch settings temporarily for resolver verification
    from app.core import config

    orig_settings = config.settings
    try:
        config.settings = mock_forced_settings
        p1 = resolve_market_data_provider()
        assert isinstance(p1, DemoMarketDataProvider)

        # 3. mock=False with alphavantage provider -> AlphaVantage
        live_settings = Settings(
            USE_MOCK_DATA=False,
            MARKET_DATA_PROVIDER="alphavantage",
            ALPHA_VANTAGE_API_KEY="mock-av-key",
        )
        config.settings = live_settings
        p2 = resolve_market_data_provider()
        assert isinstance(p2, AlphaVantageMarketDataProvider)
        assert p2.api_key == "mock-av-key"

        # 4. mock=False with demo provider -> Demo
        demo_explicit_settings = Settings(
            USE_MOCK_DATA=False,
            MARKET_DATA_PROVIDER="demo",
        )
        config.settings = demo_explicit_settings
        p3 = resolve_market_data_provider()
        assert isinstance(p3, DemoMarketDataProvider)

    finally:
        config.settings = orig_settings


@pytest.mark.asyncio
async def test_market_data_service_caching_and_stale_fallback_with_alphavantage():
    """
    Verifies that MarketDataService correctly caches valid Alpha Vantage quotes
    and falls back to stale cache during subsequent failures without caching errors.
    """
    cache = AsyncTTLCache(default_ttl_seconds=0.05)
    call_count = 0

    def mock_handler(req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json=MOCK_AV_SUCCESS_PAYLOAD)
        # Subsequent calls fail
        raise httpx.ConnectError("Connection dropped", request=req)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(api_key="test-key", http_client=client)
        service = MarketDataService(provider=provider, cache=cache, default_ttl_seconds=0.05)

        # First call: fresh fetch and cached
        quote1 = await service.get_quote("RELIANCE", "NSE")
        assert quote1.current_price == Decimal("2850.5000")
        assert quote1.cache_hit is False
        assert quote1.is_simulated is False
        assert quote1.source == "ALPHA_VANTAGE"

        # Second call immediately: fresh cache hit
        quote2 = await service.get_quote("RELIANCE", "NSE")
        assert quote2.current_price == Decimal("2850.5000")
        assert quote2.cache_hit is True
        assert quote2.is_simulated is False

        # Wait for TTL expiration
        import asyncio
        await asyncio.sleep(0.06)

        # Third call: provider fails, service serves stale cached quote
        quote3 = await service.get_quote("RELIANCE", "NSE")
        assert quote3.current_price == Decimal("2850.5000")
        assert quote3.is_stale is True
        assert quote3.cache_hit is False
        assert quote3.is_simulated is False
        assert "stale" in quote3.explanation.lower()
