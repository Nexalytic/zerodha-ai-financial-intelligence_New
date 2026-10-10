import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.analytics import (
    PortfolioAnalyticsResponse,
    PortfolioRiskAssessment,
    ValuationStatus,
)
from app.schemas.insight import PortfolioInsight
from app.schemas.market_data import BatchQuotesResponse, NewsResponse
from app.schemas.portfolio import PortfolioDetailResponse, PortfolioResponse

SYMBOL_REGEX = re.compile(r"^[A-Z0-9&-]{1,20}$")
VALID_EXCHANGES = {"NSE", "BSE"}

# Exactly eight approved, read-only tools
APPROVED_TOOLS = {
    "get_portfolio",
    "list_portfolios",
    "get_market_snapshot",
    "search_news",
    "calculate_portfolio_metrics",
    "score_portfolio_risk",
    "get_evidence_bundle",
    "generate_portfolio_ai_insights",
}


class MCPErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PORTFOLIO_NOT_FOUND = "PORTFOLIO_NOT_FOUND"
    UNAUTHORIZED_TOOL = "UNAUTHORIZED_TOOL"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# Strict Input Argument Schemas (Reject unexpected arguments via extra="forbid")
# ---------------------------------------------------------------------------

class BaseToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GetPortfolioArgs(BaseToolArgs):
    portfolio_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier of the target portfolio",
    )

    @field_validator("portfolio_id")
    @classmethod
    def validate_portfolio_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("portfolio_id must not be empty or whitespace only")
        return cleaned


class ListPortfoliosArgs(BaseToolArgs):
    is_sample: Optional[bool] = Field(
        default=None,
        description="Optional filter: True for demo/sample portfolios, False for custom user portfolios, None for all",
    )


class GetMarketSnapshotArgs(BaseToolArgs):
    symbols: List[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Non-empty list of ticker symbols (max 50, e.g. ['RELIANCE', 'TCS'])",
    )
    exchange: str = Field(
        default="NSE",
        description="Target stock exchange: NSE or BSE",
    )

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if cleaned not in VALID_EXCHANGES:
            raise ValueError(f"Exchange must be one of {sorted(VALID_EXCHANGES)}, got '{v}'")
        return cleaned

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, symbols: List[str]) -> List[str]:
        if not symbols:
            raise ValueError("symbols list must not be empty")
        if len(symbols) > 50:
            raise ValueError(f"symbols list exceeds maximum limit of 50 (got {len(symbols)})")
        normalized: List[str] = []
        for s in symbols:
            if not isinstance(s, str):
                raise ValueError(f"Each symbol must be a string, got {type(s).__name__}")
            cleaned = s.strip().upper()
            if not cleaned or not SYMBOL_REGEX.match(cleaned):
                raise ValueError(
                    f"Invalid symbol '{s}'. Must be 1-20 alphanumeric characters, &, or -"
                )
            normalized.append(cleaned)
        return normalized


class SearchNewsArgs(BaseToolArgs):
    symbols: Optional[List[str]] = Field(
        default=None,
        max_length=20,
        description="Optional list of symbols to filter news (max 20). If omitted, returns general market news.",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of news articles to return (1-50)",
    )

    @field_validator("symbols")
    @classmethod
    def validate_news_symbols(cls, symbols: Optional[List[str]]) -> Optional[List[str]]:
        if symbols is None:
            return None
        if len(symbols) > 20:
            raise ValueError(f"symbols list exceeds maximum limit of 20 (got {len(symbols)})")
        normalized: List[str] = []
        for s in symbols:
            if not isinstance(s, str):
                raise ValueError(f"Each symbol must be a string, got {type(s).__name__}")
            cleaned = s.strip().upper()
            if not cleaned or not SYMBOL_REGEX.match(cleaned):
                raise ValueError(
                    f"Invalid symbol '{s}'. Must be 1-20 alphanumeric characters, &, or -"
                )
            normalized.append(cleaned)
        return normalized


class CalculatePortfolioMetricsArgs(BaseToolArgs):
    portfolio_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier of the portfolio to analyze",
    )

    @field_validator("portfolio_id")
    @classmethod
    def validate_portfolio_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("portfolio_id must not be empty or whitespace only")
        return cleaned


class ScorePortfolioRiskArgs(BaseToolArgs):
    portfolio_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier of the portfolio to risk-score",
    )

    @field_validator("portfolio_id")
    @classmethod
    def validate_portfolio_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("portfolio_id must not be empty or whitespace only")
        return cleaned


