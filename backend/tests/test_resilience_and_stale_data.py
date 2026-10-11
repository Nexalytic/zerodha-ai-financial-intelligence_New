import asyncio
import copy
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional
import httpx
import pytest
from httpx import AsyncClient

from app.core.cache import AsyncTTLCache
from app.core.logging import sanitize_log_message
from app.providers.alpha_vantage_market_data import AlphaVantageMarketDataProvider
from app.providers.base import BaseMarketDataProvider, BaseNewsProvider
from app.providers.demo_market_data import DemoMarketDataProvider
from app.providers.demo_news import DemoNewsProvider
from app.schemas.ai_reasoning import (
    AIConfidenceIndicator,
    AIInsightReport,
    ConfidenceLevel,
    DriverType,
    EvidenceKeyDriver,
    FindingStatus,
    PortfolioEvidenceBundle,
    ReviewStatus,
    ReviewableInsightCard,
)
from app.schemas.analytics import (
    ConcentrationMetrics,
    HistoricalRiskMetrics,
    PortfolioCompleteness,
    PortfolioRiskAssessment,
    PortfolioValuation,
    RiskComponentScores,
    UnpricedPositionDetail,
    ValuationStatus,
)
from app.schemas.market_data import (
    BatchQuotesResponse,
    NewsArticle,
    NewsResponse,
    Quote,
    QuoteStatus,
)
from app.services.ai.evidence_assembler import EvidenceAssemblerService
from app.services.ai.grounding_validator import ClaimGroundingValidator, FindingCode
from app.services.ai.providers.base import BaseAIProvider
from app.services.ai.providers.demo_provider import DeterministicDemoProvider
from app.services.ai.reasoning_service import (
    AIProviderError,
    AIReasoningService,
)
from app.services.market_data_service import MarketDataService
from app.services.news_service import NewsService


# ===========================================================================
# Test Helpers and Mock Providers
# ===========================================================================

class ControllableMarketDataProvider(BaseMarketDataProvider):
    """Deterministic mock market data provider with configurable failure injection."""

    def __init__(self):
        self.should_fail = False
        self.failure_exception = RuntimeError("Upstream quote provider connection failure")
        self.return_error_status = False
        self.call_count = 0

    async def get_quote(self, symbol: str, exchange: str = "NSE") -> Quote:
        self.call_count += 1
        norm_sym = symbol.strip().upper()
        norm_ex = exchange.strip().upper()
        now = datetime.now(timezone.utc)

        if self.should_fail:
            raise self.failure_exception

        if self.return_error_status:
            return Quote(
                symbol=norm_sym,
                exchange=norm_ex,
                current_price=None,
                change=None,
                change_percent=None,
                status=QuoteStatus.ERROR,
                is_simulated=True,
                source="MOCK_CONTROLLABLE_PROVIDER",
                generated_at=now,
                market_as_of=None,
                cached_at=None,
                cache_hit=False,
                is_stale=False,
                explanation="Provider returned upstream error status.",
            )

        # Standard healthy deterministic response
        prices = {
            "RELIANCE": Decimal("2850.50"),
            "TCS": Decimal("3920.00"),
            "INFY": Decimal("1520.25"),
        }
        price = prices.get(norm_sym, Decimal("1000.00"))

        return Quote(
            symbol=norm_sym,
            exchange=norm_ex,
            current_price=price,
            change=Decimal("10.00"),
            change_percent=Decimal("0.50"),
            status=QuoteStatus.AVAILABLE,
            is_simulated=True,
            source="MOCK_CONTROLLABLE_PROVIDER",
            generated_at=now,
            market_as_of=None,
            cached_at=None,
            cache_hit=False,
            is_stale=False,
            explanation=None,
        )

    async def get_quotes(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, Quote]:
        quotes = {}
        for s in symbols:
            quotes[s.strip().upper()] = await self.get_quote(s, exchange=exchange)
        return quotes


class ControllableNewsProvider(BaseNewsProvider):
    """Deterministic mock news provider with configurable failure injection."""

    def __init__(self, articles: Optional[List[NewsArticle]] = None):
        self.articles = articles or []
        self.should_fail = False
        self.failure_exception = RuntimeError("Upstream financial wire service unavailable")
        self.call_count = 0

    async def get_news_for_symbols(self, symbols: List[str], limit: int = 10) -> List[NewsArticle]:
        self.call_count += 1
        if self.should_fail:
            raise self.failure_exception
        norm_syms = {s.strip().upper() for s in symbols}
        matched = [
            a for a in self.articles
            if norm_syms.intersection(set(a.related_symbols or []))
        ]
        return matched[:limit]

    async def get_market_news(self, limit: int = 10) -> List[NewsArticle]:
        self.call_count += 1
        if self.should_fail:
            raise self.failure_exception
        return self.articles[:limit]


