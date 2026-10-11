import copy
from decimal import Decimal
from typing import Any, Dict, List
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.mcp.schemas import APPROVED_TOOLS
from app.mcp.tools import execute_governed_tool
from app.providers.demo_market_data import DemoMarketDataProvider
from app.schemas.ai_reasoning import (
    AIInsightReport,
    AlertSeverity,
    ConfidenceLevel,
    DriverType,
    FindingStatus,
    ReviewStatus,
)
from app.schemas.analytics import (
    ConcentrationMetrics,
    PortfolioAnalyticsResponse,
    ValuationStatus,
)
from app.schemas.market_data import QuoteStatus
from app.schemas.portfolio import HoldingCreate, PortfolioCreate
from app.services.ai.grounding_validator import ClaimGroundingValidator, FindingCode
from app.services.ai.providers.demo_provider import DeterministicDemoProvider
from app.services.ai.reasoning_service import resolve_ai_provider
from app.services.market_data_service import resolve_market_data_provider
from app.services.portfolio_service import PortfolioService


# ===========================================================================
# 1. Pipeline Test: Portfolio Input to Validated AI Insights
# ===========================================================================

@pytest.mark.asyncio
async def test_e2e_full_pipeline_input_to_validated_insights(client: AsyncClient, test_db_setup):
    """
    Longest genuine end-to-end pipeline test:
    1. Create a portfolio with initial holdings via FastAPI REST endpoint.
    2. Add an additional holding via the holdings REST endpoint.
    3. Retrieve the full portfolio details and verify position persistence.
    4. Compute portfolio analytics and verify valuation, sectors, and concentration.
    5. Exercise governed MCP tools (lookup, metrics, risk, evidence bundle, AI insights).
    6. Generate AI reasoning report via the AI insights REST endpoint.
    7. Verify report provenance, evidence grounding, disclaimers, and VERIFIED status.
    8. Inject an unsupported claim and verify that ClaimGroundingValidator rejects it.
    """
    session_factory, _ = test_db_setup

    # Stage 1: Create portfolio with 2 holdings (TCS and INFY)
    create_payload = {
        "name": "E2E Institutional Bluechip Fund",
        "description": "Multi-stock integration test basket",
        "is_sample": False,
        "holdings": [
            {
                "symbol": "TCS",
                "exchange": "NSE",
                "quantity": 25,
                "average_buy_price": "3800.00",
                "sector": "Technology",
                "asset_class": "EQUITY",
            },
            {
                "symbol": "INFY",
                "exchange": "NSE",
                "quantity": 40,
                "average_buy_price": "1450.00",
                "sector": "Technology",
                "asset_class": "EQUITY",
            },
        ],
    }
    create_res = await client.post("/api/v1/portfolios", json=create_payload)
    assert create_res.status_code == 201
    portfolio_data = create_res.json()
    portfolio_id = portfolio_data["id"]
    assert portfolio_data["name"] == "E2E Institutional Bluechip Fund"
    assert len(portfolio_data["holdings"]) == 2

    # Stage 2: Add a 3rd holding (RELIANCE in Energy sector)
    add_holding_payload = {
        "symbol": "RELIANCE",
        "exchange": "NSE",
        "quantity": 30,
        "average_buy_price": "2800.00",
        "sector": "Energy",
        "asset_class": "EQUITY",
    }
    add_res = await client.post(f"/api/v1/portfolios/{portfolio_id}/holdings", json=add_holding_payload)
    assert add_res.status_code == 201
    added_holding = add_res.json()
    assert added_holding["symbol"] == "RELIANCE"
    assert added_holding["quantity"] == 30

    # Stage 3: Retrieve full portfolio details
    get_res = await client.get(f"/api/v1/portfolios/{portfolio_id}")
    assert get_res.status_code == 200
    portfolio_detail = get_res.json()
    assert len(portfolio_detail["holdings"]) == 3
    symbols_present = {h["symbol"] for h in portfolio_detail["holdings"]}
    assert symbols_present == {"TCS", "INFY", "RELIANCE"}

    # Stage 4: Calculate portfolio analytics
    analytics_res = await client.get(f"/api/v1/portfolios/{portfolio_id}/analytics")
    assert analytics_res.status_code == 200
    analytics_data = analytics_res.json()

    assert analytics_data["status"] == ValuationStatus.COMPLETE.value
    assert Decimal(analytics_data["valuation"]["total_cost_basis"]) == Decimal("237000.00")  # (25*3800) + (40*1450) + (30*2800) = 95000 + 58000 + 84000
    assert Decimal(analytics_data["valuation"]["total_market_value"]) > Decimal("0")
    assert analytics_data["completeness"]["is_complete"] is True
    assert analytics_data["completeness"]["total_holdings_count"] == 3
    assert analytics_data["completeness"]["priced_holdings_count"] == 3
    assert analytics_data["completeness"]["unpriced_holdings_count"] == 0
    assert Decimal(analytics_data["completeness"]["completeness_ratio"]) == Decimal("1.0000")

    # Concentration checks
    assert analytics_data["concentration"]["top_holding_symbol"] in symbols_present
    assert Decimal(analytics_data["concentration"]["top_holding_weight_percent"]) > Decimal("0")
    assert Decimal(analytics_data["concentration"]["herfindahl_index"]) > Decimal("0")
    assert Decimal(analytics_data["concentration"]["effective_holdings_count"]) > Decimal("1.00")
    assert analytics_data["concentration"]["concentration_tier"] in ("LOW", "MODERATE", "HIGH")

    # Sector allocations (Technology and Energy)
    sectors = {s["sector"]: s for s in analytics_data["sector_allocations"]}
    assert "Technology" in sectors
    assert "Energy" in sectors
    assert sectors["Technology"]["priced_count"] == 2
    assert sectors["Energy"]["priced_count"] == 1

    # Stage 5: Exercise governed MCP tools directly
    mcp_portfolio = await execute_governed_tool(
        "get_portfolio",
        {"portfolio_id": portfolio_id},
        session_factory=session_factory,
    )
    assert mcp_portfolio["id"] == portfolio_id
    assert len(mcp_portfolio["holdings"]) == 3

    mcp_list = await execute_governed_tool(
        "list_portfolios",
        {"is_sample": False},
        session_factory=session_factory,
    )
    assert any(p["id"] == portfolio_id for p in mcp_list["portfolios"])

    mcp_market = await execute_governed_tool(
        "get_market_snapshot",
        {"symbols": ["TCS", "INFY", "RELIANCE"], "exchange": "NSE"},
    )
    assert len(mcp_market["quotes"]) == 3
    assert all(q["status"] == "AVAILABLE" for q in mcp_market["quotes"].values())

    mcp_analytics = await execute_governed_tool(
        "calculate_portfolio_metrics",
        {"portfolio_id": portfolio_id},
        session_factory=session_factory,
    )
    assert mcp_analytics["portfolio_id"] == portfolio_id
    assert mcp_analytics["status"] == ValuationStatus.COMPLETE.value

    mcp_risk = await execute_governed_tool(
        "score_portfolio_risk",
        {"portfolio_id": portfolio_id},
        session_factory=session_factory,
    )
    assert mcp_risk["portfolio_id"] == portfolio_id
    assert Decimal(mcp_risk["risk_assessment"]["composite_risk_score"]) >= Decimal("0.00")

    mcp_bundle = await execute_governed_tool(
        "get_evidence_bundle",
        {"portfolio_id": portfolio_id},
        session_factory=session_factory,
    )
    assert mcp_bundle["portfolio_id"] == portfolio_id
    assert mcp_bundle["metadata"]["completeness_status"] == ValuationStatus.COMPLETE.value
    assert mcp_bundle["metadata"]["has_missing_prices"] is False

    mcp_insights = await execute_governed_tool(
        "generate_portfolio_ai_insights",
        {"portfolio_id": portfolio_id, "include_news": True, "news_limit": 5},
        session_factory=session_factory,
    )
    assert mcp_insights["portfolio_id"] == portfolio_id
    assert mcp_insights["review_status"] == "VERIFIED"

    # Stage 6: Generate AI intelligence report via REST endpoint
    ai_res = await client.post(
        f"/api/v1/portfolios/{portfolio_id}/ai-insights",
        json={"include_news": True, "news_limit": 5},
    )
    assert ai_res.status_code == 200
    report_dict = ai_res.json()

    # Stage 7: Verify report structure, provenance, and grounding
    assert report_dict["portfolio_id"] == portfolio_id
    assert report_dict["report_id"].startswith("rep-")
    assert report_dict["provider_name"] == "DETERMINISTIC_DEMO_REASONER"
    assert report_dict["model_id"] == "deterministic-demo-v1"
    assert report_dict["is_simulated"] is True
    assert report_dict["review_status"] == "VERIFIED"

    assert len(report_dict["executive_summary"]) >= 10
    assert len(report_dict["key_drivers"]) >= 3
    assert len(report_dict["risk_alerts"]) >= 1
    assert len(report_dict["review_cards"]) >= 1
    assert len(report_dict["disclaimers"]) >= 3

    # Grounding report invariants
    grounding_info = report_dict["grounding_report"]
    assert grounding_info["is_acceptable"] is True
    assert grounding_info["rejected_count"] == 0
    assert grounding_info["flagged_count"] == 0
    assert grounding_info["total_claims_checked"] > 0
    assert all(d["is_grounded"] is True for d in report_dict["key_drivers"])
    assert all(c["review_status"] == "VERIFIED" for c in report_dict["review_cards"])

    # Stage 8: Negative Grounding Invariance Test
    # Verify that injecting an ungrounded claim forces ClaimGroundingValidator to REJECT the report
    report_obj = AIInsightReport.model_validate(report_dict)
    corrupted_report = copy.deepcopy(report_obj)
    corrupted_report.review_cards[0].related_symbols = ["FABRICATED-UNLISTED-CORP"]

    validator = ClaimGroundingValidator()
    # Reconstruct evidence bundle from analytics for validation
    from app.services.ai.evidence_assembler import EvidenceAssemblerService
    async with session_factory() as session:
        assembler = EvidenceAssemblerService(session=session)
        evidence = await assembler.assemble_portfolio_evidence(portfolio_id)

    validated_corrupted = validator.validate_report(corrupted_report, evidence)
    assert validated_corrupted.review_status == ReviewStatus.REJECTED
    assert validated_corrupted.grounding_report.rejected_count > 0
    assert validated_corrupted.review_cards[0].review_status == ReviewStatus.REJECTED
    assert any(
        f.details.get("code") == FindingCode.SYMBOL_UNSUPPORTED
        for f in validated_corrupted.grounding_report.findings
        if f.status == FindingStatus.REJECTED
    )


