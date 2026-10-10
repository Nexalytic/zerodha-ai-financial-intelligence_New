from datetime import datetime, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.portfolio import Holding, Portfolio
from app.schemas.analytics import (
    ConcentrationMetrics,
    PortfolioCompleteness,
    PortfolioRiskAssessment,
    RiskComponentScores,
    SectorAllocation,
    ValuationStatus,
)
from app.schemas.insight import (
    InsightCategory,
    InsightSeverity,
    PortfolioInsight,
    PortfolioInsightsResponse,
)
from app.schemas.portfolio import HoldingCreate, PortfolioCreate
from app.services.analytics_service import AnalyticsService
from app.services.portfolio_service import PortfolioService
from app.services.risk_scoring_service import (
    calculate_data_quality_score,
    calculate_portfolio_breadth_score,
    calculate_portfolio_risk_assessment,
    calculate_sector_concentration_score,
    calculate_single_stock_concentration_score,
    determine_risk_tier,
    generate_portfolio_risk_insights,
)


# =====================================================================
# 1. Component Normalization & Boundary Continuity Tests
# =====================================================================

def test_single_stock_concentration_boundaries():
    """Verify piecewise continuity and boundaries for single-stock concentration."""
    # None input
    assert calculate_single_stock_concentration_score(None) is None

    # Zone 1: <= 10.00% (slope 1.50)
    assert calculate_single_stock_concentration_score(Decimal("0.00")) == Decimal("0.00")
    assert calculate_single_stock_concentration_score(Decimal("5.00")) == Decimal("7.50")
    assert calculate_single_stock_concentration_score(Decimal("10.00")) == Decimal("15.00")

    # Zone 2: 10.00% < W <= 25.00% (slope 2.00)
    assert calculate_single_stock_concentration_score(Decimal("10.01")) == Decimal("15.02")
    assert calculate_single_stock_concentration_score(Decimal("17.50")) == Decimal("30.00")
    assert calculate_single_stock_concentration_score(Decimal("25.00")) == Decimal("45.00")

    # Zone 3: 25.00% < W <= 50.00% (slope 1.40)
    assert calculate_single_stock_concentration_score(Decimal("25.01")) == Decimal("45.01")
    assert calculate_single_stock_concentration_score(Decimal("37.50")) == Decimal("62.50")
    assert calculate_single_stock_concentration_score(Decimal("50.00")) == Decimal("80.00")

    # Zone 4: W > 50.00% (slope 0.40)
    assert calculate_single_stock_concentration_score(Decimal("50.01")) == Decimal("80.00")
    assert calculate_single_stock_concentration_score(Decimal("75.00")) == Decimal("90.00")
    assert calculate_single_stock_concentration_score(Decimal("100.00")) == Decimal("100.00")

    # Clamping
    assert calculate_single_stock_concentration_score(Decimal("-5.00")) == Decimal("0.00")
    assert calculate_single_stock_concentration_score(Decimal("120.00")) == Decimal("100.00")


def test_sector_concentration_boundaries():
    """Verify piecewise continuity and boundaries for sector concentration."""
    # None input
    assert calculate_sector_concentration_score(None) is None

    # Zone 1: <= 20.00% (slope 1.00)
    assert calculate_sector_concentration_score(Decimal("0.00")) == Decimal("0.00")
    assert calculate_sector_concentration_score(Decimal("10.00")) == Decimal("10.00")
    assert calculate_sector_concentration_score(Decimal("20.00")) == Decimal("20.00")

    # Zone 2: 20.00% < S <= 40.00% (slope 1.50)
    assert calculate_sector_concentration_score(Decimal("20.01")) == Decimal("20.02")
    assert calculate_sector_concentration_score(Decimal("30.00")) == Decimal("35.00")
    assert calculate_sector_concentration_score(Decimal("40.00")) == Decimal("50.00")

    # Zone 3: 40.00% < S <= 65.00% (slope 1.20)
    assert calculate_sector_concentration_score(Decimal("40.01")) == Decimal("50.01")
    assert calculate_sector_concentration_score(Decimal("50.00")) == Decimal("62.00")
    assert calculate_sector_concentration_score(Decimal("65.00")) == Decimal("80.00")

    # Zone 4: S > 65.00% (slope 20 / 35)
    assert calculate_sector_concentration_score(Decimal("65.01")) == Decimal("80.01")
    assert calculate_sector_concentration_score(Decimal("100.00")) == Decimal("100.00")