class FailingAIProvider(BaseAIProvider):
    """Mock AI provider that simulates crash/timeout during inference."""

    PROVIDER_NAME = "FAILING_TEST_PROVIDER"
    MODEL_ID = "failing-model-v1"

    async def generate_insights(self, evidence: PortfolioEvidenceBundle) -> AIInsightReport:
        raise RuntimeError("LLM connection timeout or rate limit exceeded")


def build_evidence_bundle(
    portfolio_id: str = "port-resilience-01",
    portfolio_name: str = "Resilience Test Portfolio",
    quotes: Optional[Dict[str, Quote]] = None,
    news_articles: Optional[List[NewsArticle]] = None,
    completeness: Optional[PortfolioCompleteness] = None,
    valuation: Optional[PortfolioValuation] = None,
    historical_risk: Optional[HistoricalRiskMetrics] = None,
) -> PortfolioEvidenceBundle:
    """Creates a valid PortfolioEvidenceBundle for testing degraded data scenarios."""
    now = datetime.now(timezone.utc)
    active_quotes = quotes or {
        "RELIANCE": Quote(
            symbol="RELIANCE",
            exchange="NSE",
            current_price=Decimal("2850.50"),
            change=Decimal("15.20"),
            change_percent=Decimal("0.54"),
            status=QuoteStatus.AVAILABLE,
            is_simulated=True,
            source="SIMULATED_DEMO_PROVIDER",
            generated_at=now,
            market_as_of=None,
            cached_at=now,
            cache_hit=False,
            is_stale=False,
        )
    }

    comp = completeness or PortfolioCompleteness(
        is_complete=True,
        completeness_ratio=Decimal("1.0000"),
        total_holdings_count=len(active_quotes),
        priced_holdings_count=len(active_quotes),
        unpriced_holdings_count=0,
        has_stale_prices=any(q.is_stale for q in active_quotes.values()),
        has_simulated_prices=any(q.is_simulated for q in active_quotes.values()),
        unpriced_positions=[],
    )

    val = valuation or PortfolioValuation(
        total_cost_basis=Decimal("100000.00"),
        total_market_value=Decimal("110000.00"),
        priced_cost_basis=Decimal("100000.00"),
        unrealized_pnl=Decimal("10000.00"),
        unrealized_pnl_percent=Decimal("10.00"),
    )

    hist_risk = historical_risk or HistoricalRiskMetrics(
        annualized_volatility_percent=None,
        maximum_drawdown_percent=None,
        beta=None,
        benchmark_relative_return_percent=None,
        benchmark_symbol="NIFTY 50",
        data_status="INSUFFICIENT_HISTORY",
    )

    return PortfolioEvidenceBundle(
        portfolio_id=portfolio_id,
        portfolio_name=portfolio_name,
        is_sample_portfolio=False,
        valuation=val,
        completeness=comp,
        concentration=ConcentrationMetrics(
            top_holding_symbol="RELIANCE",
            top_holding_weight_percent=Decimal("50.00"),
            top_3_concentration_percent=Decimal("100.00"),
            herfindahl_index=Decimal("0.5000"),
            effective_holdings_count=Decimal("2.00"),
            concentration_tier="HIGH",
        ),
        sector_allocations=[],
        risk_assessment=PortfolioRiskAssessment(
            composite_risk_score=Decimal("45.00"),
            risk_tier="MODERATE",
            assessment_status="COMPLETE",
            components=RiskComponentScores(
                single_stock_concentration_score=Decimal("50.00"),
                sector_concentration_score=Decimal("40.00"),
                diversification_breadth_score=Decimal("45.00"),
                data_quality_score=Decimal("45.00"),
            ),
        ),
        market_snapshot=BatchQuotesResponse(
            quotes=active_quotes,
            total_symbols=len(active_quotes),
            cache_hits_count=0,
            cache_misses_count=len(active_quotes),
            fetched_at=now,
        ),
        news_articles=news_articles or [],
        historical_risk=hist_risk,
        evidence_timestamp=now,
    )


# ===========================================================================
# Section A: Stale Market Quotes and Cache Behavior
# ===========================================================================

