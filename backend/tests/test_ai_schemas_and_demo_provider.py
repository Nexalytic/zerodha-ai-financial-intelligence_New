import re
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.schemas.ai_reasoning import (
    AIConfidenceIndicator,
    AIInsightReport,
    AIRiskAlert,
    AlertSeverity,
    ConfidenceLevel,
    DriverType,
    EvidenceKeyDriver,
    FindingStatus,
    GroundingFinding,
    GroundingValidationReport,
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
    SectorAllocation,
    UnpricedPositionDetail,
    ValuationStatus,
)
from app.schemas.market_data import BatchQuotesResponse, NewsArticle, Quote, QuoteStatus
from app.services.ai.providers.base import BaseAIProvider
from app.services.ai.providers.demo_provider import DeterministicDemoProvider


# ===========================================================================
# Fixture & Helpers
# ===========================================================================

def build_evidence_bundle(
    *,
    portfolio_id: str = "port-test-1234",
    portfolio_name: str = "Test Core Portfolio",
    total_holdings_count: int = 3,
    priced_holdings_count: int = 3,
    unpriced_positions: list = None,
    total_cost_basis: Decimal = Decimal("100000.00"),
    total_market_value: Decimal = Decimal("115000.00"),
    unrealized_pnl: Decimal = Decimal("15000.00"),
    unrealized_pnl_percent: Decimal = Decimal("15.00"),
    top_symbol: str = "RELIANCE",
    top_weight: Decimal = Decimal("50.00"),
    hhi: Decimal = Decimal("3800.00"),
    effective_holdings: Decimal = Decimal("2.63"),
    concentration_tier: str = "HIGH",
    composite_risk_score: Decimal = Decimal("62.50"),
    risk_tier: str = "MODERATE",
    is_stale_quote: bool = False,
    include_news: bool = True,
) -> PortfolioEvidenceBundle:
    """Helper constructing a valid PortfolioEvidenceBundle for testing."""
    unpriced_count = total_holdings_count - priced_holdings_count
    unpriced_details = []
    if unpriced_positions:
        unpriced_details = [
            UnpricedPositionDetail(
                holding_id=p.get("holding_id", f"hold-{idx}"),
                symbol=p["symbol"],
                exchange=p.get("exchange", "NSE"),
                quantity=int(p.get("quantity", 10)),
                cost_basis=Decimal(str(p.get("cost_basis", "1000.00"))),
                pricing_status=p.get("pricing_status", "UNAVAILABLE"),
                pricing_source=p.get("pricing_source", "SIMULATED_DEMO_PROVIDER"),
                price_explanation=p.get("reason", "Missing quote"),
            )
            for idx, p in enumerate(unpriced_positions)
        ]

    comp_ratio = (
        Decimal(priced_holdings_count) / Decimal(total_holdings_count)
        if total_holdings_count > 0
        else Decimal("0.0000")
    )

    if total_holdings_count == 0:
        val_status = ValuationStatus.EMPTY
    elif unpriced_count == 0:
        val_status = ValuationStatus.COMPLETE
    elif priced_holdings_count > 0:
        val_status = ValuationStatus.PARTIAL
    else:
        val_status = ValuationStatus.UNVALUED

    valuation = PortfolioValuation(
        total_cost_basis=total_cost_basis,
        total_market_value=total_market_value,
        unrealized_pnl=unrealized_pnl if priced_holdings_count > 0 else None,
        unrealized_pnl_percent=unrealized_pnl_percent if priced_holdings_count > 0 else None,
        valuation_status=val_status,
        priced_cost_basis=total_cost_basis if priced_holdings_count > 0 else Decimal("0.00"),
        unpriced_cost_basis=Decimal("0.00") if unpriced_count == 0 else Decimal("20000.00"),
    )

    completeness = PortfolioCompleteness(
        is_complete=(total_holdings_count > 0 and unpriced_count == 0),
        total_holdings_count=total_holdings_count,
        priced_holdings_count=priced_holdings_count,
        unpriced_holdings_count=unpriced_count,
        completeness_ratio=comp_ratio.quantize(Decimal("0.0001")),
        unpriced_positions=unpriced_details,
    )

    concentration = ConcentrationMetrics(
        herfindahl_index=hhi if priced_holdings_count > 0 else None,
        top_holding_symbol=top_symbol if priced_holdings_count > 0 else None,
        top_holding_weight_percent=top_weight if priced_holdings_count > 0 else None,
        effective_holdings_count=effective_holdings if priced_holdings_count > 0 else None,
        concentration_tier=concentration_tier if priced_holdings_count > 0 else None,
    )

    sector_allocations = []
    if priced_holdings_count > 0:
        sector_allocations = [
            SectorAllocation(
                sector="ENERGY",
                cost_basis=Decimal("50000.00"),
                market_value=Decimal("57500.00"),
                allocation_percent=Decimal("50.00"),
                holdings_count=1,
                priced_count=1,
                unpriced_count=0,
            ),
            SectorAllocation(
                sector="TECHNOLOGY",
                cost_basis=Decimal("50000.00"),
                market_value=Decimal("57500.00"),
                allocation_percent=Decimal("50.00"),
                holdings_count=2,
                priced_count=2,
                unpriced_count=0,
            ),
        ]

    risk_assessment = PortfolioRiskAssessment(
        composite_risk_score=composite_risk_score if priced_holdings_count > 0 else None,
        risk_tier=risk_tier if priced_holdings_count > 0 else "UNKNOWN",
        component_scores=RiskComponentScores(
            single_stock_concentration=Decimal("80.00"),
            sector_concentration=Decimal("60.00"),
            portfolio_breadth=Decimal("50.00"),
            data_quality=Decimal("60.00"),
        ) if priced_holdings_count > 0 else None,
        unpriced_holdings_count=unpriced_count,
        completeness_ratio=comp_ratio.quantize(Decimal("0.0001")),
    )

    quotes = {
        "RELIANCE": Quote(
            symbol="RELIANCE",
            current_price=Decimal("2875.00"),
            change=Decimal("35.00"),
            change_percent=Decimal("1.23"),
            status=QuoteStatus.AVAILABLE,
            is_stale=is_stale_quote,
        )
    }

    news_articles = []
    if include_news:
        news_articles = [
            NewsArticle(
                id="news-test-1",
                title="Reliance Industries Expands Clean Energy Capacity",
                summary="Strategic growth in solar and battery manufacturing announced.",
                source="Simulated Financial Wire",
                related_symbols=["RELIANCE"],
                sentiment="POSITIVE",
            )
        ]

    return PortfolioEvidenceBundle(
        portfolio_id=portfolio_id,
        portfolio_name=portfolio_name,
        is_sample_portfolio=True,
        valuation=valuation,
        completeness=completeness,
        concentration=concentration,
        sector_allocations=sector_allocations,
        risk_assessment=risk_assessment,
        market_snapshot=BatchQuotesResponse(
            quotes=quotes,
            total_symbols=len(quotes),
            cache_hits_count=1,
            cache_misses_count=0,
        ),
        news_articles=news_articles,
    )


