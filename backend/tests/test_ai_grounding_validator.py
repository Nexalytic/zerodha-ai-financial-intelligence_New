from decimal import Decimal
import pytest

from app.schemas.ai_reasoning import (
    AIConfidenceIndicator,
    AIInsightReport,
    AIRiskAlert,
    AlertSeverity,
    ConfidenceLevel,
    DriverType,
    EvidenceKeyDriver,
    FindingStatus,
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
from app.services.ai.grounding_validator import ClaimGroundingValidator, FindingCode
from app.services.ai.providers.demo_provider import DeterministicDemoProvider


# ===========================================================================
# Fixture & Helpers
# ===========================================================================

def build_test_bundle(
    *,
    portfolio_id: str = "port-valid-100",
    portfolio_name: str = "Valid Grounding Test Portfolio",
    total_holdings_count: int = 3,
    priced_holdings_count: int = 3,
    total_cost_basis: Decimal = Decimal("100000.00"),
    total_market_value: Decimal = Decimal("115000.00"),
    unrealized_pnl: Decimal = Decimal("15000.00"),
    unrealized_pnl_percent: Decimal = Decimal("15.00"),
    top_symbol: str = "RELIANCE",
    top_weight: Decimal = Decimal("50.00"),
    hhi: Decimal = Decimal("3800.00"),
    composite_risk_score: Decimal = Decimal("62.50"),
    is_stale: bool = False,
    include_news: bool = True,
    unpriced_positions: list = None,
) -> PortfolioEvidenceBundle:
    """Helper constructing an evidence bundle for grounding verification tests."""
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
                pricing_source="SIMULATED_DEMO_PROVIDER",
                price_explanation="Missing quote in test",
            )
            for idx, p in enumerate(unpriced_positions)
        ]

    comp_ratio = (
        Decimal(priced_holdings_count) / Decimal(total_holdings_count)
        if total_holdings_count > 0
        else Decimal("0.0000")
    )

    valuation = PortfolioValuation(
        total_cost_basis=total_cost_basis,
        total_market_value=total_market_value,
        priced_cost_basis=total_cost_basis if priced_holdings_count > 0 else Decimal("0.00"),
        unrealized_pnl=unrealized_pnl if priced_holdings_count > 0 else None,
        unrealized_pnl_percent=unrealized_pnl_percent if priced_holdings_count > 0 else None,
    )

    completeness = PortfolioCompleteness(
        is_complete=(total_holdings_count > 0 and unpriced_count == 0),
        total_holdings_count=total_holdings_count,
        priced_holdings_count=priced_holdings_count,
        unpriced_holdings_count=unpriced_count,
        completeness_ratio=comp_ratio.quantize(Decimal("0.0001")),
        has_stale_prices=is_stale,
        unpriced_positions=unpriced_details,
    )

    concentration = ConcentrationMetrics(
        top_holding_symbol=top_symbol if priced_holdings_count > 0 else None,
        top_holding_weight_percent=top_weight if priced_holdings_count > 0 else None,
        herfindahl_index=hhi if priced_holdings_count > 0 else None,
        effective_holdings_count=Decimal("2.63") if priced_holdings_count > 0 else None,
        concentration_tier="HIGH" if priced_holdings_count > 0 else None,
    )

    sector_allocations = [
        SectorAllocation(
            sector="ENERGY",
            cost_basis=Decimal("50000.00"),
            market_value=Decimal("57500.00"),
            allocation_percent=Decimal("50.00"),
            holdings_count=1,
            priced_count=1,
            unpriced_count=0,
        )
    ] if priced_holdings_count > 0 else []

    risk_assessment = PortfolioRiskAssessment(
        composite_risk_score=composite_risk_score if priced_holdings_count > 0 else None,
        risk_tier="MODERATE" if priced_holdings_count > 0 else None,
        assessment_status="COMPLETE" if unpriced_count == 0 else "PARTIAL",
        components=RiskComponentScores(
            single_stock_concentration_score=Decimal("80.00"),
            sector_concentration_score=Decimal("60.00"),
            diversification_breadth_score=Decimal("50.00"),
            data_quality_score=Decimal("60.00"),
        ),
    )

    quotes = {
        "RELIANCE": Quote(
            symbol="RELIANCE",
            current_price=Decimal("2875.00"),
            status=QuoteStatus.AVAILABLE,
            is_stale=is_stale,
        ),
        "TCS": Quote(
            symbol="TCS",
            current_price=Decimal("3900.00"),
            status=QuoteStatus.AVAILABLE,
            is_stale=False,
        ),
    }

    news_articles = []
    if include_news:
        news_articles = [
            NewsArticle(
                id="news-rel-1",
                title="Reliance Expands Solar Capacity",
                summary="Strategic growth in clean energy.",
                related_symbols=["RELIANCE"],
            )
        ]

    return PortfolioEvidenceBundle(
        portfolio_id=portfolio_id,
        portfolio_name=portfolio_name,
        valuation=valuation,
        completeness=completeness,
        concentration=concentration,
        sector_allocations=sector_allocations,
        risk_assessment=risk_assessment,
        market_snapshot=BatchQuotesResponse(
            quotes=quotes,
            total_symbols=len(quotes),
            cache_hits_count=len(quotes),
            cache_misses_count=0,
        ),
        news_articles=news_articles,
    )


