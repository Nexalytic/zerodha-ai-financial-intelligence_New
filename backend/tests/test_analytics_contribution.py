from datetime import datetime, timezone
from decimal import Decimal
import pytest

from app.models.portfolio import Holding, Portfolio
from app.providers.base import BaseMarketDataProvider
from app.schemas.analytics import ValuationStatus
from app.schemas.market_data import Quote, QuoteStatus
from app.schemas.portfolio import HoldingCreate, PortfolioCreate
from app.services.analytics_service import AnalyticsService
from app.services.market_data_service import MarketDataService
from app.services.portfolio_service import PortfolioService


class MockCustomMarketDataProvider(BaseMarketDataProvider):
    """Custom mock provider for deterministically testing gains, losses, and missing quotes."""

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
async def test_multiple_holdings_gains_and_losses_contribution_reconciliation(test_db_setup):
    """
    Verifies that for multiple holdings with gains and losses:
    - unrealized_pnl_contribution matches holding P/L (INR).
    - Sum of holding unrealized_pnl_contribution equals portfolio unrealized_pnl.
    - cost_basis_weighted_return_contribution_percent matches (unrealized_pnl / priced_cost_basis * 100).
    - Sum of return contributions reconciles with portfolio unrealized_pnl_percent within rounding tolerance.
    """
    session_factory, _ = test_db_setup

    # Setup mock quotes:
    # Stock A (RELIANCE): Buy 2000, Current 2500 (+500/share, gain)
    # Stock B (TCS): Buy 4000, Current 3600 (-400/share, loss)
    # Stock C (INFY): Buy 1500, Current 1500 (0/share, flat)
    mock_provider = MockCustomMarketDataProvider(
        {
            ("RELIANCE", "NSE"): Quote(
                symbol="RELIANCE", exchange="NSE", current_price=Decimal("2500.00"), status=QuoteStatus.AVAILABLE
            ),
            ("TCS", "NSE"): Quote(
                symbol="TCS", exchange="NSE", current_price=Decimal("3600.00"), status=QuoteStatus.AVAILABLE
            ),
            ("INFY", "NSE"): Quote(
                symbol="INFY", exchange="NSE", current_price=Decimal("1500.00"), status=QuoteStatus.AVAILABLE
            ),
        }
    )
    custom_md = MarketDataService(provider=mock_provider)

    async with session_factory() as session:
        port_service = PortfolioService(session)
        p = await port_service.create_portfolio(
            PortfolioCreate(
                name="Contribution Test Basket",
                holdings=[
                    HoldingCreate(symbol="RELIANCE", quantity=10, average_buy_price=Decimal("2000.00"), sector="Energy"),
                    HoldingCreate(symbol="TCS", quantity=10, average_buy_price=Decimal("4000.00"), sector="IT"),
                    HoldingCreate(symbol="INFY", quantity=20, average_buy_price=Decimal("1500.00"), sector="IT"),
                ],
            )
        )

        analytics_service = AnalyticsService(session, market_data_service=custom_md)
        analytics = await analytics_service.calculate_portfolio_analytics(p.id)

        assert analytics is not None
        assert analytics.status == ValuationStatus.COMPLETE

        # Cost bases:
        # RELIANCE: 10 * 2000 = 20,000
        # TCS:      10 * 4000 = 40,000
        # INFY:     20 * 1500 = 30,000
        # Total priced cost basis = 90,000.00
        assert analytics.valuation.priced_cost_basis == Decimal("90000.00")

        # Market values:
        # RELIANCE: 10 * 2500 = 25,000 (P/L = +5,000.00)
        # TCS:      10 * 3600 = 36,000 (P/L = -4,000.00)
        # INFY:     20 * 1500 = 30,000 (P/L =     0.00)
        # Total market value = 91,000.00
        assert analytics.valuation.total_market_value == Decimal("91000.00")

        # Portfolio P/L: 91,000 - 90,000 = +1,000.00
        # Portfolio P/L %: (1,000 / 90,000) * 100 = 1.1111... -> 1.11%
        assert analytics.valuation.unrealized_pnl == Decimal("1000.00")
        assert analytics.valuation.unrealized_pnl_percent == Decimal("1.11")

        rel_h = next(h for h in analytics.holdings if h.symbol == "RELIANCE")
        tcs_h = next(h for h in analytics.holdings if h.symbol == "TCS")
        infy_h = next(h for h in analytics.holdings if h.symbol == "INFY")

        # Holding P/L contributions (INR)
        assert rel_h.unrealized_pnl_contribution == Decimal("5000.00")
        assert tcs_h.unrealized_pnl_contribution == Decimal("-4000.00")
        assert infy_h.unrealized_pnl_contribution == Decimal("0.00")

        # Conservation of P/L in INR: Sum of contributions equals total portfolio P/L
        total_pnl_contrib = (
            rel_h.unrealized_pnl_contribution
            + tcs_h.unrealized_pnl_contribution
            + infy_h.unrealized_pnl_contribution
        )
        assert total_pnl_contrib == analytics.valuation.unrealized_pnl

        # Holding return contributions (pp):
        # RELIANCE: (5000 / 90000) * 100 = 5.555... -> 5.56%
        # TCS:     (-4000 / 90000) * 100 = -4.444... -> -4.44%
        # INFY:        (0 / 90000) * 100 = 0.00%
        assert rel_h.cost_basis_weighted_return_contribution_percent == Decimal("5.56")
        assert tcs_h.cost_basis_weighted_return_contribution_percent == Decimal("-4.44")
        assert infy_h.cost_basis_weighted_return_contribution_percent == Decimal("0.00")

        # Conservation of Return Contribution:
        # Sum = 5.56 - 4.44 + 0.00 = +1.12% vs portfolio return 1.11% (difference is within ±0.01 rounding tolerance)
        total_return_contrib = (
            rel_h.cost_basis_weighted_return_contribution_percent
            + tcs_h.cost_basis_weighted_return_contribution_percent
            + infy_h.cost_basis_weighted_return_contribution_percent
        )
        assert abs(total_return_contrib - analytics.valuation.unrealized_pnl_percent) <= Decimal("0.01")