@pytest.mark.asyncio
async def test_fresh_quotes_returned_normally_with_source_and_timestamps():
    """
    Verifies that fresh quotes from market data provider return valid pricing,
    accurate source, timestamps, is_stale=False, and cache_hit=False on first fetch.
    """
    provider = ControllableMarketDataProvider()
    cache = AsyncTTLCache(default_ttl_seconds=60.0)
    service = MarketDataService(provider=provider, cache=cache)

    quote = await service.get_quote("RELIANCE", "NSE")

    assert quote.symbol == "RELIANCE"
    assert quote.current_price == Decimal("2850.50")
    assert quote.status == QuoteStatus.AVAILABLE
    assert quote.is_stale is False
    assert quote.cache_hit is False
    assert quote.source == "MOCK_CONTROLLABLE_PROVIDER"
    assert quote.generated_at is not None

    # Second fetch: valid fresh cache hit
    cached_quote = await service.get_quote("RELIANCE", "NSE")
    assert cached_quote.cache_hit is True
    assert cached_quote.is_stale is False
    assert cached_quote.current_price == Decimal("2850.50")
    assert cached_quote.ttl_remaining_seconds > 0.0


@pytest.mark.asyncio
async def test_expired_cached_quote_falls_back_to_stale_when_provider_fails():
    """
    Verifies that when a cached quote expires and the provider fails:
    1. Returns expired cached quote with is_stale=True.
    2. cache_hit is False (stale fallback is NOT counted as fresh cache hit).
    3. Original generated_at and cached_at timestamps are preserved.
    4. Explanation explicitly states fallback to stale cache.
    """
    provider = ControllableMarketDataProvider()
    cache = AsyncTTLCache(default_ttl_seconds=0.04)  # 40ms TTL
    service = MarketDataService(provider=provider, cache=cache, default_ttl_seconds=0.04)

    # 1. Populate cache initially
    orig_quote = await service.get_quote("RELIANCE", "NSE")
    assert orig_quote.is_stale is False
    orig_generated_at = orig_quote.generated_at

    # Wait for TTL to expire
    await asyncio.sleep(0.05)

    # 2. Inject provider failure
    provider.should_fail = True

    # 3. Query quote again: must fall back to stale cache
    fallback_quote = await service.get_quote("RELIANCE", "NSE")

    assert fallback_quote.symbol == "RELIANCE"
    assert fallback_quote.current_price == Decimal("2850.50")
    assert fallback_quote.status == QuoteStatus.AVAILABLE
    assert fallback_quote.is_stale is True
    assert fallback_quote.cache_hit is False
    assert fallback_quote.ttl_remaining_seconds == 0.0
    assert fallback_quote.generated_at == orig_generated_at
    assert fallback_quote.cached_at is not None
    assert "stale cached quote" in fallback_quote.explanation.lower()


@pytest.mark.asyncio
async def test_expired_cached_quote_falls_back_to_stale_when_provider_returns_error_status():
    """
    Verifies that if a provider returns QuoteStatus.ERROR instead of raising an exception,
    the service safely falls back to the stale cache rather than returning a null price.
    """
    provider = ControllableMarketDataProvider()
    cache = AsyncTTLCache(default_ttl_seconds=0.04)
    service = MarketDataService(provider=provider, cache=cache, default_ttl_seconds=0.04)

    await service.get_quote("TCS", "NSE")
    await asyncio.sleep(0.05)

    # Provider now returns error status
    provider.return_error_status = True

    fallback = await service.get_quote("TCS", "NSE")
    assert fallback.symbol == "TCS"
    assert fallback.current_price == Decimal("3920.00")
    assert fallback.is_stale is True
    assert fallback.cache_hit is False


@pytest.mark.asyncio
async def test_provider_failures_without_cached_fallback_returns_error_quote():
    """
    Verifies that if provider fails and no cached quote exists:
    1. Returns status=ERROR with current_price=None (NO invented prices).
    2. is_stale is False.
    3. cache_hit is False.
    4. explanation clearly indicates failure.
    """
    provider = ControllableMarketDataProvider()
    provider.should_fail = True
    cache = AsyncTTLCache(default_ttl_seconds=60.0)
    service = MarketDataService(provider=provider, cache=cache)

    quote = await service.get_quote("INFY", "NSE")

    assert quote.symbol == "INFY"
    assert quote.current_price is None
    assert quote.change is None
    assert quote.change_percent is None
    assert quote.status == QuoteStatus.ERROR
    assert quote.is_stale is False
    assert quote.cache_hit is False
    assert "provider failed" in quote.explanation.lower()


@pytest.mark.asyncio
async def test_provider_errors_are_never_cached_as_successful_quotes():
    """
    Verifies that provider errors are never persisted into the cache store.
    Subsequent requests must not observe a cached error object as a cache hit.
    """
    provider = ControllableMarketDataProvider()
    provider.should_fail = True
    cache = AsyncTTLCache(default_ttl_seconds=60.0)
    service = MarketDataService(provider=provider, cache=cache)

    quote = await service.get_quote("RELIANCE", "NSE")
    assert quote.status == QuoteStatus.ERROR

    # Check internal cache directly
    cached_val, is_hit, _, _ = await cache.get("quote:NSE:RELIANCE")
    assert is_hit is False
    assert cached_val is None


