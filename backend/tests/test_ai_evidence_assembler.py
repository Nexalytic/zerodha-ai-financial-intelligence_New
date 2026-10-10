from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List
import pytest

from app.core.cache import AsyncTTLCache
from app.models.portfolio import Portfolio
from app.providers.base import BaseMarketDataProvider, BaseNewsProvider
from app.schemas.ai_reasoning import PortfolioEvidenceBundle
from app.schemas.analytics import ValuationStatus
from app.schemas.market_data import NewsArticle, Quote, QuoteStatus
from app.schemas.portfolio import HoldingCreate, PortfolioCreate
from app.services.ai.evidence_assembler import EvidenceAssemblerService
from app.services.analytics_service import AnalyticsService
from app.services.market_data_service import MarketDataService
from app.services.news_service import NewsService
from app.services.portfolio_service import DEMO_PORTFOLIO_ID, PortfolioService


# ===========================================================================
# Test Providers (Mocks for local deterministic testing - ₹0 spend)
# ===========================================================================

class MockMarketDataProvider(BaseMarketDataProvider):
    """Configurable mock market data provider for unit testing."""

    def __init__(self, responses: Dict[str, Quote] = None, should_raise: bool = False):
        self.responses = responses or {}
        self.should_raise = should_raise

    async def get_quote(self, symbol: str, exchange: str = "NSE") -> Quote:
        if self.should_raise:
            raise RuntimeError(f"Connection timed out for provider on {symbol}")
        cleaned = symbol.strip().upper()
        if cleaned in self.responses:
            return self.responses[cleaned]
        return Quote(
            symbol=cleaned,
            exchange=exchange,
            current_price=None,
            status=QuoteStatus.UNAVAILABLE,
            is_simulated=True,
            explanation=f"Symbol '{cleaned}' not found in mock provider",
        )

    async def get_quotes(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, Quote]:
        return {s: await self.get_quote(s, exchange) for s in symbols}


class MockNewsProvider(BaseNewsProvider):
    """Configurable mock news provider for testing."""

    def __init__(self, articles: List[NewsArticle] = None, should_raise: bool = False):
        self.articles = articles or []
        self.should_raise = should_raise

    async def get_news_for_symbols(self, symbols: List[str], limit: int = 10) -> List[NewsArticle]:
        if self.should_raise:
            raise RuntimeError("News upstream feed unreachable")
        cleaned_symbols = {s.strip().upper() for s in symbols}
        matched = [
            a for a in self.articles
            if any(sym in cleaned_symbols for sym in a.related_symbols)
        ]
        return matched[:limit]

    async def get_market_news(self, limit: int = 10) -> List[NewsArticle]:
        if self.should_raise:
            raise RuntimeError("News upstream feed unreachable")
        return self.articles[:limit]