# ===========================================================================
# 1. Valid Grounded Reports
# ===========================================================================

@pytest.mark.asyncio
async def test_validator_passes_fully_grounded_demo_report():
    """Verify that reports generated by DeterministicDemoProvider pass all grounding checks."""
    evidence = build_test_bundle()
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    assert validated.review_status == ReviewStatus.VERIFIED
    assert validated.grounding_report.is_acceptable is True
    assert validated.grounding_report.rejected_count == 0
    assert validated.grounding_report.flagged_count == 0
    assert all(d.is_grounded for d in validated.key_drivers)
    assert all(c.review_status == ReviewStatus.VERIFIED for c in validated.review_cards)


# ===========================================================================
# 2. Symbol Validation Checks
# ===========================================================================

@pytest.mark.asyncio
async def test_validator_rejects_unsupported_symbols():
    """Verify that citing a symbol absent from evidence causes card and report REJECTION."""
    evidence = build_test_bundle()
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Inject hallucinated symbol into review card
    report.review_cards[0].related_symbols = ["FABRICATED_CORP"]

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    assert validated.review_status == ReviewStatus.REJECTED
    assert validated.grounding_report.rejected_count > 0
    assert validated.review_cards[0].review_status == ReviewStatus.REJECTED

    sym_finding = next(
        f for f in validated.grounding_report.findings
        if f.check_name == "SYMBOL_GROUNDING_CHECK" and f.status == FindingStatus.REJECTED
    )
    assert sym_finding.details["code"] == FindingCode.SYMBOL_UNSUPPORTED
    assert sym_finding.details["unsupported_symbol"] == "FABRICATED_CORP"


# ===========================================================================
# 3. Numeric Grounding Checks & Tolerance
# ===========================================================================

@pytest.mark.asyncio
async def test_validator_rejects_unknown_metric_path():
    """Verify unknown metric paths trigger METRIC_PATH_UNKNOWN rejection."""
    evidence = build_test_bundle()
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Modify driver with non-existent metric key
    report.key_drivers[0].supporting_metric_key = "valuation.non_existent_field"

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    assert validated.review_status == ReviewStatus.REJECTED
    assert validated.key_drivers[0].is_grounded is False
    path_finding = next(
        f for f in validated.grounding_report.findings
        if f.details.get("code") == FindingCode.METRIC_PATH_UNKNOWN
    )
    assert path_finding.status == FindingStatus.REJECTED


@pytest.mark.asyncio
async def test_validator_percentage_tolerance_within_boundary():
    """
    Verify percentage metric within ±0.05 tolerance PASSES.
    Evidence top_holding_weight_percent is 50.00%.
    Reported is 50.04% (diff 0.04 <= 0.05).
    """
    evidence = build_test_bundle(top_weight=Decimal("50.00"))
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    driver = next(d for d in report.key_drivers if d.driver_type == DriverType.CONCENTRATION)
    driver.supporting_metric_value = Decimal("50.04")

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    # Driver should remain grounded and passed
    assert driver.is_grounded is True
    assert not any(
        f.status == FindingStatus.REJECTED and f.target_id == driver.driver_id
        for f in validated.grounding_report.findings
    )


@pytest.mark.asyncio
async def test_validator_percentage_tolerance_exceeded():
    """
    Verify percentage metric exceeding ±0.05 tolerance is REJECTED.
    Evidence top_holding_weight_percent is 50.00%.
    Reported is 50.06% (diff 0.06 > 0.05).
    """
    evidence = build_test_bundle(top_weight=Decimal("50.00"))
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    driver = next(d for d in report.key_drivers if d.driver_type == DriverType.CONCENTRATION)
    driver.supporting_metric_value = Decimal("50.06")

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    assert driver.is_grounded is False
    assert validated.review_status == ReviewStatus.REJECTED
    mismatch_finding = next(
        f for f in validated.grounding_report.findings
        if f.target_id == driver.driver_id and f.details.get("code") == FindingCode.NUMERIC_VALUE_MISMATCH
    )
    assert mismatch_finding.status == FindingStatus.REJECTED


