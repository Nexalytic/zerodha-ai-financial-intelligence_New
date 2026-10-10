from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, localcontext
import re
from typing import Any, Dict, List, Optional

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

# Standard precision for quantitative financial calculations
DECIMAL_CALCULATION_PRECISION = 28
TWO_PLACES = Decimal("0.01")
SYMBOL_REGEX = re.compile(r"^[A-Z0-9&-]{1,20}$")

WEIGHT_SINGLE_STOCK = Decimal("0.35")
WEIGHT_SECTOR = Decimal("0.25")
WEIGHT_BREADTH = Decimal("0.20")
WEIGHT_QUALITY = Decimal("0.20")


def quantize_score(val: Decimal) -> Decimal:
    """Quantize score to 2 decimal places with ROUND_HALF_UP."""
    return val.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_single_stock_concentration_score(
    top_holding_weight_percent: Optional[Decimal],
) -> Optional[Decimal]:
    """
    Computes single-stock concentration risk score on 0.00-100.00 scale (35% composite weight).
    Piecewise linear mapping based on top holding market-value weight W_top:
    - W_top <= 10.00%: Prudent zone -> score = 1.50 * W_top in [0.00, 15.00]
    - 10.00% < W_top <= 25.00%: Moderate -> score = 15.00 + 2.00 * (W_top - 10.00) in (15.00, 45.00]
    - 25.00% < W_top <= 50.00%: High -> score = 45.00 + 1.40 * (W_top - 25.00) in (45.00, 80.00]
    - W_top > 50.00%: Dominant -> score = 80.00 + 0.40 * (W_top - 50.00) in (80.00, 100.00]

    Returns None if top_holding_weight_percent is None.
    Guaranteed continuous at boundaries and bounded within [0.00, 100.00].
    """
    if top_holding_weight_percent is None:
        return None

    with localcontext() as ctx:
        ctx.prec = DECIMAL_CALCULATION_PRECISION
        w = max(Decimal("0.00"), min(Decimal("100.00"), top_holding_weight_percent))

        if w <= Decimal("10.00"):
            score = Decimal("1.50") * w
        elif w <= Decimal("25.00"):
            score = Decimal("15.00") + Decimal("2.00") * (w - Decimal("10.00"))
        elif w <= Decimal("50.00"):
            score = Decimal("45.00") + Decimal("1.40") * (w - Decimal("25.00"))
        else:
            score = Decimal("80.00") + Decimal("0.40") * (w - Decimal("50.00"))

        score = max(Decimal("0.00"), min(Decimal("100.00"), score))
        return quantize_score(score)


def calculate_sector_concentration_score(
    top_sector_allocation_percent: Optional[Decimal],
) -> Optional[Decimal]:
    """
    Computes sector concentration risk score on 0.00-100.00 scale (25% composite weight).
    Piecewise linear mapping based on top sector market-value allocation S_top:
    - S_top <= 20.00%: Diversified -> score = 1.00 * S_top in [0.00, 20.00]
    - 20.00% < S_top <= 40.00%: Moderate -> score = 20.00 + 1.50 * (S_top - 20.00) in (20.00, 50.00]
    - 40.00% < S_top <= 65.00%: High -> score = 50.00 + 1.20 * (S_top - 40.00) in (50.00, 80.00]
    - S_top > 65.00%: Monolithic -> score = 80.00 + (20.00 / 35.00) * (S_top - 65.00) in (80.00, 100.00]

    Returns None if top_sector_allocation_percent is None.
    Guaranteed continuous at boundaries and bounded within [0.00, 100.00].
    """
    if top_sector_allocation_percent is None:
        return None

    with localcontext() as ctx:
        ctx.prec = DECIMAL_CALCULATION_PRECISION
        s = max(Decimal("0.00"), min(Decimal("100.00"), top_sector_allocation_percent))

        if s <= Decimal("20.00"):
            score = Decimal("1.00") * s
        elif s <= Decimal("40.00"):
            score = Decimal("20.00") + Decimal("1.50") * (s - Decimal("20.00"))
        elif s <= Decimal("65.00"):
            score = Decimal("50.00") + Decimal("1.20") * (s - Decimal("40.00"))
        else:
            score = Decimal("80.00") + (Decimal("20.00") / Decimal("35.00")) * (s - Decimal("65.00"))

        score = max(Decimal("0.00"), min(Decimal("100.00"), score))
        return quantize_score(score)