# ===========================================================================
# 1. Core Evidence Assembly Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_evidence_assembler_fully_priced_portfolio(test_db_setup):
    """
    Verify complete evidence assembly for fully priced portfolio:
    - Retains portfolio metadata and holdings.
    - Captures deterministic valuation and completeness metrics.
    - Builds market snapshot with fresh quote provenance.
    - Gathers relevant news articles.
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        portfolio = await port_service.create_portfolio(
            PortfolioCreate(
                name="Bluechip Growth",
                description="Core Indian equities",
                holdings=[
                    HoldingCreate(
                        symbol="RELIANCE",
                        exchange="NSE",
                        quantity=10,
                        average_buy_price=Decimal("2500.00"),
                        sector="Energy",
                    ),
                    HoldingCreate(
                        symbol="TCS",
                        exchange="NSE",
                        quantity=5,
                        average_buy_price=Decimal("3500.00"),
                        sector="Technology",
                    ),
                ],
            )
        )

        mock_market = MockMarketDataProvider(
            responses={
                "RELIANCE": Quote(
                    symbol="RELIANCE",
                    exchange="NSE",
                    current_price=Decimal("3000.00"),
                    change=Decimal("500.00"),
                    change_percent=Decimal("20.00"),
                    status=QuoteStatus.AVAILABLE,
                    is_simulated=True,
                    source="SIMULATED_DEMO_PROVIDER",
                ),
                "TCS": Quote(
                    symbol="TCS",
                    exchange="NSE",
                    current_price=Decimal("4000.00"),
                    change=Decimal("500.00"),
                    change_percent=Decimal("14.29"),
                    status=QuoteStatus.AVAILABLE,
                    is_simulated=True,
                    source="SIMULATED_DEMO_PROVIDER",
                ),
            }
        )
        mock_news = MockNewsProvider(
            articles=[
                NewsArticle(
                    id="art-rel-1",
                    title="Reliance Announces Renewable Expansion",
                    summary="Major green hydrogen project commissioned.",
                    source="Simulated Financial News",
                    related_symbols=["RELIANCE"],
                )
            ]
        )

        market_service = MarketDataService(provider=mock_market)
        news_service = NewsService(provider=mock_news)
        assembler = EvidenceAssemblerService(
            session=session,
            market_data_service=market_service,
            news_service=news_service,
        )

        bundle = await assembler.assemble_portfolio_evidence(portfolio.id)

        assert bundle is not None
        assert bundle.portfolio_id == portfolio.id
        assert bundle.portfolio_name == "Bluechip Growth"
        assert bundle.is_sample_portfolio is False

        # Valuation checks: 10 * 3000 + 5 * 4000 = 30000 + 20000 = 50000 market value
        # Cost basis: 10 * 2500 + 5 * 3500 = 25000 + 17500 = 42500 cost basis
        assert bundle.valuation.total_market_value == Decimal("50000.00")
        assert bundle.valuation.total_cost_basis == Decimal("42500.00")
        assert bundle.valuation.unrealized_pnl == Decimal("7500.00")

        # Completeness
        assert bundle.completeness.is_complete is True
        assert bundle.completeness.completeness_ratio == Decimal("1.0000")
        assert bundle.completeness.unpriced_holdings_count == 0
        assert len(bundle.completeness.unpriced_positions) == 0

        # Market Snapshot
        assert bundle.market_snapshot.total_symbols == 2
        assert "RELIANCE" in bundle.market_snapshot.quotes
        assert "TCS" in bundle.market_snapshot.quotes
        assert bundle.market_snapshot.quotes["RELIANCE"].current_price == Decimal("3000.00")
        assert bundle.market_snapshot.quotes["RELIANCE"].is_stale is False

        # News Articles
        assert len(bundle.news_articles) == 1
        assert bundle.news_articles[0].id == "art-rel-1"
        assert "RELIANCE" in bundle.news_articles[0].related_symbols

        # Structural Risk Assessment
        assert bundle.risk_assessment.composite_risk_score is not None
        assert bundle.risk_assessment.risk_tier in ["LOW", "MODERATE", "ELEVATED", "HIGH"]
        assert bundle.risk_assessment.assessment_status == "COMPLETE"

        # Timestamp and disclaimers
        assert bundle.evidence_timestamp is not None
        assert bundle.evidence_timestamp.tzinfo is not None
        assert "Not SEBI-registered" in bundle.disclaimer


@pytest.mark.asyncio
async def test_evidence_assembler_empty_portfolio(test_db_setup):
    """Verify evidence assembler safely handles an empty portfolio."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        portfolio = await port_service.create_portfolio(
            PortfolioCreate(name="Empty Savings", holdings=[])
        )

        assembler = EvidenceAssemblerService(session=session)
        bundle = await assembler.assemble_portfolio_evidence(portfolio.id)

        assert bundle is not None
        assert bundle.portfolio_id == portfolio.id
        assert bundle.valuation.total_market_value == Decimal("0.00")
        assert bundle.valuation.unrealized_pnl is None

        assert bundle.completeness.is_complete is False
        assert bundle.completeness.total_holdings_count == 0
        assert bundle.completeness.priced_holdings_count == 0

        assert bundle.market_snapshot.total_symbols == 0
        assert len(bundle.market_snapshot.quotes) == 0
        assert len(bundle.news_articles) == 0
        assert len(bundle.sector_allocations) == 0
        assert bundle.risk_assessment.composite_risk_score is None
        assert bundle.risk_assessment.assessment_status == "EMPTY"