@pytest.mark.asyncio
async def test_validator_currency_not_using_percentage_tolerance():
    """
    Verify non-percentage metrics (like total_market_value) do NOT receive the 0.05% tolerance.
    Evidence market value is 115000.00.
    Reported is 115000.04 (diff 0.04 > currency tolerance 0.01).
    """
    evidence = build_test_bundle(total_market_value=Decimal("115000.00"))
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Attach card citing market_value
    report.review_cards[0].cited_metrics = {"valuation.total_market_value": Decimal("115000.04")}

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    assert validated.review_cards[0].review_status == ReviewStatus.REJECTED
    mismatch = next(
        f for f in validated.grounding_report.findings
        if f.target_id == report.review_cards[0].card_id and f.details.get("code") == FindingCode.NUMERIC_VALUE_MISMATCH
    )
    assert mismatch.status == FindingStatus.REJECTED


# ===========================================================================
# 4. Directional Consistency Checks
# ===========================================================================

@pytest.mark.asyncio
async def test_validator_rejects_positive_evidence_claimed_as_loss():
    """Verify that claiming portfolio loss when evidence shows profit is REJECTED."""
    evidence = build_test_bundle(unrealized_pnl=Decimal("15000.00"))  # Positive profit
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Contradictory executive summary claiming negative return
    report.executive_summary = (
        "The portfolio is facing severe losses with a negative return of -15.00% across holdings."
    )

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    assert validated.review_status == ReviewStatus.REJECTED
    dir_finding = next(
        f for f in validated.grounding_report.findings
        if f.details.get("code") == FindingCode.DIRECTIONAL_CONTRADICTION
    )
    assert dir_finding.status == FindingStatus.REJECTED


@pytest.mark.asyncio
async def test_validator_rejects_negative_evidence_claimed_as_profit():
    """Verify that claiming portfolio profit when evidence shows loss is REJECTED."""
    evidence = build_test_bundle(
        total_market_value=Decimal("80000.00"),
        total_cost_basis=Decimal("100000.00"),
        unrealized_pnl=Decimal("-20000.00"),
        unrealized_pnl_percent=Decimal("-20.00"),
    )
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Inject false claim of profit
    report.executive_summary = "The portfolio delivered strong growth with an unrealized profit of ₹20,000.00."

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    assert validated.review_status == ReviewStatus.REJECTED
    dir_finding = next(
        f for f in validated.grounding_report.findings
        if f.details.get("code") == FindingCode.DIRECTIONAL_CONTRADICTION
    )
    assert dir_finding.status == FindingStatus.REJECTED


@pytest.mark.asyncio
async def test_validator_rejects_pnl_claim_on_unpriced_portfolio():
    """Verify asserting P/L when portfolio is unpriced is REJECTED."""
    evidence = build_test_bundle(
        priced_holdings_count=0,
        unrealized_pnl=None,
        unpriced_positions=[{"symbol": "UNPRICED", "quantity": 10}],
    )
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Inject claim asserting profit on unpriced assets
    report.executive_summary = "Portfolio generated an unrealized pnl of +₹5,000.00 despite missing quotes."

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    assert validated.review_status == ReviewStatus.REJECTED
    dir_finding = next(
        f for f in validated.grounding_report.findings
        if f.details.get("code") == FindingCode.DIRECTIONAL_CONTRADICTION
    )
    assert dir_finding.status == FindingStatus.REJECTED


# ===========================================================================
# 5. Historical Risk Fabrication Checks
# ===========================================================================

@pytest.mark.asyncio
async def test_validator_rejects_fabricated_volatility_or_drawdown():
    """Verify that asserting specific numeric volatility or beta when history is insufficient is REJECTED."""
    evidence = build_test_bundle()  # historical_risk data_status is INSUFFICIENT_HISTORY
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Assert specific numerical historical metrics
    report.executive_summary += " The portfolio exhibits an annualized volatility of 18.5% and a maximum drawdown of 12.0%."

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    assert validated.review_status == ReviewStatus.REJECTED
    fab_finding = next(
        f for f in validated.grounding_report.findings
        if f.details.get("code") == FindingCode.HISTORICAL_RISK_FABRICATION
    )
    assert fab_finding.status == FindingStatus.REJECTED


@pytest.mark.asyncio
async def test_validator_accepts_honest_disclosure_of_insufficient_history():
    """Verify that stating historical volatility is unavailable PASSES."""
    evidence = build_test_bundle()
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Standard demo provider already states:
    # "Historical risk metrics are unavailable (data_status: INSUFFICIENT_HISTORY); price volatility, beta, and maximum drawdown are not inferred from snapshot quotes."
    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    # Must NOT have any HISTORICAL_RISK_FABRICATION findings
    assert not any(
        f.details.get("code") == FindingCode.HISTORICAL_RISK_FABRICATION
        for f in validated.grounding_report.findings
    )


# ===========================================================================
# 6. Missing-Data Disclosure Checks
# ===========================================================================