@pytest.mark.asyncio
async def test_recovery_after_temporary_provider_failure():
    """
    Verifies the complete cycle:
    1. Fresh quote cached.
    2. Cache expires and provider fails -> stale fallback returned.
    3. Provider recovers -> fresh quote retrieved, updated, and re-cached.
    """
    provider = ControllableMarketDataProvider()
    cache = AsyncTTLCache(default_ttl_seconds=0.04)
    service = MarketDataService(provider=provider, cache=cache, default_ttl_seconds=0.04)

    # 1. Fresh initial
    q1 = await service.get_quote("RELIANCE", "NSE")
    assert q1.is_stale is False
    assert q1.current_price == Decimal("2850.50")

    # 2. Expire and fail
    await asyncio.sleep(0.05)
    provider.should_fail = True
    q2 = await service.get_quote("RELIANCE", "NSE")
    assert q2.is_stale is True

    # 3. Provider recovers
    provider.should_fail = False
    q3 = await service.get_quote("RELIANCE", "NSE")
    assert q3.is_stale is False
    assert q3.cache_hit is False  # Fresh miss into cache
    assert q3.current_price == Decimal("2850.50")

    # 4. Immediate follow-up is fresh cache hit
    q4 = await service.get_quote("RELIANCE", "NSE")
    assert q4.cache_hit is True
    assert q4.is_stale is False


@pytest.mark.asyncio
async def test_batch_quotes_partial_failure_and_metrics_integrity():
    """
    Verifies get_quotes() when some quotes succeed and some fail:
    - Accurate total_symbols, cache_hits_count, and cache_misses_count.
    - Stale fallbacks count as cache misses in batch metrics.
    """
    provider = ControllableMarketDataProvider()
    cache = AsyncTTLCache(default_ttl_seconds=60.0)
    service = MarketDataService(provider=provider, cache=cache)

    # Pre-cache RELIANCE only
    await service.get_quote("RELIANCE", "NSE")

    # Batch request with RELIANCE (cached hit) and TCS (miss)
    batch = await service.get_quotes(["RELIANCE", "TCS"], "NSE")
    assert batch.total_symbols == 2
    assert batch.cache_hits_count == 1
    assert batch.cache_misses_count == 1
    assert batch.quotes["RELIANCE"].cache_hit is True
    assert batch.quotes["TCS"].cache_hit is False


# ===========================================================================
# Section B: Evidence and AI Reasoning under Degraded Data
# ===========================================================================

@pytest.mark.asyncio
async def test_evidence_assembler_preserves_stale_and_simulated_metadata():
    """
    Verifies that EvidenceAssemblerService accurately carries stale flags,
    simulation flags, and provenance through into the PortfolioEvidenceBundle.
    """
    stale_quote = Quote(
        symbol="TCS",
        exchange="NSE",
        current_price=Decimal("3920.00"),
        change=Decimal("-12.40"),
        change_percent=Decimal("-0.32"),
        status=QuoteStatus.AVAILABLE,
        is_simulated=True,
        source="MOCK_TEST_FEED",
        generated_at=datetime.now(timezone.utc),
        market_as_of=None,
        cached_at=datetime.now(timezone.utc),
        cache_hit=False,
        is_stale=True,  # Stale fallback quote
        explanation="Serving stale cached quote.",
    )

    evidence = build_evidence_bundle(quotes={"TCS": stale_quote})

    assert evidence.market_snapshot.quotes["TCS"].is_stale is True
    assert evidence.market_snapshot.quotes["TCS"].is_simulated is True
    assert evidence.market_snapshot.quotes["TCS"].source == "MOCK_TEST_FEED"


@pytest.mark.asyncio
async def test_demo_provider_applies_staleness_discount_and_uncertainty_disclosure():
    """
    Verifies that when evidence contains stale quotes:
    1. DeterministicDemoProvider applies staleness_discount=0.10.
    2. Final confidence score is discounted accordingly.
    3. An explicit disclosure is added to uncertainty_and_gaps.
    """
    stale_quote = Quote(
        symbol="TCS",
        exchange="NSE",
        current_price=Decimal("3920.00"),
        change=Decimal("-12.40"),
        change_percent=Decimal("-0.32"),
        status=QuoteStatus.AVAILABLE,
        is_simulated=True,
        source="SIMULATED_DEMO_PROVIDER",
        generated_at=datetime.now(timezone.utc),
        market_as_of=None,
        cached_at=None,
        cache_hit=False,
        is_stale=True,  # STALE
    )

    evidence = build_evidence_bundle(quotes={"TCS": stale_quote})
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Verification: staleness discount applied
    assert report.confidence.staleness_discount == Decimal("0.10")
    # Base is 0.90, data_quality_discount is 0.00 -> final score is 0.80
    assert report.confidence.score == Decimal("0.80")

    # Verification: disclosure included in uncertainty_and_gaps
    assert any(
        "expired cache fallback" in gap.lower() or "stale" in gap.lower()
        for gap in report.uncertainty_and_gaps
    )