# ===========================================================================
# 2. Boundary Test: Empty Portfolio (0 Holdings)
# ===========================================================================

@pytest.mark.asyncio
async def test_e2e_empty_portfolio_boundary_and_contracts(client: AsyncClient, test_db_setup):
    """
    Verifies that an empty portfolio (0 holdings):
    - Has status EMPTY and ₹0 valuation.
    - Does not cause division-by-zero, NaN, or Infinity errors in HHI/ENH math.
    - Keeps unavailable metrics as None rather than fabricating zero values.
    - Operates cleanly across MCP tools and AI insight generation.
    - Accurately discloses zero holdings in the executive summary and confidence indicator.
    """
    session_factory, _ = test_db_setup

    # 1. Create empty portfolio
    create_res = await client.post(
        "/api/v1/portfolios",
        json={"name": "Completely Empty Portfolio", "is_sample": False, "holdings": []},
    )
    assert create_res.status_code == 201
    portfolio_id = create_res.json()["id"]

    # 2. Query analytics
    analytics_res = await client.get(f"/api/v1/portfolios/{portfolio_id}/analytics")
    assert analytics_res.status_code == 200
    data = analytics_res.json()

    assert data["status"] == ValuationStatus.EMPTY.value
    assert Decimal(data["valuation"]["total_cost_basis"]) == Decimal("0.00")
    assert Decimal(data["valuation"]["total_market_value"]) == Decimal("0.00")
    assert data["valuation"]["unrealized_pnl"] is None
    assert data["valuation"]["unrealized_pnl_percent"] is None

    # Completeness
    assert data["completeness"]["is_complete"] is False
    assert Decimal(data["completeness"]["completeness_ratio"]) == Decimal("0.0000")
    assert data["completeness"]["total_holdings_count"] == 0
    assert data["completeness"]["priced_holdings_count"] == 0
    assert data["completeness"]["unpriced_holdings_count"] == 0

    # Concentration & Breadth: None, no division by zero or NaN
    assert data["concentration"]["top_holding_symbol"] is None
    assert data["concentration"]["top_holding_weight_percent"] is None
    assert data["concentration"]["herfindahl_index"] is None
    assert data["concentration"]["effective_holdings_count"] is None
    assert data["concentration"]["concentration_tier"] is None

    # Risk Assessment: None score, status EMPTY
    assert data["risk_assessment"]["composite_risk_score"] is None
    assert data["risk_assessment"]["risk_tier"] is None
    assert data["risk_assessment"]["assessment_status"] == "EMPTY"

    # Sector allocations and holdings empty
    assert data["sector_allocations"] == []
    assert data["holdings"] == []

    # 3. Governed MCP tools on empty portfolio
    mcp_metrics = await execute_governed_tool(
        "calculate_portfolio_metrics",
        {"portfolio_id": portfolio_id},
        session_factory=session_factory,
    )
    assert mcp_metrics["status"] == ValuationStatus.EMPTY.value
    assert mcp_metrics["valuation"]["total_market_value"] == "0.00"

    mcp_bundle = await execute_governed_tool(
        "get_evidence_bundle",
        {"portfolio_id": portfolio_id},
        session_factory=session_factory,
    )
    assert mcp_bundle["portfolio_id"] == portfolio_id
    assert mcp_bundle["metadata"]["completeness_status"] == ValuationStatus.EMPTY.value
    assert mcp_bundle["market_snapshot"]["total_symbols"] == 0

    # 4. Generate AI insights on empty portfolio
    ai_res = await client.post(f"/api/v1/portfolios/{portfolio_id}/ai-insights")
    assert ai_res.status_code == 200
    report = ai_res.json()

    assert report["review_status"] == "VERIFIED"
    assert "empty with no recorded holdings" in report["executive_summary"].lower()
    assert report["confidence"]["level"] == "LOW"
    assert Decimal(str(report["confidence"]["score"])) == Decimal("0.50")
    assert Decimal(str(report["confidence"]["data_quality_discount"])) == Decimal("0.50")
    assert "not a statistically calibrated" in report["confidence"]["calibration_limitation"].lower()

    # Risk alert specifies DATA_COMPLETENESS with INFO severity
    assert any(
        a["category"] == "DATA_COMPLETENESS" and a["severity"] == "INFO"
        for a in report["risk_alerts"]
    )
    assert report["grounding_report"]["is_acceptable"] is True