@pytest.mark.asyncio
async def test_validator_flags_omitted_unpriced_disclosure():
    """Verify that omitting unpriced disclosure when unpriced assets exist is FLAGGED."""
    evidence = build_test_bundle(
        total_holdings_count=3,
        priced_holdings_count=2,
        unpriced_positions=[{"symbol": "UNPRICED1", "quantity": 10}],
    )
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Wipe out uncertainty disclosures and alerts discussing unpriced assets
    report.uncertainty_and_gaps = []
    report.risk_alerts = []
    report.executive_summary = "All holdings are evaluated normally without caveats."

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    assert validated.review_status == ReviewStatus.FLAGGED_WITH_WARNINGS
    flag = next(
        f for f in validated.grounding_report.findings
        if f.details.get("code") == FindingCode.MISSING_DATA_DISCLOSURE_OMITTED
    )
    assert flag.status == FindingStatus.FLAGGED


@pytest.mark.asyncio
async def test_validator_flags_omitted_stale_disclosure():
    """Verify that omitting stale quote disclosure is FLAGGED."""
    evidence = build_test_bundle(is_stale=True)
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Wipe out uncertainty disclosures
    report.uncertainty_and_gaps = []
    report.risk_alerts = []

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    assert validated.review_status == ReviewStatus.FLAGGED_WITH_WARNINGS
    flag = next(
        f for f in validated.grounding_report.findings
        if f.details.get("issue") == "stale_quote_omitted"
    )
    assert flag.status == FindingStatus.FLAGGED


# ===========================================================================
# 7. Confidence Calibration Checks
# ===========================================================================

@pytest.mark.asyncio
async def test_validator_rejects_missing_confidence_limitation():
    """Verify that short or absent confidence limitation is REJECTED."""
    evidence = build_test_bundle()
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Replace with invalid short text
    report.confidence.calibration_limitation = "Too short"

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    assert validated.review_status == ReviewStatus.REJECTED
    conf_finding = next(
        f for f in validated.grounding_report.findings
        if f.details.get("code") == FindingCode.CONFIDENCE_CALIBRATION_UNGROUNDED
    )
    assert conf_finding.status == FindingStatus.REJECTED


@pytest.mark.asyncio
async def test_validator_flags_unpriced_without_confidence_discount():
    """Verify that having unpriced positions with 0.00 data_quality_discount is FLAGGED."""
    evidence = build_test_bundle(
        total_holdings_count=3,
        priced_holdings_count=2,
        unpriced_positions=[{"symbol": "UNPRICED1", "quantity": 10}],
    )
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Set data_quality_discount to zero
    report.confidence.data_quality_discount = Decimal("0.00")

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    assert any(
        f.details.get("code") == FindingCode.CONFIDENCE_CALIBRATION_UNGROUNDED
        and "data_quality_discount is 0.00" in (f.reason or "")
        for f in validated.grounding_report.findings
    )


# ===========================================================================
# 8. Malformed Inputs and Deterministic Reproducibility
# ===========================================================================

def test_validator_rejects_none_inputs():
    """Verify validator raises ValueError on None inputs."""
    validator = ClaimGroundingValidator()
    with pytest.raises(ValueError, match="must not be None"):
        validator.validate_report(None, None)


@pytest.mark.asyncio
async def test_validator_rejects_portfolio_id_mismatch():
    """Verify mismatched portfolio_id triggers PORTFOLIO_ID_MISMATCH rejection."""
    evidence = build_test_bundle(portfolio_id="port-AAA")
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Change report portfolio ID
    report.portfolio_id = "port-BBB"

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    assert validated.review_status == ReviewStatus.REJECTED
    id_finding = next(
        f for f in validated.grounding_report.findings
        if f.details.get("code") == FindingCode.PORTFOLIO_ID_MISMATCH
    )
    assert id_finding.status == FindingStatus.REJECTED


@pytest.mark.asyncio
async def test_validator_deterministic_reproducibility():
    """Verify validator produces identical findings across multiple executions."""
    evidence = build_test_bundle()
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    validator = ClaimGroundingValidator()
    rep1 = validator.generate_validation_report(report, evidence)
    rep2 = validator.generate_validation_report(report, evidence)

    assert rep1.total_claims_checked == rep2.total_claims_checked
    assert rep1.passed_count == rep2.passed_count
    assert rep1.flagged_count == rep2.flagged_count
    assert rep1.rejected_count == rep2.rejected_count
    assert rep1.is_acceptable == rep2.is_acceptable
    assert len(rep1.findings) == len(rep2.findings)
    for f1, f2 in zip(rep1.findings, rep2.findings):
        assert f1.check_name == f2.check_name
        assert f1.target_id == f2.target_id
        assert f1.status == f2.status
        assert f1.reason == f2.reason