@pytest.mark.asyncio
async def test_sector_pnl_and_contribution_reconciliation(test_db_setup):
    """
    Verifies that sector allocations compute P/L and return contributions,
    and reconcile with portfolio totals.
    """
    session_factory, _ = test_db_setup

    mock_provider = MockCustomMarketDataProvider(
        {
            ("RELIANCE", "NSE"): Quote(symbol="RELIANCE", exchange="NSE", current_price=Decimal("3000.00"), status=QuoteStatus.AVAILABLE),
            ("TCS", "NSE"): Quote(symbol="TCS", exchange="NSE", current_price=Decimal("4200.00"), status=QuoteStatus.AVAILABLE),
        }
    )
    custom_md = MarketDataService(provider=mock_provider)

    async with session_factory() as session:
        port_service = PortfolioService(session)
        p = await port_service.create_portfolio(
            PortfolioCreate(
                name="Sector Reconcile Basket",
                holdings=[
                    HoldingCreate(symbol="RELIANCE", quantity=10, average_buy_price=Decimal("2500.00"), sector="Energy"),  # cb 25000, mv 30000, pnl +5000
                    HoldingCreate(symbol="TCS", quantity=10, average_buy_price=Decimal("4000.00"), sector="IT"),          # cb 40000, mv 42000, pnl +2000
                ],
            )
        )

        analytics_service = AnalyticsService(session, market_data_service=custom_md)
        analytics = await analytics_service.calculate_portfolio_analytics(p.id)

        assert analytics is not None
        # Total cost = 65,000, total mv = 72,000, portfolio P/L = +7,000.00
        # Portfolio return %: (7000 / 65000) * 100 = 10.7692... -> 10.77%
        assert analytics.valuation.unrealized_pnl == Decimal("7000.00")
        assert analytics.valuation.unrealized_pnl_percent == Decimal("10.77")

        assert len(analytics.sector_allocations) == 2
        sec_energy = next(s for s in analytics.sector_allocations if s.sector == "Energy")
        sec_it = next(s for s in analytics.sector_allocations if s.sector == "IT")

        # Energy sector P/L: 30,000 - 25,000 = +5,000.00; % = (5000/25000)*100 = 20.00%
        # Energy return contribution: (5000 / 65000) * 100 = 7.6923... -> 7.69%
        assert sec_energy.unrealized_pnl == Decimal("5000.00")
        assert sec_energy.unrealized_pnl_percent == Decimal("20.00")
        assert sec_energy.cost_basis_weighted_return_contribution_percent == Decimal("7.69")

        # IT sector P/L: 42,000 - 40,000 = +2,000.00; % = (2000/40000)*100 = 5.00%
        # IT return contribution: (2000 / 65000) * 100 = 3.0769... -> 3.08%
        assert sec_it.unrealized_pnl == Decimal("2000.00")
        assert sec_it.unrealized_pnl_percent == Decimal("5.00")
        assert sec_it.cost_basis_weighted_return_contribution_percent == Decimal("3.08")

        # Sum of sector P/L == portfolio P/L
        assert sec_energy.unrealized_pnl + sec_it.unrealized_pnl == analytics.valuation.unrealized_pnl

        # Sum of sector return contributions == portfolio return % (7.69 + 3.08 = 10.77%)
        total_sec_contrib = (
            sec_energy.cost_basis_weighted_return_contribution_percent
            + sec_it.cost_basis_weighted_return_contribution_percent
        )
        assert abs(total_sec_contrib - analytics.valuation.unrealized_pnl_percent) <= Decimal("0.01")