def test_portfolio_breadth_boundaries():
    """Verify piecewise continuity and boundaries for breadth / HHI score."""
    # None input
    assert calculate_portfolio_breadth_score(None) is None

    # Zone 1: HHI <= 0.0800 (slope 250.00)
    assert calculate_portfolio_breadth_score(Decimal("0.0000")) == Decimal("0.00")
    assert calculate_portfolio_breadth_score(Decimal("0.0400")) == Decimal("10.00")
    assert calculate_portfolio_breadth_score(Decimal("0.0800")) == Decimal("20.00")

    # Zone 2: 0.0800 < HHI <= 0.1500
    assert calculate_portfolio_breadth_score(Decimal("0.1150")) == Decimal("30.00")
    assert calculate_portfolio_breadth_score(Decimal("0.1500")) == Decimal("40.00")

    # Zone 3: 0.1500 < HHI <= 0.2500
    assert calculate_portfolio_breadth_score(Decimal("0.2000")) == Decimal("55.00")
    assert calculate_portfolio_breadth_score(Decimal("0.2500")) == Decimal("70.00")

    # Zone 4: HHI > 0.2500
    assert calculate_portfolio_breadth_score(Decimal("0.6250")) == Decimal("85.00")
    assert calculate_portfolio_breadth_score(Decimal("1.0000")) == Decimal("100.00")


def test_data_quality_boundaries():
    """Verify completeness ratio (position count) and stale quote penalties."""
    # Fresh & 100% complete
    assert calculate_data_quality_score(Decimal("1.0000"), has_stale_prices=False) == Decimal("0.00")

    # Fresh & 80% complete (20% missing -> 0.20 * 80 = 16.00)
    assert calculate_data_quality_score(Decimal("0.8000"), has_stale_prices=False) == Decimal("16.00")

    # Fresh & 50% complete (50% missing -> 0.50 * 80 = 40.00)
    assert calculate_data_quality_score(Decimal("0.5000"), has_stale_prices=False) == Decimal("40.00")

    # Fresh & 0% complete (80.00)
    assert calculate_data_quality_score(Decimal("0.0000"), has_stale_prices=False) == Decimal("80.00")

    # Stale quote adds +20.00 points
    assert calculate_data_quality_score(Decimal("1.0000"), has_stale_prices=True) == Decimal("20.00")
    assert calculate_data_quality_score(Decimal("0.5000"), has_stale_prices=True) == Decimal("60.00")
    assert calculate_data_quality_score(Decimal("0.0000"), has_stale_prices=True) == Decimal("100.00")

    # None completeness ratio handled safely as 0.0000
    assert calculate_data_quality_score(None, has_stale_prices=False) == Decimal("80.00")


# =====================================================================
# 2. Risk Tier Classification Boundary Tests
# =====================================================================

def test_risk_tier_boundary_thresholds():
    """Verify exact tier boundaries at 30.00, 30.01, 55.00, 55.01, 75.00, 75.01."""
    assert determine_risk_tier(Decimal("0.00")) == "LOW"
    assert determine_risk_tier(Decimal("29.99")) == "LOW"
    assert determine_risk_tier(Decimal("30.00")) == "LOW"

    assert determine_risk_tier(Decimal("30.01")) == "MODERATE"
    assert determine_risk_tier(Decimal("54.99")) == "MODERATE"
    assert determine_risk_tier(Decimal("55.00")) == "MODERATE"

    assert determine_risk_tier(Decimal("55.01")) == "ELEVATED"
    assert determine_risk_tier(Decimal("74.99")) == "ELEVATED"
    assert determine_risk_tier(Decimal("75.00")) == "ELEVATED"

    assert determine_risk_tier(Decimal("75.01")) == "HIGH"
    assert determine_risk_tier(Decimal("100.00")) == "HIGH"