# ===========================================================================
# 9. Phase 06 Grounding Remediation Regressions
# ===========================================================================

@pytest.mark.asyncio
async def test_validator_portfolio_breadth_alias_resolved():
    """Verify portfolio_breadth resolves to diversification_breadth_score in evidence."""
    evidence = build_test_bundle()
    # evidence.risk_assessment.components.diversification_breadth_score is Decimal("50.00")
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Add driver citing portfolio_breadth via component_scores path
    report.key_drivers.append(
        EvidenceKeyDriver(
            driver_id="driver-breadth-alias",
            driver_type=DriverType.RISK,
            title="Portfolio Breadth Metric",
            statement="Diversification breadth component score is 50.00.",
            supporting_metric_key="risk_assessment.component_scores.portfolio_breadth",
            supporting_metric_value=Decimal("50.00"),
            source_reference="analytics.risk",
            is_grounded=True,
        )
    )

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    breadth_finding = next(
        f for f in validated.grounding_report.findings
        if f.target_id == "driver-breadth-alias" and f.check_name == "NUMERIC_GROUNDING_CHECK"
    )
    assert breadth_finding.status == FindingStatus.PASSED


@pytest.mark.asyncio
async def test_validator_sector_specific_lookup_resolved():
    """Verify sector_allocations.<sector>.<field> resolves for valid sectors and allowed fields."""
    evidence = build_test_bundle()
    # Sector in test bundle is ENERGY with allocation_percent=50.00, market_value=57500.00
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    report.key_drivers.append(
        EvidenceKeyDriver(
            driver_id="driver-sector-specific",
            driver_type=DriverType.SECTOR,
            title="Energy Sector Allocation",
            statement="Energy sector represents 50.00% of the portfolio.",
            supporting_metric_key="sector_allocations.ENERGY.allocation_percent",
            supporting_metric_value=Decimal("50.00"),
            source_reference="analytics.sector_allocations",
            is_grounded=True,
        )
    )

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    sec_finding = next(
        f for f in validated.grounding_report.findings
        if f.target_id == "driver-sector-specific" and f.check_name == "NUMERIC_GROUNDING_CHECK"
    )
    assert sec_finding.status == FindingStatus.PASSED


@pytest.mark.asyncio
async def test_validator_unknown_sector_or_field_rejected():
    """Verify unknown sectors or disallowed fields are rejected with METRIC_PATH_UNKNOWN."""
    evidence = build_test_bundle()
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Unknown sector
    report.key_drivers.append(
        EvidenceKeyDriver(
            driver_id="driver-unknown-sec",
            driver_type=DriverType.SECTOR,
            title="Unknown Sector",
            statement="Pharma sector allocation is 20%.",
            supporting_metric_key="sector_allocations.PHARMA.allocation_percent",
            supporting_metric_value=Decimal("20.00"),
            source_reference="analytics.sector_allocations",
            is_grounded=True,
        )
    )
    # Disallowed field
    report.key_drivers.append(
        EvidenceKeyDriver(
            driver_id="driver-disallowed-field",
            driver_type=DriverType.SECTOR,
            title="Disallowed Field",
            statement="Energy sector internal secret is 123.",
            supporting_metric_key="sector_allocations.ENERGY.internal_secret",
            supporting_metric_value=123,
            source_reference="analytics.sector_allocations",
            is_grounded=True,
        )
    )

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    f_sec = next(
        f for f in validated.grounding_report.findings
        if f.target_id == "driver-unknown-sec" and f.check_name == "NUMERIC_GROUNDING_CHECK"
    )
    assert f_sec.status == FindingStatus.REJECTED
    assert f_sec.details.get("code") == FindingCode.METRIC_PATH_UNKNOWN

    f_field = next(
        f for f in validated.grounding_report.findings
        if f.target_id == "driver-disallowed-field" and f.check_name == "NUMERIC_GROUNDING_CHECK"
    )
    assert f_field.status == FindingStatus.REJECTED
    assert f_field.details.get("code") == FindingCode.METRIC_PATH_UNKNOWN


