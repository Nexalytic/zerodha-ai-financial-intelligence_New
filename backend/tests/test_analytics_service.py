from datetime import datetime, timezone
from decimal import Decimal
import pytest
from app.core.cache import AsyncTTLCache
from app.models.portfolio import Holding, Portfolio
from app.providers.base import BaseMarketDataProvider
from app.schemas.analytics import ValuationStatus
from app.schemas.market_data import Quote, QuoteStatus
from app.schemas.portfolio import HoldingCreate, PortfolioCreate
from app.services.analytics_service import AnalyticsService
from app.services.market_data_service import MarketDataService
from app.services.portfolio_service import PortfolioService

class MockCustomMarketDataProvider(BaseMarketDataProvider):
    """Custom provider for testing edge cases, stale fallback, and errors."""

    def __init__(self, responses: dict):
        self.responses = responses

    async def get_quote(self, symbol: str, exchange: str = "NSE") -> Quote:
        key = (symbol.strip().upper(), exchange.strip().upper())
        if key in self.responses:
            return self.responses[key]
        return Quote(
            symbol=symbol,
            exchange=exchange,
            current_price=None,
            status=QuoteStatus.UNAVAILABLE,
            is_simulated=True,
            explanation=f"Symbol '{symbol}' not found",
        )

    async def get_quotes(self, symbols: list[str], exchange: str = "NSE") -> dict[str, Quote]:
        return {s: await self.get_quote(s, exchange) for s in symbols}