@pytest.mark.asyncio
async def test_unpriced_holdings_and_unpriced_sectors_have_none_contributions(test_db_setup):
    """
    Verifies that unpriced holdings and sectors containing only unpriced holdings
    return strictly None for contributions and P/L, without fabricating zero gains.
    """
    session_factory, _ = test_db_setup

    mock_provider = MockCustomMarketDataProvider(
        {
            ("RELIANCE", "NSE"): Quote(symbol="RELIANCE", exchange="NSE", current_price=Decimal("2800.00"), status=QuoteStatus.AVAILABLE),
            # UNKNOWN-SYM is unpriced
        }
    )
    custom_md = MarketDataService(provider=mock_provider)

    async with session_factory() as session:
        port_service = PortfolioService(session)
        p = await port_service.create_portfolio(
            PortfolioCreate(
                name="Unpriced Contribution Test",
                holdings=[
                    HoldingCreate(symbol="RELIANCE", quantity=10, average_buy_price=Decimal("2500.00"), sector="Energy"),
                    HoldingCreate(symbol="UNKNOWN-SYM", quantity=50, average_buy_price=Decimal("100.00"), sector="Pharma"),
                ],
            )
        )

        analytics_service = AnalyticsService(session, market_data_service=custom_md)
        analytics = await analytics_service.calculate_portfolio_analytics(p.id)

        assert analytics is not None
        assert analytics.status == ValuationStatus.PARTIAL

        # Unpriced holding checks
        unp_h = next(h for h in analytics.holdings if h.symbol == "UNKNOWN-SYM")
        assert unp_h.unrealized_pnl is None
        assert unp_h.unrealized_pnl_contribution is None
        assert unp_h.cost_basis_weighted_return_contribution_percent is None

        # Priced holding checks (RELIANCE: cb 25000, mv 28000, pnl +3000)
        # Priced cost basis = 25,000; return contrib = (3000 / 25000) * 100 = 12.00%
        rel_h = next(h for h in analytics.holdings if h.symbol == "RELIANCE")
        assert rel_h.unrealized_pnl_contribution == Decimal("3000.00")
        assert rel_h.cost_basis_weighted_return_contribution_percent == Decimal("12.00")

        # Unpriced sector checks (Pharma has 0 priced holdings)
        sec_pharma = next(s for s in analytics.sector_allocations if s.sector == "Pharma")
        assert sec_pharma.priced_count == 0
        assert sec_pharma.unpriced_count == 1
        assert sec_pharma.unrealized_pnl is None
        assert sec_pharma.unrealized_pnl_percent is None
        assert sec_pharma.cost_basis_weighted_return_contribution_percent is None
        assert sec_pharma.allocation_percent is None  # no false 0% exposure

        # Priced sector checks (Energy)
        sec_energy = next(s for s in analytics.sector_allocations if s.sector == "Energy")
        assert sec_energy.unrealized_pnl == Decimal("3000.00")
        assert sec_energy.unrealized_pnl_percent == Decimal("12.00")
        assert sec_energy.cost_basis_weighted_return_contribution_percent == Decimal("12.00")