# =====================================================================
# 3. Composite Score Calculation Against Hand-Verified Plan Examples
# =====================================================================

def test_hand_verified_plan_example_1_balanced_portfolio():
    """
    Plan Example 1: Balanced 5-holding portfolio:
    W_top = 25.00% -> C_stock = 45.00
    S_top = 40.00% -> C_sector = 50.00
    HHI = 0.2050 -> C_breadth = 56.50
    CR = 1.0000, stale = False -> C_quality = 0.00
    Composite = 0.35(45) + 0.25(50) + 0.20(56.50) + 0.20(0) = 15.75 + 12.50 + 11.30 = 39.55 -> MODERATE
    """
    conc = ConcentrationMetrics(
        top_holding_symbol="RELIANCE",
        top_holding_weight_percent=Decimal("25.00"),
        top_3_concentration_percent=Decimal("65.00"),
        herfindahl_index=Decimal("0.2050"),
        effective_holdings_count=Decimal("4.88"),
        concentration_tier="MODERATE",
    )
    comp = PortfolioCompleteness(
        is_complete=True,
        completeness_ratio=Decimal("1.0000"),
        total_holdings_count=5,
        priced_holdings_count=5,
        unpriced_holdings_count=0,
        has_stale_prices=False,
    )
    sectors = [
        SectorAllocation(
            sector="Technology",
            cost_basis=Decimal("4000.00"),
            market_value=Decimal("4000.00"),
            allocation_percent=Decimal("40.00"),
            holdings_count=2,
            priced_count=2,
            unpriced_count=0,
        ),
        SectorAllocation(
            sector="Financial Services",
            cost_basis=Decimal("3500.00"),
            market_value=Decimal("3500.00"),
            allocation_percent=Decimal("35.00"),
            holdings_count=2,
            priced_count=2,
            unpriced_count=0,
        ),
        SectorAllocation(
            sector="Energy",
            cost_basis=Decimal("2500.00"),
            market_value=Decimal("2500.00"),
            allocation_percent=Decimal("25.00"),
            holdings_count=1,
            priced_count=1,
            unpriced_count=0,
        ),
    ]

    res = calculate_portfolio_risk_assessment(
        status=ValuationStatus.COMPLETE,
        concentration=conc,
        completeness=comp,
        sector_allocations=sectors,
    )

    assert res.composite_risk_score == Decimal("39.55")
    assert res.risk_tier == "MODERATE"
    assert res.assessment_status == "COMPLETE"
    assert res.components.single_stock_concentration_score == Decimal("45.00")
    assert res.components.sector_concentration_score == Decimal("50.00")
    assert res.components.diversification_breadth_score == Decimal("56.50")
    assert res.components.data_quality_score == Decimal("0.00")


def test_hand_verified_plan_example_2_single_stock_portfolio():
    """
    Plan Example 2: Extreme single-stock portfolio (100% RELIANCE):
    C_stock = 100.00, C_sector = 100.00, C_breadth = 100.00, C_quality = 0.00
    Composite = 0.35(100) + 0.25(100) + 0.20(100) + 0.20(0) = 80.00 -> HIGH
    """
    conc = ConcentrationMetrics(
        top_holding_symbol="RELIANCE",
        top_holding_weight_percent=Decimal("100.00"),
        top_3_concentration_percent=Decimal("100.00"),
        herfindahl_index=Decimal("1.0000"),
        effective_holdings_count=Decimal("1.00"),
        concentration_tier="HIGH",
    )
    comp = PortfolioCompleteness(
        is_complete=True,
        completeness_ratio=Decimal("1.0000"),
        total_holdings_count=1,
        priced_holdings_count=1,
        unpriced_holdings_count=0,
        has_stale_prices=False,
    )
    sectors = [
        SectorAllocation(
            sector="Energy",
            cost_basis=Decimal("2500.00"),
            market_value=Decimal("2500.00"),
            allocation_percent=Decimal("100.00"),
            holdings_count=1,
            priced_count=1,
            unpriced_count=0,
        ),
    ]

    res = calculate_portfolio_risk_assessment(
        status=ValuationStatus.COMPLETE,
        concentration=conc,
        completeness=comp,
        sector_allocations=sectors,
    )

    assert res.composite_risk_score == Decimal("80.00")
    assert res.risk_tier == "HIGH"
    assert res.assessment_status == "COMPLETE"
    assert res.components.single_stock_concentration_score == Decimal("100.00")
    assert res.components.sector_concentration_score == Decimal("100.00")
    assert res.components.diversification_breadth_score == Decimal("100.00")
    assert res.components.data_quality_score == Decimal("0.00")


