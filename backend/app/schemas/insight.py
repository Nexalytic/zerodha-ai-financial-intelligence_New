import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SYMBOL_REGEX = re.compile(r"^[A-Z0-9&-]{1,20}$")


class InsightCategory(str, Enum):
    CONCENTRATION = "CONCENTRATION"
    DIVERSIFICATION = "DIVERSIFICATION"
    RISK = "RISK"
    PERFORMANCE = "PERFORMANCE"
    ALLOCATION = "ALLOCATION"


class InsightSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class PortfolioInsight(BaseModel):
    id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Stable unique identifier for the insight",
    )
    portfolio_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Associated portfolio identifier",
    )
    category: InsightCategory = Field(
        ...,
        description="Insight category: CONCENTRATION, DIVERSIFICATION, RISK, PERFORMANCE, ALLOCATION",
    )
    severity: InsightSeverity = Field(
        ...,
        description="Severity level: INFO, WARNING, CRITICAL",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Concise, actionable insight headline",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Detailed observation, financial context, or explanation",
    )
    evidence: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional structured metrics or evidence supporting this observation",
    )
    related_symbols: List[str] = Field(
        default_factory=list,
        description="List of related stock symbols referenced in this insight",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timezone-aware UTC creation timestamp",
    )
    is_simulated: bool = Field(
        default=True,
        description="Flag indicating simulated educational insight or demo intelligence",
    )
    source: str = Field(
        default="RULE_BASED_ANALYTICS",
        description="Originating generator or rule provenance tag",
    )
    disclaimer: str = Field(
        default="Financial insight for educational and demonstration purposes only. Not SEBI-registered investment advice.",
        description="Regulatory and educational disclaimer",
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Insight identifier cannot be empty or whitespace only")
        return cleaned

    @field_validator("portfolio_id")
    @classmethod
    def validate_portfolio_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Portfolio identifier cannot be empty or whitespace only")
        return cleaned

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Insight title cannot be empty or whitespace only")
        return cleaned

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Insight description cannot be empty or whitespace only")
        return cleaned

    @field_validator("related_symbols")
    @classmethod
    def validate_and_normalize_related_symbols(cls, symbols: List[str]) -> List[str]:
        normalized: List[str] = []
        for s in symbols:
            if not isinstance(s, str):
                raise ValueError("Symbol must be a string")
            cleaned = s.strip().upper()
            if not cleaned or not SYMBOL_REGEX.match(cleaned):
                raise ValueError(
                    f"Invalid symbol '{s}' in related_symbols. Must be 1-20 alphanumeric characters, &, or -"
                )
            normalized.append(cleaned)
        return normalized

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_created_at(cls, v: Any) -> datetime:
        if v is None:
            return datetime.now(timezone.utc)
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v)
            except Exception as e:
                raise ValueError(f"Invalid created_at timestamp format: {e}")
        elif isinstance(v, datetime):
            dt = v
        else:
            raise ValueError("created_at must be a datetime object or ISO-8601 string")

        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            raise ValueError("created_at timestamp must be timezone-aware (e.g. UTC)")
        return dt.astimezone(timezone.utc)

    model_config = ConfigDict(from_attributes=True)


class PortfolioInsightsResponse(BaseModel):
    portfolio_id: str = Field(
        ...,
        description="Target portfolio identifier",
    )
    insights: List[PortfolioInsight] = Field(
        default_factory=list,
        description="List of structured insights for the portfolio",
    )
    total_insights: int = Field(
        default=0,
        description="Count of insights in the response",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timezone-aware UTC timestamp when insights response was assembled",
    )
    is_sample_portfolio: bool = Field(
        default=False,
        description="Marker indicating whether the analyzed portfolio is a demo/sample",
    )
    disclaimer: str = Field(
        default="Portfolio insights for educational and demonstration purposes only. Not SEBI-registered investment advice.",
        description="Legal and compliance disclaimer",
    )

    @field_validator("portfolio_id")
    @classmethod
    def validate_response_portfolio_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Portfolio identifier cannot be empty or whitespace only")
        return cleaned

    @field_validator("generated_at", mode="before")
    @classmethod
    def validate_generated_at(cls, v: Any) -> datetime:
        if v is None:
            return datetime.now(timezone.utc)
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v)
            except Exception as e:
                raise ValueError(f"Invalid generated_at timestamp format: {e}")
        elif isinstance(v, datetime):
            dt = v
        else:
            raise ValueError("generated_at must be a datetime object or ISO-8601 string")

        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            raise ValueError("generated_at timestamp must be timezone-aware (e.g. UTC)")
        return dt.astimezone(timezone.utc)

    @model_validator(mode="after")
    def sync_total_count(self) -> "PortfolioInsightsResponse":
        self.total_insights = len(self.insights)
        return self

    model_config = ConfigDict(from_attributes=True)