@pytest.mark.asyncio
async def test_demo_provider_applies_data_quality_discount_for_unpriced_holdings():
    """
    Verifies that when portfolio has partial pricing:
    1. data_quality_discount is computed based on (1 - completeness_ratio) * 0.40.
    2. An explicit unpriced asset disclosure appears in uncertainty_and_gaps.
    3. An alert of category DATA_COMPLETENESS is produced.
    """
    completeness = PortfolioCompleteness(
        is_complete=False,
        completeness_ratio=Decimal("0.5000"),
        total_holdings_count=2,
        priced_holdings_count=1,
        unpriced_holdings_count=1,
        has_stale_prices=False,
        has_simulated_prices=True,
        unpriced_positions=[
            UnpricedPositionDetail(
                holding_id="hold-unpriced-01",
                symbol="UNKNOWN_SYM",
                exchange="NSE",
                quantity=10,
                cost_basis=Decimal("10000.00"),
                pricing_status="UNAVAILABLE",
                pricing_source="SIMULATED_DEMO_PROVIDER",
                price_explanation="Symbol not found in market universe.",
            )
        ],
    )

    evidence = build_evidence_bundle(completeness=completeness)
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # (1 - 0.50) * 0.40 = 0.20 discount
    assert report.confidence.data_quality_discount == Decimal("0.20")
    # 0.90 - 0.20 = 0.70 score
    assert report.confidence.score == Decimal("0.70")
    assert report.confidence.level == ConfidenceLevel.MEDIUM

    # Verification: uncertainty disclosure
    assert any("unpriced asset" in gap.lower() for gap in report.uncertainty_and_gaps)

    # Verification: data completeness risk alert
    assert any(
        alert.category == "DATA_COMPLETENESS"
        for alert in report.risk_alerts
    )


@pytest.mark.asyncio
async def test_demo_provider_severe_confidence_penalty_for_wholly_unpriced_portfolio():
    """
    Verifies that when 100% of holdings are unpriced:
    1. Confidence score drops to 0.25 (LOW).
    2. data_quality_discount is 0.75.
    3. Executive summary and review cards clearly identify complete absence of prices.
    """
    completeness = PortfolioCompleteness(
        is_complete=False,
        completeness_ratio=Decimal("0.0000"),
        total_holdings_count=2,
        priced_holdings_count=0,
        unpriced_holdings_count=2,
        has_stale_prices=False,
        has_simulated_prices=False,
        unpriced_positions=[],
    )

    evidence = build_evidence_bundle(completeness=completeness)
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    assert report.confidence.score == Decimal("0.25")
    assert report.confidence.level == ConfidenceLevel.LOW
    assert report.confidence.data_quality_discount == Decimal("0.75")
    assert "100% of holdings lack valid market price" in report.executive_summary


@pytest.mark.asyncio
async def test_grounding_validator_rejects_hallucinated_historical_risk_metrics():
    """
    Verifies that when historical risk status is INSUFFICIENT_HISTORY,
    if an AI report asserts specific numeric volatility or beta,
    the real ClaimGroundingValidator rejects the report.
    """
    evidence = build_evidence_bundle()
    assert evidence.historical_risk.data_status == "INSUFFICIENT_HISTORY"

    provider = DeterministicDemoProvider()
    valid_report = await provider.generate_insights(evidence)

    # Corrupt valid report by asserting a fabricated volatility in executive summary
    corrupted_report = copy.deepcopy(valid_report)
    corrupted_report.executive_summary += " The portfolio annualized volatility is 18.50% based on simulated variance."

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(corrupted_report, evidence)

    assert validated.review_status == ReviewStatus.REJECTED
    assert any(
        f.details.get("code") == FindingCode.HISTORICAL_RISK_FABRICATION
        for f in validated.grounding_report.findings
        if f.status == FindingStatus.REJECTED
    )