# ===========================================================================
# 1. Schema Validation Tests
# ===========================================================================

def test_confidence_indicator_validations():
    """Verify confidence score boundaries and mandatory calibration disclosure."""
    # Valid indicator
    indicator = AIConfidenceIndicator(
        score=Decimal("0.85"),
        level=ConfidenceLevel.HIGH,
        calibration_limitation="Heuristic discount penalty applied due to partial data. Not statistical probability.",
        data_quality_discount=Decimal("0.10"),
        staleness_discount=Decimal("0.05"),
    )
    assert indicator.score == Decimal("0.85")
    assert indicator.level == ConfidenceLevel.HIGH

    # Score below 0.00 rejected
    with pytest.raises(ValidationError):
        AIConfidenceIndicator(
            score=Decimal("-0.01"),
            level=ConfidenceLevel.LOW,
            calibration_limitation="Valid length calibration text that exceeds minimum length threshold.",
        )

    # Score above 1.00 rejected
    with pytest.raises(ValidationError):
        AIConfidenceIndicator(
            score=Decimal("1.01"),
            level=ConfidenceLevel.HIGH,
            calibration_limitation="Valid length calibration text that exceeds minimum length threshold.",
        )

    # Short calibration limitation (< 20 chars) rejected
    with pytest.raises(ValidationError):
        AIConfidenceIndicator(
            score=Decimal("0.80"),
            level=ConfidenceLevel.HIGH,
            calibration_limitation="Too short",
        )