def test_hand_verified_plan_example_3_partial_missing_data():
    """
    Plan Example 3: Example 1 with 1 holding unpriced (CR = 0.8000):
    C_stock = 45.00, C_sector = 50.00, C_breadth = 56.50
    C_quality = (1 - 0.8000) * 80 = 16.00
    Composite = 39.55 + 0.20(16) = 39.55 + 3.20 = 42.75 -> MODERATE (status PARTIAL)
    """
    conc = ConcentrationMetrics(
        top_holding_symbol="RELIANCE",
        top_holding_weight_percent=Decimal("25.00"),
        top_3_concentration_percent=Decimal("65.00"),
        herfindahl_index=Decimal("0.2050"),
        effective_holdings_count=Decimal("4.88"),
        concentration_tier="MODERATE",
    )
    comp = PortfolioCompleteness(
        is_complete=False,
        completeness_ratio=Decimal("0.8000"),
        total_holdings_count=5,
        priced_holdings_count=4,
        unpriced_holdings_count=1,
        has_stale_prices=False,
    )
    sectors = [
        SectorAllocation(
            sector="Technology",
            cost_basis=Decimal("4000.00"),
            market_value=Decimal("4000.00"),
            allocation_percent=Decimal("40.00"),
            holdings_count=2,
            priced_count=2,
            unpriced_count=0,
        ),
        SectorAllocation(
            sector="Financial Services",
            cost_basis=Decimal("3500.00"),
            market_value=Decimal("3500.00"),
            allocation_percent=Decimal("35.00"),
            holdings_count=2,
            priced_count=2,
            unpriced_count=0,
        ),
        SectorAllocation(
            sector="Energy",
            cost_basis=Decimal("2500.00"),
            market_value=Decimal("2500.00"),
            allocation_percent=Decimal("25.00"),
            holdings_count=1,
            priced_count=1,
            unpriced_count=0,
        ),
    ]

    res = calculate_portfolio_risk_assessment(
        status=ValuationStatus.PARTIAL,
        concentration=conc,
        completeness=comp,
        sector_allocations=sectors,
    )

    assert res.composite_risk_score == Decimal("42.75")
    assert res.risk_tier == "MODERATE"
    assert res.assessment_status == "PARTIAL"
    assert res.components.data_quality_score == Decimal("16.00")


# =====================================================================
# 4. Missing Data & Incomplete States Handling
# =====================================================================

def test_empty_portfolio_risk_assessment():
    """Verify empty portfolio yields None scores and EMPTY status."""
    res = calculate_portfolio_risk_assessment(
        status=ValuationStatus.EMPTY,
        concentration=ConcentrationMetrics(),
        completeness=PortfolioCompleteness(
            is_complete=False,
            completeness_ratio=Decimal("0.0000"),
            total_holdings_count=0,
            priced_holdings_count=0,
            unpriced_holdings_count=0,
        ),
        sector_allocations=[],
    )

    assert res.composite_risk_score is None
    assert res.risk_tier is None
    assert res.assessment_status == "EMPTY"
    assert res.components.single_stock_concentration_score is None
    assert res.components.sector_concentration_score is None
    assert res.components.diversification_breadth_score is None
    assert res.components.data_quality_score is None