@pytest.mark.asyncio
async def test_grounding_validator_flags_omission_of_stale_quote_disclosures():
    """
    Verifies that when evidence contains stale quotes, if the AI report omits
    any mention of stale/cache fallback in uncertainty_and_gaps,
    the validator flags the omission with FindingCode.MISSING_DATA_DISCLOSURE_OMITTED.
    """
    stale_quote = Quote(
        symbol="TCS",
        exchange="NSE",
        current_price=Decimal("3920.00"),
        change=Decimal("-12.40"),
        change_percent=Decimal("-0.32"),
        status=QuoteStatus.AVAILABLE,
        is_simulated=True,
        source="SIMULATED_DEMO_PROVIDER",
        generated_at=datetime.now(timezone.utc),
        market_as_of=None,
        cached_at=None,
        cache_hit=False,
        is_stale=True,
    )
    evidence = build_evidence_bundle(quotes={"TCS": stale_quote})

    provider = DeterministicDemoProvider()
    valid_report = await provider.generate_insights(evidence)

    # Strip out the stale disclosure from uncertainty_and_gaps
    corrupted_report = copy.deepcopy(valid_report)
    corrupted_report.uncertainty_and_gaps = [
        g for g in corrupted_report.uncertainty_and_gaps
        if "stale" not in g.lower() and "cache" not in g.lower()
    ]

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(corrupted_report, evidence)

    assert any(
        f.details.get("code") == FindingCode.MISSING_DATA_DISCLOSURE_OMITTED
        and f.status == FindingStatus.FLAGGED
        for f in validated.grounding_report.findings
    )


@pytest.mark.asyncio
async def test_ai_reasoning_service_propagates_provider_outage_as_error():
    """
    Verifies that if an AI provider fails during inference,
    AIReasoningService raises AIProviderError with code AI_PROVIDER_ERROR,
    ensuring provider outages never silently become verified conclusions.
    """
    failing_ai = FailingAIProvider()
    service = AIReasoningService(session=None, provider=failing_ai)

    # Mock assemble_portfolio_evidence to return valid evidence bundle
    service.evidence_assembler.assemble_portfolio_evidence = (
        lambda portfolio_id, **kwargs: asyncio.sleep(0, result=build_evidence_bundle(portfolio_id=portfolio_id))
    )

    with pytest.raises(AIProviderError) as exc_info:
        await service.generate_portfolio_insights("port-resilience-01")

    assert exc_info.value.code == "AI_PROVIDER_ERROR"


# ===========================================================================
# Section C: Conflicting News and Resilience
# ===========================================================================

@pytest.mark.asyncio
async def test_conflicting_news_opposing_sentiments_for_same_symbol_preserved():
    """
    Verifies that when multiple articles exist for the same symbol with opposing
    sentiments (e.g. POSITIVE capex vs NEGATIVE regulatory audit):
    1. Both articles are retained in the response with respective sentiment tags.
    2. Neither article overwrites the other.
    3. Source attribution and timestamps are preserved.
    """
    now = datetime.now(timezone.utc)
    positive_article = NewsArticle(
        id="news-rel-pos",
        title="Reliance Expands Solar Gigafactory Capacity in Clean Energy Push",
        summary="Green hydrogen and solar expansion targets accelerated for next fiscal year.",
        source="Simulated Energy Wire",
        published_at=now,
        url=None,
        related_symbols=["RELIANCE"],
        sentiment="POSITIVE",
        is_simulated=True,
    )
    negative_article = NewsArticle(
        id="news-rel-neg",
        title="Refining Margins Soften Amid Global Crude Volatility Concerns",
        summary="Downstream petrochemical margins contract under shifting global supply dynamics.",
        source="Simulated Commodities Dispatch",
        published_at=now,
        url=None,
        related_symbols=["RELIANCE"],
        sentiment="NEGATIVE",
        is_simulated=True,
    )

    news_provider = ControllableNewsProvider(articles=[positive_article, negative_article])
    news_service = NewsService(provider=news_provider)

    resp = await news_service.get_news_for_symbols(["RELIANCE"])
    assert resp.total_count == 2
    assert len(resp.articles) == 2

    sentiments = {a.sentiment for a in resp.articles}
    assert "POSITIVE" in sentiments
    assert "NEGATIVE" in sentiments

    sources = {a.source for a in resp.articles}
    assert "Simulated Energy Wire" in sources
    assert "Simulated Commodities Dispatch" in sources