@pytest.mark.asyncio
async def test_empty_portfolio_and_zero_denominator_cases(test_db_setup):
    """
    Verifies that empty portfolios and zero-denominator cases safely return None
    without raising ZeroDivisionError.
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        p = await port_service.create_portfolio(PortfolioCreate(name="Empty Basket"))

        analytics_service = AnalyticsService(session)
        analytics = await analytics_service.calculate_portfolio_analytics(p.id)

        assert analytics is not None
        assert analytics.status == ValuationStatus.EMPTY
        assert analytics.concentration.effective_holdings_count is None
        assert analytics.concentration.concentration_tier is None
        assert analytics.sector_allocations == []
        assert analytics.holdings == []


@pytest.mark.asyncio
async def test_enh_and_concentration_tier_boundaries(test_db_setup):
    """
    Verifies that Effective Number of Holdings (ENH = 1 / HHI) and concentration tiers
    correctly enforce the documented boundaries:
    - LOW: HHI < 0.1500
    - MODERATE: 0.1500 <= HHI <= 0.2500
    - HIGH: HHI > 0.2500
    """
    session_factory, _ = test_db_setup

    # 1. Single holding: 100% weight -> HHI = 1.0000, ENH = 1.0000, tier = HIGH
    mock_single = MockCustomMarketDataProvider(
        {("STOCK1", "NSE"): Quote(symbol="STOCK1", current_price=Decimal("100.00"), status=QuoteStatus.AVAILABLE)}
    )
    async with session_factory() as session:
        port_service = PortfolioService(session)
        p1 = await port_service.create_portfolio(
            PortfolioCreate(
                name="Single Stock",
                holdings=[HoldingCreate(symbol="STOCK1", quantity=10, average_buy_price=Decimal("100.00"))],
            )
        )
        analytics_service = AnalyticsService(session, market_data_service=MarketDataService(provider=mock_single))
        a1 = await analytics_service.calculate_portfolio_analytics(p1.id)
        assert a1 is not None
        assert a1.concentration.herfindahl_index == Decimal("1.0000")
        assert a1.concentration.effective_holdings_count == Decimal("1.0000")
        assert a1.concentration.concentration_tier == "HIGH"

    # 2. 10 equally weighted holdings (each 10% weight):
    # share = 0.10, HHI = 10 * (0.10)^2 = 0.1000 (< 0.1500 -> LOW)
    # ENH = 1 / 0.1000 = 10.0000
    quotes_10 = {
        (f"SYM{i}", "NSE"): Quote(symbol=f"SYM{i}", current_price=Decimal("100.00"), status=QuoteStatus.AVAILABLE)
        for i in range(1, 11)
    }
    mock_10 = MockCustomMarketDataProvider(quotes_10)
    async with session_factory() as session:
        port_service = PortfolioService(session)
        p2 = await port_service.create_portfolio(
            PortfolioCreate(
                name="Ten Equal Basket",
                holdings=[
                    HoldingCreate(symbol=f"SYM{i}", quantity=10, average_buy_price=Decimal("100.00"))
                    for i in range(1, 11)
                ],
            )
        )
        analytics_service = AnalyticsService(session, market_data_service=MarketDataService(provider=mock_10))
        a2 = await analytics_service.calculate_portfolio_analytics(p2.id)
        assert a2 is not None
        assert a2.concentration.herfindahl_index == Decimal("0.1000")
        assert a2.concentration.effective_holdings_count == Decimal("10.0000")
        assert a2.concentration.concentration_tier == "LOW"

    # 3. 5 equally weighted holdings (each 20% weight):
    # share = 0.20, HHI = 5 * (0.20)^2 = 0.2000 (0.1500 <= HHI <= 0.2500 -> MODERATE)
    # ENH = 1 / 0.2000 = 5.0000
    quotes_5 = {
        (f"SYM{i}", "NSE"): Quote(symbol=f"SYM{i}", current_price=Decimal("100.00"), status=QuoteStatus.AVAILABLE)
        for i in range(1, 6)
    }
    mock_5 = MockCustomMarketDataProvider(quotes_5)
    async with session_factory() as session:
        port_service = PortfolioService(session)
        p3 = await port_service.create_portfolio(
            PortfolioCreate(
                name="Five Equal Basket",
                holdings=[
                    HoldingCreate(symbol=f"SYM{i}", quantity=10, average_buy_price=Decimal("100.00"))
                    for i in range(1, 6)
                ],
            )
        )
        analytics_service = AnalyticsService(session, market_data_service=MarketDataService(provider=mock_5))
        a3 = await analytics_service.calculate_portfolio_analytics(p3.id)
        assert a3 is not None
        assert a3.concentration.herfindahl_index == Decimal("0.2000")
        assert a3.concentration.effective_holdings_count == Decimal("5.0000")
        assert a3.concentration.concentration_tier == "MODERATE"


@pytest.mark.asyncio
async def test_contributions_distinct_from_static_allocations(test_db_setup):
    """
    Verifies that static market-value allocation (weight) and performance return contribution
    are distinct metrics with different semantics and values.
    For example, a high-weight position with flat price has return contribution = 0.00%.
    """
    session_factory, _ = test_db_setup

    mock_provider = MockCustomMarketDataProvider(
        {
            # RELIANCE: 80% of portfolio, flat price (0% return)
            ("RELIANCE", "NSE"): Quote(symbol="RELIANCE", current_price=Decimal("2000.00"), status=QuoteStatus.AVAILABLE),
            # TCS: 20% of portfolio, doubled in price (+100% return)
            ("TCS", "NSE"): Quote(symbol="TCS", current_price=Decimal("2000.00"), status=QuoteStatus.AVAILABLE),
        }
    )
    custom_md = MarketDataService(provider=mock_provider)

    async with session_factory() as session:
        port_service = PortfolioService(session)
        p = await port_service.create_portfolio(
            PortfolioCreate(
                name="Allocation vs Contribution Test",
                holdings=[
                    HoldingCreate(symbol="RELIANCE", quantity=40, average_buy_price=Decimal("2000.00")),  # cb 80,000, mv 80,000
                    HoldingCreate(symbol="TCS", quantity=20, average_buy_price=Decimal("1000.00")),       # cb 20,000, mv 40,000
                ],
            )
        )

        analytics_service = AnalyticsService(session, market_data_service=custom_md)
        analytics = await analytics_service.calculate_portfolio_analytics(p.id)

        assert analytics is not None
        # Total cb = 100,000, Total mv = 120,000. Portfolio return = +20.00%
        rel_h = next(h for h in analytics.holdings if h.symbol == "RELIANCE")
        tcs_h = next(h for h in analytics.holdings if h.symbol == "TCS")

        # Static Market Value Weights:
        # RELIANCE: 80,000 / 120,000 = 66.67%
        # TCS:      40,000 / 120,000 = 33.33%
        assert rel_h.market_value_weight_percent == Decimal("66.67")
        assert tcs_h.market_value_weight_percent == Decimal("33.33")

        # Return Contributions:
        # RELIANCE: P/L = 0 -> Contribution = 0.00% (even though it represents 66.67% of market value!)
        # TCS:      P/L = +20,000 -> Contribution = (20000 / 100000) * 100 = 20.00%
        assert rel_h.cost_basis_weighted_return_contribution_percent == Decimal("0.00")
        assert tcs_h.cost_basis_weighted_return_contribution_percent == Decimal("20.00")

        # Proves they are mathematically distinct
        assert rel_h.market_value_weight_percent != rel_h.cost_basis_weighted_return_contribution_percent
        assert tcs_h.market_value_weight_percent != tcs_h.cost_basis_weighted_return_contribution_percent