def calculate_portfolio_breadth_score(
    herfindahl_index: Optional[Decimal],
) -> Optional[Decimal]:
    """
    Computes portfolio breadth and diversification risk score on 0.00-100.00 scale (20% composite weight).
    Piecewise linear mapping based on Herfindahl-Hirschman Index (HHI, where ENH = 1 / HHI):
    - HHI <= 0.0800 (ENH >= 12.5): Broad -> score = HHI * 250.00 in [0.00, 20.00]
    - 0.0800 < HHI <= 0.1500 (6.7 <= ENH < 12.5): Low concentration -> score = 20.00 + ((HHI - 0.0800) / 0.0700) * 20.00 in (20.00, 40.00]
    - 0.1500 < HHI <= 0.2500 (4.0 <= ENH < 6.7): Moderate concentration -> score = 40.00 + ((HHI - 0.1500) / 0.1000) * 30.00 in (40.00, 70.00]
    - HHI > 0.2500 (ENH < 4.0): High concentration -> score = 70.00 + ((HHI - 0.2500) / 0.7500) * 30.00 in (70.00, 100.00]

    Returns None if herfindahl_index is None.
    Guaranteed continuous at boundaries and bounded within [0.00, 100.00].
    """
    if herfindahl_index is None:
        return None

    with localcontext() as ctx:
        ctx.prec = DECIMAL_CALCULATION_PRECISION
        h = max(Decimal("0.00"), min(Decimal("1.0000"), herfindahl_index))

        if h <= Decimal("0.0800"):
            score = h * Decimal("250.00")
        elif h <= Decimal("0.1500"):
            score = Decimal("20.00") + ((h - Decimal("0.0800")) / Decimal("0.0700")) * Decimal("20.00")
        elif h <= Decimal("0.2500"):
            score = Decimal("40.00") + ((h - Decimal("0.1500")) / Decimal("0.1000")) * Decimal("30.00")
        else:
            score = Decimal("70.00") + ((h - Decimal("0.2500")) / Decimal("0.7500")) * Decimal("30.00")

        score = max(Decimal("0.00"), min(Decimal("100.00"), score))
        return quantize_score(score)


def calculate_data_quality_score(
    completeness_ratio: Optional[Decimal],
    has_stale_prices: bool,
) -> Decimal:
    """
    Computes data quality & completeness risk score on 0.00-100.00 scale (20% composite weight).
    Note: completeness_ratio represents position-count completeness
    (priced_holdings_count / total_holdings_count) as defined in PortfolioCompleteness.

    Formula:
    Missing price penalty: (1.0000 - completeness_ratio) * 80.00
    Stale price penalty: +20.00 if has_stale_prices is True, else +0.00
    Total score = min(100.00, Missing penalty + Stale penalty)

    Guaranteed bounded within [0.00, 100.00].
    """
    with localcontext() as ctx:
        ctx.prec = DECIMAL_CALCULATION_PRECISION
        cr = Decimal("0.0000") if completeness_ratio is None else max(
            Decimal("0.0000"), min(Decimal("1.0000"), completeness_ratio)
        )

        missing_penalty = (Decimal("1.0000") - cr) * Decimal("80.00")
        stale_penalty = Decimal("20.00") if has_stale_prices else Decimal("0.00")

        total = min(Decimal("100.00"), missing_penalty + stale_penalty)
        return quantize_score(total)


def determine_risk_tier(composite_score: Decimal) -> str:
    """
    Determines qualitative risk tier based on composite score (0-100):
    - LOW: score <= 30.00
    - MODERATE: 30.00 < score <= 55.00
    - ELEVATED: 55.00 < score <= 75.00
    - HIGH: score > 75.00
    """
    if composite_score <= Decimal("30.00"):
        return "LOW"
    elif composite_score <= Decimal("55.00"):
        return "MODERATE"
    elif composite_score <= Decimal("75.00"):
        return "ELEVATED"
    else:
        return "HIGH"