@pytest.mark.asyncio
async def test_analytics_empty_portfolio(test_db_setup):
    """
    Verifies that an empty portfolio returns:
    - status = EMPTY
    - is_complete = False
    - completeness_ratio = 0.0000
    - monetary totals = 0.00
    - unrealized_pnl = None, unrealized_pnl_percent = None
    - zero division errors are guarded
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        p = await port_service.create_portfolio(PortfolioCreate(name="Empty Test Portfolio"))

        analytics_service = AnalyticsService(session)
        analytics = await analytics_service.calculate_portfolio_analytics(p.id)

        assert analytics is not None
        assert analytics.status == ValuationStatus.EMPTY
        assert analytics.completeness.is_complete is False
        assert analytics.completeness.completeness_ratio == Decimal("0.0000")
        assert analytics.completeness.total_holdings_count == 0
        assert analytics.completeness.priced_holdings_count == 0
        assert analytics.completeness.unpriced_holdings_count == 0

        # Zero monetary totals
        assert analytics.valuation.total_cost_basis == Decimal("0.00")
        assert analytics.valuation.total_market_value == Decimal("0.00")
        assert analytics.valuation.priced_cost_basis == Decimal("0.00")

        # P/L explicitly None
        assert analytics.valuation.unrealized_pnl is None
        assert analytics.valuation.unrealized_pnl_percent is None

        # Concentration metrics None
        assert analytics.concentration.top_holding_symbol is None
        assert analytics.concentration.herfindahl_index is None
        assert analytics.sector_allocations == []
        assert analytics.holdings == []

@pytest.mark.asyncio
async def test_analytics_fully_priced_portfolio(test_db_setup):
    """
    Verifies complete valuation on a fully priced portfolio:
    - Correct Decimal P/L and percentage using ROUND_HALF_UP
    - Weights sum to 100.00%
    - Herfindahl-Hirschman Index computed on 0-1 scale using unrounded intermediate shares
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        p = await port_service.create_portfolio(
            PortfolioCreate(
                name="Bluechip Test",
                holdings=[
                    HoldingCreate(
                        symbol="RELIANCE",
                        exchange="NSE",
                        quantity=50,
                        average_buy_price=Decimal("2800.00"),
                        sector="Energy",
                    ),
                    HoldingCreate(
                        symbol="TCS",
                        exchange="NSE",
                        quantity=20,
                        average_buy_price=Decimal("3900.00"),
                        sector="IT",
                    ),
                ],
            )
        )

        analytics_service = AnalyticsService(session)
        analytics = await analytics_service.calculate_portfolio_analytics(p.id)

        assert analytics is not None
        assert analytics.status == ValuationStatus.COMPLETE
        assert analytics.completeness.is_complete is True
        assert analytics.completeness.completeness_ratio == Decimal("1.0000")
        assert analytics.completeness.priced_holdings_count == 2
        assert analytics.completeness.unpriced_holdings_count == 0

        # Cost basis: 50*2800 = 140000; 20*3900 = 78000; Total = 218000.00
        assert analytics.valuation.total_cost_basis == Decimal("218000.00")
        assert analytics.valuation.priced_cost_basis == Decimal("218000.00")

        # Market prices from DemoMarketDataProvider: RELIANCE=2850.50, TCS=3920.00
        # Market values: 50*2850.50 = 142525.00; 20*3920.00 = 78400.00; Total = 220925.00
        assert analytics.valuation.total_market_value == Decimal("220925.00")

        # P/L: 220925 - 218000 = +2925.00
        assert analytics.valuation.unrealized_pnl == Decimal("2925.00")
        # P/L %: (2925 / 218000) * 100 = 1.3417... -> 1.34%
        assert analytics.valuation.unrealized_pnl_percent == Decimal("1.34")

        # Weights check
        assert len(analytics.holdings) == 2
        rel_h = next(h for h in analytics.holdings if h.symbol == "RELIANCE")
        tcs_h = next(h for h in analytics.holdings if h.symbol == "TCS")
        assert rel_h.market_value_weight_percent == Decimal("64.51")
        assert tcs_h.market_value_weight_percent == Decimal("35.49")
        assert rel_h.market_value_weight_percent + tcs_h.market_value_weight_percent == Decimal("100.00")

        # Concentration metrics
        assert analytics.concentration.top_holding_symbol == "RELIANCE"
        assert analytics.concentration.top_holding_weight_percent == Decimal("64.51")
        assert analytics.concentration.top_3_concentration_percent == Decimal("100.00")

        # HHI: (142525/220925)^2 + (78400/220925)^2 = 0.41619 + 0.12593 = 0.54212 -> 0.5421
        assert analytics.concentration.herfindahl_index == Decimal("0.5421")

        # Sectors
        assert len(analytics.sector_allocations) == 2
        sec_energy = next(s for s in analytics.sector_allocations if s.sector == "Energy")
        sec_it = next(s for s in analytics.sector_allocations if s.sector == "IT")
        assert sec_energy.allocation_percent == Decimal("64.51")
        assert sec_it.allocation_percent == Decimal("35.49")