def test_evidence_key_driver_validation():
    """Verify EvidenceKeyDriver validation rules."""
    driver = EvidenceKeyDriver(
        driver_id="driver-1",
        driver_type=DriverType.CONCENTRATION,
        title="Heavy Concentration in RELIANCE",
        statement="RELIANCE represents 50% of the portfolio market value.",
        supporting_metric_key="concentration.top_holding_weight_percent",
        supporting_metric_value=Decimal("50.00"),
        source_reference="analytics.concentration",
        is_grounded=True,
    )
    assert driver.driver_id == "driver-1"
    assert driver.driver_type == DriverType.CONCENTRATION
    assert driver.is_grounded is True

    # Valid RISK driver type accepted via enum and string
    risk_driver = EvidenceKeyDriver(
        driver_id="driver-risk-1",
        driver_type=DriverType.RISK,
        title="High Composite Risk Score",
        statement="Portfolio composite risk score is elevated at 62.50.",
        supporting_metric_key="risk_assessment.composite_risk_score",
        supporting_metric_value=Decimal("62.50"),
        source_reference="analytics.risk_assessment",
        is_grounded=True,
    )
    assert risk_driver.driver_type == DriverType.RISK

    risk_driver_str = EvidenceKeyDriver(
        driver_id="driver-risk-2",
        driver_type="RISK",
        title="Elevated Volatility Risk",
        statement="Risk tier is MODERATE.",
        supporting_metric_key="risk_assessment.risk_tier",
        supporting_metric_value="MODERATE",
        source_reference="analytics.risk_assessment",
    )
    assert risk_driver_str.driver_type == DriverType.RISK

    # Arbitrary / unallowlisted driver type strictly rejected
    with pytest.raises(ValidationError):
        EvidenceKeyDriver(
            driver_id="driver-invalid-1",
            driver_type="INVALID_CUSTOM_TYPE",
            title="Invalid Driver Type",
            statement="Statement here",
            supporting_metric_key="key",
            supporting_metric_value=123,
            source_reference="source",
        )

    # Empty title rejected
    with pytest.raises(ValidationError):
        EvidenceKeyDriver(
            driver_id="driver-1",
            driver_type=DriverType.CONCENTRATION,
            title="",
            statement="Statement here",
            supporting_metric_key="key",
            supporting_metric_value=123,
            source_reference="source",
        )


def test_reviewable_insight_card_symbol_normalization():
    """Verify symbol validation and uppercase normalization in ReviewableInsightCard."""
    card = ReviewableInsightCard(
        card_id="card-1",
        category="CONCENTRATION",
        severity="HIGH",
        title="Top Holding Risk",
        description="RELIANCE is over-concentrated.",
        cited_metrics={"top_weight": "50.00"},
        related_symbols=[" reliance ", "tcs", "M&M"],
        review_status=ReviewStatus.PENDING_REVIEW,
    )
    assert card.related_symbols == ["RELIANCE", "TCS", "M&M"]

    # Invalid symbol with special illegal characters
    with pytest.raises(ValidationError):
        ReviewableInsightCard(
            card_id="card-2",
            category="CONCENTRATION",
            severity="HIGH",
            title="Invalid Symbol Card",
            description="Testing invalid symbol.",
            related_symbols=["INVALID$$SYMBOL"],
        )


def test_ai_insight_report_empty_disclaimers_rejected():
    """Verify AIInsightReport mandates at least one disclaimer."""
    with pytest.raises(ValidationError):
        AIInsightReport(
            report_id="rep-123",
            portfolio_id="port-123",
            provider_name="DETERMINISTIC_DEMO_REASONER",
            model_id="deterministic-demo-v1",
            is_simulated=True,
            executive_summary="Valid narrative summary for the portfolio testing disclaimers.",
            confidence=AIConfidenceIndicator(
                score=Decimal("0.80"),
                level=ConfidenceLevel.HIGH,
                calibration_limitation="Heuristic limitation disclosure string meeting requirements.",
            ),
            disclaimers=[],  # Must reject empty list
        )


def test_portfolio_evidence_bundle_empty_id_rejected():
    """Verify PortfolioEvidenceBundle rejects empty string portfolio_id."""
    with pytest.raises(ValidationError):
        build_evidence_bundle(portfolio_id="   ")


# ===========================================================================
# 2. DeterministicDemoProvider Scenario Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_demo_provider_empty_portfolio():
    """Verify provider handles empty portfolio with zero holdings safely and factually."""
    evidence = build_evidence_bundle(
        total_holdings_count=0,
        priced_holdings_count=0,
        total_cost_basis=Decimal("0.00"),
        total_market_value=Decimal("0.00"),
        unrealized_pnl=Decimal("0.00"),
        unrealized_pnl_percent=Decimal("0.00"),
        top_weight=Decimal("0.00"),
        hhi=Decimal("0.00"),
        composite_risk_score=Decimal("0.00"),
    )

    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    assert report.provider_name == DeterministicDemoProvider.PROVIDER_NAME
    assert report.model_id == DeterministicDemoProvider.MODEL_ID
    assert report.is_simulated is True
    assert "currently empty with no recorded holdings" in report.executive_summary
    assert report.confidence.score == Decimal("0.50")
    assert report.confidence.level == ConfidenceLevel.LOW
    assert report.confidence.data_quality_discount == Decimal("0.50")
    assert "empty portfolio" in report.confidence.calibration_limitation.lower()

    # Key driver and risk alerts
    assert len(report.key_drivers) == 1
    assert report.key_drivers[0].driver_type == DriverType.DATA_QUALITY
    assert report.key_drivers[0].supporting_metric_value == 0

    assert len(report.risk_alerts) == 1
    assert report.risk_alerts[0].severity == AlertSeverity.INFO
    assert report.risk_alerts[0].category == "DATA_COMPLETENESS"

    # Review cards & gaps
    assert len(report.review_cards) == 1
    assert report.review_cards[0].review_status == ReviewStatus.VERIFIED
    assert len(report.uncertainty_and_gaps) == 1
    assert report.grounding_report.is_acceptable is True


