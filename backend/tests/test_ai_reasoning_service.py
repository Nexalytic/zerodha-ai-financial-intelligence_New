from decimal import Decimal
from typing import Any, AsyncGenerator, Dict, List
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import AsyncTTLCache
from app.db.session import get_db
from app.main import app
from app.providers.base import BaseMarketDataProvider, BaseNewsProvider
from app.schemas.ai_reasoning import (
    AIInsightReport,
    AlertSeverity,
    ConfidenceLevel,
    DriverType,
    EvidenceKeyDriver,
    FindingStatus,
    PortfolioEvidenceBundle,
    ReviewStatus,
)
from app.schemas.market_data import NewsArticle, Quote, QuoteStatus
from app.schemas.portfolio import HoldingCreate, PortfolioCreate
from app.services.ai import (
    AIMalformedOutputError,
    AIProviderError,
    AIReasoningError,
    AIReasoningService,
)
from app.services.ai.evidence_assembler import EvidenceAssemblerService
from app.services.ai.grounding_validator import ClaimGroundingValidator
from app.services.ai.providers.base import BaseAIProvider
from app.services.ai.providers.demo_provider import DeterministicDemoProvider
from app.services.market_data_service import MarketDataService
from app.services.news_service import NewsService
from app.services.portfolio_service import DEMO_PORTFOLIO_ID, PortfolioService


# ===========================================================================
# Mock Providers for Controlled Failure Testing (₹0 spend)
# ===========================================================================

class FailingMarketProvider(BaseMarketDataProvider):
    async def get_quote(self, symbol: str, exchange: str = "NSE") -> Quote:
        raise RuntimeError("Market provider connection refused")

    async def get_quotes(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, Quote]:
        raise RuntimeError("Market provider connection refused")


class FailingNewsProvider(BaseNewsProvider):
    async def get_news_for_symbols(self, symbols: List[str], limit: int = 10) -> List[NewsArticle]:
        raise RuntimeError("News upstream failure")

    async def get_market_news(self, limit: int = 10) -> List[NewsArticle]:
        raise RuntimeError("News upstream failure")


class ExceptionThrowingAIProvider(BaseAIProvider):
    PROVIDER_NAME = "CRASHING_AI_PROVIDER"
    MODEL_ID = "crashing-model"

    async def generate_insights(self, evidence: PortfolioEvidenceBundle) -> AIInsightReport:
        raise RuntimeError("Neural model memory crash")


class MalformedOutputAIProvider(BaseAIProvider):
    PROVIDER_NAME = "MALFORMED_AI_PROVIDER"
    MODEL_ID = "malformed-model"

    async def generate_insights(self, evidence: PortfolioEvidenceBundle) -> Any:  # type: ignore
        # Return invalid object that cannot validate to AIInsightReport
        return {"unexpected_bad_key": 12345}


class HallucinatingAIProvider(BaseAIProvider):
    PROVIDER_NAME = "HALLUCINATING_AI_PROVIDER"
    MODEL_ID = "hallucinating-model"

    async def generate_insights(self, evidence: PortfolioEvidenceBundle) -> AIInsightReport:
        # Generate a report using demo provider but inject a hallucinated unsupported symbol
        demo = DeterministicDemoProvider()
        report = await demo.generate_insights(evidence)
        report.review_cards[0].related_symbols = ["FABRICATED_GHOST_CORP"]
        return report


# ===========================================================================
# 1. Service Layer Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_service_successful_deterministic_reasoning(test_db_setup):
    """Verify end-to-end evidence assembly, demo reasoning, and grounding verification."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        demo_port, _ = await port_service.seed_demo_portfolio()

        service = AIReasoningService(session=session)
        report = await service.generate_portfolio_insights(portfolio_id=demo_port.id)

        assert report is not None
        assert report.portfolio_id == demo_port.id
        assert report.provider_name == "DETERMINISTIC_DEMO_REASONER"
        assert report.model_id == "deterministic-demo-v1"
        assert report.is_simulated is True
        assert report.review_status == ReviewStatus.VERIFIED
        assert report.grounding_report.is_acceptable is True
        assert report.grounding_report.rejected_count == 0
        assert all(d.is_grounded for d in report.key_drivers)
        assert len(report.review_cards) > 0
        assert all(c.review_status == ReviewStatus.VERIFIED for c in report.review_cards)


@pytest.mark.asyncio
async def test_service_missing_portfolio_returns_none(test_db_setup):
    """Verify non-existent portfolio returns None."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        service = AIReasoningService(session=session)
        report = await service.generate_portfolio_insights("00000000-0000-0000-0000-000000000099")
        assert report is None