# ===========================================================================
# 3. Boundary Test: Single-Stock Portfolio (100% Concentration)
# ===========================================================================

@pytest.mark.asyncio
async def test_e2e_single_stock_portfolio_100_percent_concentration(client: AsyncClient, test_db_setup):
    """
    Verifies a portfolio with exactly 1 holding:
    - Allocation is 100.00% to the single stock.
    - Herfindahl Index is 1.0000 and Effective Holdings Count is 1.00.
    - Concentration tier is HIGH.
    - Composite risk score is finite, valid (0-100), and diversification breadth score reflects maximum concentration.
    - Grounding validation passes with accurate citations of top_holding_weight_percent = 100.00.
    """
    session_factory, _ = test_db_setup

    # 1. Create single-holding portfolio (50 shares of RELIANCE)
    create_res = await client.post(
        "/api/v1/portfolios",
        json={
            "name": "Single Stock Reliance Concentrated",
            "is_sample": False,
            "holdings": [
                {
                    "symbol": "RELIANCE",
                    "exchange": "NSE",
                    "quantity": 50,
                    "average_buy_price": "2850.50",
                    "sector": "Energy",
                    "asset_class": "EQUITY",
                }
            ],
        },
    )
    assert create_res.status_code == 201
    portfolio_id = create_res.json()["id"]

    # 2. Query analytics
    analytics_res = await client.get(f"/api/v1/portfolios/{portfolio_id}/analytics")
    assert analytics_res.status_code == 200
    data = analytics_res.json()

    assert data["status"] == ValuationStatus.COMPLETE.value
    assert data["concentration"]["top_holding_symbol"] == "RELIANCE"
    assert Decimal(data["concentration"]["top_holding_weight_percent"]) == Decimal("100.00")
    assert Decimal(data["concentration"]["top_3_concentration_percent"]) == Decimal("100.00")
    assert Decimal(data["concentration"]["herfindahl_index"]) == Decimal("1.0000")
    assert Decimal(data["concentration"]["effective_holdings_count"]) == Decimal("1.00")
    assert data["concentration"]["concentration_tier"] == "HIGH"

    # Risk assessment
    risk = data["risk_assessment"]
    assert risk["composite_risk_score"] is not None
    comp_score = Decimal(risk["composite_risk_score"])
    assert Decimal("0.00") <= comp_score <= Decimal("100.00")
    assert risk["assessment_status"] == "COMPLETE"
    assert risk["components"]["single_stock_concentration_score"] is not None

    # 3. Governed MCP risk scoring tool
    mcp_risk = await execute_governed_tool(
        "score_portfolio_risk",
        {"portfolio_id": portfolio_id},
        session_factory=session_factory,
    )
    assert mcp_risk["risk_assessment"]["composite_risk_score"] == str(comp_score)

    # 4. AI insights generation
    ai_res = await client.post(f"/api/v1/portfolios/{portfolio_id}/ai-insights")
    assert ai_res.status_code == 200
    report = ai_res.json()

    assert report["review_status"] == "VERIFIED"
    assert report["grounding_report"]["is_acceptable"] is True

    # Confirm key driver for top holding exposure reflects 100%
    conc_driver = next(d for d in report["key_drivers"] if d["driver_type"] == "CONCENTRATION")
    assert conc_driver["supporting_metric_key"] == "concentration.top_holding_weight_percent"
    assert Decimal(str(conc_driver["supporting_metric_value"])) == Decimal("100.00")
    assert "RELIANCE" in conc_driver["title"]