@pytest.mark.asyncio
async def test_evidence_assembler_wholly_unpriced_portfolio(test_db_setup):
    """
    Verify wholly unpriced portfolio:
    - Retains cost basis.
    - Market value is 0.00, unrealized_pnl is None (distinguished from zero return).
    - Unpriced positions are completely enumerated.
    - Prices are NOT fabricated.
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        portfolio = await port_service.create_portfolio(
            PortfolioCreate(
                name="Unlisted Microcap Basket",
                holdings=[
                    HoldingCreate(
                        symbol="UNLISTED-A",
                        exchange="NSE",
                        quantity=100,
                        average_buy_price=Decimal("50.00"),
                        sector="Industrials",
                    ),
                    HoldingCreate(
                        symbol="UNLISTED-B",
                        exchange="NSE",
                        quantity=200,
                        average_buy_price=Decimal("25.00"),
                        sector="Materials",
                    ),
                ],
            )
        )

        # Mock market data returns UNAVAILABLE for both
        mock_market = MockMarketDataProvider(responses={})
        market_service = MarketDataService(provider=mock_market)
        assembler = EvidenceAssemblerService(
            session=session,
            market_data_service=market_service,
        )

        bundle = await assembler.assemble_portfolio_evidence(portfolio.id)

        assert bundle is not None
        assert bundle.risk_assessment.assessment_status == "UNVALUED"
        assert bundle.valuation.total_cost_basis == Decimal("10000.00")
        assert bundle.valuation.total_market_value == Decimal("0.00")
        assert bundle.valuation.unrealized_pnl is None
        assert bundle.valuation.unrealized_pnl_percent is None

        assert bundle.completeness.is_complete is False
        assert bundle.completeness.priced_holdings_count == 0
        assert bundle.completeness.unpriced_holdings_count == 2
        assert len(bundle.completeness.unpriced_positions) == 2
        unpriced_syms = [p.symbol for p in bundle.completeness.unpriced_positions]
        assert "UNLISTED-A" in unpriced_syms
        assert "UNLISTED-B" in unpriced_syms

        # Quotes have current_price=None, not 0.00
        for quote in bundle.market_snapshot.quotes.values():
            assert quote.current_price is None
            assert quote.status == QuoteStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_evidence_assembler_partially_priced_portfolio(test_db_setup):
    """
    Verify partially priced portfolio:
    - Priced positions reflected in market value.
    - Unpriced positions recorded in completeness.
    - completeness_ratio is accurately calculated.
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        portfolio = await port_service.create_portfolio(
            PortfolioCreate(
                name="Mixed Basket",
                holdings=[
                    HoldingCreate(
                        symbol="PRICED-SYM",
                        exchange="NSE",
                        quantity=10,
                        average_buy_price=Decimal("100.00"),
                        sector="Energy",
                    ),
                    HoldingCreate(
                        symbol="UNPRICED-SYM",
                        exchange="NSE",
                        quantity=20,
                        average_buy_price=Decimal("50.00"),
                        sector="IT",
                    ),
                ],
            )
        )

        mock_market = MockMarketDataProvider(
            responses={
                "PRICED-SYM": Quote(
                    symbol="PRICED-SYM",
                    exchange="NSE",
                    current_price=Decimal("120.00"),
                    status=QuoteStatus.AVAILABLE,
                    is_simulated=True,
                )
            }
        )
        market_service = MarketDataService(provider=mock_market)
        assembler = EvidenceAssemblerService(
            session=session,
            market_data_service=market_service,
        )

        bundle = await assembler.assemble_portfolio_evidence(portfolio.id)

        assert bundle is not None
        assert bundle.risk_assessment.assessment_status == "PARTIAL"
        assert bundle.valuation.total_cost_basis == Decimal("2000.00")
        assert bundle.valuation.total_market_value == Decimal("1200.00")
        assert bundle.valuation.priced_cost_basis == Decimal("1000.00")
        assert bundle.completeness.unpriced_positions[0].cost_basis == Decimal("1000.00")
        assert bundle.valuation.unrealized_pnl == Decimal("200.00")

        assert bundle.completeness.is_complete is False
        assert bundle.completeness.total_holdings_count == 2
        assert bundle.completeness.priced_holdings_count == 1
        assert bundle.completeness.unpriced_holdings_count == 1
        assert bundle.completeness.completeness_ratio == Decimal("0.5000")