@pytest.mark.asyncio
async def test_service_empty_portfolio(test_db_setup):
    """Verify empty portfolio gracefully produces an empty intelligence report."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        empty_port = await port_service.create_portfolio(PortfolioCreate(name="Empty Fund", holdings=[]))

        service = AIReasoningService(session=session)
        report = await service.generate_portfolio_insights(portfolio_id=empty_port.id)

        assert report is not None
        assert report.confidence.level == ConfidenceLevel.LOW
        assert "currently empty" in report.executive_summary
        assert report.review_status == ReviewStatus.VERIFIED


@pytest.mark.asyncio
async def test_service_wholly_unpriced_portfolio(test_db_setup):
    """Verify wholly unpriced portfolio produces critical completeness alert with verified status."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        unpriced_port = await port_service.create_portfolio(
            PortfolioCreate(
                name="Unpriced Fund",
                holdings=[
                    HoldingCreate(
                        symbol="UNLISTED-1",
                        exchange="NSE",
                        quantity=10,
                        average_buy_price=Decimal("100.00"),
                        sector="Industrials",
                    )
                ],
            )
        )

        market_service = MarketDataService(provider=FailingMarketProvider())
        service = AIReasoningService(session=session, market_data_service=market_service)
        report = await service.generate_portfolio_insights(portfolio_id=unpriced_port.id)

        assert report is not None
        assert report.confidence.level == ConfidenceLevel.LOW
        assert any(a.severity == AlertSeverity.CRITICAL for a in report.risk_alerts)
        assert report.review_status == ReviewStatus.VERIFIED


@pytest.mark.asyncio
async def test_service_news_provider_failure_graceful(test_db_setup):
    """Verify news provider failure does not break the intelligence pipeline."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        demo_port, _ = await port_service.seed_demo_portfolio()

        news_service = NewsService(provider=FailingNewsProvider())
        service = AIReasoningService(session=session, news_service=news_service)
        report = await service.generate_portfolio_insights(portfolio_id=demo_port.id)

        assert report is not None
        assert report.review_status == ReviewStatus.VERIFIED
        assert not any(d.driver_type == DriverType.NEWS for d in report.key_drivers)


@pytest.mark.asyncio
async def test_service_reasoning_provider_exception_raises_error(test_db_setup):
    """Verify provider exception is caught, logged, and raised as AIProviderError."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        demo_port, _ = await port_service.seed_demo_portfolio()

        crashing_provider = ExceptionThrowingAIProvider()
        service = AIReasoningService(session=session, provider=crashing_provider)

        with pytest.raises(AIProviderError, match="AI reasoning provider failed"):
            await service.generate_portfolio_insights(portfolio_id=demo_port.id)


@pytest.mark.asyncio
async def test_service_malformed_provider_output_raises_error(test_db_setup):
    """Verify malformed provider output raises AIMalformedOutputError."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        demo_port, _ = await port_service.seed_demo_portfolio()

        malformed_provider = MalformedOutputAIProvider()
        service = AIReasoningService(session=session, provider=malformed_provider)

        with pytest.raises(AIMalformedOutputError, match="invalid report structure"):
            await service.generate_portfolio_insights(portfolio_id=demo_port.id)


@pytest.mark.asyncio
async def test_service_rejected_grounding_never_marked_verified(test_db_setup):
    """Verify hallucinating provider output is marked REJECTED and never returned as VERIFIED."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        demo_port, _ = await port_service.seed_demo_portfolio()

        hallucinating_provider = HallucinatingAIProvider()
        service = AIReasoningService(session=session, provider=hallucinating_provider)

        report = await service.generate_portfolio_insights(portfolio_id=demo_port.id)

        assert report is not None
        assert report.review_status == ReviewStatus.REJECTED
        assert report.grounding_report.is_acceptable is False
        assert report.grounding_report.rejected_count > 0
        assert report.review_cards[0].review_status == ReviewStatus.REJECTED