@pytest.mark.asyncio
async def test_validator_formatted_currency_and_percent_normalized():
    """Verify numeric parser normalizes currency symbols, commas, and percentage strings."""
    evidence = build_test_bundle()
    # total_market_value is Decimal("115000.00")
    # top_holding_weight_percent is Decimal("50.00")
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    report.key_drivers.append(
        EvidenceKeyDriver(
            driver_id="driver-formatted-curr",
            driver_type=DriverType.PERFORMANCE,
            title="Formatted Valuation",
            statement="Total market value is ₹1,15,000.00.",
            supporting_metric_key="valuation.total_market_value",
            supporting_metric_value="₹1,15,000.00",
            source_reference="analytics.valuation",
            is_grounded=True,
        )
    )
    report.key_drivers.append(
        EvidenceKeyDriver(
            driver_id="driver-formatted-pct",
            driver_type=DriverType.CONCENTRATION,
            title="Formatted Percentage",
            statement="Top holding weight is 50.00%.",
            supporting_metric_key="concentration.top_holding_weight_percent",
            supporting_metric_value="50.00%",
            source_reference="analytics.concentration",
            is_grounded=True,
        )
    )

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    f_curr = next(
        f for f in validated.grounding_report.findings
        if f.target_id == "driver-formatted-curr" and f.check_name == "NUMERIC_GROUNDING_CHECK"
    )
    assert f_curr.status == FindingStatus.PASSED

    f_pct = next(
        f for f in validated.grounding_report.findings
        if f.target_id == "driver-formatted-pct" and f.check_name == "NUMERIC_GROUNDING_CHECK"
    )
    assert f_pct.status == FindingStatus.PASSED


@pytest.mark.asyncio
async def test_validator_malformed_numeric_string_rejected():
    """Verify malformed numeric strings fail comparison and out-of-tolerance values are rejected."""
    evidence = build_test_bundle()
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Malformed numeric string
    report.key_drivers.append(
        EvidenceKeyDriver(
            driver_id="driver-malformed-num",
            driver_type=DriverType.PERFORMANCE,
            title="Malformed Number",
            statement="Value is 1.2.3.4.",
            supporting_metric_key="valuation.total_market_value",
            supporting_metric_value="1.2.3.4",
            source_reference="analytics.valuation",
            is_grounded=True,
        )
    )
    # Out of tolerance percentage (50.10% vs source 50.00%, diff 0.10 > tolerance 0.05)
    report.key_drivers.append(
        EvidenceKeyDriver(
            driver_id="driver-out-of-tolerance",
            driver_type=DriverType.CONCENTRATION,
            title="Out of Tolerance",
            statement="Top holding weight is 50.10%.",
            supporting_metric_key="concentration.top_holding_weight_percent",
            supporting_metric_value="50.10%",
            source_reference="analytics.concentration",
            is_grounded=True,
        )
    )

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    f_mal = next(
        f for f in validated.grounding_report.findings
        if f.target_id == "driver-malformed-num" and f.check_name == "NUMERIC_GROUNDING_CHECK"
    )
    assert f_mal.status == FindingStatus.REJECTED
    assert f_mal.details.get("code") == FindingCode.NUMERIC_VALUE_MISMATCH

    f_tol = next(
        f for f in validated.grounding_report.findings
        if f.target_id == "driver-out-of-tolerance" and f.check_name == "NUMERIC_GROUNDING_CHECK"
    )
    assert f_tol.status == FindingStatus.REJECTED
    assert f_tol.details.get("code") == FindingCode.NUMERIC_VALUE_MISMATCH


@pytest.mark.asyncio
async def test_validator_driver_source_reference_symbol_check():
    """Verify driver source_reference prefixes (holdings., quotes., etc.) are checked against valid symbols."""
    evidence = build_test_bundle()
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    report.key_drivers.append(
        EvidenceKeyDriver(
            driver_id="driver-invalid-source-sym",
            driver_type=DriverType.PERFORMANCE,
            title="Source Reference Symbol",
            statement="Position detail.",
            supporting_metric_key="valuation.total_market_value",
            supporting_metric_value=Decimal("115000.00"),
            source_reference="holdings.UNKNOWN_TICKER",
            is_grounded=True,
        )
    )

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    finding = next(
        f for f in validated.grounding_report.findings
        if f.target_id == "driver-invalid-source-sym" and f.check_name == "SYMBOL_GROUNDING_CHECK"
    )
    assert finding.status == FindingStatus.REJECTED
    assert finding.details.get("code") == FindingCode.SYMBOL_UNSUPPORTED
    assert finding.details.get("unsupported_symbol") == "UNKNOWN_TICKER"


@pytest.mark.asyncio
async def test_validator_stock_specific_driver_claim_without_evidence_rejected():
    """Verify unsupported stock-specific claim cannot pass merely by attaching a valid metric."""
    evidence = build_test_bundle()
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    report.key_drivers.append(
        EvidenceKeyDriver(
            driver_id="driver-hallucinated-stock",
            driver_type=DriverType.PERFORMANCE,
            title="Fake Corp Surge",
            statement="Shares of FAKE_CORP rallied 45% following buyout rumors.",
            supporting_metric_key="valuation.total_market_value",
            supporting_metric_value=Decimal("115000.00"),
            source_reference="analytics.valuation",
            is_grounded=True,
        )
    )

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    finding = next(
        f for f in validated.grounding_report.findings
        if f.target_id == "driver-hallucinated-stock" and f.check_name == "SYMBOL_GROUNDING_CHECK"
    )
    assert finding.status == FindingStatus.REJECTED
    assert finding.details.get("code") == FindingCode.SYMBOL_UNSUPPORTED
    assert finding.details.get("unsupported_symbol") == "FAKE_CORP"

    # Verify driver is_grounded is False and overall report is REJECTED
    driver = next(d for d in validated.key_drivers if d.driver_id == "driver-hallucinated-stock")
    assert driver.is_grounded is False
    assert validated.review_status == ReviewStatus.REJECTED


