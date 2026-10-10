import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.logging import logger
from app.schemas.ai_reasoning import (
    AIInsightReport,
    DriverType,
    FindingStatus,
    GroundingFinding,
    GroundingValidationReport,
    PortfolioEvidenceBundle,
    ReviewStatus,
)


class FindingCode:
    """Standardized programmatic finding codes for grounding verification."""
    SYMBOL_UNSUPPORTED = "SYMBOL_UNSUPPORTED"
    METRIC_PATH_UNKNOWN = "METRIC_PATH_UNKNOWN"
    NUMERIC_VALUE_MISMATCH = "NUMERIC_VALUE_MISMATCH"
    DIRECTIONAL_CONTRADICTION = "DIRECTIONAL_CONTRADICTION"
    HISTORICAL_RISK_FABRICATION = "HISTORICAL_RISK_FABRICATION"
    MISSING_DATA_DISCLOSURE_OMITTED = "MISSING_DATA_DISCLOSURE_OMITTED"
    CONFIDENCE_CALIBRATION_UNGROUNDED = "CONFIDENCE_CALIBRATION_UNGROUNDED"
    PORTFOLIO_ID_MISMATCH = "PORTFOLIO_ID_MISMATCH"


class ClaimGroundingValidator:
    """
    Deterministic Claim Grounding & Verification Engine.
    Cross-references AI insight reports against ground-truth PortfolioEvidenceBundle.
    Never invokes a language model or external network endpoint.
    Produces typed GroundingValidationReport and enforces review status invariants.
    """

    TOLERANCE_PERCENT = Decimal("0.05")   # ±0.05 percentage-point tolerance for percentage metrics
    TOLERANCE_CURRENCY = Decimal("0.01")  # ±0.01 standard rounding tolerance for currency/totals/scores

    RISK_COMPONENT_ALIASES: Dict[str, str] = {
        "single_stock_concentration": "single_stock_concentration_score",
        "single_stock_concentration_score": "single_stock_concentration_score",
        "sector_concentration": "sector_concentration_score",
        "sector_concentration_score": "sector_concentration_score",
        "portfolio_breadth": "diversification_breadth_score",
        "diversification_breadth": "diversification_breadth_score",
        "diversification_breadth_score": "diversification_breadth_score",
        "data_quality": "data_quality_score",
        "data_quality_score": "data_quality_score",
    }

    ALLOWED_SECTOR_FIELDS: Set[str] = frozenset({
        "allocation_percent",
        "market_value",
        "cost_basis",
        "priced_count",
        "unpriced_count",
        "holdings_count",
        "unrealized_pnl",
        "unrealized_pnl_percent",
        "cost_basis_weight_percent",
        "cost_basis_weighted_return_contribution_percent",
    })

    COMMON_NON_TICKER_TERMS: Set[str] = frozenset({
        "THE", "A", "AN", "THIS", "THAT", "THESE", "THOSE",
        "TOP", "LARGE", "SMALL", "MID", "TOTAL", "HIGH", "LOW",
        "NEW", "OLD", "FIRST", "SECOND", "THIRD",
        "EQUITY", "STOCK", "STOCKS", "SHARE", "SHARES", "PORTFOLIO",
        "SECTOR", "MARKET", "VALUE", "GROWTH", "RISK", "CASH",
        "PRICE", "PRICES", "HOLDING", "HOLDINGS", "POSITION", "POSITIONS",
        "LOSS", "PROFIT", "RETURN", "RETURNS", "GAIN", "GAINS",
        "INDEX", "FUNDS", "FUND", "ETF", "ETFS", "CORP", "COMPANY",
        "NSE", "BSE", "NIFTY", "SENSEX",
        "MODERATE", "CRITICAL", "INFO", "MEDIUM", "ALERT",
        "PARTIAL", "COMPLETE", "UNKNOWN", "UNPRICED", "STALE",
        "ACTIVE", "EMPTY", "HEALTHY",
        "IS", "ARE", "WAS", "WERE", "BE", "BEEN", "BEING",
        "HAS", "HAVE", "HAD", "DO", "DOES", "DID",
        "IN", "ON", "AT", "TO", "FOR", "WITH", "BY", "FROM", "OF",
        "AND", "OR", "BUT", "NOT", "AS", "IF", "WHILE",
    })

    FORBIDDEN_PSEUDO_SYMBOLS: Set[str] = frozenset({
        "SIMULATED",
        "DEMO",
        "MOCK",
        "GENERAL",
        "NEWS",
        "ARTICLE",
        "FEED",
        "SOURCE",
        "UNKNOWN",
        "TEST",
        "ENGINE",
        "SAMPLE",
    })

    _EXPLICIT_STOCK_PATTERN = re.compile(
        r"\b(?:shares?\s+of\s+|stock\s+|ticker\s+|company\s+|holding\s+in\s+)\(?([A-Z0-9&_\-]{2,15})\)?",
        re.IGNORECASE,
    )
    _FINANCIAL_DECIMAL_PATTERN = re.compile(
        r"^(?P<lead_sign>[-+])?\s*(?P<currency>₹|\$|rs\.?|inr)?\s*(?P<inner_sign>[-+])?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<pct>%?)$",
        re.IGNORECASE,
    )

    def validate_report(
        self,
        report: AIInsightReport,
        evidence: PortfolioEvidenceBundle,
    ) -> AIInsightReport:
        """
        Validate an AIInsightReport against its evidence bundle.
        Updates review_status on individual cards and report, updates driver.is_grounded,
        attaches GroundingValidationReport, and returns the updated report.
        """
        if report is None or evidence is None:
            raise ValueError("Report and evidence bundle must not be None")

        findings = self._run_all_checks(report, evidence)

        total_claims = len(findings)
        passed_count = sum(1 for f in findings if f.status == FindingStatus.PASSED)
        flagged_count = sum(1 for f in findings if f.status == FindingStatus.FLAGGED)
        rejected_count = sum(1 for f in findings if f.status == FindingStatus.REJECTED)
        is_acceptable = (rejected_count == 0 and flagged_count <= 2)

        grounding_report = GroundingValidationReport(
            total_claims_checked=total_claims,
            passed_count=passed_count,
            flagged_count=flagged_count,
            rejected_count=rejected_count,
            findings=findings,
            is_acceptable=is_acceptable,
        )

        # -------------------------------------------------------------------
        # Enforcement: Update Card & Driver Statuses
        # -------------------------------------------------------------------
        # Map findings by target_id
        rejected_targets = {f.target_id for f in findings if f.status == FindingStatus.REJECTED}
        flagged_targets = {f.target_id for f in findings if f.status == FindingStatus.FLAGGED}

        for card in report.review_cards:
            if card.card_id in rejected_targets:
                card.review_status = ReviewStatus.REJECTED
            elif card.card_id in flagged_targets:
                card.review_status = ReviewStatus.FLAGGED_WITH_WARNINGS
            else:
                card.review_status = ReviewStatus.VERIFIED

        for driver in report.key_drivers:
            if driver.driver_id in rejected_targets:
                driver.is_grounded = False
            elif driver.driver_id in flagged_targets:
                driver.is_grounded = False
            else:
                driver.is_grounded = True

        # Overall report review status
        if rejected_count > 0:
            report.review_status = ReviewStatus.REJECTED
        elif flagged_count > 0:
            report.review_status = ReviewStatus.FLAGGED_WITH_WARNINGS
        else:
            report.review_status = ReviewStatus.VERIFIED

        report.grounding_report = grounding_report

        logger.info(
            "Grounding validation completed for report %s: passed=%d, flagged=%d, rejected=%d (status=%s)",
            report.report_id,
            passed_count,
            flagged_count,
            rejected_count,
            report.review_status.value,
        )

        return report

    def generate_validation_report(
        self,
        report: AIInsightReport,
        evidence: PortfolioEvidenceBundle,
    ) -> GroundingValidationReport:
        """
        Runs all grounding checks and returns the GroundingValidationReport without mutating report.
        """
        if report is None or evidence is None:
            raise ValueError("Report and evidence bundle must not be None")

        findings = self._run_all_checks(report, evidence)
        total_claims = len(findings)
        passed_count = sum(1 for f in findings if f.status == FindingStatus.PASSED)
        flagged_count = sum(1 for f in findings if f.status == FindingStatus.FLAGGED)
        rejected_count = sum(1 for f in findings if f.status == FindingStatus.REJECTED)

        return GroundingValidationReport(
            total_claims_checked=total_claims,
            passed_count=passed_count,
            flagged_count=flagged_count,
            rejected_count=rejected_count,
            findings=findings,
            is_acceptable=(rejected_count == 0 and flagged_count <= 2),
        )

    def _run_all_checks(
        self,
        report: AIInsightReport,
        evidence: PortfolioEvidenceBundle,
    ) -> List[GroundingFinding]:
        findings: List[GroundingFinding] = []

        # 0. Portfolio Identity Check
        if report.portfolio_id.strip() != evidence.portfolio_id.strip():
            findings.append(
                GroundingFinding(
                    check_name="PORTFOLIO_IDENTITY_CHECK",
                    target_id=report.report_id,
                    status=FindingStatus.REJECTED,
                    reason=(
                        f"Report portfolio_id '{report.portfolio_id}' does not match "
                        f"evidence bundle portfolio_id '{evidence.portfolio_id}'."
                    ),
                    details={"code": FindingCode.PORTFOLIO_ID_MISMATCH},
                )
            )

        # 1. Symbol Validation
        findings.extend(self._check_symbols(report, evidence))

        # 2. Numeric Grounding
        findings.extend(self._check_numeric_grounding(report, evidence))

        # 3. News Grounding & Alignment
        findings.extend(self._check_news_grounding(report, evidence))

        # 4. Directional Consistency
        findings.extend(self._check_directional_consistency(report, evidence))

        # 5. Historical Risk Fabrication
        findings.extend(self._check_historical_risk_fabrication(report, evidence))

        # 6. Missing-Data Disclosure
        findings.extend(self._check_missing_data_disclosures(report, evidence))

        # 7. Confidence Calibration Limitations
        findings.extend(self._check_confidence_limitations(report, evidence))

        return findings

    # -----------------------------------------------------------------------
    # 1. Symbol Validation Check
    # -----------------------------------------------------------------------
    def _check_symbols(
        self,
        report: AIInsightReport,
        evidence: PortfolioEvidenceBundle,
    ) -> List[GroundingFinding]:
        findings: List[GroundingFinding] = []

        # Build set of ground-truth supported symbols
        valid_symbols: Set[str] = set()
        for sym in evidence.market_snapshot.quotes.keys():
            valid_symbols.add(sym.strip().upper())
        for p in evidence.completeness.unpriced_positions:
            valid_symbols.add(p.symbol.strip().upper())
        for art in evidence.news_articles:
            for s in art.related_symbols:
                valid_symbols.add(s.strip().upper())
        if evidence.concentration.top_holding_symbol:
            valid_symbols.add(evidence.concentration.top_holding_symbol.strip().upper())
        for s in evidence.sector_allocations:
            valid_symbols.add(s.sector.strip().upper())

        # Valid symbols associated with news articles in evidence
        valid_news_symbols: Set[str] = {
            s.strip().upper()
            for art in evidence.news_articles
            for s in (art.related_symbols or [])
            if s.strip() and s.strip().upper() not in self.FORBIDDEN_PSEUDO_SYMBOLS
        }

        # Check Reviewable Cards
        for card in report.review_cards:
            for sym in card.related_symbols:
                norm_sym = sym.strip().upper()
                if norm_sym in self.FORBIDDEN_PSEUDO_SYMBOLS:
                    findings.append(
                        GroundingFinding(
                            check_name="SYMBOL_GROUNDING_CHECK",
                            target_id=card.card_id,
                            status=FindingStatus.REJECTED,
                            reason=f"Card references invalid pseudo-symbol '{norm_sym}'.",
                            details={
                                "code": FindingCode.SYMBOL_UNSUPPORTED,
                                "unsupported_symbol": norm_sym,
                                "valid_symbols": sorted(list(valid_symbols)),
                            },
                        )
                    )
                elif norm_sym not in valid_symbols:
                    findings.append(
                        GroundingFinding(
                            check_name="SYMBOL_GROUNDING_CHECK",
                            target_id=card.card_id,
                            status=FindingStatus.REJECTED,
                            reason=f"Card references symbol '{norm_sym}' which is not in portfolio or news evidence.",
                            details={
                                "code": FindingCode.SYMBOL_UNSUPPORTED,
                                "unsupported_symbol": norm_sym,
                                "valid_symbols": sorted(list(valid_symbols)),
                            },
                        )
                    )
                else:
                    findings.append(
                        GroundingFinding(
                            check_name="SYMBOL_GROUNDING_CHECK",
                            target_id=card.card_id,
                            status=FindingStatus.PASSED,
                            details={"symbol": norm_sym},
                        )
                    )

        # Check Key Drivers source references and narrative statements
        for driver in report.key_drivers:
            ref = driver.source_reference.strip()
            # 1. Check known source_reference prefixes
            for prefix in ("news.", "holdings.", "quotes.", "market_data.", "stock."):
                if ref.startswith(prefix):
                    ref_sym = ref.split(".", 1)[1].strip().upper()
                    if ref_sym in self.FORBIDDEN_PSEUDO_SYMBOLS:
                        findings.append(
                            GroundingFinding(
                                check_name="SYMBOL_GROUNDING_CHECK",
                                target_id=driver.driver_id,
                                status=FindingStatus.REJECTED,
                                reason=f"Driver source reference '{ref}' cites invalid pseudo-symbol '{ref_sym}'.",
                                details={
                                    "code": FindingCode.SYMBOL_UNSUPPORTED,
                                    "unsupported_symbol": ref_sym,
                                    "valid_symbols": sorted(list(valid_symbols)),
                                },
                            )
                        )
                        break

                    if prefix == "news.":
                        if not evidence.news_articles:
                            findings.append(
                                GroundingFinding(
                                    check_name="SYMBOL_GROUNDING_CHECK",
                                    target_id=driver.driver_id,
                                    status=FindingStatus.REJECTED,
                                    reason=f"Driver source reference '{ref}' cites news, but no news articles exist in evidence bundle.",
                                    details={
                                        "code": FindingCode.SYMBOL_UNSUPPORTED,
                                        "unsupported_symbol": ref_sym,
                                        "valid_symbols": sorted(list(valid_symbols)),
                                    },
                                )
                            )
                            break

                        if ref_sym != "MARKET" and ref_sym not in valid_news_symbols:
                            findings.append(
                                GroundingFinding(
                                    check_name="SYMBOL_GROUNDING_CHECK",
                                    target_id=driver.driver_id,
                                    status=FindingStatus.REJECTED,
                                    reason=f"Driver source reference '{ref}' cites symbol '{ref_sym}' which is not in news evidence.",
                                    details={
                                        "code": FindingCode.SYMBOL_UNSUPPORTED,
                                        "unsupported_symbol": ref_sym,
                                        "valid_symbols": sorted(list(valid_symbols)),
                                    },
                                )
                            )
                            break
                    else:
                        if ref_sym != "MARKET" and ref_sym not in valid_symbols:
                            findings.append(
                                GroundingFinding(
                                    check_name="SYMBOL_GROUNDING_CHECK",
                                    target_id=driver.driver_id,
                                    status=FindingStatus.REJECTED,
                                    reason=f"Driver source reference '{ref}' cites symbol '{ref_sym}' which is not in evidence.",
                                    details={
                                        "code": FindingCode.SYMBOL_UNSUPPORTED,
                                        "unsupported_symbol": ref_sym,
                                        "valid_symbols": sorted(list(valid_symbols)),
                                    },
                                )
                            )
                            break
                    break

            # 2. Check narrative statement and title for stock-specific claims
            narrative = f"{driver.title} {driver.statement}"
            detected_symbols: Set[str] = set()
            for m in self._EXPLICIT_STOCK_PATTERN.finditer(narrative):
                cand = m.group(1).strip().upper()
                if any(ch.isalpha() for ch in cand) and cand not in self.COMMON_NON_TICKER_TERMS:
                    detected_symbols.add(cand)

            for sym in detected_symbols:
                if sym in self.FORBIDDEN_PSEUDO_SYMBOLS:
                    findings.append(
                        GroundingFinding(
                            check_name="SYMBOL_GROUNDING_CHECK",
                            target_id=driver.driver_id,
                            status=FindingStatus.REJECTED,
                            reason=f"Driver narrative cites invalid pseudo-symbol '{sym}'.",
                            details={
                                "code": FindingCode.SYMBOL_UNSUPPORTED,
                                "unsupported_symbol": sym,
                                "valid_symbols": sorted(list(valid_symbols)),
                            },
                        )
                    )
                elif sym not in valid_symbols:
                    findings.append(
                        GroundingFinding(
                            check_name="SYMBOL_GROUNDING_CHECK",
                            target_id=driver.driver_id,
                            status=FindingStatus.REJECTED,
                            reason=f"Driver narrative asserts stock claim for '{sym}' which is not in portfolio or market evidence.",
                            details={
                                "code": FindingCode.SYMBOL_UNSUPPORTED,
                                "unsupported_symbol": sym,
                                "valid_symbols": sorted(list(valid_symbols)),
                            },
                        )
                    )

        return findings

    # -----------------------------------------------------------------------
    # 2. News Grounding & Alignment Check
    # -----------------------------------------------------------------------
    def _check_news_grounding(
        self,
        report: AIInsightReport,
        evidence: PortfolioEvidenceBundle,
    ) -> List[GroundingFinding]:
        findings: List[GroundingFinding] = []

        for driver in report.key_drivers:
            if driver.driver_type == DriverType.NEWS:
                if not evidence.news_articles:
                    findings.append(
                        GroundingFinding(
                            check_name="NEWS_GROUNDING_CHECK",
                            target_id=driver.driver_id,
                            status=FindingStatus.REJECTED,
                            reason="Driver is of type NEWS, but evidence bundle contains no news articles.",
                            details={"code": FindingCode.METRIC_PATH_UNKNOWN, "driver_id": driver.driver_id},
                        )
                    )
                    continue

                if not driver.supporting_metric_key.startswith("news."):
                    findings.append(
                        GroundingFinding(
                            check_name="NEWS_GROUNDING_CHECK",
                            target_id=driver.driver_id,
                            status=FindingStatus.REJECTED,
                            reason=f"Driver is of type NEWS, but supporting_metric_key '{driver.supporting_metric_key}' does not reference news evidence.",
                            details={"code": FindingCode.METRIC_PATH_UNKNOWN, "metric_key": driver.supporting_metric_key},
                        )
                    )
                    continue

                if not driver.source_reference.startswith("news."):
                    findings.append(
                        GroundingFinding(
                            check_name="NEWS_GROUNDING_CHECK",
                            target_id=driver.driver_id,
                            status=FindingStatus.REJECTED,
                            reason=f"Driver is of type NEWS, but source_reference '{driver.source_reference}' is not a news reference.",
                            details={"code": FindingCode.SYMBOL_UNSUPPORTED, "source_reference": driver.source_reference},
                        )
                    )
                    continue

                # Cross-reference headline against news articles
                ref_sym = driver.source_reference.split(".", 1)[1].strip().upper()
                reported_val_str = str(driver.supporting_metric_value).strip().lower()
                matching_articles = [
                    art for art in evidence.news_articles
                    if reported_val_str in (getattr(art, "title", "") or "").strip().lower()
                    or (getattr(art, "title", "") or "").strip().lower() in reported_val_str
                ]

                if not matching_articles:
                    findings.append(
                        GroundingFinding(
                            check_name="NEWS_GROUNDING_CHECK",
                            target_id=driver.driver_id,
                            status=FindingStatus.REJECTED,
                            reason=f"News driver headline '{driver.supporting_metric_value}' does not match any article in evidence.",
                            details={
                                "code": FindingCode.NUMERIC_VALUE_MISMATCH,
                                "reported_headline": str(driver.supporting_metric_value),
                            },
                        )
                    )
                    continue

                if ref_sym != "MARKET" and ref_sym not in self.FORBIDDEN_PSEUDO_SYMBOLS:
                    art_symbols = {
                        s.strip().upper()
                        for ma in matching_articles
                        for s in (ma.related_symbols or [])
                        if s.strip()
                    }
                    if art_symbols and ref_sym not in art_symbols:
                        findings.append(
                            GroundingFinding(
                                check_name="NEWS_GROUNDING_CHECK",
                                target_id=driver.driver_id,
                                status=FindingStatus.REJECTED,
                                reason=f"Driver source reference cites '{ref_sym}', but matching news headline belongs to {sorted(list(art_symbols))}.",
                                details={
                                    "code": FindingCode.SYMBOL_UNSUPPORTED,
                                    "unsupported_symbol": ref_sym,
                                    "article_symbols": sorted(list(art_symbols)),
                                },
                            )
                        )
                        continue

                findings.append(
                    GroundingFinding(
                        check_name="NEWS_GROUNDING_CHECK",
                        target_id=driver.driver_id,
                        status=FindingStatus.PASSED,
                        details={"driver_id": driver.driver_id, "source_reference": driver.source_reference},
                    )
                )

        return findings

    # -----------------------------------------------------------------------
    # 3. Numeric Grounding Check
    # -----------------------------------------------------------------------
    def _check_numeric_grounding(
        self,
        report: AIInsightReport,
        evidence: PortfolioEvidenceBundle,
    ) -> List[GroundingFinding]:
        findings: List[GroundingFinding] = []

        # 1. Validate Key Drivers
        for driver in report.key_drivers:
            key = driver.supporting_metric_key
            reported_val = driver.supporting_metric_value

            resolved, source_val = self._resolve_metric_path(key, evidence)
            if not resolved:
                findings.append(
                    GroundingFinding(
                        check_name="NUMERIC_GROUNDING_CHECK",
                        target_id=driver.driver_id,
                        status=FindingStatus.REJECTED,
                        reason=f"Metric key '{key}' cannot be resolved in evidence bundle.",
                        details={"code": FindingCode.METRIC_PATH_UNKNOWN, "metric_key": key},
                    )
                )
                continue

            matches, mismatch_reason = self._compare_values(key, reported_val, source_val)
            if matches:
                findings.append(
                    GroundingFinding(
                        check_name="NUMERIC_GROUNDING_CHECK",
                        target_id=driver.driver_id,
                        status=FindingStatus.PASSED,
                        details={"metric_key": key, "verified_value": str(reported_val)},
                    )
                )
            else:
                findings.append(
                    GroundingFinding(
                        check_name="NUMERIC_GROUNDING_CHECK",
                        target_id=driver.driver_id,
                        status=FindingStatus.REJECTED,
                        reason=f"Metric value contradiction for '{key}': {mismatch_reason}",
                        details={
                            "code": FindingCode.NUMERIC_VALUE_MISMATCH,
                            "metric_key": key,
                            "reported_value": str(reported_val),
                            "evidence_value": str(source_val),
                        },
                    )
                )

        # 2. Validate cited metrics in Review Cards
        for card in report.review_cards:
            for key, reported_val in card.cited_metrics.items():
                if key in ["evidence_reference"]:
                    continue  # metadata reference, not numeric metric
                resolved, source_val = self._resolve_metric_path(key, evidence)
                if not resolved:
                    # If cited metric key is local (e.g. unpriced_count), try shorthand alias
                    shorthand_resolved, source_val = self._resolve_shorthand_metric(key, evidence)
                    if not shorthand_resolved:
                        findings.append(
                            GroundingFinding(
                                check_name="NUMERIC_GROUNDING_CHECK",
                                target_id=card.card_id,
                                status=FindingStatus.REJECTED,
                                reason=f"Card cited metric '{key}' cannot be resolved in evidence.",
                                details={"code": FindingCode.METRIC_PATH_UNKNOWN, "metric_key": key},
                            )
                        )
                        continue

                matches, mismatch_reason = self._compare_values(key, reported_val, source_val)
                if matches:
                    findings.append(
                        GroundingFinding(
                            check_name="NUMERIC_GROUNDING_CHECK",
                            target_id=card.card_id,
                            status=FindingStatus.PASSED,
                            details={"metric_key": key, "verified_value": str(reported_val)},
                        )
                    )
                else:
                    findings.append(
                        GroundingFinding(
                            check_name="NUMERIC_GROUNDING_CHECK",
                            target_id=card.card_id,
                            status=FindingStatus.REJECTED,
                            reason=f"Card cited metric '{key}' contradicts evidence: {mismatch_reason}",
                            details={
                                "code": FindingCode.NUMERIC_VALUE_MISMATCH,
                                "metric_key": key,
                                "reported_value": str(reported_val),
                                "evidence_value": str(source_val),
                            },
                        )
                    )

        return findings

    # -----------------------------------------------------------------------
    # 3. Directional Consistency Check
    # -----------------------------------------------------------------------
    def _check_directional_consistency(
        self,
        report: AIInsightReport,
        evidence: PortfolioEvidenceBundle,
    ) -> List[GroundingFinding]:
        findings: List[GroundingFinding] = []
        pnl = evidence.valuation.unrealized_pnl
        is_unpriced = (evidence.completeness.priced_holdings_count == 0)
        is_empty = (evidence.completeness.total_holdings_count == 0)

        # Check executive summary and drivers
        texts_to_check = [("executive_summary", report.executive_summary)]
        for d in report.key_drivers:
            if d.driver_type == DriverType.PERFORMANCE:
                texts_to_check.append((d.driver_id, d.statement))

        for target_id, text in texts_to_check:
            # Case A: Unpriced or Empty -> No gains or losses can be asserted
            if is_unpriced or is_empty or pnl is None:
                has_gain_claim = bool(
                    re.search(
                        r"\b(unrealized|net|total)\s+(pnl|return|gain|profit)\s+(of|is)\s+[+-]?\s*₹?\s*\d",
                        text,
                        re.IGNORECASE,
                    )
                )
                has_loss_claim = bool(
                    re.search(
                        r"\b(unrealized\s+loss|portfolio\s+loss)\s+(of|is)\s+[+-]?\s*₹?\s*\d",
                        text,
                        re.IGNORECASE,
                    )
                )
                if has_gain_claim or has_loss_claim:
                    findings.append(
                        GroundingFinding(
                            check_name="DIRECTIONAL_CONSISTENCY_CHECK",
                            target_id=target_id,
                            status=FindingStatus.REJECTED,
                            reason="Claim asserts realized/unrealized profit or loss while portfolio is unpriced or empty.",
                            details={"code": FindingCode.DIRECTIONAL_CONTRADICTION},
                        )
                    )
                else:
                    findings.append(
                        GroundingFinding(
                            check_name="DIRECTIONAL_CONSISTENCY_CHECK",
                            target_id=target_id,
                            status=FindingStatus.PASSED,
                            details={"target": target_id, "note": "Properly avoided claiming P/L on unpriced portfolio"},
                        )
                    )

            # Case B: Portfolio in Profit (pnl > 0)
            elif pnl > Decimal("0.00"):
                # Contradiction: claiming net portfolio loss
                contradicts = bool(
                    re.search(
                        r"\b(unrealized\s+loss|negative\s+return|portfolio\s+in\s+loss|net\s+loss)\b",
                        text,
                        re.IGNORECASE,
                    )
                )
                if contradicts:
                    findings.append(
                        GroundingFinding(
                            check_name="DIRECTIONAL_CONSISTENCY_CHECK",
                            target_id=target_id,
                            status=FindingStatus.REJECTED,
                            reason=f"Claim asserts negative return/loss while evidence shows unrealized profit of ₹{pnl}.",
                            details={"code": FindingCode.DIRECTIONAL_CONTRADICTION, "evidence_pnl": str(pnl)},
                        )
                    )
                else:
                    findings.append(
                        GroundingFinding(
                            check_name="DIRECTIONAL_CONSISTENCY_CHECK",
                            target_id=target_id,
                            status=FindingStatus.PASSED,
                            details={"target": target_id, "direction": "POSITIVE_VERIFIED"},
                        )
                    )

            # Case C: Portfolio in Loss (pnl < 0)
            elif pnl < Decimal("0.00"):
                # Contradiction: claiming net portfolio profit
                contradicts = bool(
                    re.search(
                        r"\b(unrealized\s+profit|positive\s+return|portfolio\s+gain|net\s+profit)\b",
                        text,
                        re.IGNORECASE,
                    )
                )
                if contradicts:
                    findings.append(
                        GroundingFinding(
                            check_name="DIRECTIONAL_CONSISTENCY_CHECK",
                            target_id=target_id,
                            status=FindingStatus.REJECTED,
                            reason=f"Claim asserts positive profit while evidence shows unrealized loss of ₹{pnl}.",
                            details={"code": FindingCode.DIRECTIONAL_CONTRADICTION, "evidence_pnl": str(pnl)},
                        )
                    )
                else:
                    findings.append(
                        GroundingFinding(
                            check_name="DIRECTIONAL_CONSISTENCY_CHECK",
                            target_id=target_id,
                            status=FindingStatus.PASSED,
                            details={"target": target_id, "direction": "NEGATIVE_VERIFIED"},
                        )
                    )

            # Case D: Zero return
            else:
                findings.append(
                    GroundingFinding(
                        check_name="DIRECTIONAL_CONSISTENCY_CHECK",
                        target_id=target_id,
                        status=FindingStatus.PASSED,
                        details={"target": target_id, "direction": "FLAT_ZERO"},
                    )
                )

        return findings

    # -----------------------------------------------------------------------
    # 4. Historical Risk Fabrication Check
    # -----------------------------------------------------------------------
    def _check_historical_risk_fabrication(
        self,
        report: AIInsightReport,
        evidence: PortfolioEvidenceBundle,
    ) -> List[GroundingFinding]:
        findings: List[GroundingFinding] = []
        is_insufficient = (evidence.historical_risk.data_status == "INSUFFICIENT_HISTORY")

        if not is_insufficient:
            return findings

        # Check all text blocks for fabricated specific numeric volatility, drawdown, or beta
        blocks = [("executive_summary", report.executive_summary)]
        for d in report.key_drivers:
            blocks.append((d.driver_id, d.statement))
        for card in report.review_cards:
            blocks.append((card.card_id, card.description))

        vol_regex = re.compile(r"\b(annualized\s+volatility|price\s+volatility)\s+(is|of|at)\s+\d+(\.\d+)?%", re.IGNORECASE)
        mdd_regex = re.compile(r"\b(maximum\s+drawdown|max\s+drawdown)\s+(is|of|at)\s+\d+(\.\d+)?%", re.IGNORECASE)
        beta_regex = re.compile(r"\b(portfolio\s+beta|beta)\s+(is|of|at)\s+\d+(\.\d+)?\b", re.IGNORECASE)

        for target_id, text in blocks:
            # Skip if explicitly disclosing unavailability
            lower_text = text.lower()
            if any(term in lower_text for term in ["unavailable", "not inferred", "insufficient", "cannot be determined"]):
                continue

            match_vol = vol_regex.search(text)
            match_mdd = mdd_regex.search(text)
            match_beta = beta_regex.search(text)

            if match_vol or match_mdd or match_beta:
                matched_str = (match_vol or match_mdd or match_beta).group(0)
                findings.append(
                    GroundingFinding(
                        check_name="HISTORICAL_RISK_FABRICATION_CHECK",
                        target_id=target_id,
                        status=FindingStatus.REJECTED,
                        reason=f"Asserted historical metric '{matched_str}' while data_status is INSUFFICIENT_HISTORY.",
                        details={
                            "code": FindingCode.HISTORICAL_RISK_FABRICATION,
                            "assertion": matched_str,
                        },
                    )
                )
            else:
                findings.append(
                    GroundingFinding(
                        check_name="HISTORICAL_RISK_FABRICATION_CHECK",
                        target_id=target_id,
                        status=FindingStatus.PASSED,
                        details={"target": target_id, "status": "No historical risk hallucinated"},
                    )
                )

        return findings

    # -----------------------------------------------------------------------
    # 5. Missing-Data Disclosure Check
    # -----------------------------------------------------------------------
    def _check_missing_data_disclosures(
        self,
        report: AIInsightReport,
        evidence: PortfolioEvidenceBundle,
    ) -> List[GroundingFinding]:
        findings: List[GroundingFinding] = []
        all_disclosures = " ".join(
            report.uncertainty_and_gaps
            + [report.executive_summary]
            + [a.explanation for a in report.risk_alerts]
        ).lower()

        # Case 1: Unpriced positions
        if evidence.completeness.unpriced_holdings_count > 0:
            has_unpriced_disclosure = any(
                w in all_disclosures for w in ["unpriced", "missing quote", "missing price", "lacks market quote", "partial valuation"]
            )
            if not has_unpriced_disclosure:
                findings.append(
                    GroundingFinding(
                        check_name="MISSING_DATA_DISCLOSURE_CHECK",
                        target_id="report.uncertainty_and_gaps",
                        status=FindingStatus.FLAGGED,
                        reason="Portfolio has unpriced positions but no disclosure exists in uncertainty_and_gaps or alerts.",
                        details={"code": FindingCode.MISSING_DATA_DISCLOSURE_OMITTED, "unpriced_count": evidence.completeness.unpriced_holdings_count},
                    )
                )
            else:
                findings.append(
                    GroundingFinding(
                        check_name="MISSING_DATA_DISCLOSURE_CHECK",
                        target_id="report.uncertainty_and_gaps",
                        status=FindingStatus.PASSED,
                        details={"topic": "unpriced_positions_disclosed"},
                    )
                )

        # Case 2: Stale data
        has_stale = evidence.completeness.has_stale_prices or any(
            q.is_stale for q in evidence.market_snapshot.quotes.values()
        )
        if has_stale:
            has_stale_disclosure = any(
                w in all_disclosures for w in ["stale", "expired cache", "cache fallback", "emergency fallback"]
            )
            if not has_stale_disclosure:
                findings.append(
                    GroundingFinding(
                        check_name="MISSING_DATA_DISCLOSURE_CHECK",
                        target_id="report.uncertainty_and_gaps",
                        status=FindingStatus.FLAGGED,
                        reason="Portfolio quotes contain stale cache fallbacks but no stale disclosure was provided.",
                        details={"code": FindingCode.MISSING_DATA_DISCLOSURE_OMITTED, "issue": "stale_quote_omitted"},
                    )
                )
            else:
                findings.append(
                    GroundingFinding(
                        check_name="MISSING_DATA_DISCLOSURE_CHECK",
                        target_id="report.uncertainty_and_gaps",
                        status=FindingStatus.PASSED,
                        details={"topic": "stale_prices_disclosed"},
                    )
                )

        # Case 3: Insufficient history
        if evidence.historical_risk.data_status == "INSUFFICIENT_HISTORY" and evidence.completeness.total_holdings_count > 0:
            has_history_disclosure = any(
                w in all_disclosures for w in ["historical", "insufficient_history", "volatility", "not inferred"]
            )
            if not has_history_disclosure:
                findings.append(
                    GroundingFinding(
                        check_name="MISSING_DATA_DISCLOSURE_CHECK",
                        target_id="report.uncertainty_and_gaps",
                        status=FindingStatus.FLAGGED,
                        reason="Historical risk metrics are unavailable but no disclosure was provided.",
                        details={"code": FindingCode.MISSING_DATA_DISCLOSURE_OMITTED, "issue": "history_omitted"},
                    )
                )
            else:
                findings.append(
                    GroundingFinding(
                        check_name="MISSING_DATA_DISCLOSURE_CHECK",
                        target_id="report.uncertainty_and_gaps",
                        status=FindingStatus.PASSED,
                        details={"topic": "insufficient_history_disclosed"},
                    )
                )

        return findings

    # -----------------------------------------------------------------------
    # 6. Confidence Limitations Check
    # -----------------------------------------------------------------------
    def _check_confidence_limitations(
        self,
        report: AIInsightReport,
        evidence: PortfolioEvidenceBundle,
    ) -> List[GroundingFinding]:
        findings: List[GroundingFinding] = []
        conf = report.confidence

        # Check limitation length
        limitation_text = conf.calibration_limitation.strip().lower()
        if len(limitation_text) < 20:
            findings.append(
                GroundingFinding(
                    check_name="CONFIDENCE_CALIBRATION_CHECK",
                    target_id="report.confidence",
                    status=FindingStatus.REJECTED,
                    reason="Confidence calibration limitation is too short or missing (< 20 characters).",
                    details={"code": FindingCode.CONFIDENCE_CALIBRATION_UNGROUNDED},
                )
            )
            return findings

        # Check qualitative heuristic disclosure
        has_heuristic_notice = any(
            w in limitation_text for w in ["heuristic", "not a statistically calibrated", "not statistically calibrated", "penalty", "discount"]
        )
        if not has_heuristic_notice:
            findings.append(
                GroundingFinding(
                    check_name="CONFIDENCE_CALIBRATION_CHECK",
                    target_id="report.confidence",
                    status=FindingStatus.FLAGGED,
                    reason="Confidence limitation does not clearly disclose heuristic/non-statistical calibration nature.",
                    details={"code": FindingCode.CONFIDENCE_CALIBRATION_UNGROUNDED},
                )
            )
        else:
            findings.append(
                GroundingFinding(
                    check_name="CONFIDENCE_CALIBRATION_CHECK",
                    target_id="report.confidence",
                    status=FindingStatus.PASSED,
                    details={"topic": "heuristic_calibration_disclosed"},
                )
            )

        # Check unpriced penalty applied
        if evidence.completeness.unpriced_holdings_count > 0 and conf.data_quality_discount == Decimal("0.00"):
            findings.append(
                GroundingFinding(
                    check_name="CONFIDENCE_CALIBRATION_CHECK",
                    target_id="report.confidence",
                    status=FindingStatus.FLAGGED,
                    reason="Portfolio has unpriced holdings but data_quality_discount is 0.00.",
                    details={"code": FindingCode.CONFIDENCE_CALIBRATION_UNGROUNDED},
                )
            )

        # Check staleness penalty applied
        has_stale = evidence.completeness.has_stale_prices or any(
            q.is_stale for q in evidence.market_snapshot.quotes.values()
        )
        if has_stale and conf.staleness_discount == Decimal("0.00"):
            findings.append(
                GroundingFinding(
                    check_name="CONFIDENCE_CALIBRATION_CHECK",
                    target_id="report.confidence",
                    status=FindingStatus.FLAGGED,
                    reason="Portfolio has stale quotes but staleness_discount is 0.00.",
                    details={"code": FindingCode.CONFIDENCE_CALIBRATION_UNGROUNDED},
                )
            )

        return findings

    # -----------------------------------------------------------------------
    # Helper: Resolve Metric Paths in Evidence
    # -----------------------------------------------------------------------
    def _resolve_metric_path(
        self,
        metric_key: str,
        evidence: PortfolioEvidenceBundle,
    ) -> Tuple[bool, Any]:
        cleaned = metric_key.strip()
        parts = cleaned.split(".")

        # Sector allocations special resolution
        if parts[0] == "sector_allocations":
            if not evidence.sector_allocations:
                return False, None
            if len(parts) == 2:
                field = parts[1]
                if field in self.ALLOWED_SECTOR_FIELDS:
                    values = [getattr(s, field) for s in evidence.sector_allocations if hasattr(s, field)]
                    return (True, values) if values else (False, None)
                return False, None
            if len(parts) == 3:
                target_sector = parts[1].strip()
                field = parts[2].strip()
                if field not in self.ALLOWED_SECTOR_FIELDS:
                    return False, None
                for s in evidence.sector_allocations:
                    norm_s = s.sector.strip().lower()
                    norm_target = target_sector.lower()
                    if (
                        norm_s == norm_target
                        or norm_s.replace(" ", "_") == norm_target
                        or norm_s.replace("_", " ") == norm_target
                    ):
                        if hasattr(s, field):
                            return True, getattr(s, field)
                return False, None

        # News headline special resolution
        if parts[0] == "news":
            if not evidence.news_articles:
                return False, None
            field = parts[1] if len(parts) > 1 else "title"
            titles = [
                getattr(a, field, getattr(a, "title", getattr(a, "headline", None)))
                for a in evidence.news_articles
            ]
            return (True, titles) if titles else (False, None)

        # Risk component scores aliases
        comp_container = getattr(evidence.risk_assessment, "components", None) or getattr(
            evidence.risk_assessment, "component_scores", None
        )
        if comp_container:
            if parts[0] == "risk_assessment":
                if len(parts) == 3 and parts[1] in ("components", "component_scores"):
                    raw_field = parts[2].strip()
                    target_field = self.RISK_COMPONENT_ALIASES.get(raw_field, raw_field)
                    if hasattr(comp_container, target_field):
                        return True, getattr(comp_container, target_field)
                    if hasattr(comp_container, f"{target_field}_score"):
                        return True, getattr(comp_container, f"{target_field}_score")
                    return False, None
                elif len(parts) == 2 and parts[1].strip() in self.RISK_COMPONENT_ALIASES:
                    target_field = self.RISK_COMPONENT_ALIASES[parts[1].strip()]
                    if hasattr(comp_container, target_field):
                        return True, getattr(comp_container, target_field)
                    return False, None
            elif parts[0] in ("components", "component_scores") and len(parts) == 2:
                raw_field = parts[1].strip()
                target_field = self.RISK_COMPONENT_ALIASES.get(raw_field, raw_field)
                if hasattr(comp_container, target_field):
                    return True, getattr(comp_container, target_field)
                if hasattr(comp_container, f"{target_field}_score"):
                    return True, getattr(comp_container, f"{target_field}_score")
                return False, None

        # Standard recursive attribute navigation
        curr: Any = evidence
        for part in parts:
            if isinstance(curr, dict):
                if part in curr:
                    curr = curr[part]
                else:
                    return False, None
            elif hasattr(curr, part):
                curr = getattr(curr, part)
            else:
                return False, None

        return True, curr

    def _resolve_shorthand_metric(
        self,
        shorthand: str,
        evidence: PortfolioEvidenceBundle,
    ) -> Tuple[bool, Any]:
        """Resolves local card metrics like 'unpriced_count' or 'top_weight'."""
        mapping = {
            "unpriced_count": ("completeness.unpriced_holdings_count", evidence.completeness.unpriced_holdings_count),
            "priced_count": ("completeness.priced_holdings_count", evidence.completeness.priced_holdings_count),
            "total_holdings_count": ("completeness.total_holdings_count", evidence.completeness.total_holdings_count),
            "cost_basis": ("valuation.total_cost_basis", evidence.valuation.total_cost_basis),
            "market_value": ("valuation.total_market_value", evidence.valuation.total_market_value),
            "unrealized_pnl": ("valuation.unrealized_pnl", evidence.valuation.unrealized_pnl),
            "unrealized_pnl_percent": ("valuation.unrealized_pnl_percent", evidence.valuation.unrealized_pnl_percent),
            "top_weight": ("concentration.top_holding_weight_percent", evidence.concentration.top_holding_weight_percent),
            "top_holding_weight": ("concentration.top_holding_weight_percent", evidence.concentration.top_holding_weight_percent),
            "top_holding_weight_percent": ("concentration.top_holding_weight_percent", evidence.concentration.top_holding_weight_percent),
            "herfindahl_index": ("concentration.herfindahl_index", evidence.concentration.herfindahl_index),
            "composite_risk_score": ("risk_assessment.composite_risk_score", evidence.risk_assessment.composite_risk_score),
        }
        if shorthand in mapping:
            return True, mapping[shorthand][1]
        return False, None

    # -----------------------------------------------------------------------
    # Helper: Decimal and Percentage Comparison
    # -----------------------------------------------------------------------
    def _parse_financial_decimal(self, val: Any) -> Optional[Decimal]:
        """
        Safely parse financial numeric strings with optional currency markers (₹, $, Rs., INR),
        thousands separators (commas), and percentage signs (%).
        Returns None for non-numeric, malformed, or ambiguous values.
        """
        if val is None or isinstance(val, (bool, list, dict, set)):
            return None
        if isinstance(val, (int, Decimal)):
            return Decimal(val)
        if isinstance(val, float):
            return Decimal(str(val))

        s = str(val).strip()
        if not s:
            return None

        m = self._FINANCIAL_DECIMAL_PATTERN.match(s)
        if not m:
            return None

        lead_sign = m.group("lead_sign") or ""
        inner_sign = m.group("inner_sign") or ""
        if lead_sign and inner_sign:
            return None
        sign = lead_sign or inner_sign

        num_str = m.group("num").replace(",", "")
        if num_str.count(".") > 1:
            return None

        try:
            return Decimal(f"{sign}{num_str}")
        except (ValueError, ArithmeticError):
            return None

    def _compare_values(
        self,
        metric_key: str,
        reported: Any,
        source: Any,
    ) -> Tuple[bool, Optional[str]]:
        if isinstance(source, list):
            for candidate in source:
                match, _ = self._compare_single(metric_key, reported, candidate)
                if match:
                    return True, None
            return False, f"Reported value '{reported}' does not match any candidate in evidence list: {source}"

        return self._compare_single(metric_key, reported, source)

    def _compare_single(
        self,
        metric_key: str,
        reported: Any,
        source: Any,
    ) -> Tuple[bool, Optional[str]]:
        if source is None:
            if reported is None or str(reported).strip().upper() == "NONE":
                return True, None
            return False, f"Evidence is None but reported is '{reported}'"

        # Try Decimal comparison using safe financial decimal parser
        rep_dec = self._parse_financial_decimal(reported)
        src_dec = self._parse_financial_decimal(source)

        if rep_dec is not None and src_dec is not None:
            is_percent = (
                metric_key.endswith("_percent")
                or "percent" in metric_key
                or metric_key.endswith("_ratio")
                or "ratio" in metric_key
            )
            tolerance = self.TOLERANCE_PERCENT if is_percent else self.TOLERANCE_CURRENCY
            diff = abs(rep_dec - src_dec)
            if diff <= tolerance:
                return True, None
            return False, f"Difference {diff} exceeds tolerance {tolerance} (reported={rep_dec}, source={src_dec})"

        # String comparison
        rep_str = str(reported).strip().lower()
        src_str = str(source).strip().lower()
        if rep_str == src_str or rep_str in src_str or src_str in rep_str:
            return True, None

        return False, f"String mismatch (reported='{reported}', source='{source}')"
