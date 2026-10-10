import re
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.analytics import (
    ConcentrationMetrics,
    HistoricalRiskMetrics,
    PortfolioCompleteness,
    PortfolioRiskAssessment,
    PortfolioValuation,
    SectorAllocation,
)
from app.schemas.market_data import BatchQuotesResponse, NewsArticle
from app.schemas.portfolio import PortfolioDetailResponse

SYMBOL_REGEX = re.compile(r"^[A-Z0-9&-]{1,20}$")
TWO_PLACES = Decimal("0.01")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DriverType(str, Enum):
    CONCENTRATION = "CONCENTRATION"
    SECTOR = "SECTOR"
    PERFORMANCE = "PERFORMANCE"
    RISK = "RISK"
    DATA_QUALITY = "DATA_QUALITY"
    DIVERSIFICATION = "DIVERSIFICATION"
    NEWS = "NEWS"


class AlertSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ReviewStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    VERIFIED = "VERIFIED"
    FLAGGED_WITH_WARNINGS = "FLAGGED_WITH_WARNINGS"
    REJECTED = "REJECTED"


class FindingStatus(str, Enum):
    PASSED = "PASSED"
    FLAGGED = "FLAGGED"
    REJECTED = "REJECTED"


# ---------------------------------------------------------------------------
# Input Evidence Schema
# ---------------------------------------------------------------------------

class PortfolioEvidenceBundle(BaseModel):
    """
    Structured, verified evidence bundle fed into the AI reasoning engine.
    Contains strictly factual analytics, market data, news, and completeness indicators.
    """
    portfolio_id: str = Field(..., min_length=1, max_length=64, description="Target portfolio ID")
    portfolio_name: str = Field(..., min_length=1, max_length=100, description="Human-readable portfolio name")
    is_sample_portfolio: bool = Field(default=False, description="Whether this is a demo/sample portfolio")
    valuation: PortfolioValuation = Field(..., description="Cost basis and market value metrics")
    completeness: PortfolioCompleteness = Field(..., description="Data completeness and unpriced asset detail")
    concentration: ConcentrationMetrics = Field(..., description="HHI, top holding, and concentration tier")
    sector_allocations: List[SectorAllocation] = Field(default_factory=list, description="Sector allocations")
    risk_assessment: PortfolioRiskAssessment = Field(..., description="4-component structural risk scores")
    market_snapshot: BatchQuotesResponse = Field(..., description="Market quotes for portfolio holdings")
    news_articles: List[NewsArticle] = Field(default_factory=list, description="Relevant news items")
    historical_risk: HistoricalRiskMetrics = Field(
        default_factory=lambda: HistoricalRiskMetrics(data_status="INSUFFICIENT_HISTORY"),
        description="Historical price series metrics and data availability status",
    )
    evidence_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when evidence bundle was gathered",
    )
    disclaimer: str = Field(
        default="Verified evidence bundle for AI analysis and demonstration. Not SEBI-registered investment advice.",
        description="Compliance notice",
    )

    @field_validator("portfolio_id", "portfolio_name")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty or whitespace only")
        return cleaned

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Output Component Schemas
# ---------------------------------------------------------------------------

class EvidenceKeyDriver(BaseModel):
    """
    Key factor driving portfolio performance, concentration, or risk,
    explicitly tied to a supporting metric from the evidence bundle.
    """
    driver_id: str = Field(..., min_length=1, max_length=50, description="Unique driver ID (e.g. driver-1)")
    driver_type: DriverType = Field(..., description="Category of key driver")
    title: str = Field(..., min_length=1, max_length=150, description="Short driver headline")
    statement: str = Field(..., min_length=1, max_length=1000, description="Factual, grounded narrative explanation")
    supporting_metric_key: str = Field(
        ..., min_length=1, max_length=100, description="Exact metric path in evidence (e.g. concentration.top_holding_weight_percent)"
    )
    supporting_metric_value: Any = Field(..., description="Exact metric value cited from evidence")
    source_reference: str = Field(
        ..., min_length=1, max_length=100, description="Originating domain source (e.g. analytics.concentration, market_data.TCS)"
    )
    is_grounded: bool = Field(default=True, description="Flag indicating programmatic verification against evidence")

    model_config = ConfigDict(from_attributes=True)


