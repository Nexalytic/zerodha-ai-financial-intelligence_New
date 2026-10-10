from datetime import datetime, timezone, timedelta
import pytest
from pydantic import ValidationError

from app.schemas.insight import (
    InsightCategory,
    InsightSeverity,
    PortfolioInsight,
    PortfolioInsightsResponse,
)


def test_valid_portfolio_insight_creation():
    """Verifies that a valid portfolio insight can be constructed with structured evidence."""
    now_utc = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    insight = PortfolioInsight(
        id="INSIGHT-CONC-001",
        portfolio_id="PORTFOLIO-123",
        category=InsightCategory.CONCENTRATION,
        severity=InsightSeverity.WARNING,
        title="High Top Holding Concentration",
        description="The top holding RELIANCE accounts for 42.5% of known market value, exceeding the 25% guideline.",
        evidence={
            "top_holding_symbol": "RELIANCE",
            "weight_percent": "42.5",
            "guideline_threshold": "25.0",
        },
        related_symbols=[" reliance "],
        created_at=now_utc,
    )
    assert insight.id == "INSIGHT-CONC-001"
    assert insight.portfolio_id == "PORTFOLIO-123"
    assert insight.category == InsightCategory.CONCENTRATION
    assert insight.severity == InsightSeverity.WARNING
    assert insight.title == "High Top Holding Concentration"
    assert insight.evidence["weight_percent"] == "42.5"
    assert insight.related_symbols == ["RELIANCE"]
    assert insight.is_simulated is True
    assert insight.source == "RULE_BASED_ANALYTICS"
    assert "SEBI-registered" in insight.disclaimer


def test_insight_category_and_severity_enums():
    """Verifies all valid categories and severities, and that invalid strings are rejected."""
    categories = [
        InsightCategory.CONCENTRATION,
        InsightCategory.DIVERSIFICATION,
        InsightCategory.RISK,
        InsightCategory.PERFORMANCE,
        InsightCategory.ALLOCATION,
    ]
    for cat in categories:
        ins = PortfolioInsight(
            id="test-id",
            portfolio_id="port-id",
            category=cat,
            severity=InsightSeverity.INFO,
            title="Valid Title",
            description="Valid Description",
        )
        assert ins.category == cat

    severities = [
        InsightSeverity.INFO,
        InsightSeverity.WARNING,
        InsightSeverity.CRITICAL,
    ]
    for sev in severities:
        ins = PortfolioInsight(
            id="test-id",
            portfolio_id="port-id",
            category=InsightCategory.RISK,
            severity=sev,
            title="Valid Title",
            description="Valid Description",
        )
        assert ins.severity == sev

    with pytest.raises(ValidationError):
        PortfolioInsight(
            id="test-id",
            portfolio_id="port-id",
            category="UNKNOWN_CATEGORY",
            severity=InsightSeverity.INFO,
            title="Valid Title",
            description="Valid Description",
        )

    with pytest.raises(ValidationError):
        PortfolioInsight(
            id="test-id",
            portfolio_id="port-id",
            category=InsightCategory.RISK,
            severity="FATAL",
            title="Valid Title",
            description="Valid Description",
        )


def test_insight_rejects_empty_and_whitespace_fields():
    """Verifies that empty or whitespace-only strings are rejected for id, portfolio_id, title, and description."""
    # Empty ID
    with pytest.raises(ValidationError):
        PortfolioInsight(
            id="   ",
            portfolio_id="p-1",
            category=InsightCategory.RISK,
            severity=InsightSeverity.INFO,
            title="Valid",
            description="Valid",
        )

    # Empty portfolio_id
    with pytest.raises(ValidationError):
        PortfolioInsight(
            id="i-1",
            portfolio_id="   ",
            category=InsightCategory.RISK,
            severity=InsightSeverity.INFO,
            title="Valid",
            description="Valid",
        )

    # Empty title
    with pytest.raises(ValidationError):
        PortfolioInsight(
            id="i-1",
            portfolio_id="p-1",
            category=InsightCategory.RISK,
            severity=InsightSeverity.INFO,
            title="   ",
            description="Valid",
        )

    # Empty description
    with pytest.raises(ValidationError):
        PortfolioInsight(
            id="i-1",
            portfolio_id="p-1",
            category=InsightCategory.RISK,
            severity=InsightSeverity.INFO,
            title="Valid",
            description="   ",
        )