def test_wholly_unpriced_portfolio_risk_assessment():
    """Verify wholly unpriced portfolio yields None scores and UNVALUED status."""
    res = calculate_portfolio_risk_assessment(
        status=ValuationStatus.UNVALUED,
        concentration=ConcentrationMetrics(),
        completeness=PortfolioCompleteness(
            is_complete=False,
            completeness_ratio=Decimal("0.0000"),
            total_holdings_count=3,
            priced_holdings_count=0,
            unpriced_holdings_count=3,
        ),
        sector_allocations=[],
    )

    assert res.composite_risk_score is None
    assert res.risk_tier is None
    assert res.assessment_status == "UNVALUED"
    assert res.components.single_stock_concentration_score is None


# =====================================================================
# 5. Explainable Insights Generator Tests
# =====================================================================

def test_generate_insights_empty_portfolio():
    """Verify empty portfolio yields truthful single INFO insight."""
    insights = generate_portfolio_risk_insights(
        portfolio_id="test-empty",
        status=ValuationStatus.EMPTY,
        concentration=ConcentrationMetrics(),
        completeness=PortfolioCompleteness(
            is_complete=False,
            completeness_ratio=Decimal("0.0000"),
            total_holdings_count=0,
            priced_holdings_count=0,
            unpriced_holdings_count=0,
        ),
        sector_allocations=[],
        risk_assessment=PortfolioRiskAssessment(
            composite_risk_score=None,
            risk_tier=None,
            assessment_status="EMPTY",
        ),
    )

    assert len(insights) == 1
    ins = insights[0]
    assert ins.id == "test-empty-risk-empty"
    assert ins.category == InsightCategory.RISK
    assert ins.severity == InsightSeverity.INFO
    assert "Portfolio is Empty" in ins.title
    assert ins.evidence == {"holdings_count": 0}
    assert ins.is_simulated is True
    assert ins.source == "DETERMINISTIC_RISK_ENGINE"
    assert ins.created_at.tzinfo is not None


def test_generate_insights_wholly_unpriced_portfolio():
    """Verify wholly unpriced portfolio yields WARNING insight without fabricating prices."""
    insights = generate_portfolio_risk_insights(
        portfolio_id="test-unvalued",
        status=ValuationStatus.UNVALUED,
        concentration=ConcentrationMetrics(),
        completeness=PortfolioCompleteness(
            is_complete=False,
            completeness_ratio=Decimal("0.0000"),
            total_holdings_count=2,
            priced_holdings_count=0,
            unpriced_holdings_count=2,
        ),
        sector_allocations=[],
        risk_assessment=PortfolioRiskAssessment(
            composite_risk_score=None,
            risk_tier=None,
            assessment_status="UNVALUED",
        ),
    )

    assert len(insights) == 1
    ins = insights[0]
    assert ins.id == "test-unvalued-risk-unvalued"
    assert ins.category == InsightCategory.RISK
    assert ins.severity == InsightSeverity.WARNING
    assert "Market Prices Unavailable" in ins.title