class AIRiskAlert(BaseModel):
    """
    High-priority risk warning derived directly from concentration or completeness evidence.
    """
    alert_id: str = Field(..., min_length=1, max_length=50, description="Unique alert identifier")
    severity: AlertSeverity = Field(..., description="Alert severity: CRITICAL, HIGH, MEDIUM, LOW, INFO")
    category: str = Field(..., min_length=1, max_length=100, description="Risk category tag")
    headline: str = Field(..., min_length=1, max_length=150, description="Concise alert headline")
    explanation: str = Field(..., min_length=1, max_length=1000, description="Detailed explanation of the risk factor")
    evidence_reference: str = Field(..., min_length=1, max_length=100, description="Source metric path or evidence citation")
    actionable_mitigation: Optional[str] = Field(
        default=None, max_length=500, description="Optional non-advisory educational mitigation observation"
    )

    model_config = ConfigDict(from_attributes=True)


class AIConfidenceIndicator(BaseModel):
    """
    Confidence assessment with mandatory calibration limitation disclosure.
    Prevents misrepresenting heuristic scores as statistical probabilities.
    """
    score: Decimal = Field(..., ge=Decimal("0.00"), le=Decimal("1.00"), description="Confidence score on 0.00-1.00 scale")
    level: ConfidenceLevel = Field(..., description="Qualitative confidence tier: HIGH, MEDIUM, LOW")
    calibration_limitation: str = Field(
        ...,
        min_length=20,
        description="Mandatory documentation of confidence meaning (e.g. heuristic penalty vs statistical calibration)",
    )
    data_quality_discount: Decimal = Field(
        default=Decimal("0.00"), ge=Decimal("0.00"), le=Decimal("1.00"), description="Confidence deduction for unpriced positions"
    )
    staleness_discount: Decimal = Field(
        default=Decimal("0.00"), ge=Decimal("0.00"), le=Decimal("1.00"), description="Confidence deduction for stale quote data"
    )

    model_config = ConfigDict(from_attributes=True)


class ReviewableInsightCard(BaseModel):
    """
    Modular, reviewable UI card representing an individual observation,
    ready for user review and audit verification.
    """
    card_id: str = Field(..., min_length=1, max_length=50, description="Unique card ID")
    category: str = Field(..., min_length=1, max_length=50, description="Functional category")
    severity: str = Field(..., min_length=1, max_length=20, description="Severity tag")
    title: str = Field(..., min_length=1, max_length=150, description="Insight card title")
    description: str = Field(..., min_length=1, max_length=1000, description="Observation description")
    cited_metrics: Dict[str, Any] = Field(default_factory=dict, description="Dictionary of exact metrics cited in card")
    related_symbols: List[str] = Field(default_factory=list, description="Related stock symbols")
    review_status: ReviewStatus = Field(default=ReviewStatus.PENDING_REVIEW, description="Review verification status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC creation timestamp")

    @field_validator("related_symbols")
    @classmethod
    def validate_symbols(cls, symbols: List[str]) -> List[str]:
        normalized = []
        for s in symbols:
            cleaned = s.strip().upper()
            if not SYMBOL_REGEX.match(cleaned):
                raise ValueError(f"Invalid symbol '{s}' in related_symbols")
            normalized.append(cleaned)
        return normalized

    model_config = ConfigDict(from_attributes=True)


class GroundingFinding(BaseModel):
    """
    Programmatic finding from verifying an individual claim or cited metric.
    """
    check_name: str = Field(..., min_length=1, max_length=100, description="Name of validation rule (e.g. SYMBOL_HALLUCINATION_CHECK)")
    target_id: str = Field(..., min_length=1, max_length=100, description="Identifier of the claim, driver, or alert checked")
    status: FindingStatus = Field(..., description="Check status: PASSED, FLAGGED, REJECTED")
    reason: Optional[str] = Field(default=None, description="Explanation if check was flagged or rejected")
    details: Dict[str, Any] = Field(default_factory=dict, description="Supporting comparison metrics or discrepancies")

    model_config = ConfigDict(from_attributes=True)