@pytest.mark.asyncio
async def test_validator_card_shorthand_metrics_resolved():
    """Verify review cards citing shorthand metrics resolve and validate accurately."""
    evidence = build_test_bundle()
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    report.review_cards.append(
        ReviewableInsightCard(
            card_id="card-shorthand-test",
            category="ALLOCATION",
            severity="INFO",
            title="Shorthand Card",
            description="Card citing shorthand metrics.",
            cited_metrics={
                "market_value": "₹1,15,000.00",
                "cost_basis": Decimal("100000.00"),
                "top_weight": "50.00%",
            },
            related_symbols=["RELIANCE"],
            review_status=ReviewStatus.VERIFIED,
        )
    )

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    card_findings = [
        f for f in validated.grounding_report.findings
        if f.target_id == "card-shorthand-test" and f.check_name == "NUMERIC_GROUNDING_CHECK"
    ]
    assert len(card_findings) == 3
    assert all(f.status == FindingStatus.PASSED for f in card_findings)


# ===========================================================================
# 9. News Grounding and Calibration Disclosure Tests (Phase 06 Hardening)
# ===========================================================================

@pytest.mark.asyncio
async def test_validator_rejects_news_simulated():
    """Verify that source_reference='news.simulated' is rejected as invalid pseudo-symbol."""
    evidence = build_test_bundle()
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Inject driver with simulated pseudo-symbol reference
    report.key_drivers.append(
        EvidenceKeyDriver(
            driver_id="driver-news-simulated",
            driver_type=DriverType.NEWS,
            title="Simulated News Headline",
            statement="Simulated news reports growth.",
            supporting_metric_key="news.title",
            supporting_metric_value="Reliance Expands Solar Capacity",
            source_reference="news.simulated",
            is_grounded=True,
        )
    )

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    assert validated.review_status == ReviewStatus.REJECTED
    driver = next(d for d in validated.key_drivers if d.driver_id == "driver-news-simulated")
    assert driver.is_grounded is False

    finding = next(
        f for f in validated.grounding_report.findings
        if f.target_id == "driver-news-simulated" and f.details.get("code") == FindingCode.SYMBOL_UNSUPPORTED
    )
    assert finding.status == FindingStatus.REJECTED
    assert finding.details.get("unsupported_symbol") == "SIMULATED"
    assert "invalid pseudo-symbol" in (finding.reason or "")


@pytest.mark.asyncio
async def test_validator_accepts_valid_grounded_news_reference():
    """Verify that valid news references matching evidence pass all grounding checks."""
    evidence = build_test_bundle(
        include_news=True,
    )
    provider = DeterministicDemoProvider()
    report = await provider.generate_insights(evidence)

    # Filter out existing demo news driver if present, add clean test driver
    report.key_drivers = [d for d in report.key_drivers if d.driver_type != DriverType.NEWS]
    report.key_drivers.append(
        EvidenceKeyDriver(
            driver_id="driver-news-valid",
            driver_type=DriverType.NEWS,
            title="Reliance Solar Expansion",
            statement="Reliance expands clean energy footprint across solar installations.",
            supporting_metric_key="news.title",
            supporting_metric_value="Reliance Expands Solar Capacity",
            source_reference="news.RELIANCE",
            is_grounded=True,
        )
    )

    validator = ClaimGroundingValidator()
    validated = validator.validate_report(report, evidence)

    assert validated.review_status == ReviewStatus.VERIFIED
    driver = next(d for d in validated.key_drivers if d.driver_id == "driver-news-valid")
    assert driver.is_grounded is True

    news_findings = [
        f for f in validated.grounding_report.findings
        if f.target_id == "driver-news-valid"
    ]
    assert all(f.status == FindingStatus.PASSED for f in news_findings)