@pytest.mark.asyncio
async def test_evidence_assembler_stale_market_data(test_db_setup):
    """
    Verify stale market data:
    - Provider failure falls back to expired cached quote.
    - Quote is explicitly marked is_stale=True.
    - Portfolio completeness indicates has_stale_prices=True.
    - Stale quote is not misrepresented as fresh.
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        portfolio = await port_service.create_portfolio(
            PortfolioCreate(
                name="Stale Price Test",
                holdings=[
                    HoldingCreate(
                        symbol="TCS",
                        exchange="NSE",
                        quantity=10,
                        average_buy_price=Decimal("3500.00"),
                        sector="IT",
                    )
                ],
            )
        )

        # Pre-seed cache with an expired quote
        cache = AsyncTTLCache(default_ttl_seconds=60.0)
        stale_quote = Quote(
            symbol="TCS",
            exchange="NSE",
            current_price=Decimal("3800.00"),
            status=QuoteStatus.AVAILABLE,
            is_simulated=True,
        )
        await cache.set("quote:NSE:TCS", stale_quote, ttl_seconds=-10.0)  # Expired immediately

        # Mock provider that fails
        mock_provider = MockMarketDataProvider(should_raise=True)
        market_service = MarketDataService(provider=mock_provider, cache=cache)

        assembler = EvidenceAssemblerService(
            session=session,
            market_data_service=market_service,
        )

        bundle = await assembler.assemble_portfolio_evidence(portfolio.id)

        assert bundle is not None
        assert bundle.completeness.has_stale_prices is True
        tcs_quote = bundle.market_snapshot.quotes.get("TCS")
        assert tcs_quote is not None
        assert tcs_quote.is_stale is True
        assert tcs_quote.cache_hit is False
        assert tcs_quote.current_price == Decimal("3800.00")


@pytest.mark.asyncio
async def test_evidence_assembler_market_provider_unavailable(test_db_setup):
    """
    Verify that when market provider fails with empty cache:
    - Evidence assembly succeeds without throwing exceptions.
    - Quotes are marked with status=ERROR, current_price=None.
    - Holding is classified as unpriced.
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        portfolio = await port_service.create_portfolio(
            PortfolioCreate(
                name="Provider Outage Test",
                holdings=[
                    HoldingCreate(
                        symbol="INFY",
                        exchange="NSE",
                        quantity=15,
                        average_buy_price=Decimal("1500.00"),
                        sector="IT",
                    )
                ],
            )
        )

        failing_provider = MockMarketDataProvider(should_raise=True)
        market_service = MarketDataService(provider=failing_provider)
        assembler = EvidenceAssemblerService(
            session=session,
            market_data_service=market_service,
        )

        bundle = await assembler.assemble_portfolio_evidence(portfolio.id)

        assert bundle is not None
        infy_quote = bundle.market_snapshot.quotes.get("INFY")
        assert infy_quote is not None
        assert infy_quote.status == QuoteStatus.ERROR
        assert infy_quote.current_price is None

        assert bundle.completeness.unpriced_holdings_count == 1
        assert bundle.risk_assessment.assessment_status == "UNVALUED"