class GroundingValidationReport(BaseModel):
    """
    Summary report of programmatic claim grounding and veracity verification.
    """
    total_claims_checked: int = Field(default=0, ge=0, description="Total assertions evaluated")
    passed_count: int = Field(default=0, ge=0, description="Claims verified against evidence")
    flagged_count: int = Field(default=0, ge=0, description="Claims flagged with discrepancies")
    rejected_count: int = Field(default=0, ge=0, description="Fabricated or contradictory claims rejected")
    findings: List[GroundingFinding] = Field(default_factory=list, description="List of granular validation findings")
    is_acceptable: bool = Field(default=True, description="True if no claims were rejected and flagged count is acceptable")

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Complete AI Insight Report Schema
# ---------------------------------------------------------------------------

class AIInsightReport(BaseModel):
    """
    Complete, evidence-grounded AI intelligence report for an investment portfolio.
    Comprises narrative summary, evidence-linked drivers, risk alerts, review cards,
    confidence metrics, uncertainty disclosures, and grounding audit.
    """
    report_id: str = Field(..., min_length=1, max_length=64, description="Unique report ID")
    portfolio_id: str = Field(..., min_length=1, max_length=64, description="Target portfolio identifier")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC report generation timestamp",
    )
    provider_name: str = Field(..., min_length=1, max_length=100, description="Originating AI provider identifier")
    model_id: str = Field(..., min_length=1, max_length=100, description="Model or heuristic engine ID")
    is_simulated: bool = Field(default=True, description="Marker indicating simulated or heuristic intelligence")
    executive_summary: str = Field(
        ..., min_length=10, max_length=3000, description="Grounded executive summary of portfolio status"
    )
    key_drivers: List[EvidenceKeyDriver] = Field(
        default_factory=list, description="Evidence-backed factors explaining portfolio posture"
    )
    risk_alerts: List[AIRiskAlert] = Field(
        default_factory=list, description="Prioritized structural and data risk warnings"
    )
    confidence: AIConfidenceIndicator = Field(
        ..., description="Confidence score, discounts, and mandatory calibration limitation"
    )
    review_cards: List[ReviewableInsightCard] = Field(
        default_factory=list, description="Modular reviewable cards for user interface inspection"
    )
    uncertainty_and_gaps: List[str] = Field(
        default_factory=list, description="Explicit disclosures of missing, stale, or partial data"
    )
    disclaimers: List[str] = Field(
        default_factory=lambda: [
            "Financial intelligence for educational and demonstration purposes only. Not SEBI-registered investment advice.",
            "Generated by deterministic heuristic demonstration engine. Not genuine LLM reasoning.",
        ],
        description="Compliance, educational, and simulation disclaimers",
    )
    review_status: ReviewStatus = Field(
        default=ReviewStatus.PENDING_REVIEW,
        description="Overall review state: VERIFIED, FLAGGED_WITH_WARNINGS, or REJECTED",
    )
    grounding_report: GroundingValidationReport = Field(
        default_factory=GroundingValidationReport,
        description="Programmatic claim-grounding audit report",
    )

    @field_validator("report_id", "portfolio_id", "provider_name", "model_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty or whitespace only")
        return cleaned

    @field_validator("disclaimers")
    @classmethod
    def validate_disclaimers(cls, disclaimers: List[str]) -> List[str]:
        if not disclaimers:
            raise ValueError("At least one legal and compliance disclaimer must be provided")
        return disclaimers

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class GenerateAIInsightsRequest(BaseModel):
    """
    Request options for generating evidence-grounded AI insights for a portfolio.
    """
    include_news: bool = Field(
        default=True,
        description="Whether to include relevant simulated market news in the evidence bundle.",
    )
    news_limit: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum number of news articles to retrieve (1-20).",
    )
    provider_override: Optional[str] = Field(
        default=None,
        description="Optional provider identifier (e.g. 'DETERMINISTIC_DEMO_REASONER').",
    )

    model_config = ConfigDict(extra="forbid")