def test_generate_insights_balanced_portfolio():
    """Verify insights generated for complete balanced portfolio."""
    conc = ConcentrationMetrics(
        top_holding_symbol="M&M",  # test symbol with '&'
        top_holding_weight_percent=Decimal("20.00"),
        top_3_concentration_percent=Decimal("50.00"),
        herfindahl_index=Decimal("0.1000"),
        effective_holdings_count=Decimal("10.00"),
        concentration_tier="LOW",
    )
    comp = PortfolioCompleteness(
        is_complete=True,
        completeness_ratio=Decimal("1.0000"),
        total_holdings_count=5,
        priced_holdings_count=5,
        unpriced_holdings_count=0,
        has_stale_prices=False,
    )
    sectors = [
        SectorAllocation(
            sector="Auto",
            cost_basis=Decimal("1000.00"),
            market_value=Decimal("1000.00"),
            allocation_percent=Decimal("25.00"),
            holdings_count=1,
            priced_count=1,
            unpriced_count=0,
        ),
    ]
    risk_assessment = PortfolioRiskAssessment(
        composite_risk_score=Decimal("25.00"),
        risk_tier="LOW",
        assessment_status="COMPLETE",
        components=RiskComponentScores(
            single_stock_concentration_score=Decimal("30.00"),
            sector_concentration_score=Decimal("25.00"),
            diversification_breadth_score=Decimal("25.00"),
            data_quality_score=Decimal("0.00"),
        ),
    )

    insights = generate_portfolio_risk_insights(
        portfolio_id="test-port",
        status=ValuationStatus.COMPLETE,
        concentration=conc,
        completeness=comp,
        sector_allocations=sectors,
        risk_assessment=risk_assessment,
    )

    # Expect composite, stock, sector, breadth, and quality insights
    assert len(insights) >= 5
    ids = [i.id for i in insights]
    assert "test-port-risk-composite" in ids
    assert "test-port-concentration-stock" in ids
    assert "test-port-concentration-sector" in ids
    assert "test-port-breadth-enh" in ids
    assert "test-port-data-complete" in ids

    # Check symbol with '&' passes SYMBOL_REGEX
    stock_ins = next(i for i in insights if i.id == "test-port-concentration-stock")
    assert stock_ins.related_symbols == ["M&M"]


# =====================================================================
# 6. Service & API Integration Tests
# =====================================================================

@pytest.mark.asyncio
async def test_analytics_service_attaches_risk_assessment(test_db_setup):
    """Verify AnalyticsService calculate_portfolio_analytics populates risk_assessment."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        p = await port_service.create_portfolio(
            PortfolioCreate(
                name="Risk Assessment Test",
                holdings=[
                    HoldingCreate(
                        symbol="RELIANCE",
                        exchange="NSE",
                        asset_class="EQUITY",
                        quantity=10,
                        average_buy_price=Decimal("2500.00"),
                        sector="Energy",
                    ),
                ],
            )
        )

        analytics_service = AnalyticsService(session)
        analytics = await analytics_service.calculate_portfolio_analytics(p.id)

        assert analytics is not None
        assert analytics.risk_assessment is not None
        assert analytics.risk_assessment.composite_risk_score is not None
        assert analytics.risk_assessment.risk_tier == "HIGH"
        assert analytics.risk_assessment.assessment_status == "COMPLETE"
        assert analytics.risk_assessment.components.single_stock_concentration_score == Decimal("100.00")


@pytest.mark.asyncio
async def test_api_insights_endpoint(client: AsyncClient):
    """Verify GET /api/v1/portfolios/{portfolio_id}/insights endpoint works end-to-end."""
    # 1. Create portfolio via API
    res_create = await client.post(
        "/api/v1/portfolios",
        json={
            "name": "API Insights Test",
            "is_sample": False,
            "holdings": [
                {
                    "symbol": "TCS",
                    "exchange": "NSE",
                    "quantity": 5,
                    "average_buy_price": "3500.00",
                    "sector": "Technology",
                }
            ],
        },
    )
    assert res_create.status_code == 201
    port_id = res_create.json()["id"]

    # 2. Existing analytics endpoint returns risk_assessment
    res_analytics = await client.get(f"/api/v1/portfolios/{port_id}/analytics")
    assert res_analytics.status_code == 200
    data_analytics = res_analytics.json()
    assert "risk_assessment" in data_analytics
    assert data_analytics["risk_assessment"]["composite_risk_score"] is not None

    # 3. Insights endpoint returns PortfolioInsightsResponse
    res_insights = await client.get(f"/api/v1/portfolios/{port_id}/insights")
    assert res_insights.status_code == 200
    data_insights = res_insights.json()
    assert data_insights["portfolio_id"] == port_id
    assert data_insights["total_insights"] > 0
    assert len(data_insights["insights"]) == data_insights["total_insights"]

    # 4. Not found returns 404 envelope
    res_404 = await client.get("/api/v1/portfolios/00000000-0000-0000-0000-000000000000/insights")
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "PORTFOLIO_NOT_FOUND"