@pytest.mark.asyncio
async def test_analytics_partially_priced_portfolio(test_db_setup):
    """
    Verifies that a partially priced portfolio:
    - Sets status = PARTIAL, is_complete = False
    - Completeness ratio reflects fraction of priced holdings
    - Unpriced position has current_price=null, market_value=null, pnl=null
    - Total market value sums ONLY priced holdings
    - Unrealized P/L compares market value ONLY against priced cost basis (no false loss)
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        p = await port_service.create_portfolio(
            PortfolioCreate(
                name="Partial Portfolio",
                holdings=[
                    HoldingCreate(
                        symbol="RELIANCE",
                        exchange="NSE",
                        quantity=10,
                        average_buy_price=Decimal("2800.00"),
                        sector="Energy",
                    ),
                    HoldingCreate(
                        symbol="UNKNOWN-STOCK",
                        exchange="NSE",
                        quantity=100,
                        average_buy_price=Decimal("500.00"),  # Cost basis = 50,000 INR
                        sector="Speculative",
                    ),
                ],
            )
        )

        analytics_service = AnalyticsService(session)
        analytics = await analytics_service.calculate_portfolio_analytics(p.id)

        assert analytics is not None
        assert analytics.status == ValuationStatus.PARTIAL
        assert analytics.completeness.is_complete is False
        assert analytics.completeness.completeness_ratio == Decimal("0.5000")
        assert analytics.completeness.priced_holdings_count == 1
        assert analytics.completeness.unpriced_holdings_count == 1

        # Total cost basis sums BOTH holdings (28,000 + 50,000 = 78,000)
        assert analytics.valuation.total_cost_basis == Decimal("78000.00")

        # Priced cost basis is ONLY RELIANCE (28,000)
        assert analytics.valuation.priced_cost_basis == Decimal("28000.00")

        # Market value is ONLY RELIANCE (10 * 2850.50 = 28505.00)
        assert analytics.valuation.total_market_value == Decimal("28505.00")

        # P/L is 28505.00 - 28000.00 = +505.00 (crucial: NOT comparing against 78,000 which would falsely show -49,495 loss!)
        assert analytics.valuation.unrealized_pnl == Decimal("505.00")
        assert analytics.valuation.unrealized_pnl_percent == Decimal("1.80")

        # Check unpriced position detail
        assert len(analytics.completeness.unpriced_positions) == 1
        unp = analytics.completeness.unpriced_positions[0]
        assert unp.symbol == "UNKNOWN-STOCK"
        assert unp.cost_basis == Decimal("50000.00")
        assert unp.pricing_status == "UNAVAILABLE"

        # Check holding details
        unknown_h = next(h for h in analytics.holdings if h.symbol == "UNKNOWN-STOCK")
        assert unknown_h.current_price is None
        assert unknown_h.market_value is None
        assert unknown_h.unrealized_pnl is None
        assert unknown_h.unrealized_pnl_percent is None
        assert unknown_h.market_value_weight_percent is None
        assert unknown_h.cost_basis_weight_percent == Decimal("64.10")  # 50000 / 78000 * 100

        # Sector check: unpriced sector allocation_percent must be None (not 0.00 to avoid implying 0 exposure)
        sec_spec = next(s for s in analytics.sector_allocations if s.sector == "Speculative")
        assert sec_spec.market_value == Decimal("0.00")
        assert sec_spec.allocation_percent is None

@pytest.mark.asyncio
async def test_analytics_all_unpriced_holdings(test_db_setup):
    """
    Verifies that a portfolio where all holdings lack prices returns:
    - status = UNVALUED
    - is_complete = False, completeness_ratio = 0.0000
    - total_market_value = 0.00, priced_cost_basis = 0.00
    - unrealized_pnl = None, unrealized_pnl_percent = None
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        p = await port_service.create_portfolio(
            PortfolioCreate(
                name="All Unpriced Basket",
                holdings=[
                    HoldingCreate(symbol="UNKNOWN1", quantity=10, average_buy_price=Decimal("100.00")),
                    HoldingCreate(symbol="UNKNOWN2", quantity=20, average_buy_price=Decimal("200.00")),
                ],
            )
        )

        analytics_service = AnalyticsService(session)
        analytics = await analytics_service.calculate_portfolio_analytics(p.id)

        assert analytics is not None
        assert analytics.status == ValuationStatus.UNVALUED
        assert analytics.completeness.is_complete is False
        assert analytics.completeness.completeness_ratio == Decimal("0.0000")
        assert analytics.completeness.priced_holdings_count == 0
        assert analytics.completeness.unpriced_holdings_count == 2

        assert analytics.valuation.total_cost_basis == Decimal("5000.00")
        assert analytics.valuation.total_market_value == Decimal("0.00")
        assert analytics.valuation.priced_cost_basis == Decimal("0.00")

        # Explicitly None
        assert analytics.valuation.unrealized_pnl is None
        assert analytics.valuation.unrealized_pnl_percent is None

        # Concentration metrics None
        assert analytics.concentration.top_holding_symbol is None
        assert analytics.concentration.herfindahl_index is None