@pytest.mark.asyncio
async def test_service_invalid_provider_override_raises_value_error(test_db_setup):
    """Verify unrecognized provider override raises ValueError."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        demo_port, _ = await port_service.seed_demo_portfolio()

        service = AIReasoningService(session=session)
        with pytest.raises(ValueError, match="Unsupported AI reasoning provider"):
            await service.generate_portfolio_insights(
                portfolio_id=demo_port.id,
                provider_override="NON_EXISTENT_LLM",
            )


@pytest.mark.asyncio
async def test_service_groq_override_blocked_under_mock_mode(test_db_setup):
    """Verify provider_override='GROQ' is blocked when USE_MOCK_DATA is True."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        demo_port, _ = await port_service.seed_demo_portfolio()

        service = AIReasoningService(session=session)
        with pytest.raises(
            ValueError,
            match="Live AI provider 'GROQ' cannot be selected while USE_MOCK_DATA is true.",
        ):
            await service.generate_portfolio_insights(
                portfolio_id=demo_port.id,
                provider_override="GROQ",
            )

        # Also verify case-insensitive "groq"
        with pytest.raises(
            ValueError,
            match="Live AI provider 'GROQ' cannot be selected while USE_MOCK_DATA is true.",
        ):
            await service.generate_portfolio_insights(
                portfolio_id=demo_port.id,
                provider_override="groq",
            )


@pytest.mark.asyncio
async def test_service_demo_override_accepted_under_mock_mode(test_db_setup):
    """Verify provider_override='DEMO' succeeds under mock mode."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        demo_port, _ = await port_service.seed_demo_portfolio()

        service = AIReasoningService(session=session)
        report = await service.generate_portfolio_insights(
            portfolio_id=demo_port.id,
            provider_override="DEMO",
        )
        assert report is not None
        assert report.provider_name == "DETERMINISTIC_DEMO_REASONER"
        assert report.review_status == ReviewStatus.VERIFIED


@pytest.mark.asyncio
async def test_service_deterministic_reproducibility(test_db_setup):
    """Verify identical inputs yield identical narrative, confidence, and driver values."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        demo_port, _ = await port_service.seed_demo_portfolio()

        service = AIReasoningService(session=session)
        rep1 = await service.generate_portfolio_insights(portfolio_id=demo_port.id)
        rep2 = await service.generate_portfolio_insights(portfolio_id=demo_port.id)

        assert rep1.executive_summary == rep2.executive_summary
        assert rep1.confidence.score == rep2.confidence.score
        assert rep1.review_status == rep2.review_status
        assert len(rep1.key_drivers) == len(rep2.key_drivers)
        for d1, d2 in zip(rep1.key_drivers, rep2.key_drivers):
            assert d1.title == d2.title
            assert d1.statement == d2.statement
            assert d1.supporting_metric_value == d2.supporting_metric_value