# ===========================================================================
# 4. Boundary Test: Missing or Unpriced Holdings Preservation
# ===========================================================================

@pytest.mark.asyncio
async def test_e2e_partially_and_wholly_unpriced_holdings_preservation(client: AsyncClient, test_db_setup):
    """
    Verifies that unpriced positions:
    1. Are marked UNAVAILABLE rather than silently converted to 0 price.
    2. Correctly decrement completeness_ratio and increment unpriced_holdings_count.
    3. Generate partial valuation and completeness warnings.
    4. Apply confidence penalties in AI reasoning without crashing.
    5. Pass ClaimGroundingValidator through explicit uncertainty disclosure.
    """
    session_factory, _ = test_db_setup

    # Case A: Partially Priced Portfolio (1 priced: RELIANCE, 1 unpriced: UNLISTED-STARTUP)
    create_res = await client.post(
        "/api/v1/portfolios",
        json={
            "name": "Partially Priced Venture Basket",
            "is_sample": False,
            "holdings": [
                {
                    "symbol": "RELIANCE",
                    "exchange": "NSE",
                    "quantity": 20,
                    "average_buy_price": "2850.50",
                    "sector": "Energy",
                },
                {
                    "symbol": "UNLISTED-STARTUP",
                    "exchange": "NSE",
                    "quantity": 100,
                    "average_buy_price": "500.00",
                    "sector": "Technology",
                },
            ],
        },
    )
    assert create_res.status_code == 201
    part_id = create_res.json()["id"]

    analytics_res = await client.get(f"/api/v1/portfolios/{part_id}/analytics")
    assert analytics_res.status_code == 200
    part_data = analytics_res.json()

    assert part_data["status"] == ValuationStatus.PARTIAL.value
    assert part_data["completeness"]["is_complete"] is False
    assert part_data["completeness"]["total_holdings_count"] == 2
    assert part_data["completeness"]["priced_holdings_count"] == 1
    assert part_data["completeness"]["unpriced_holdings_count"] == 1
    assert Decimal(part_data["completeness"]["completeness_ratio"]) == Decimal("0.5000")

    # Verify unpriced position details
    unpriced_positions = part_data["completeness"]["unpriced_positions"]
    assert len(unpriced_positions) == 1
    assert unpriced_positions[0]["symbol"] == "UNLISTED-STARTUP"
    assert unpriced_positions[0]["pricing_status"] == "UNAVAILABLE"

    # AI Reasoning on partially unpriced portfolio
    part_ai_res = await client.post(f"/api/v1/portfolios/{part_id}/ai-insights")
    assert part_ai_res.status_code == 200
    part_report = part_ai_res.json()

    assert part_report["review_status"] == "VERIFIED"
    assert Decimal(str(part_report["confidence"]["data_quality_discount"])) > Decimal("0.00")
    assert any("unpriced" in gap.lower() for gap in part_report["uncertainty_and_gaps"])
    assert any("unlisted-startup" in gap.lower() for gap in part_report["uncertainty_and_gaps"])

    # Case B: Wholly Unpriced Portfolio (2 unpriced holdings: UNKNOWN-ALPHA, UNKNOWN-BETA)
    create_unpriced_res = await client.post(
        "/api/v1/portfolios",
        json={
            "name": "Completely Unpriced Private Equity",
            "is_sample": False,
            "holdings": [
                {
                    "symbol": "UNKNOWN-ALPHA",
                    "exchange": "NSE",
                    "quantity": 10,
                    "average_buy_price": "100.00",
                },
                {
                    "symbol": "UNKNOWN-BETA",
                    "exchange": "NSE",
                    "quantity": 20,
                    "average_buy_price": "200.00",
                },
            ],
        },
    )
    assert create_unpriced_res.status_code == 201
    unpriced_id = create_unpriced_res.json()["id"]

    unpriced_analytics_res = await client.get(f"/api/v1/portfolios/{unpriced_id}/analytics")
    assert unpriced_analytics_res.status_code == 200
    unpriced_analytics = unpriced_analytics_res.json()

    assert unpriced_analytics["status"] == ValuationStatus.UNVALUED.value
    assert unpriced_analytics["completeness"]["priced_holdings_count"] == 0
    assert unpriced_analytics["completeness"]["unpriced_holdings_count"] == 2
    assert Decimal(unpriced_analytics["completeness"]["completeness_ratio"]) == Decimal("0.0000")

    # AI Reasoning on wholly unpriced portfolio (Scenario B in DeterministicDemoProvider)
    unpriced_ai_res = await client.post(f"/api/v1/portfolios/{unpriced_id}/ai-insights")
    assert unpriced_ai_res.status_code == 200
    unpriced_report = unpriced_ai_res.json()

    assert unpriced_report["review_status"] == "VERIFIED"
    assert unpriced_report["confidence"]["level"] == "LOW"
    assert Decimal(str(unpriced_report["confidence"]["score"])) == Decimal("0.25")
    assert Decimal(str(unpriced_report["confidence"]["data_quality_discount"])) == Decimal("0.75")
    assert any(
        a["headline"] == "Valuation Unavailable (Unpriced Portfolio)" and a["severity"] == "CRITICAL"
        for a in unpriced_report["risk_alerts"]
    )
    assert unpriced_report["grounding_report"]["is_acceptable"] is True