@pytest.mark.asyncio
async def test_analytics_stale_and_error_quote_provenance(test_db_setup):
    """
    Verifies that quote provenance (stale flag, error status vs unavailable status)
    is preserved cleanly without conflation.
    """
    session_factory, _ = test_db_setup

    mock_provider = MockCustomMarketDataProvider(
        {
            ("TCS", "NSE"): Quote(
                symbol="TCS",
                exchange="NSE",
                current_price=Decimal("4000.00"),
                status=QuoteStatus.AVAILABLE,
                is_stale=True,  # Stale fallback quote
                source="MOCK_STALE_CACHE",
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            ("INFY", "NSE"): Quote(
                symbol="INFY",
                exchange="NSE",
                current_price=None,
                status=QuoteStatus.ERROR,  # Provider error
                source="MOCK_FAILING_PROVIDER",
                explanation="Connection timeout to upstream provider",
            ),
        }
    )

    custom_md_service = MarketDataService(provider=mock_provider)

    async with session_factory() as session:
        port_service = PortfolioService(session)
        p = await port_service.create_portfolio(
            PortfolioCreate(
                name="Provenance Test",
                holdings=[
                    HoldingCreate(symbol="TCS", quantity=10, average_buy_price=Decimal("3900.00")),
                    HoldingCreate(symbol="INFY", quantity=20, average_buy_price=Decimal("1500.00")),
                ],
            )
        )

        analytics_service = AnalyticsService(session, market_data_service=custom_md_service)
        analytics = await analytics_service.calculate_portfolio_analytics(p.id)

        assert analytics is not None
        assert analytics.completeness.has_stale_prices is True

        tcs_h = next(h for h in analytics.holdings if h.symbol == "TCS")
        assert tcs_h.is_stale is True
        assert tcs_h.pricing_status == "AVAILABLE"
        assert tcs_h.quote_generated_at == datetime(2026, 1, 1, tzinfo=timezone.utc)

        infy_h = next(h for h in analytics.holdings if h.symbol == "INFY")
        assert infy_h.pricing_status == "ERROR"
        assert "Connection timeout" in infy_h.price_explanation

@pytest.mark.asyncio
async def test_analytics_same_symbol_different_exchanges(test_db_setup):
    """
    Verifies that the same ticker symbol on different exchanges (NSE vs BSE)
    is resolved independently per position without key collision.
    """
    session_factory, _ = test_db_setup

    mock_provider = MockCustomMarketDataProvider(
        {
            ("RELIANCE", "NSE"): Quote(
                symbol="RELIANCE",
                exchange="NSE",
                current_price=Decimal("2850.00"),
                status=QuoteStatus.AVAILABLE,
            ),
            ("RELIANCE", "BSE"): Quote(
                symbol="RELIANCE",
                exchange="BSE",
                current_price=Decimal("2848.50"),
                status=QuoteStatus.AVAILABLE,
            ),
        }
    )

    custom_md_service = MarketDataService(provider=mock_provider)

    async with session_factory() as session:
        port_service = PortfolioService(session)
        p = await port_service.create_portfolio(
            PortfolioCreate(
                name="Dual Exchange Basket",
                holdings=[
                    HoldingCreate(symbol="RELIANCE", exchange="NSE", quantity=10, average_buy_price=Decimal("2800.00")),
                    HoldingCreate(symbol="RELIANCE", exchange="BSE", quantity=20, average_buy_price=Decimal("2800.00")),
                ],
            )
        )

        analytics_service = AnalyticsService(session, market_data_service=custom_md_service)
        analytics = await analytics_service.calculate_portfolio_analytics(p.id)

        assert analytics is not None
        assert len(analytics.holdings) == 2
        nse_h = next(h for h in analytics.holdings if h.exchange == "NSE")
        bse_h = next(h for h in analytics.holdings if h.exchange == "BSE")

        assert nse_h.current_price == Decimal("2850.00")
        assert bse_h.current_price == Decimal("2848.50")
        assert analytics.valuation.total_market_value == Decimal("28500.00") + Decimal("56970.00")