def calculate_portfolio_risk_assessment(
    status: ValuationStatus,
    concentration: ConcentrationMetrics,
    completeness: PortfolioCompleteness,
    sector_allocations: List[SectorAllocation],
) -> PortfolioRiskAssessment:
    """
    Aggregates deterministic four-component risk assessment for a portfolio.
    Handles EMPTY and UNVALUED states by returning None scores without fabricating data.
    """
    # 1. Edge Case: Empty portfolio
    if status == ValuationStatus.EMPTY or completeness.total_holdings_count == 0:
        return PortfolioRiskAssessment(
            composite_risk_score=None,
            risk_tier=None,
            assessment_status="EMPTY",
            components=RiskComponentScores(
                single_stock_concentration_score=None,
                sector_concentration_score=None,
                diversification_breadth_score=None,
                data_quality_score=None,
            ),
        )

    # 2. Edge Case: Wholly unpriced portfolio
    if status == ValuationStatus.UNVALUED or completeness.priced_holdings_count == 0:
        return PortfolioRiskAssessment(
            composite_risk_score=None,
            risk_tier=None,
            assessment_status="UNVALUED",
            components=RiskComponentScores(
                single_stock_concentration_score=None,
                sector_concentration_score=None,
                diversification_breadth_score=None,
                data_quality_score=None,
            ),
        )

    # 3. Calculate top sector weight from priced sector allocations
    top_sector_pct: Optional[Decimal] = None
    if sector_allocations:
        valid_allocs = [s.allocation_percent for s in sector_allocations if s.allocation_percent is not None]
        if valid_allocs:
            top_sector_pct = max(valid_allocs)

    # 4. Compute the 4 deterministic component scores
    c_stock = calculate_single_stock_concentration_score(concentration.top_holding_weight_percent)
    c_sector = calculate_sector_concentration_score(top_sector_pct)
    c_breadth = calculate_portfolio_breadth_score(concentration.herfindahl_index)
    c_quality = calculate_data_quality_score(completeness.completeness_ratio, completeness.has_stale_prices)

    components = RiskComponentScores(
        single_stock_concentration_score=c_stock,
        sector_concentration_score=c_sector,
        diversification_breadth_score=c_breadth,
        data_quality_score=c_quality,
    )

    # Guard: if structural metrics could not be computed, preserve honest None
    if c_stock is None or c_sector is None or c_breadth is None:
        return PortfolioRiskAssessment(
            composite_risk_score=None,
            risk_tier=None,
            assessment_status="UNVALUED",
            components=components,
        )

    # 5. Composite score calculation
    with localcontext() as ctx:
        ctx.prec = DECIMAL_CALCULATION_PRECISION
        composite = (
            WEIGHT_SINGLE_STOCK * c_stock
            + WEIGHT_SECTOR * c_sector
            + WEIGHT_BREADTH * c_breadth
            + WEIGHT_QUALITY * c_quality
        )
        composite = quantize_score(composite)
        tier = determine_risk_tier(composite)

    assessment_status = "PARTIAL" if status == ValuationStatus.PARTIAL else "COMPLETE"

    return PortfolioRiskAssessment(
        composite_risk_score=composite,
        risk_tier=tier,
        assessment_status=assessment_status,
        components=components,
    )