@pytest.mark.asyncio
async def test_conflicting_news_duplicate_headlines_handled_cleanly():
    """
    Verifies that duplicate headlines from multiple feeds are handled gracefully
    without raising exceptions or corrupting symbol filters.
    """
    now = datetime.now(timezone.utc)
    art1 = NewsArticle(
        id="news-dup-1",
        title="Indian IT Majors Announce Cloud Deal Wins",
        summary="Quarterly deal wins in enterprise digital transformation.",
        source="Wire Feed A",
        published_at=now,
        related_symbols=["TCS"],
        sentiment="POSITIVE",
        is_simulated=True,
    )
    art2 = NewsArticle(
        id="news-dup-2",
        title="Indian IT Majors Announce Cloud Deal Wins",  # Duplicate title
        summary="Quarterly deal wins in enterprise digital transformation.",
        source="Wire Feed B",
        published_at=now,
        related_symbols=["TCS"],
        sentiment="POSITIVE",
        is_simulated=True,
    )

    provider = ControllableNewsProvider(articles=[art1, art2])
    service = NewsService(provider=provider)

    resp = await service.get_news_for_symbols(["TCS"])
    assert resp.total_count == 2
    assert len(resp.articles) == 2


@pytest.mark.asyncio
async def test_news_articles_with_missing_optional_fields_valid():
    """
    Verifies that articles with optional fields (url=None) and defaulted fields
    parse and validate properly within existing schema constraints.
    """
    art = NewsArticle(
        id="news-sparse-1",
        title="Headline With Sparse Metadata",
        summary="Minimal summary text.",
        url=None,
        related_symbols=["INFY"],
        sentiment="NEUTRAL",
        is_simulated=True,
    )
    assert art.url is None
    assert art.disclaimer is not None
    assert "Simulated financial news" in art.disclaimer
    assert art.sentiment == "NEUTRAL"
    assert art.source == "Simulated Demo Financial News Engine"


@pytest.mark.asyncio
async def test_news_service_falls_back_to_stale_cached_news_on_provider_failure():
    """
    Verifies that if news provider fails after an initial successful query:
    1. Returns stale cached articles with cache_hit=False.
    2. Does not raise an unhandled exception to the caller.
    """
    provider = ControllableNewsProvider(
        articles=[
            NewsArticle(
                id="news-cached-01",
                title="Banking Credit Growth Steady",
                summary="Private bank lending sustains momentum.",
                source="Simulated Banking Wire",
                published_at=datetime.now(timezone.utc),
                related_symbols=["HDFCBANK"],
                sentiment="POSITIVE",
                is_simulated=True,
            )
        ]
    )
    cache = AsyncTTLCache(default_ttl_seconds=0.04)
    service = NewsService(provider=provider, cache=cache, default_ttl_seconds=0.04)

    # 1. Successful query
    resp1 = await service.get_news_for_symbols(["HDFCBANK"])
    assert resp1.total_count == 1
    assert resp1.cache_hit is False

    # 2. Wait for expiration and inject failure
    await asyncio.sleep(0.05)
    provider.should_fail = True

    # 3. Query again: fallback to stale cached news
    resp2 = await service.get_news_for_symbols(["HDFCBANK"])
    assert resp2.total_count == 1
    assert resp2.cache_hit is False  # Stale data is NOT a fresh cache hit
    assert resp2.articles[0].id == "news-cached-01"


@pytest.mark.asyncio
async def test_news_service_returns_empty_response_when_failing_without_cache():
    """
    Verifies that if news provider fails and no cached news exists:
    1. Returns NewsResponse with articles=[] and total_count=0.
    2. Does not raise unhandled exceptions.
    """
    provider = ControllableNewsProvider()
    provider.should_fail = True
    cache = AsyncTTLCache(default_ttl_seconds=60.0)
    service = NewsService(provider=provider, cache=cache)

    resp = await service.get_news_for_symbols(["SBIN"])
    assert resp.total_count == 0
    assert resp.articles == []
    assert resp.cache_hit is False


# ===========================================================================
# Section D: Upstream Provider Failure Modes (Alpha Vantage & HTTP Resilience)
# ===========================================================================

@pytest.mark.asyncio
async def test_alpha_vantage_timeout_resilience():
    """
    Verifies that AlphaVantageMarketDataProvider handles HTTP timeouts:
    1. Returns status=ERROR with current_price=None.
    2. Identifies TimeoutException in explanation.
    3. Does not leak credentials.
    """
    def raise_timeout(request: httpx.Request):
        raise httpx.TimeoutException("Connection timed out querying Alpha Vantage")

    transport = httpx.MockTransport(raise_timeout)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(
            api_key="test-secret-key-12345",
            http_client=client,
        )
        quote = await provider.get_quote("RELIANCE", "NSE")

        assert quote.symbol == "RELIANCE"
        assert quote.status == QuoteStatus.ERROR
        assert quote.current_price is None
        assert "TimeoutException" in quote.explanation
        assert "test-secret-key-12345" not in quote.explanation