@pytest.mark.asyncio
async def test_demo_provider_wholly_unpriced_portfolio():
    """Verify provider handles portfolio with holdings where 100% are unpriced."""
    evidence = build_evidence_bundle(
        total_holdings_count=3,
        priced_holdings_count=0,
        unpriced_positions=[
            {"symbol": "UNPRICED1", "quantity": 10},
            {"symbol": "UNPRICED2", "quantity": 20},
            {"symbol": "UNPRICED3", "quantity": 30},
        ],
        total_cost_basis=Decimal("50000.00"),
        total_market_value=Decimal("0.00"),
    )

    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    assert "100% of holdings lack valid market price observations" in report.executive_summary
    assert report.confidence.score == Decimal("0.25")
    assert report.confidence.level == ConfidenceLevel.LOW
    assert report.confidence.data_quality_discount == Decimal("0.75")

    # Critical risk alert for complete lack of valuation
    assert any(a.severity == AlertSeverity.CRITICAL for a in report.risk_alerts)
    assert any("DATA_COMPLETENESS" in a.category for a in report.risk_alerts)
    assert len(report.key_drivers) == 1
    assert report.key_drivers[0].supporting_metric_value == 3
    assert report.grounding_report.is_acceptable is True


@pytest.mark.asyncio
async def test_demo_provider_fully_priced_portfolio_with_news():
    """Verify comprehensive insights for standard priced portfolio with news."""
    evidence = build_evidence_bundle(
        total_holdings_count=3,
        priced_holdings_count=3,
        total_cost_basis=Decimal("100000.00"),
        total_market_value=Decimal("115000.00"),
        unrealized_pnl=Decimal("15000.00"),
        unrealized_pnl_percent=Decimal("15.00"),
        top_symbol="RELIANCE",
        top_weight=Decimal("50.00"),
        hhi=Decimal("3800.00"),
        composite_risk_score=Decimal("62.50"),
        risk_tier="MODERATE",
        is_stale_quote=False,
        include_news=True,
    )

    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Narrative checks
    assert "₹115,000.00" in report.executive_summary
    assert "+₹15,000.00 (+15.00%)" in report.executive_summary
    assert "RELIANCE" in report.executive_summary
    assert "62.50/100" in report.executive_summary

    # Driver verification: 5 drivers (CONCENTRATION, SECTOR, PERFORMANCE, DIVERSIFICATION, NEWS)
    assert len(report.key_drivers) == 5
    driver_types = [d.driver_type for d in report.key_drivers]
    assert DriverType.CONCENTRATION in driver_types
    assert DriverType.SECTOR in driver_types
    assert DriverType.PERFORMANCE in driver_types
    assert DriverType.DIVERSIFICATION in driver_types
    assert DriverType.NEWS in driver_types

    news_driver = next(d for d in report.key_drivers if d.driver_type == DriverType.NEWS)
    assert "Reliance Industries Expands" in news_driver.statement
    assert news_driver.source_reference == "news.RELIANCE"

    # Risk alerts: Top weight is 50.00% (HIGH severity) and composite score is 62.50 (MEDIUM severity)
    assert len(report.risk_alerts) == 2
    conc_alert = next(a for a in report.risk_alerts if "CONCENTRATION" in a.category)
    assert conc_alert.severity == AlertSeverity.HIGH
    assert conc_alert.evidence_reference == "concentration.top_holding_weight_percent"

    score_alert = next(a for a in report.risk_alerts if "RISK" in a.category)
    assert score_alert.severity == AlertSeverity.MEDIUM
    assert score_alert.evidence_reference == "risk_assessment.composite_risk_score"

    # Confidence: 0.90 (capped due to insufficient history, 0 discounts)
    assert report.confidence.score == Decimal("0.90")
    assert report.confidence.level == ConfidenceLevel.HIGH
    assert report.confidence.data_quality_discount == Decimal("0.00")
    assert report.confidence.staleness_discount == Decimal("0.00")

    # Review cards: 5 drivers + 2 alerts = 7 review cards
    assert len(report.review_cards) == 7
    for card in report.review_cards:
        assert card.review_status == ReviewStatus.VERIFIED

    # Grounding report
    assert report.grounding_report.total_claims_checked == 7
    assert report.grounding_report.passed_count == 7
    assert report.grounding_report.rejected_count == 0
    assert report.grounding_report.is_acceptable is True

    # Disclaimers
    assert len(report.disclaimers) >= 2
    assert any("Not SEBI-registered" in d for d in report.disclaimers)
    assert any("heuristic demonstration engine" in d for d in report.disclaimers)