@pytest.mark.asyncio
async def test_validator_rejects_unsupported_news_claim_with_plausible_reference():
    """Verify that ungrounded news claims are rejected even if the source reference looks plausible."""
    evidence = build_test_bundle(include_news=True)
    provider = DeterministicDemoProvider()
    validator = ClaimGroundingValidator()

    # Case A: Plausible reference 'news.RELIANCE', but hallucinated headline value
    report_a = await provider.generate_insights(evidence)
    report_a.key_drivers = [d for d in report_a.key_drivers if d.driver_type != DriverType.NEWS]
    report_a.key_drivers.append(
        EvidenceKeyDriver(
            driver_id="driver-fake-headline",
            driver_type=DriverType.NEWS,
            title="Reliance Mega Buyout",
            statement="Reliance acquires foreign tech firm for $10B.",
            supporting_metric_key="news.title",
            supporting_metric_value="Reliance Announces $10B Cross-Border Takeover",
            source_reference="news.RELIANCE",
            is_grounded=True,
        )
    )
    val_a = validator.validate_report(report_a, evidence)
    assert val_a.review_status == ReviewStatus.REJECTED
    assert any(
        f.target_id == "driver-fake-headline"
        and f.status == FindingStatus.REJECTED
        and f.details.get("code") == FindingCode.NUMERIC_VALUE_MISMATCH
        for f in val_a.grounding_report.findings
    )

    # Case B: Plausible reference 'news.RELIANCE', but portfolio has zero news articles
    evidence_no_news = build_test_bundle(include_news=False)
    report_b = await provider.generate_insights(evidence_no_news)
    report_b.key_drivers.append(
        EvidenceKeyDriver(
            driver_id="driver-no-news-bundle",
            driver_type=DriverType.NEWS,
            title="Solar Expansion",
            statement="Clean energy push.",
            supporting_metric_key="news.title",
            supporting_metric_value="Reliance Expands Solar Capacity",
            source_reference="news.RELIANCE",
            is_grounded=True,
        )
    )
    val_b = validator.validate_report(report_b, evidence_no_news)
    assert val_b.review_status == ReviewStatus.REJECTED
    assert any(
        f.target_id == "driver-no-news-bundle"
        and f.status == FindingStatus.REJECTED
        and "no news articles exist" in (f.reason or "").lower()
        for f in val_b.grounding_report.findings
    )

    # Case C: Plausible reference 'news.RELIANCE', but evidence news is only about TCS
    evidence_tcs_only = build_test_bundle(include_news=False)
    evidence_tcs_only.news_articles = [
        NewsArticle(
            id="news-tcs-1",
            title="TCS Signs Major Cloud Deal",
            summary="Multi-year digital transformation contract.",
            related_symbols=["TCS"],
        )
    ]
    report_c = await provider.generate_insights(evidence_tcs_only)
    report_c.key_drivers.append(
        EvidenceKeyDriver(
            driver_id="driver-mismatched-news-sym",
            driver_type=DriverType.NEWS,
            title="Reliance Solar Update",
            statement="Reliance solar investment report.",
            supporting_metric_key="news.title",
            supporting_metric_value="TCS Signs Major Cloud Deal",
            source_reference="news.RELIANCE",
            is_grounded=True,
        )
    )
    val_c = validator.validate_report(report_c, evidence_tcs_only)
    assert val_c.review_status == ReviewStatus.REJECTED
    assert any(
        f.target_id == "driver-mismatched-news-sym"
        and f.status == FindingStatus.REJECTED
        and f.details.get("code") == FindingCode.SYMBOL_UNSUPPORTED
        for f in val_c.grounding_report.findings
    )


@pytest.mark.asyncio
async def test_validator_flags_missing_or_weak_confidence_disclosure():
    """Verify that confidence limitation lacking heuristic calibration keywords is FLAGGED."""
    evidence = build_test_bundle()
    provider = DeterministicDemoProvider()
    validator = ClaimGroundingValidator()

    # Subcase 1: Text >= 20 chars but lacking 'heuristic', 'not statistically calibrated', etc.
    report_weak = await provider.generate_insights(evidence)
    report_weak.confidence.calibration_limitation = (
        "High confidence based on full price coverage and complete holding details across portfolios."
    )
    val_weak = validator.validate_report(report_weak, evidence)
    assert val_weak.review_status == ReviewStatus.FLAGGED_WITH_WARNINGS
    flagged_f = next(
        f for f in val_weak.grounding_report.findings
        if f.target_id == "report.confidence" and f.status == FindingStatus.FLAGGED
    )
    assert flagged_f.details.get("code") == FindingCode.CONFIDENCE_CALIBRATION_UNGROUNDED
    assert "heuristic" in (flagged_f.reason or "").lower()

    # Subcase 2: Compliant text with required keywords passes
    report_compliant = await provider.generate_insights(evidence)
    report_compliant.confidence.calibration_limitation = (
        "Heuristic confidence score based on qualitative analysis; not a statistically calibrated probability distribution."
    )
    val_comp = validator.validate_report(report_compliant, evidence)
    assert val_comp.review_status == ReviewStatus.VERIFIED
    passed_f = next(
        f for f in val_comp.grounding_report.findings
        if f.target_id == "report.confidence"
        and f.details.get("topic") == "heuristic_calibration_disclosed"
    )
    assert passed_f.status == FindingStatus.PASSED