@pytest.mark.asyncio
async def test_evidence_assembler_news_provider_unavailable(test_db_setup):
    """
    Verify news provider failure does not break portfolio evidence assembly:
    - Error is logged and caught.
    - news_articles defaults to empty list.
    - Other evidence metrics assemble successfully.
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        portfolio = await port_service.create_portfolio(
            PortfolioCreate(
                name="News Outage Test",
                holdings=[
                    HoldingCreate(
                        symbol="RELIANCE",
                        exchange="NSE",
                        quantity=10,
                        average_buy_price=Decimal("2500.00"),
                        sector="Energy",
                    )
                ],
            )
        )

        mock_market = MockMarketDataProvider(
            responses={
                "RELIANCE": Quote(
                    symbol="RELIANCE",
                    exchange="NSE",
                    current_price=Decimal("2800.00"),
                    status=QuoteStatus.AVAILABLE,
                    is_simulated=True,
                )
            }
        )
        failing_news = MockNewsProvider(should_raise=True)

        assembler = EvidenceAssemblerService(
            session=session,
            market_data_service=MarketDataService(provider=mock_market),
            news_service=NewsService(provider=failing_news),
        )

        bundle = await assembler.assemble_portfolio_evidence(portfolio.id)

        assert bundle is not None
        assert bundle.risk_assessment.assessment_status == "COMPLETE"
        assert bundle.news_articles == []


@pytest.mark.asyncio
async def test_evidence_assembler_no_news_flag(test_db_setup):
    """Verify include_news=False omits news retrieval completely."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        portfolio = await port_service.create_portfolio(
            PortfolioCreate(
                name="No News Test",
                holdings=[
                    HoldingCreate(
                        symbol="TCS",
                        exchange="NSE",
                        quantity=10,
                        average_buy_price=Decimal("3500.00"),
                        sector="IT",
                    )
                ],
            )
        )

        mock_market = MockMarketDataProvider(
            responses={
                "TCS": Quote(
                    symbol="TCS",
                    exchange="NSE",
                    current_price=Decimal("3900.00"),
                    status=QuoteStatus.AVAILABLE,
                    is_simulated=True,
                )
            }
        )
        mock_news = MockNewsProvider(
            articles=[
                NewsArticle(
                    id="art-1",
                    title="TCS Quarterly Results",
                    summary="Strong margin growth.",
                    source="Wire",
                    related_symbols=["TCS"],
                )
            ]
        )

        assembler = EvidenceAssemblerService(
            session=session,
            market_data_service=MarketDataService(provider=mock_market),
            news_service=NewsService(provider=mock_news),
        )

        bundle = await assembler.assemble_portfolio_evidence(portfolio.id, include_news=False)

        assert bundle is not None
        assert bundle.news_articles == []


@pytest.mark.asyncio
async def test_evidence_assembler_simulated_versus_non_simulated_provenance(test_db_setup):
    """
    Verify simulation flags are faithfully preserved:
    - Simulated quote keeps is_simulated=True.
    - Non-simulated quote keeps is_simulated=False.
    - Neither is converted or relabeled.
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        portfolio = await port_service.create_portfolio(
            PortfolioCreate(
                name="Provenance Test",
                holdings=[
                    HoldingCreate(
                        symbol="SIM-SYM",
                        exchange="NSE",
                        quantity=10,
                        average_buy_price=Decimal("100.00"),
                        sector="Finance",
                    ),
                    HoldingCreate(
                        symbol="REAL-SYM",
                        exchange="NSE",
                        quantity=10,
                        average_buy_price=Decimal("200.00"),
                        sector="Finance",
                    ),
                ],
            )
        )

        mock_market = MockMarketDataProvider(
            responses={
                "SIM-SYM": Quote(
                    symbol="SIM-SYM",
                    exchange="NSE",
                    current_price=Decimal("110.00"),
                    status=QuoteStatus.AVAILABLE,
                    is_simulated=True,
                    source="SIMULATED_DEMO_PROVIDER",
                ),
                "REAL-SYM": Quote(
                    symbol="REAL-SYM",
                    exchange="NSE",
                    current_price=Decimal("220.00"),
                    status=QuoteStatus.AVAILABLE,
                    is_simulated=False,
                    source="REAL_EXCHANGE_FEED",
                ),
            }
        )

        assembler = EvidenceAssemblerService(
            session=session,
            market_data_service=MarketDataService(provider=mock_market),
        )

        bundle = await assembler.assemble_portfolio_evidence(portfolio.id)

        assert bundle is not None
        sim_q = bundle.market_snapshot.quotes["SIM-SYM"]
        real_q = bundle.market_snapshot.quotes["REAL-SYM"]

        assert sim_q.is_simulated is True
        assert sim_q.source == "SIMULATED_DEMO_PROVIDER"

        assert real_q.is_simulated is False
        assert real_q.source == "REAL_EXCHANGE_FEED"


@pytest.mark.asyncio
async def test_evidence_assembler_insufficient_historical_data(test_db_setup):
    """
    Verify historical risk metrics state:
    - INSUFFICIENT_HISTORY data_status is preserved.
    - Metrics are None, not 0.00 (which would falsely imply zero volatility).
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        portfolio = await port_service.create_portfolio(
            PortfolioCreate(
                name="History Status Test",
                holdings=[
                    HoldingCreate(
                        symbol="RELIANCE",
                        exchange="NSE",
                        quantity=10,
                        average_buy_price=Decimal("2500.00"),
                        sector="Energy",
                    )
                ],
            )
        )

        mock_market = MockMarketDataProvider(
            responses={
                "RELIANCE": Quote(
                    symbol="RELIANCE",
                    exchange="NSE",
                    current_price=Decimal("2750.00"),
                    status=QuoteStatus.AVAILABLE,
                    is_simulated=True,
                )
            }
        )

        assembler = EvidenceAssemblerService(
            session=session,
            market_data_service=MarketDataService(provider=mock_market),
        )

        bundle = await assembler.assemble_portfolio_evidence(portfolio.id)

        assert bundle is not None
        assert bundle.historical_risk.data_status == "INSUFFICIENT_HISTORY"
        assert bundle.historical_risk.annualized_volatility_percent is None
        assert bundle.historical_risk.maximum_drawdown_percent is None
        assert bundle.historical_risk.beta is None