# ===========================================================================
# 2. REST API Endpoint Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_api_successful_ai_insights_endpoint(client: AsyncClient):
    """Verifies POST /api/v1/portfolios/{id}/ai-insights returns 200 with typed report."""
    # Seed demo portfolio
    seed_resp = await client.post("/api/v1/portfolios/seed-demo")
    assert seed_resp.status_code == 200
    portfolio_id = seed_resp.json()["portfolio"]["id"]

    # Call AI insights endpoint
    response = await client.post(
        f"/api/v1/portfolios/{portfolio_id}/ai-insights",
        json={"include_news": True, "news_limit": 5},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["portfolio_id"] == portfolio_id
    assert data["provider_name"] == "DETERMINISTIC_DEMO_REASONER"
    assert data["model_id"] == "deterministic-demo-v1"
    assert data["is_simulated"] is True
    assert data["review_status"] == "VERIFIED"
    assert len(data["key_drivers"]) >= 4
    assert len(data["review_cards"]) >= 4
    assert data["grounding_report"]["is_acceptable"] is True
    assert len(data["disclaimers"]) >= 2


@pytest.mark.asyncio
async def test_api_ai_insights_missing_portfolio_returns_404(client: AsyncClient):
    """Verifies POST /api/v1/portfolios/{id}/ai-insights with invalid ID returns 404 envelope."""
    response = await client.post("/api/v1/portfolios/00000000-0000-0000-0000-000000000000/ai-insights")
    assert response.status_code == 404

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "PORTFOLIO_NOT_FOUND"
    assert "not found" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_api_ai_insights_empty_body_uses_defaults(client: AsyncClient):
    """Verifies POST /api/v1/portfolios/{id}/ai-insights without JSON body uses default options."""
    seed_resp = await client.post("/api/v1/portfolios/seed-demo")
    portfolio_id = seed_resp.json()["portfolio"]["id"]

    response = await client.post(f"/api/v1/portfolios/{portfolio_id}/ai-insights")
    assert response.status_code == 200
    assert response.json()["review_status"] == "VERIFIED"


@pytest.mark.asyncio
async def test_api_ai_insights_forbids_unknown_fields(client: AsyncClient):
    """Verifies extra payload fields are rejected with HTTP 422 VALIDATION_ERROR envelope."""
    seed_resp = await client.post("/api/v1/portfolios/seed-demo")
    portfolio_id = seed_resp.json()["portfolio"]["id"]

    response = await client.post(
        f"/api/v1/portfolios/{portfolio_id}/ai-insights",
        json={"forbidden_extra_field": 123},
    )
    assert response.status_code == 422

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_api_ai_insights_invalid_provider_override_returns_422(client: AsyncClient):
    """Verifies unsupported provider override returns HTTP 422 envelope."""
    seed_resp = await client.post("/api/v1/portfolios/seed-demo")
    portfolio_id = seed_resp.json()["portfolio"]["id"]

    response = await client.post(
        f"/api/v1/portfolios/{portfolio_id}/ai-insights",
        json={"provider_override": "UNSUPPORTED_EXTERNAL_LLM"},
    )
    assert response.status_code == 422

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "Unsupported AI reasoning provider" in data["error"]["message"]


@pytest.mark.asyncio
async def test_api_ai_insights_groq_override_blocked_under_mock_mode_returns_422(client: AsyncClient):
    """Verifies that requesting GROQ override while USE_MOCK_DATA=true returns 422 VALIDATION_ERROR."""
    seed_resp = await client.post("/api/v1/portfolios/seed-demo")
    portfolio_id = seed_resp.json()["portfolio"]["id"]

    response = await client.post(
        f"/api/v1/portfolios/{portfolio_id}/ai-insights",
        json={"provider_override": "GROQ"},
    )
    assert response.status_code == 422

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "Live AI provider 'GROQ' cannot be selected while USE_MOCK_DATA is true." in data["error"]["message"]


@pytest.mark.asyncio
async def test_api_ai_insights_provider_failure_returns_502(client: AsyncClient, test_db_setup):
    """Verifies provider failure returns HTTP 502 without leaking secrets or stack traces."""
    seed_resp = await client.post("/api/v1/portfolios/seed-demo")
    portfolio_id = seed_resp.json()["portfolio"]["id"]

    session_factory, _ = test_db_setup

    # Override AI reasoning service dependency with one using a crashing provider
    async def override_get_ai_service():
        async with session_factory() as session:
            yield AIReasoningService(
                session=session,
                provider=ExceptionThrowingAIProvider(),
            )

    from app.api.v1.endpoints.portfolios import get_ai_reasoning_service
    app.dependency_overrides[get_ai_reasoning_service] = override_get_ai_service

    try:
        response = await client.post(f"/api/v1/portfolios/{portfolio_id}/ai-insights")
        assert response.status_code == 502

        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "AI_PROVIDER_ERROR"
        # Ensure raw exception "Neural model memory crash" is NOT in client error message
        assert "Neural model memory crash" not in data["error"]["message"]
        assert "AI reasoning provider failed" in data["error"]["message"]
    finally:
        app.dependency_overrides.pop(get_ai_reasoning_service, None)


@pytest.mark.asyncio
async def test_api_ai_insights_rejected_grounding_returned_with_rejected_status(client: AsyncClient, test_db_setup):
    """Verifies that an ungrounded/hallucinated report is returned with review_status=REJECTED."""
    seed_resp = await client.post("/api/v1/portfolios/seed-demo")
    portfolio_id = seed_resp.json()["portfolio"]["id"]

    session_factory, _ = test_db_setup

    async def override_get_ai_service():
        async with session_factory() as session:
            yield AIReasoningService(
                session=session,
                provider=HallucinatingAIProvider(),
            )

    from app.api.v1.endpoints.portfolios import get_ai_reasoning_service
    app.dependency_overrides[get_ai_reasoning_service] = override_get_ai_service

    try:
        response = await client.post(f"/api/v1/portfolios/{portfolio_id}/ai-insights")
        assert response.status_code == 200

        data = response.json()
        # Must NEVER return an ungrounded report as VERIFIED
        assert data["review_status"] == "REJECTED"
        assert data["grounding_report"]["is_acceptable"] is False
        assert data["grounding_report"]["rejected_count"] > 0
    finally:
        app.dependency_overrides.pop(get_ai_reasoning_service, None)