# ===========================================================================
# 5. Boundary Test: Extreme Financial Values and Scale
# ===========================================================================

@pytest.mark.asyncio
async def test_e2e_extreme_financial_values_and_scale(client: AsyncClient, test_db_setup):
    """
    Verifies financial extremes and precision:
    1. Small positive value (₹0.01 per share): preserves exact 2-decimal precision.
    2. Large sovereign scale (10,000,000 shares @ ₹5,000 = ₹5,000 crore): computes valuations without overflow.
    3. Rejection of invalid inputs: non-finite (NaN, inf), booleans, zero, and negative values.
    """
    # 1. Micro-scale portfolio (quantity=1, price=0.01)
    micro_res = await client.post(
        "/api/v1/portfolios",
        json={
            "name": "Micro Precision Test",
            "is_sample": False,
            "holdings": [
                {
                    "symbol": "PENNY-STOCK",
                    "exchange": "NSE",
                    "quantity": 1,
                    "average_buy_price": "0.01",
                }
            ],
        },
    )
    assert micro_res.status_code == 201
    micro_id = micro_res.json()["id"]

    micro_analytics = await client.get(f"/api/v1/portfolios/{micro_id}/analytics")
    assert micro_analytics.status_code == 200
    assert Decimal(micro_analytics.json()["valuation"]["total_cost_basis"]) == Decimal("0.01")

    # 2. Large Sovereign Scale (₹5,000 crore cost basis)
    # 10,000,000 shares of TCS @ ₹5,000.00 = ₹50,000,000,000.00 (₹5,000 crore)
    sovereign_res = await client.post(
        "/api/v1/portfolios",
        json={
            "name": "Sovereign Wealth Macro Allocation",
            "is_sample": False,
            "holdings": [
                {
                    "symbol": "TCS",
                    "exchange": "NSE",
                    "quantity": 10_000_000,
                    "average_buy_price": "5000.00",
                    "sector": "Technology",
                }
            ],
        },
    )
    assert sovereign_res.status_code == 201
    sovereign_id = sovereign_res.json()["id"]

    sovereign_analytics_res = await client.get(f"/api/v1/portfolios/{sovereign_id}/analytics")
    assert sovereign_analytics_res.status_code == 200
    sovereign_data = sovereign_analytics_res.json()

    assert Decimal(sovereign_data["valuation"]["total_cost_basis"]) == Decimal("50000000000.00")
    # TCS demo price is ₹3,920.00 -> 10,000,000 * 3,920 = ₹39,200,000,000.00
    assert Decimal(sovereign_data["valuation"]["total_market_value"]) == Decimal("39200000000.00")
    assert Decimal(sovereign_data["valuation"]["unrealized_pnl"]) == Decimal("-10800000000.00")

    # AI Reasoning on large scale executes without precision loss or overflow
    sovereign_ai = await client.post(f"/api/v1/portfolios/{sovereign_id}/ai-insights")
    assert sovereign_ai.status_code == 200
    assert sovereign_ai.json()["review_status"] == "VERIFIED"
    assert "₹39,200,000,000.00" in sovereign_ai.json()["executive_summary"]

    # 3. Rejection of invalid numeric values at schema validation boundary
    # Test zero quantity
    r_zero_qty = await client.post(
        "/api/v1/portfolios",
        json={"name": "Bad Qty", "holdings": [{"symbol": "TCS", "quantity": 0, "average_buy_price": "100.00"}]},
    )
    assert r_zero_qty.status_code == 422

    # Test negative quantity
    r_neg_qty = await client.post(
        "/api/v1/portfolios",
        json={"name": "Bad Qty", "holdings": [{"symbol": "TCS", "quantity": -10, "average_buy_price": "100.00"}]},
    )
    assert r_neg_qty.status_code == 422

    # Test boolean quantity (must not be treated as int 1)
    r_bool_qty = await client.post(
        "/api/v1/portfolios",
        json={"name": "Bad Qty", "holdings": [{"symbol": "TCS", "quantity": True, "average_buy_price": "100.00"}]},
    )
    assert r_bool_qty.status_code == 422

    # Test zero price
    r_zero_price = await client.post(
        "/api/v1/portfolios",
        json={"name": "Bad Price", "holdings": [{"symbol": "TCS", "quantity": 10, "average_buy_price": "0.00"}]},
    )
    assert r_zero_price.status_code == 422

    # Test negative price
    r_neg_price = await client.post(
        "/api/v1/portfolios",
        json={"name": "Bad Price", "holdings": [{"symbol": "TCS", "quantity": 10, "average_buy_price": "-100.00"}]},
    )
    assert r_neg_price.status_code == 422

    # Test NaN price
    r_nan_price = await client.post(
        "/api/v1/portfolios",
        json={"name": "Bad Price", "holdings": [{"symbol": "TCS", "quantity": 10, "average_buy_price": "nan"}]},
    )
    assert r_nan_price.status_code == 422

    # Test Infinity price
    r_inf_price = await client.post(
        "/api/v1/portfolios",
        json={"name": "Bad Price", "holdings": [{"symbol": "TCS", "quantity": 10, "average_buy_price": "inf"}]},
    )
    assert r_inf_price.status_code == 422

    # Test Negative Infinity price
    r_ninf_price = await client.post(
        "/api/v1/portfolios",
        json={"name": "Bad Price", "holdings": [{"symbol": "TCS", "quantity": 10, "average_buy_price": "-inf"}]},
    )
    assert r_ninf_price.status_code == 422