@pytest.mark.asyncio
async def test_evidence_assembler_consistency_with_analytics_service(test_db_setup):
    """
    Verify that evidence bundle metrics are identical to direct AnalyticsService calculations.
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        demo_port, _ = await port_service.seed_demo_portfolio()

        market_service = MarketDataService()
        analytics_service = AnalyticsService(session=session, market_data_service=market_service)
        direct_analytics = await analytics_service.calculate_portfolio_analytics(demo_port.id)

        assembler = EvidenceAssemblerService(
            session=session,
            market_data_service=market_service,
            analytics_service=analytics_service,
        )
        bundle = await assembler.assemble_portfolio_evidence(demo_port.id)

        assert bundle is not None
        assert direct_analytics is not None

        # Exact financial equality
        assert bundle.valuation.total_market_value == direct_analytics.valuation.total_market_value
        assert bundle.valuation.total_cost_basis == direct_analytics.valuation.total_cost_basis
        assert bundle.valuation.unrealized_pnl == direct_analytics.valuation.unrealized_pnl
        assert bundle.completeness.completeness_ratio == direct_analytics.completeness.completeness_ratio
        assert bundle.concentration.herfindahl_index == direct_analytics.concentration.herfindahl_index
        assert bundle.risk_assessment.composite_risk_score == direct_analytics.risk_assessment.composite_risk_score


@pytest.mark.asyncio
async def test_evidence_assembler_nonexistent_portfolio_returns_none(test_db_setup):
    """Verify non-existent portfolio ID returns None gracefully."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        assembler = EvidenceAssemblerService(session=session)
        bundle = await assembler.assemble_portfolio_evidence("00000000-0000-0000-0000-000000000099")
        assert bundle is None


@pytest.mark.asyncio
async def test_evidence_assembler_assemble_from_analytics_helper(test_db_setup):
    """Verify assemble_from_analytics generates consistent evidence from precomputed analytics."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        portfolio = await port_service.create_portfolio(
            PortfolioCreate(
                name="Direct Analytics Test",
                holdings=[
                    HoldingCreate(
                        symbol="TCS",
                        exchange="NSE",
                        quantity=5,
                        average_buy_price=Decimal("3500.00"),
                        sector="IT",
                    )
                ],
            )
        )

        mock_market = MockMarketDataProvider(
            responses={
                "TCS": Quote(
                    symbol="TCS",
                    exchange="NSE",
                    current_price=Decimal("3800.00"),
                    status=QuoteStatus.AVAILABLE,
                    is_simulated=True,
                )
            }
        )
        market_service = MarketDataService(provider=mock_market)
        analytics_service = AnalyticsService(session=session, market_data_service=market_service)
        analytics = await analytics_service.calculate_portfolio_analytics(portfolio.id)

        assembler = EvidenceAssemblerService(
            session=session,
            market_data_service=market_service,
        )

        bundle = await assembler.assemble_from_analytics(analytics=analytics)

        assert bundle is not None
        assert bundle.portfolio_id == portfolio.id
        assert bundle.valuation.total_market_value == Decimal("19000.00")
        assert "TCS" in bundle.market_snapshot.quotes
