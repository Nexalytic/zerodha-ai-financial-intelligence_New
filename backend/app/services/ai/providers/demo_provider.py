from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

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
from app.services.ai.providers.base import BaseAIProvider

TWO_PLACES = Decimal("0.01")


def _quantize_decimal(val: Optional[Decimal]) -> Decimal:
    if val is None:
        return Decimal("0.00")
    return val.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class DeterministicDemoProvider(BaseAIProvider):
    """
    Deterministic, zero-cost portfolio reasoning provider for demonstration and testing.
    Derives structured narrative insights, key drivers, risk alerts, and review cards
    strictly from the supplied PortfolioEvidenceBundle.
    Never invents metrics, prices, news, or sources.
    """

    PROVIDER_NAME: str = "DETERMINISTIC_DEMO_REASONER"
    MODEL_ID: str = "deterministic-demo-v1"
    IS_SIMULATED: bool = True

    async def generate_insights(self, evidence: PortfolioEvidenceBundle) -> AIInsightReport:
        """
        Generate grounded, reviewable AI insights from the verified evidence bundle.
        """
        report_id = self.generate_report_id(evidence.portfolio_id)
        now = datetime.now(timezone.utc)

        # -------------------------------------------------------------------
        # Scenario A: Empty Portfolio
        # -------------------------------------------------------------------
        if evidence.completeness.total_holdings_count == 0:
            summary = (
                f"Portfolio '{evidence.portfolio_name}' is currently empty with no recorded "
                f"holdings or capital allocation. Quantitative metrics, sector exposure, and "
                f"concentration scoring cannot be calculated."
            )
            confidence = AIConfidenceIndicator(
                score=Decimal("0.50"),
                level=ConfidenceLevel.LOW,
                calibration_limitation=(
                    "Heuristic confidence score penalized due to empty portfolio with zero active positions. "
                    "This is not a statistically calibrated Bayesian or probability distribution."
                ),
                data_quality_discount=Decimal("0.50"),
                staleness_discount=Decimal("0.00"),
            )
            key_drivers = [
                EvidenceKeyDriver(
                    driver_id="driver-empty-1",
                    driver_type=DriverType.DATA_QUALITY,
                    title="Zero Active Positions",
                    statement="The portfolio contains 0 holdings; all financial metrics and valuations are zero.",
                    supporting_metric_key="completeness.total_holdings_count",
                    supporting_metric_value=0,
                    source_reference="analytics.completeness",
                    is_grounded=True,
                )
            ]
            risk_alerts = [
                AIRiskAlert(
                    alert_id="alert-empty-1",
                    severity=AlertSeverity.INFO,
                    category="DATA_COMPLETENESS",
                    headline="Empty Portfolio Detected",
                    explanation="No active holdings exist. Add or import holdings to enable intelligence analysis.",
                    evidence_reference="completeness.total_holdings_count",
                    actionable_mitigation="Import holdings via CSV or seed demo portfolio to begin analysis.",
                )
            ]
            review_cards = [
                ReviewableInsightCard(
                    card_id="card-empty-1",
                    category="ALLOCATION",
                    severity="INFO",
                    title="Empty Portfolio Notice",
                    description="Portfolio has no allocated capital or active positions.",
                    cited_metrics={"total_holdings_count": 0},
                    related_symbols=[],
                    review_status=ReviewStatus.VERIFIED,
                )
            ]
            gaps = [
                "Portfolio contains zero active positions; market valuation and risk metrics are unavailable."
            ]
            disclaimers = self._get_standard_disclaimers()

            return AIInsightReport(
                report_id=report_id,
                portfolio_id=evidence.portfolio_id,
                generated_at=now,
                provider_name=self.PROVIDER_NAME,
                model_id=self.MODEL_ID,
                is_simulated=self.IS_SIMULATED,
                executive_summary=summary,
                key_drivers=key_drivers,
                risk_alerts=risk_alerts,
                confidence=confidence,
                review_cards=review_cards,
                uncertainty_and_gaps=gaps,
                disclaimers=disclaimers,
                review_status=ReviewStatus.VERIFIED,
                grounding_report=GroundingValidationReport(
                    total_claims_checked=2,
                    passed_count=2,
                    flagged_count=0,
                    rejected_count=0,
                    is_acceptable=True,
                ),
            )

        # -------------------------------------------------------------------
        # Scenario B: Wholly Unpriced Portfolio
        # -------------------------------------------------------------------
        if evidence.completeness.priced_holdings_count == 0:
            total = evidence.completeness.total_holdings_count
            cost_basis = evidence.valuation.total_cost_basis
            summary = (
                f"Portfolio '{evidence.portfolio_name}' contains {total} position(s) with an acquisition "
                f"cost basis of ₹{cost_basis:,.2f}. However, 100% of holdings lack valid market price observations. "
                f"Current market valuation, unrealized returns, and structural risk scores cannot be determined."
            )
            confidence = AIConfidenceIndicator(
                score=Decimal("0.25"),
                level=ConfidenceLevel.LOW,
                calibration_limitation=(
                    "Heuristic confidence score heavily penalized due to complete absence of market prices. "
                    "This is not a statistically calibrated Bayesian or probability distribution."
                ),
                data_quality_discount=Decimal("0.75"),
                staleness_discount=Decimal("0.00"),
            )
            key_drivers = [
                EvidenceKeyDriver(
                    driver_id="driver-unpriced-1",
                    driver_type=DriverType.DATA_QUALITY,
                    title="100% Unpriced Positions",
                    statement=f"All {total} holding(s) currently lack market quotes; valuation reflects acquisition cost only.",
                    supporting_metric_key="completeness.unpriced_holdings_count",
                    supporting_metric_value=total,
                    source_reference="analytics.completeness",
                    is_grounded=True,
                )
            ]
            risk_alerts = [
                AIRiskAlert(
                    alert_id="alert-unpriced-1",
                    severity=AlertSeverity.CRITICAL,
                    category="DATA_COMPLETENESS",
                    headline="Valuation Unavailable (Unpriced Portfolio)",
                    explanation="Absence of quote observations prevents calculating current market value and P/L.",
                    evidence_reference="completeness.unpriced_holdings_count",
                    actionable_mitigation="Verify market data connectivity or exchange ticker symbols.",
                )
            ]
            review_cards = [
                ReviewableInsightCard(
                    card_id="card-unpriced-1",
                    category="DATA_QUALITY",
                    severity="CRITICAL",
                    title="Market Prices Unavailable",
                    description="All positions lack market quotes; portfolio metrics cannot be reliably calculated.",
                    cited_metrics={"unpriced_count": total, "cost_basis": str(cost_basis)},
                    related_symbols=[],
                    review_status=ReviewStatus.VERIFIED,
                )
            ]
            gaps = [
                f"All {total} holding(s) lack market quotes. Valuation, returns, and concentration are unavailable.",
                "Historical risk metrics are unavailable (data_status: INSUFFICIENT_HISTORY); price volatility, beta, and maximum drawdown are not inferred.",
            ]
            disclaimers = self._get_standard_disclaimers()

            return AIInsightReport(
                report_id=report_id,
                portfolio_id=evidence.portfolio_id,
                generated_at=now,
                provider_name=self.PROVIDER_NAME,
                model_id=self.MODEL_ID,
                is_simulated=self.IS_SIMULATED,
                executive_summary=summary,
                key_drivers=key_drivers,
                risk_alerts=risk_alerts,
                confidence=confidence,
                review_cards=review_cards,
                uncertainty_and_gaps=gaps,
                disclaimers=disclaimers,
                review_status=ReviewStatus.VERIFIED,
                grounding_report=GroundingValidationReport(
                    total_claims_checked=2,
                    passed_count=2,
                    flagged_count=0,
                    rejected_count=0,
                    is_acceptable=True,
                ),
            )

        # -------------------------------------------------------------------
        # Scenario C: Priced or Partially Priced Portfolio
        # -------------------------------------------------------------------
        market_val = evidence.valuation.total_market_value
        cost_basis = evidence.valuation.total_cost_basis
        pnl = evidence.valuation.unrealized_pnl or Decimal("0.00")
        pnl_pct = evidence.valuation.unrealized_pnl_percent or Decimal("0.00")
        top_sym = evidence.concentration.top_holding_symbol or "N/A"
        top_weight = evidence.concentration.top_holding_weight_percent or Decimal("0.00")
        hhi = evidence.concentration.herfindahl_index or Decimal("0.00")
        tier = evidence.concentration.concentration_tier or "UNKNOWN"
        risk_score = evidence.risk_assessment.composite_risk_score or Decimal("0.00")
        risk_tier = evidence.risk_assessment.risk_tier or "UNKNOWN"
        unpriced_count = evidence.completeness.unpriced_holdings_count
        has_stale = any(q.is_stale for q in evidence.market_snapshot.quotes.values())

        # 1. Executive Summary
        pnl_sign = "+" if pnl >= Decimal("0.00") else ""
        summary_parts = [
            f"Portfolio '{evidence.portfolio_name}' is currently valued at ₹{market_val:,.2f} "
            f"against a total acquisition cost basis of ₹{cost_basis:,.2f}, representing an unrealized "
            f"return of {pnl_sign}₹{pnl:,.2f} ({pnl_sign}{pnl_pct}%).",
            f"Concentration risk is evaluated as {tier}, with the top holding {top_sym} comprising "
            f"{top_weight}% of total priced market value and a Herfindahl-Hirschman Index (HHI) of {hhi}.",
            f"The overall deterministic 4-component structural risk engine assigns a score of {risk_score}/100 "
            f"({risk_tier} tier).",
        ]
        if unpriced_count > 0:
            summary_parts.append(
                f"Data quality notice: {unpriced_count} position(s) lack market quotes; reported valuations "
                f"and return metrics reflect priced positions only."
            )
        executive_summary = " ".join(summary_parts)

        # 2. Key Drivers
        key_drivers: List[EvidenceKeyDriver] = []

        # Driver 1: Single-Stock Concentration
        key_drivers.append(
            EvidenceKeyDriver(
                driver_id="driver-concentration-1",
                driver_type=DriverType.CONCENTRATION,
                title=f"Top Holding Exposure: {top_sym} ({top_weight}%)",
                statement=(
                    f"The portfolio's largest single asset allocation is {top_sym}, accounting for "
                    f"{top_weight}% of priced market value, classifying single-stock risk as {tier}."
                ),
                supporting_metric_key="concentration.top_holding_weight_percent",
                supporting_metric_value=top_weight,
                source_reference="analytics.concentration",
                is_grounded=True,
            )
        )

        # Driver 2: Dominant Sector Exposure
        if evidence.sector_allocations:
            sorted_sectors = sorted(
                evidence.sector_allocations,
                key=lambda s: s.market_value if s.market_value is not None else Decimal("0.00"),
                reverse=True,
            )
            top_sector = sorted_sectors[0]
            top_sec_alloc = top_sector.allocation_percent or Decimal("0.00")
            key_drivers.append(
                EvidenceKeyDriver(
                    driver_id="driver-sector-1",
                    driver_type=DriverType.SECTOR,
                    title=f"Dominant Sector Exposure: {top_sector.sector} ({top_sec_alloc}%)",
                    statement=(
                        f"The {top_sector.sector} sector is the primary sector allocation, representing "
                        f"₹{top_sector.market_value:,.2f} ({top_sec_alloc}%) across {top_sector.priced_count} priced asset(s)."
                    ),
                    supporting_metric_key="sector_allocations.allocation_percent",
                    supporting_metric_value=top_sec_alloc,
                    source_reference="analytics.sector_allocations",
                    is_grounded=True,
                )
            )

        # Driver 3: Performance & Return Contribution
        key_drivers.append(
            EvidenceKeyDriver(
                driver_id="driver-performance-1",
                driver_type=DriverType.PERFORMANCE,
                title=f"Priced Unrealized Return: {pnl_sign}{pnl_pct}%",
                statement=(
                    f"Priced holdings reflect an aggregate unrealized P/L of ₹{pnl:,.2f} ({pnl_sign}{pnl_pct}%) "
                    f"relative to priced cost basis of ₹{evidence.valuation.priced_cost_basis:,.2f}."
                ),
                supporting_metric_key="valuation.unrealized_pnl_percent",
                supporting_metric_value=pnl_pct,
                source_reference="analytics.valuation",
                is_grounded=True,
            )
        )

        # Driver 4: Diversification Breadth
        enh = evidence.concentration.effective_holdings_count or Decimal("1.00")
        key_drivers.append(
            EvidenceKeyDriver(
                driver_id="driver-breadth-1",
                driver_type=DriverType.DIVERSIFICATION,
                title=f"Portfolio Breadth (HHI: {hhi}, ENH: {enh})",
                statement=(
                    f"The portfolio demonstrates an effective number of holdings (ENH) of {enh} based on "
                    f"an HHI of {hhi}, indicating {tier.lower()} dispersion across priced assets."
                ),
                supporting_metric_key="concentration.herfindahl_index",
                supporting_metric_value=hhi,
                source_reference="analytics.concentration",
                is_grounded=True,
            )
        )

        # Driver 5: Grounded News Headline (strictly if news provided)
        if evidence.news_articles:
            top_article = evidence.news_articles[0]
            headline = getattr(top_article, "title", getattr(top_article, "headline", "Market Intelligence Update"))
            symbols = getattr(top_article, "related_symbols", getattr(top_article, "symbols", []))
            rel_sym = symbols[0] if symbols else "MARKET"
            key_drivers.append(
                EvidenceKeyDriver(
                    driver_id="driver-news-1",
                    driver_type=DriverType.NEWS,
                    title=f"Market Intelligence: {headline[:60]}",
                    statement=(
                        f"Simulated news for {rel_sym} reported: '{headline}' "
                        f"(Source: {top_article.source})."
                    ),
                    supporting_metric_key="news.title",
                    supporting_metric_value=headline,
                    source_reference=f"news.{rel_sym}",
                    is_grounded=True,
                )
            )

        # 3. Risk Alerts
        risk_alerts: List[AIRiskAlert] = []

        # Alert 1: Concentration
        if top_weight >= Decimal("25.00"):
            risk_alerts.append(
                AIRiskAlert(
                    alert_id="alert-concentration-1",
                    severity=AlertSeverity.HIGH if top_weight >= Decimal("40.00") else AlertSeverity.MEDIUM,
                    category="SINGLE_STOCK_CONCENTRATION",
                    headline=f"Elevated Concentration in {top_sym} ({top_weight}%)",
                    explanation=(
                        f"{top_sym} accounts for {top_weight}% of priced market value. Excessive single-stock "
                        f"weight exposes the portfolio to firm-specific downside volatility."
                    ),
                    evidence_reference="concentration.top_holding_weight_percent",
                    actionable_mitigation="Consider periodic rebalancing to diversify single-stock capital risk.",
                )
            )

        # Alert 2: Structural Risk Score
        if risk_score >= Decimal("55.00"):
            risk_alerts.append(
                AIRiskAlert(
                    alert_id="alert-risk-1",
                    severity=AlertSeverity.HIGH if risk_score >= Decimal("75.00") else AlertSeverity.MEDIUM,
                    category="STRUCTURAL_PORTFOLIO_RISK",
                    headline=f"Elevated Structural Risk Score: {risk_score}/100 ({risk_tier})",
                    explanation=(
                        f"The 4-component risk engine classified this portfolio as {risk_tier} ({risk_score}/100), "
                        f"driven by asset concentration and sector clustering."
                    ),
                    evidence_reference="risk_assessment.composite_risk_score",
                    actionable_mitigation="Evaluate sector and holding distribution to lower concentration score.",
                )
            )

        # Alert 3: Data Completeness Warning
        if unpriced_count > 0:
            risk_alerts.append(
                AIRiskAlert(
                    alert_id="alert-data-1",
                    severity=AlertSeverity.MEDIUM,
                    category="DATA_COMPLETENESS",
                    headline=f"Partial Valuation Warning: {unpriced_count} Unpriced Asset(s)",
                    explanation=(
                        f"{unpriced_count} holding(s) lack current market prices. Reported valuation and "
                        f"risk metrics represent priced positions only."
                    ),
                    evidence_reference="completeness.unpriced_holdings_count",
                    actionable_mitigation="Review unpriced holdings and confirm ticker symbol formatting.",
                )
            )

        # 4. Confidence Calculation
        base_confidence = Decimal("0.90")  # Capped at 0.90 because historical volatility is unavailable
        comp_ratio = evidence.completeness.completeness_ratio
        data_quality_discount = _quantize_decimal((Decimal("1.0000") - comp_ratio) * Decimal("0.40"))
        staleness_discount = Decimal("0.10") if has_stale else Decimal("0.00")

        final_score = max(Decimal("0.10"), base_confidence - data_quality_discount - staleness_discount)
        conf_level = ConfidenceLevel.HIGH if final_score >= Decimal("0.75") else (
            ConfidenceLevel.MEDIUM if final_score >= Decimal("0.50") else ConfidenceLevel.LOW
        )

        confidence = AIConfidenceIndicator(
            score=_quantize_decimal(final_score),
            level=conf_level,
            calibration_limitation=(
                "Heuristic confidence score calculated from data completeness and price freshness penalties. "
                "This is not a statistically calibrated Bayesian or probability distribution."
            ),
            data_quality_discount=data_quality_discount,
            staleness_discount=staleness_discount,
        )

        # 5. Reviewable Insight Cards
        review_cards: List[ReviewableInsightCard] = []
        card_idx = 1
        for driver in key_drivers:
            rel_syms = [top_sym] if driver.driver_type == DriverType.CONCENTRATION and top_sym != "N/A" else []
            review_cards.append(
                ReviewableInsightCard(
                    card_id=f"card-driver-{card_idx}",
                    category=driver.driver_type.value,
                    severity="INFO",
                    title=driver.title,
                    description=driver.statement,
                    cited_metrics={driver.supporting_metric_key: driver.supporting_metric_value},
                    related_symbols=rel_syms,
                    review_status=ReviewStatus.VERIFIED,
                )
            )
            card_idx += 1

        for alert in risk_alerts:
            rel_syms = [top_sym] if "CONCENTRATION" in alert.category and top_sym != "N/A" else []
            review_cards.append(
                ReviewableInsightCard(
                    card_id=f"card-alert-{card_idx}",
                    category=alert.category,
                    severity=alert.severity.value,
                    title=alert.headline,
                    description=alert.explanation,
                    cited_metrics={"evidence_reference": alert.evidence_reference},
                    related_symbols=rel_syms,
                    review_status=ReviewStatus.VERIFIED,
                )
            )
            card_idx += 1

        # 6. Uncertainty and Missing Evidence Disclosures
        gaps: List[str] = [
            "Historical risk metrics are unavailable (data_status: INSUFFICIENT_HISTORY); "
            "price volatility, beta, and maximum drawdown are not inferred from snapshot quotes."
        ]
        if unpriced_count > 0:
            unpriced_syms = [p.symbol for p in evidence.completeness.unpriced_positions]
            gaps.append(
                f"Portfolio contains {unpriced_count} unpriced asset(s) ({', '.join(unpriced_syms)}); "
                f"valuation and concentration metrics reflect priced positions only."
            )
        if has_stale:
            gaps.append(
                "One or more asset quotes were served from expired cache fallback due to simulated provider unavailability."
            )

        disclaimers = self._get_standard_disclaimers()

        # 7. Grounding Audit Report
        total_claims = len(key_drivers) + len(risk_alerts)
        grounding_findings = [
            GroundingFinding(
                check_name="METRIC_GROUNDING_CHECK",
                target_id=d.driver_id,
                status=FindingStatus.PASSED,
                details={"metric_key": d.supporting_metric_key, "cited_value": str(d.supporting_metric_value)},
            )
            for d in key_drivers
        ]
        grounding_report = GroundingValidationReport(
            total_claims_checked=total_claims,
            passed_count=total_claims,
            flagged_count=0,
            rejected_count=0,
            findings=grounding_findings,
            is_acceptable=True,
        )

        return AIInsightReport(
            report_id=report_id,
            portfolio_id=evidence.portfolio_id,
            generated_at=now,
            provider_name=self.PROVIDER_NAME,
            model_id=self.MODEL_ID,
            is_simulated=self.IS_SIMULATED,
            executive_summary=executive_summary,
            key_drivers=key_drivers,
            risk_alerts=risk_alerts,
            confidence=confidence,
            review_cards=review_cards,
            uncertainty_and_gaps=gaps,
            disclaimers=disclaimers,
            review_status=ReviewStatus.VERIFIED,
            grounding_report=grounding_report,
        )

    def _get_standard_disclaimers(self) -> List[str]:
        return [
            "Financial intelligence for educational and demonstration purposes only. Not SEBI-registered investment advice.",
            "Generated by deterministic heuristic demonstration engine (DETERMINISTIC_DEMO_REASONER). Not genuine LLM reasoning.",
            "Market data and news items are sourced from simulated demo providers.",
        ]