def generate_portfolio_risk_insights(
    portfolio_id: str,
    status: ValuationStatus,
    concentration: ConcentrationMetrics,
    completeness: PortfolioCompleteness,
    sector_allocations: List[SectorAllocation],
    risk_assessment: PortfolioRiskAssessment,
) -> List[PortfolioInsight]:
    """
    Generates explainable, deterministic PortfolioInsight objects grounded in computed metrics.
    Follows exact PortfolioInsight schema rules:
    - Stable identifiers
    - Explicit InsightCategory and InsightSeverity
    - Supported related_symbols validated against SYMBOL_REGEX
    - Timezone-aware UTC timestamp
    - Structured evidence dictionaries
    - Provenance and educational disclaimer
    """
    insights: List[PortfolioInsight] = []
    now = datetime.now(timezone.utc)

    # 1. Edge Case: Empty portfolio
    if status == ValuationStatus.EMPTY or completeness.total_holdings_count == 0:
        insights.append(
            PortfolioInsight(
                id=f"{portfolio_id}-risk-empty",
                portfolio_id=portfolio_id,
                category=InsightCategory.RISK,
                severity=InsightSeverity.INFO,
                title="Portfolio is Empty",
                description="Portfolio has no recorded holdings. Add holdings to enable deterministic risk analysis and diversification insights.",
                evidence={"holdings_count": 0},
                related_symbols=[],
                created_at=now,
                is_simulated=True,
                source="DETERMINISTIC_RISK_ENGINE",
            )
        )
        return insights

    # 2. Edge Case: Wholly unpriced portfolio
    if status == ValuationStatus.UNVALUED or completeness.priced_holdings_count == 0:
        unpriced_syms = [
            p.symbol.strip().upper()
            for p in completeness.unpriced_positions
            if p.symbol and SYMBOL_REGEX.match(p.symbol.strip().upper())
        ]
        insights.append(
            PortfolioInsight(
                id=f"{portfolio_id}-risk-unvalued",
                portfolio_id=portfolio_id,
                category=InsightCategory.RISK,
                severity=InsightSeverity.WARNING,
                title="Market Prices Unavailable for Valuation",
                description="Market quotes could not be obtained for any holdings. Risk scoring and concentration metrics require at least one priced holding.",
                evidence={
                    "priced_count": 0,
                    "total_holdings_count": completeness.total_holdings_count,
                    "unpriced_count": completeness.unpriced_holdings_count,
                },
                related_symbols=unpriced_syms[:10],
                created_at=now,
                is_simulated=True,
                source="DETERMINISTIC_RISK_ENGINE",
            )
        )
        return insights

    # 3. Composite Risk Assessment Insight
    if risk_assessment.composite_risk_score is not None and risk_assessment.risk_tier is not None:
        tier = risk_assessment.risk_tier
        score_val = str(risk_assessment.composite_risk_score)
        if tier == "HIGH":
            sev = InsightSeverity.CRITICAL
        elif tier == "ELEVATED":
            sev = InsightSeverity.WARNING
        else:
            sev = InsightSeverity.INFO

        c_stock = str(risk_assessment.components.single_stock_concentration_score)
        c_sector = str(risk_assessment.components.sector_concentration_score)
        c_breadth = str(risk_assessment.components.diversification_breadth_score)
        c_quality = str(risk_assessment.components.data_quality_score)

        insights.append(
            PortfolioInsight(
                id=f"{portfolio_id}-risk-composite",
                portfolio_id=portfolio_id,
                category=InsightCategory.RISK,
                severity=sev,
                title=f"{tier.title()} Portfolio Risk (Score: {score_val}/100)",
                description=(
                    f"Overall portfolio structural risk is classified as {tier} with a composite score of {score_val}/100. "
                    f"Component scores: single-stock concentration {c_stock}/100, sector concentration {c_sector}/100, "
                    f"breadth deficiency {c_breadth}/100, and data quality uncertainty {c_quality}/100."
                ),
                evidence={
                    "composite_risk_score": score_val,
                    "risk_tier": tier,
                    "assessment_status": risk_assessment.assessment_status,
                    "components": {
                        "single_stock_concentration": c_stock,
                        "sector_concentration": c_sector,
                        "diversification_breadth": c_breadth,
                        "data_quality": c_quality,
                    },
                },
                related_symbols=[],
                created_at=now,
                is_simulated=True,
                source="DETERMINISTIC_RISK_ENGINE",
            )
        )

    # 4. Single-Stock Concentration Insight
    top_sym = concentration.top_holding_symbol
    top_sym_clean = top_sym.strip().upper() if top_sym and SYMBOL_REGEX.match(top_sym.strip().upper()) else None
    top_w = concentration.top_holding_weight_percent

    if top_w is not None and top_sym:
        sym_list = [top_sym_clean] if top_sym_clean else []
        if top_w > Decimal("50.00"):
            insights.append(
                PortfolioInsight(
                    id=f"{portfolio_id}-concentration-stock",
                    portfolio_id=portfolio_id,
                    category=InsightCategory.CONCENTRATION,
                    severity=InsightSeverity.CRITICAL,
                    title=f"Dominant Single-Stock Exposure in {top_sym}",
                    description=(
                        f"{top_sym} accounts for {top_w}% of total priced portfolio market value. "
                        f"A single asset exceeding 50.00% creates dominant concentration risk."
                    ),
                    evidence={
                        "symbol": top_sym,
                        "weight_percent": str(top_w),
                        "threshold_percent": "50.00",
                    },
                    related_symbols=sym_list,
                    created_at=now,
                    is_simulated=True,
                    source="DETERMINISTIC_RISK_ENGINE",
                )
            )
        elif top_w > Decimal("25.00"):
            insights.append(
                PortfolioInsight(
                    id=f"{portfolio_id}-concentration-stock",
                    portfolio_id=portfolio_id,
                    category=InsightCategory.CONCENTRATION,
                    severity=InsightSeverity.WARNING,
                    title=f"High Single-Stock Exposure in {top_sym}",
                    description=(
                        f"{top_sym} accounts for {top_w}% of total priced portfolio market value, "
                        f"exceeding the prudent 25.00% single-stock concentration threshold."
                    ),
                    evidence={
                        "symbol": top_sym,
                        "weight_percent": str(top_w),
                        "threshold_percent": "25.00",
                    },
                    related_symbols=sym_list,
                    created_at=now,
                    is_simulated=True,
                    source="DETERMINISTIC_RISK_ENGINE",
                )
            )
        else:
            insights.append(
                PortfolioInsight(
                    id=f"{portfolio_id}-concentration-stock",
                    portfolio_id=portfolio_id,
                    category=InsightCategory.CONCENTRATION,
                    severity=InsightSeverity.INFO,
                    title=f"Balanced Individual Holding Exposure ({top_sym})",
                    description=(
                        f"Largest single holding {top_sym} accounts for {top_w}% of portfolio value, "
                        f"remaining comfortably within prudent single-position guidelines (<= 25.00%)."
                    ),
                    evidence={
                        "symbol": top_sym,
                        "weight_percent": str(top_w),
                        "prudent_threshold_percent": "25.00",
                    },
                    related_symbols=sym_list,
                    created_at=now,
                    is_simulated=True,
                    source="DETERMINISTIC_RISK_ENGINE",
                )
            )

    # 5. Sector Concentration Insight
    if sector_allocations:
        priced_sectors = [s for s in sector_allocations if s.allocation_percent is not None]
        if priced_sectors:
            top_sector = max(priced_sectors, key=lambda s: s.allocation_percent)  # type: ignore
            top_sec_name = top_sector.sector
            top_sec_pct = top_sector.allocation_percent

            if top_sec_pct > Decimal("65.00"):
                insights.append(
                    PortfolioInsight(
                        id=f"{portfolio_id}-concentration-sector",
                        portfolio_id=portfolio_id,
                        category=InsightCategory.CONCENTRATION,
                        severity=InsightSeverity.CRITICAL,
                        title=f"Severe Sector Concentration in {top_sec_name}",
                        description=(
                            f"{top_sec_name} sector represents {top_sec_pct}% of total priced portfolio market value, "
                            f"indicating severe monolithic industry risk."
                        ),
                        evidence={
                            "sector": top_sec_name,
                            "allocation_percent": str(top_sec_pct),
                            "critical_threshold_percent": "65.00",
                        },
                        related_symbols=[],
                        created_at=now,
                        is_simulated=True,
                        source="DETERMINISTIC_RISK_ENGINE",
                    )
                )
            elif top_sec_pct > Decimal("40.00"):
                insights.append(
                    PortfolioInsight(
                        id=f"{portfolio_id}-concentration-sector",
                        portfolio_id=portfolio_id,
                        category=InsightCategory.CONCENTRATION,
                        severity=InsightSeverity.WARNING,
                        title=f"Elevated Sector Exposure in {top_sec_name}",
                        description=(
                            f"{top_sec_name} sector represents {top_sec_pct}% of portfolio market value, "
                            f"exceeding the prudent 40.00% sector diversification threshold."
                        ),
                        evidence={
                            "sector": top_sec_name,
                            "allocation_percent": str(top_sec_pct),
                            "threshold_percent": "40.00",
                        },
                        related_symbols=[],
                        created_at=now,
                        is_simulated=True,
                        source="DETERMINISTIC_RISK_ENGINE",
                    )
                )
            else:
                insights.append(
                    PortfolioInsight(
                        id=f"{portfolio_id}-concentration-sector",
                        portfolio_id=portfolio_id,
                        category=InsightCategory.CONCENTRATION,
                        severity=InsightSeverity.INFO,
                        title=f"Diversified Sector Allocation ({top_sec_name})",
                        description=(
                            f"Largest sector allocation is {top_sec_name} at {top_sec_pct}%, "
                            f"indicating balanced distribution across distinct industries."
                        ),
                        evidence={
                            "sector": top_sec_name,
                            "allocation_percent": str(top_sec_pct),
                        },
                        related_symbols=[],
                        created_at=now,
                        is_simulated=True,
                        source="DETERMINISTIC_RISK_ENGINE",
                    )
                )

    # 6. Portfolio Breadth / ENH Insight
    if concentration.herfindahl_index is not None and concentration.effective_holdings_count is not None:
        enh = concentration.effective_holdings_count
        hhi = concentration.herfindahl_index

        if enh < Decimal("4.00"):
            insights.append(
                PortfolioInsight(
                    id=f"{portfolio_id}-breadth-enh",
                    portfolio_id=portfolio_id,
                    category=InsightCategory.DIVERSIFICATION,
                    severity=InsightSeverity.WARNING,
                    title=f"Limited Effective Breadth (ENH: {enh})",
                    description=(
                        f"The portfolio has an effective breadth of only {enh} equally-sized positions (HHI: {hhi}), "
                        f"meaning volatility and returns are heavily dominated by a very small set of holdings."
                    ),
                    evidence={
                        "effective_holdings_count": str(enh),
                        "herfindahl_index": str(hhi),
                        "threshold_enh": "4.00",
                    },
                    related_symbols=[],
                    created_at=now,
                    is_simulated=True,
                    source="DETERMINISTIC_RISK_ENGINE",
                )
            )
        else:
            insights.append(
                PortfolioInsight(
                    id=f"{portfolio_id}-breadth-enh",
                    portfolio_id=portfolio_id,
                    category=InsightCategory.DIVERSIFICATION,
                    severity=InsightSeverity.INFO,
                    title=f"Healthy Portfolio Breadth (ENH: {enh})",
                    description=(
                        f"The portfolio exhibits strong position spread with an effective holdings count of {enh} (HHI: {hhi}), "
                        f"providing structural resilience against individual asset shocks."
                    ),
                    evidence={
                        "effective_holdings_count": str(enh),
                        "herfindahl_index": str(hhi),
                    },
                    related_symbols=[],
                    created_at=now,
                    is_simulated=True,
                    source="DETERMINISTIC_RISK_ENGINE",
                )
            )

    # 7. Data Quality & Completeness Insight
    if completeness.unpriced_holdings_count > 0:
        unpriced_syms = [
            p.symbol.strip().upper()
            for p in completeness.unpriced_positions
            if p.symbol and SYMBOL_REGEX.match(p.symbol.strip().upper())
        ]
        insights.append(
            PortfolioInsight(
                id=f"{portfolio_id}-data-unpriced",
                portfolio_id=portfolio_id,
                category=InsightCategory.RISK,
                severity=InsightSeverity.WARNING,
                title="Unpriced Positions Increase Valuation Uncertainty",
                description=(
                    f"{completeness.unpriced_holdings_count} of {completeness.total_holdings_count} positions lack market quotes "
                    f"(completeness ratio: {completeness.completeness_ratio}). A data quality penalty has been incorporated into the risk score."
                ),
                evidence={
                    "unpriced_holdings_count": completeness.unpriced_holdings_count,
                    "total_holdings_count": completeness.total_holdings_count,
                    "completeness_ratio": str(completeness.completeness_ratio),
                },
                related_symbols=unpriced_syms[:10],
                created_at=now,
                is_simulated=True,
                source="DETERMINISTIC_RISK_ENGINE",
            )
        )
    elif completeness.has_stale_prices:
        insights.append(
            PortfolioInsight(
                id=f"{portfolio_id}-data-stale",
                portfolio_id=portfolio_id,
                category=InsightCategory.RISK,
                severity=InsightSeverity.WARNING,
                title="Stale Quotes Detected in Valuation",
                description=(
                    "One or more holding positions were valued using cached emergency stale quotes due to provider unavailability, "
                    f"increasing price latency risk."
                ),
                evidence={
                    "has_stale_prices": True,
                    "completeness_ratio": str(completeness.completeness_ratio),
                },
                related_symbols=[],
                created_at=now,
                is_simulated=True,
                source="DETERMINISTIC_RISK_ENGINE",
            )
        )
    else:
        insights.append(
            PortfolioInsight(
                id=f"{portfolio_id}-data-complete",
                portfolio_id=portfolio_id,
                category=InsightCategory.RISK,
                severity=InsightSeverity.INFO,
                title="Complete Market Data Valuation",
                description=(
                    f"All {completeness.total_holdings_count} holding positions are valued with fresh market quotes "
                    f"(100.00% completeness ratio)."
                ),
                evidence={
                    "completeness_ratio": str(completeness.completeness_ratio),
                    "total_holdings_count": completeness.total_holdings_count,
                    "has_stale_prices": False,
                },
                related_symbols=[],
                created_at=now,
                is_simulated=True,
                source="DETERMINISTIC_RISK_ENGINE",
            )
        )

    return insights
