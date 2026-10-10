from decimal import Decimal
import pytest
from app.providers.demo_market_data import DemoMarketDataProvider
from app.schemas.market_data import QuoteStatus

@pytest.mark.asyncio
async def test_known_symbols_deterministic_quote():
    """
    Verifies that known symbols return fixed deterministic simulated quotes
    with is_simulated=True, market_as_of=None, and explicit disclaimers.
    Repeated queries must return the exact same price (no random drift).
    """
    provider = DemoMarketDataProvider()

    quote_1 = await provider.get_quote("RELIANCE", "NSE")
    quote_2 = await provider.get_quote("RELIANCE", "NSE")

    # Strict price determinism
    assert quote_1.current_price == Decimal("2850.50")
    assert quote_2.current_price == Decimal("2850.50")
    assert quote_1.change == Decimal("15.20")
    assert quote_1.change_percent == Decimal("0.54")

    # Strict simulation semantics
    assert quote_1.is_simulated is True
    assert quote_1.market_as_of is None  # Strictly None for simulated values
    assert quote_1.status == QuoteStatus.AVAILABLE
    assert quote_1.source == "SIMULATED_DEMO_PROVIDER"
    assert "Simulated market quote" in quote_1.disclaimer
    assert quote_1.generated_at is not None

@pytest.mark.asyncio
async def test_unknown_symbol_returns_null_price_and_explanation():
    """
    Verifies that unknown tickers return strictly current_price=None,
    status=UNAVAILABLE, and an explanation confirming no fabricated price was produced.
    """
    provider = DemoMarketDataProvider()

    quote = await provider.get_quote("XYZ_NONEXISTENT", "NSE")

    assert quote.symbol == "XYZ_NONEXISTENT"
    assert quote.current_price is None
    assert quote.change is None
    assert quote.change_percent is None
    assert quote.status == QuoteStatus.UNAVAILABLE
    assert quote.is_simulated is True
    assert quote.market_as_of is None
    assert "not found in demo market universe" in quote.explanation
    assert "No price fabricated" in quote.explanation

@pytest.mark.asyncio
async def test_batch_quotes_mixed_symbols():
    """
    Verifies batch quotes return accurate per-symbol results for mixed
    known and unknown symbols without price fabrication.
    """
    provider = DemoMarketDataProvider()
    symbols = ["RELIANCE", "UNKNOWN_1", "TCS"]

    quotes = await provider.get_quotes(symbols, "NSE")

    assert len(quotes) == 3
    assert quotes["RELIANCE"].current_price == Decimal("2850.50")
    assert quotes["RELIANCE"].status == QuoteStatus.AVAILABLE

    assert quotes["UNKNOWN_1"].current_price is None
    assert quotes["UNKNOWN_1"].status == QuoteStatus.UNAVAILABLE

    assert quotes["TCS"].current_price == Decimal("3920.00")
    assert quotes["TCS"].status == QuoteStatus.AVAILABLE

@pytest.mark.asyncio
async def test_symbol_case_and_whitespace_normalization():
    """Verifies that symbol inputs are normalized to uppercase stripped tokens."""
    provider = DemoMarketDataProvider()

    quote = await provider.get_quote("  infy  ", "nse")
    assert quote.symbol == "INFY"
    assert quote.exchange == "NSE"
    assert quote.current_price == Decimal("1520.25")