def test_insight_validates_and_normalizes_related_symbols():
    """Verifies that valid symbols are normalized and invalid/blank symbols are strictly rejected."""
    # Valid symbols with whitespace
    ins = PortfolioInsight(
        id="i-1",
        portfolio_id="p-1",
        category=InsightCategory.RISK,
        severity=InsightSeverity.INFO,
        title="Valid",
        description="Valid",
        related_symbols=[" tcs ", "m&m", "INFY"],
    )
    assert ins.related_symbols == ["TCS", "M&M", "INFY"]

    # Rejects invalid symbol
    with pytest.raises(ValidationError) as exc1:
        PortfolioInsight(
            id="i-1",
            portfolio_id="p-1",
            category=InsightCategory.RISK,
            severity=InsightSeverity.INFO,
            title="Valid",
            description="Valid",
            related_symbols=["TCS", "BAD$SYM"],
        )
    assert "Invalid symbol" in str(exc1.value)

    # Rejects empty string in symbols list rather than silently dropping
    with pytest.raises(ValidationError) as exc2:
        PortfolioInsight(
            id="i-1",
            portfolio_id="p-1",
            category=InsightCategory.RISK,
            severity=InsightSeverity.INFO,
            title="Valid",
            description="Valid",
            related_symbols=["TCS", "   "],
        )
    assert "Invalid symbol" in str(exc2.value)


def test_insight_timezone_aware_timestamp():
    """Verifies timezone-aware timestamp requirement and UTC normalization."""
    # Rejects naive datetime
    naive_dt = datetime(2026, 1, 15, 10, 0)
    with pytest.raises(ValidationError) as exc:
        PortfolioInsight(
            id="i-1",
            portfolio_id="p-1",
            category=InsightCategory.RISK,
            severity=InsightSeverity.INFO,
            title="Valid",
            description="Valid",
            created_at=naive_dt,
        )
    assert "timezone-aware" in str(exc.value)

    # Normalizes timezone offset
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    ist_dt = datetime(2026, 1, 15, 15, 30, tzinfo=ist_tz)
    ins = PortfolioInsight(
        id="i-1",
        portfolio_id="p-1",
        category=InsightCategory.RISK,
        severity=InsightSeverity.INFO,
        title="Valid",
        description="Valid",
        created_at=ist_dt,
    )
    assert ins.created_at.tzinfo == timezone.utc
    assert ins.created_at.hour == 10
    assert ins.created_at.minute == 0


def test_portfolio_insights_response_container():
    """Verifies PortfolioInsightsResponse container serialization and total_insights synchronization."""
    ins1 = PortfolioInsight(
        id="i-1",
        portfolio_id="port-demo",
        category=InsightCategory.CONCENTRATION,
        severity=InsightSeverity.WARNING,
        title="Concentration Warning",
        description="Top holding accounts for >30% of portfolio.",
    )
    ins2 = PortfolioInsight(
        id="i-2",
        portfolio_id="port-demo",
        category=InsightCategory.ALLOCATION,
        severity=InsightSeverity.INFO,
        title="Balanced Sector Spread",
        description="Holdings are distributed across 4 sectors.",
    )

    response = PortfolioInsightsResponse(
        portfolio_id="port-demo",
        insights=[ins1, ins2],
        is_sample_portfolio=True,
    )
    assert response.portfolio_id == "port-demo"
    assert response.total_insights == 2
    assert response.is_sample_portfolio is True
    assert len(response.insights) == 2
    assert "SEBI-registered" in response.disclaimer


def test_portfolio_insights_response_empty():
    """Verifies PortfolioInsightsResponse with zero insights."""
    response = PortfolioInsightsResponse(
        portfolio_id="port-empty",
        insights=[],
    )
    assert response.total_insights == 0
    assert response.insights == []


def test_portfolio_insights_response_rejects_empty_portfolio_id():
    """Verifies that empty portfolio_id in response wrapper is rejected."""
    with pytest.raises(ValidationError):
        PortfolioInsightsResponse(
            portfolio_id="   ",
            insights=[],
        )