class GetEvidenceBundleArgs(BaseToolArgs):
    portfolio_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier of the portfolio for evidence bundling",
    )

    @field_validator("portfolio_id")
    @classmethod
    def validate_portfolio_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("portfolio_id must not be empty or whitespace only")
        return cleaned


class GeneratePortfolioAIInsightsArgs(BaseToolArgs):
    portfolio_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier of the portfolio to analyze with AI reasoning",
    )
    include_news: bool = Field(
        default=True,
        description="Whether to include recent financial news in the evidence bundle",
    )
    news_limit: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum number of news articles to include as evidence (1-20)",
    )

    @field_validator("portfolio_id")
    @classmethod
    def validate_portfolio_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("portfolio_id must not be empty or whitespace only")
        return cleaned


# ---------------------------------------------------------------------------
# Output Schemas & Response Wrappers
# ---------------------------------------------------------------------------

class PortfolioRiskScoreResponse(BaseModel):
    portfolio_id: str = Field(..., description="Target portfolio identifier")
    risk_assessment: PortfolioRiskAssessment = Field(
        ...,
        description="Comprehensive 4-component risk score, risk tier, component breakdowns, and methodology scope",
    )
    insights: List[PortfolioInsight] = Field(
        default_factory=list,
        description="Related explainable rule-based insights supporting the risk assessment",
    )
    total_insights: int = Field(default=0, description="Count of supporting insights")
    is_sample_portfolio: bool = Field(default=False, description="Marker indicating demo/sample portfolio")
    calculated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC calculation timestamp",
    )
    disclaimer: str = Field(
        default="Portfolio risk assessment for educational and demonstration purposes only. Not SEBI-registered investment advice.",
        description="Legal and compliance disclaimer",
    )

    model_config = ConfigDict(from_attributes=True)


class EvidenceBundleMetadata(BaseModel):
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when evidence bundle was assembled",
    )
    completeness_status: ValuationStatus = Field(
        ...,
        description="Portfolio completeness tier: COMPLETE, PARTIAL, EMPTY, or UNPRICED",
    )
    has_missing_prices: bool = Field(
        ...,
        description="Flag indicating one or more portfolio holdings lacked market quotes",
    )
    has_stale_data: bool = Field(
        ...,
        description="Flag indicating one or more quotes were served from expired cache fallback",
    )
    is_simulated: bool = Field(
        default=True,
        description="Flag indicating simulated market data, news, and rule-based insights",
    )
    data_status: str = Field(
        default="INSUFFICIENT_HISTORY",
        description="Historical price series availability status",
    )
    partial_data_warning: Optional[str] = Field(
        default=None,
        description="Explicit advisory warning if metrics were computed on partial holdings",
    )
    disclaimer: str = Field(
        default="Evidence bundle compiled for AI analysis and educational demonstration only. Not SEBI-registered investment advice.",
        description="Compliance and educational disclaimer",
    )

    model_config = ConfigDict(from_attributes=True)


class EvidenceBundle(BaseModel):
    portfolio_id: str = Field(..., description="Target portfolio identifier")
    portfolio: PortfolioDetailResponse = Field(..., description="Portfolio master record and holdings list")
    market_snapshot: BatchQuotesResponse = Field(..., description="Market quotes for all portfolio holdings")
    analytics: PortfolioAnalyticsResponse = Field(
        ...,
        description="Financial valuation, sector allocation, concentration, and historical risk status",
    )
    risk_assessment: PortfolioRiskAssessment = Field(
        ...,
        description="Deterministic 4-component risk assessment and component scores",
    )
    insights: List[PortfolioInsight] = Field(
        default_factory=list,
        description="List of structured rule-based observations and warnings",
    )
    metadata: EvidenceBundleMetadata = Field(
        ...,
        description="Data provenance, freshness, simulation, and completeness metadata",
    )

    model_config = ConfigDict(from_attributes=True)


class MCPErrorEnvelope(BaseModel):
    is_error: bool = True
    error_code: MCPErrorCode
    message: str
    correlation_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: Optional[Dict[str, Any]] = None


class AuditLogRecord(BaseModel):
    timestamp: str
    correlation_id: str
    tool_name: str
    arguments_sanitized: Dict[str, Any]
    duration_ms: float
    status: str  # "SUCCESS" or "ERROR"
    error_code: Optional[str] = None
    error_message: Optional[str] = None