@pytest.mark.asyncio
async def test_demo_provider_without_news_omits_news_driver():
    """Verify that absent news strictly omits news key driver without fabricating."""
    evidence = build_evidence_bundle(
        total_holdings_count=3,
        priced_holdings_count=3,
        include_news=False,
    )

    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    driver_types = [d.driver_type for d in report.key_drivers]
    assert DriverType.NEWS not in driver_types
    assert len(report.key_drivers) == 4


@pytest.mark.asyncio
async def test_demo_provider_partially_priced_portfolio():
    """Verify partially priced portfolio triggers completeness alert and discount."""
    evidence = build_evidence_bundle(
        total_holdings_count=3,
        priced_holdings_count=2,
        unpriced_positions=[{"symbol": "UNPRICED_XYZ", "quantity": 100, "reason": "No feed"}],
    )

    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Narrative note
    assert "1 position(s) lack market quotes" in report.executive_summary

    # Data alert exists
    assert any(a.category == "DATA_COMPLETENESS" for a in report.risk_alerts)

    # Confidence penalized
    # completeness_ratio = 2/3 = 0.6667. discount = (1 - 0.6667) * 0.40 = 0.1333 -> 0.13
    assert report.confidence.data_quality_discount > Decimal("0.10")
    assert report.confidence.score < Decimal("0.90")

    # Gaps disclosure notes the unpriced symbol
    assert any("UNPRICED_XYZ" in g for g in report.uncertainty_and_gaps)


@pytest.mark.asyncio
async def test_demo_provider_stale_quote_discount():
    """Verify stale quote data applies staleness discount to confidence score."""
    fresh_evidence = build_evidence_bundle(is_stale_quote=False)
    stale_evidence = build_evidence_bundle(is_stale_quote=True)

    provider = DeterministicDemoProvider()
    fresh_report = await provider.generate_insights(fresh_evidence)
    stale_report = await provider.generate_insights(stale_evidence)

    assert stale_report.confidence.staleness_discount == Decimal("0.10")
    assert fresh_report.confidence.staleness_discount == Decimal("0.00")
    assert stale_report.confidence.score == fresh_report.confidence.score - Decimal("0.10")
    assert any("expired cache fallback" in g for g in stale_report.uncertainty_and_gaps)


@pytest.mark.asyncio
async def test_demo_provider_deterministic_reproducibility():
    """Verify identical input bundle produces identically structured reports."""
    evidence = build_evidence_bundle(portfolio_id="port-repeatable-1")
    provider = DeterministicDemoProvider()

    report_a = await provider.generate_insights(evidence)
    report_b = await provider.generate_insights(evidence)

    # Executive summaries identical
    assert report_a.executive_summary == report_b.executive_summary
    # Confidence metrics identical
    assert report_a.confidence.score == report_b.confidence.score
    assert report_a.confidence.level == report_b.confidence.level
    # Driver counts and titles identical
    assert len(report_a.key_drivers) == len(report_b.key_drivers)
    for da, db in zip(report_a.key_drivers, report_b.key_drivers):
        assert da.title == db.title
        assert da.statement == db.statement
        assert da.supporting_metric_value == db.supporting_metric_value
    # Alert counts and headlines identical
    assert len(report_a.risk_alerts) == len(report_b.risk_alerts)
    for aa, ab in zip(report_a.risk_alerts, report_b.risk_alerts):
        assert aa.headline == ab.headline
        assert aa.explanation == ab.explanation
    # Gaps identical
    assert report_a.uncertainty_and_gaps == report_b.uncertainty_and_gaps
    # Report IDs are unique structured IDs
    assert report_a.report_id != report_b.report_id
    assert report_a.report_id.startswith("rep-port-rep-")
    assert report_b.report_id.startswith("rep-port-rep-")