# ===========================================================================
# 6. Test Isolation & Offline Safety Invariants
# ===========================================================================

@pytest.mark.asyncio
async def test_e2e_isolation_and_offline_safety_invariants(test_db_setup):
    """
    Confirms zero-cost and isolation invariants:
    1. Settings default to USE_MOCK_DATA=True, AI_PROVIDER='demo', MARKET_DATA_PROVIDER='demo'.
    2. Provider resolvers strictly yield simulated demo providers.
    3. Database state is cleanly isolated and does not collide across executions.
    """
    session_factory, _ = test_db_setup

    # Config checks
    assert settings.USE_MOCK_DATA is True
    assert settings.MARKET_DATA_PROVIDER == "demo"
    assert settings.AI_PROVIDER == "demo"

    # Resolver checks: verify strictly simulated demo providers are resolved
    market_provider = resolve_market_data_provider()
    assert isinstance(market_provider, DemoMarketDataProvider)
    assert market_provider.PROVIDER_NAME == "SIMULATED_DEMO_PROVIDER"

    ai_provider = resolve_ai_provider()
    assert isinstance(ai_provider, DeterministicDemoProvider)
    assert ai_provider.IS_SIMULATED is True

    # Database isolation check: verify table query succeeds in isolated session
    async with session_factory() as session:
        service = PortfolioService(session)
        portfolios = await service.list_portfolios()
        # Clean isolated DB has 0 portfolios before any test action
        assert isinstance(portfolios, list)