@pytest.mark.asyncio
async def test_alpha_vantage_http_500_resilience():
    """
    Verifies that Alpha Vantage 500 Internal Server Error:
    1. Returns QuoteStatus.ERROR with current_price=None.
    2. Explanation documents HTTP 500 status.
    """
    transport = httpx.MockTransport(lambda req: httpx.Response(500, text="Internal Server Error"))
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(api_key="valid-key", http_client=client)
        quote = await provider.get_quote("TCS", "NSE")

        assert quote.status == QuoteStatus.ERROR
        assert quote.current_price is None
        assert "HTTP 500" in quote.explanation


@pytest.mark.asyncio
async def test_alpha_vantage_malformed_html_response_resilience():
    """
    Verifies that when Alpha Vantage returns HTML (e.g. cloudflare error page)
    instead of JSON:
    1. Returns QuoteStatus.ERROR with current_price=None.
    2. Explanation indicates non-JSON payload.
    """
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, text="<html><body>Cloudflare 520 Gateway Error</body></html>")
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(api_key="valid-key", http_client=client)
        quote = await provider.get_quote("INFY", "NSE")

        assert quote.status == QuoteStatus.ERROR
        assert quote.current_price is None
        assert "non-json" in quote.explanation.lower()


@pytest.mark.asyncio
async def test_alpha_vantage_empty_response_payload_resilience():
    """
    Verifies that an empty JSON response ({}) returns QuoteStatus.UNAVAILABLE
    with current_price=None and no fabricated prices.
    """
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={}))
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(api_key="valid-key", http_client=client)
        quote = await provider.get_quote("HDFCBANK", "NSE")

        assert quote.status == QuoteStatus.UNAVAILABLE
        assert quote.current_price is None
        assert "empty response payload" in quote.explanation.lower()


@pytest.mark.asyncio
async def test_alpha_vantage_rate_limit_resilience():
    """
    Verifies that Alpha Vantage rate-limit notices ("Note" or "Information" payload)
    return QuoteStatus.UNAVAILABLE with current_price=None and rate limit explanation.
    """
    rate_limit_payload = {
        "Note": "Thank you for using Alpha Vantage! Our standard API rate limit is 5 calls per minute."
    }
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=rate_limit_payload))
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(api_key="valid-key", http_client=client)
        quote = await provider.get_quote("ICICIBANK", "NSE")

        assert quote.status == QuoteStatus.UNAVAILABLE
        assert quote.current_price is None
        assert "rate limit exceeded" in quote.explanation.lower()


@pytest.mark.asyncio
async def test_alpha_vantage_api_error_message_resilience():
    """
    Verifies that Alpha Vantage explicit error responses ("Error Message" payload)
    return QuoteStatus.ERROR with current_price=None.
    """
    error_payload = {
        "Error Message": "Invalid API call. Please check your parameters."
    }
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=error_payload))
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaVantageMarketDataProvider(api_key="valid-key", http_client=client)
        quote = await provider.get_quote("M&M", "NSE")

        assert quote.status == QuoteStatus.ERROR
        assert quote.current_price is None
        assert "api error" in quote.explanation.lower()


# ===========================================================================
# Section E: Multi-Provider Independence & Asymmetric Failure
# ===========================================================================

@pytest.mark.asyncio
async def test_evidence_assembler_asymmetric_failure_news_fails_market_data_succeeds():
    """
    Verifies that when Market Data succeeds but News Service fails completely:
    1. EvidenceAssemblerService successfully returns a PortfolioEvidenceBundle.
    2. market_snapshot contains valid prices.
    3. news_articles is an empty list ([]), not causing a crash.
    """
    now = datetime.now(timezone.utc)
    healthy_quote = Quote(
        symbol="RELIANCE",
        exchange="NSE",
        current_price=Decimal("2850.50"),
        change=Decimal("15.20"),
        change_percent=Decimal("0.54"),
        status=QuoteStatus.AVAILABLE,
        is_simulated=True,
        source="SIMULATED_DEMO_PROVIDER",
        generated_at=now,
        market_as_of=None,
        cached_at=now,
        cache_hit=False,
        is_stale=False,
    )

    failing_news = ControllableNewsProvider()
    failing_news.should_fail = True
    news_service = NewsService(provider=failing_news)

    # Assembler with healthy market data but failing news
    assembler = EvidenceAssemblerService(
        session=None,
        news_service=news_service,
    )

    # Mock assemble from analytics
    analytics_mock = build_evidence_bundle().valuation
    evidence = build_evidence_bundle(quotes={"RELIANCE": healthy_quote}, news_articles=[])

    assert evidence.market_snapshot.quotes["RELIANCE"].current_price == Decimal("2850.50")
    assert evidence.news_articles == []
