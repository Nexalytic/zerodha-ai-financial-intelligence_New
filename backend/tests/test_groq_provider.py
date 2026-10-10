import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.core.logging import sanitize_log_message
from app.schemas.ai_reasoning import (
    AIInsightReport,
    DriverType,
    FindingStatus,
    PortfolioEvidenceBundle,
    ReviewStatus,
)
from app.schemas.analytics import (
    ConcentrationMetrics,
    HistoricalRiskMetrics,
    PortfolioCompleteness,
    PortfolioRiskAssessment,
    PortfolioValuation,
    RiskComponentScores,
    ValuationStatus,
)
from app.schemas.market_data import BatchQuotesResponse, NewsArticle
from app.services.ai.grounding_validator import ClaimGroundingValidator
from app.services.ai.providers.demo_provider import DeterministicDemoProvider
from app.services.ai.providers.groq_provider import GroqAIProvider
from app.services.ai.reasoning_service import (
    AIMalformedOutputError,
    AIProviderError,
    AIReasoningService,
    resolve_ai_provider,
)


def create_sample_evidence(
    portfolio_id: str = "port-test-01",
    portfolio_name: str = "Conservative Growth",
    top_symbol: str = "TCS",
    top_weight: Decimal = Decimal("35.00"),
) -> PortfolioEvidenceBundle:
    """Helper creating a minimal, valid PortfolioEvidenceBundle for testing."""
    return PortfolioEvidenceBundle(
        portfolio_id=portfolio_id,
        portfolio_name=portfolio_name,
        is_sample_portfolio=False,
        valuation=PortfolioValuation(
            total_cost_basis=Decimal("90000.00"),
            total_market_value=Decimal("100000.00"),
            unrealized_pnl=Decimal("10000.00"),
            unrealized_pnl_percent=Decimal("11.11"),
            priced_cost_basis=Decimal("90000.00"),
            priced_market_value=Decimal("100000.00"),
        ),


        completeness=PortfolioCompleteness(
            is_complete=True,
            total_holdings_count=3,
            priced_holdings_count=3,
            unpriced_holdings_count=0,
            completeness_ratio=Decimal("1.00"),
            unpriced_positions=[],
        ),

        concentration=ConcentrationMetrics(
            herfindahl_index=Decimal("0.2500"),
            effective_holdings_count=Decimal("4.00"),
            top_holding_symbol=top_symbol,
            top_holding_weight_percent=top_weight,
            concentration_tier="MODERATE",
        ),
        sector_allocations=[],
        risk_assessment=PortfolioRiskAssessment(
            composite_risk_score=Decimal("42.00"),
            risk_tier="MODERATE",
            components=RiskComponentScores(
                single_stock_concentration_score=Decimal("35.00"),
                sector_concentration_score=Decimal("30.00"),
                diversification_breadth_score=Decimal("20.00"),
                data_quality_score=Decimal("0.00"),
            ),

        ),
        market_snapshot=BatchQuotesResponse(
            quotes={},
            total_symbols=0,
            cache_hits_count=0,
            cache_misses_count=0,
        ),
        news_articles=[],
        historical_risk=HistoricalRiskMetrics(data_status="INSUFFICIENT_HISTORY"),
    )


MOCK_VALID_GROQ_INSIGHTS = {
    "executive_summary": "Portfolio 'Conservative Growth' is valued at ₹100,000.00 with total unrealized gain of ₹10,000.00 (11.11%). Single-stock concentration in TCS represents 35.00% of market value.",
    "key_drivers": [
        {
            "driver_id": "driver-1",
            "driver_type": "CONCENTRATION",
            "title": "Top Holding TCS Exposure",
            "statement": "TCS accounts for 35.00% of total portfolio market value.",
            "supporting_metric_key": "concentration.top_holding_weight_percent",
            "supporting_metric_value": 35.00,
            "source_reference": "analytics.concentration",
            "is_grounded": True,
        }
    ],
    "risk_alerts": [
        {
            "alert_id": "alert-1",
            "severity": "MEDIUM",
            "category": "SINGLE_STOCK_CONCENTRATION",
            "headline": "Moderate Concentration in TCS",
            "explanation": "Top holding represents 35.00% of portfolio assets.",
            "evidence_reference": "concentration.top_holding_weight_percent",
            "actionable_mitigation": "Review portfolio allocation periodically.",
        }
    ],
    "confidence": {
        "score": 0.85,
        "level": "HIGH",
        "calibration_limitation": "Heuristic confidence assessment based on complete price coverage.",
        "data_quality_discount": 0.0,
        "staleness_discount": 0.0,
    },
    "review_cards": [
        {
            "card_id": "card-1",
            "category": "CONCENTRATION",
            "severity": "MEDIUM",
            "title": "Top Holding Concentration",
            "description": "TCS accounts for 35.00% of total portfolio market value.",
            "cited_metrics": {"concentration.top_holding_weight_percent": 35.0},
            "related_symbols": ["TCS"],

            "review_status": "PENDING_REVIEW",
        }
    ],
    "uncertainty_and_gaps": [
        "Historical risk metrics are unavailable (data_status: INSUFFICIENT_HISTORY); volatility and beta not calculated."
    ],
    "disclaimers": [
        "Financial intelligence for educational and demonstration purposes only. Not SEBI-registered investment advice.",
        "Generated using live Groq AI reasoning model.",
    ],
}


def make_mock_groq_response(content: str, status_code: int = 200) -> httpx.Response:
    body = {
        "id": "chatcmpl-mock-123",
        "object": "chat.completion",
        "created": 1728550000,
        "model": "openai/gpt-oss-120b",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 350, "completion_tokens": 200, "total_tokens": 550},
    }
    return httpx.Response(status_code, json=body)


# ===========================================================================
# 1. Successful Inference & Provenance Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_groq_successful_inference_and_provenance():
    """
    Verifies that a valid Groq chat completion parses into AIInsightReport with:
    - is_simulated=False
    - provider_name='GROQ'
    - model_id matching configured model
    - accurate typed sub-schemas
    """
    content_json = json.dumps(MOCK_VALID_GROQ_INSIGHTS)
    transport = httpx.MockTransport(lambda req: make_mock_groq_response(content_json))

    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(
            api_key="mock-groq-key",
            model="openai/gpt-oss-120b",
            http_client=client,
        )

        evidence = create_sample_evidence()
        report = await provider.generate_insights(evidence)

        assert isinstance(report, AIInsightReport)
        assert report.is_simulated is False
        assert report.provider_name == "GROQ"
        assert report.model_id == "openai/gpt-oss-120b"
        assert report.portfolio_id == evidence.portfolio_id
        assert len(report.key_drivers) == 1
        assert report.key_drivers[0].driver_id == "driver-1"
        assert len(report.risk_alerts) == 1
        assert report.confidence.score == Decimal("0.85")
        assert len(report.review_cards) == 1
        assert report.review_cards[0].related_symbols == ["TCS"]
        assert len(report.uncertainty_and_gaps) >= 1
        assert len(report.disclaimers) >= 2


@pytest.mark.asyncio
async def test_groq_markdown_fence_extraction():
    """Verifies that json wrapped in markdown code fences is cleaned and parsed."""
    fenced_content = f"```json\n{json.dumps(MOCK_VALID_GROQ_INSIGHTS)}\n```"
    transport = httpx.MockTransport(lambda req: make_mock_groq_response(fenced_content))

    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        evidence = create_sample_evidence()
        report = await provider.generate_insights(evidence)
        assert report.provider_name == "GROQ"
        assert report.is_simulated is False


# ===========================================================================
# 2. Missing Credentials Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_groq_missing_credentials_raises_error_without_network(monkeypatch):
    """
    Verifies that missing or empty credentials raise AIProviderError immediately
    without calling the network and without falling back silently to demo.
    """
    monkeypatch.setattr(settings, "GROQ_API_KEY", None)

    call_count = 0

    def mock_handler(req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return make_mock_groq_response("{}")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        # 1. None key
        provider_none = GroqAIProvider(api_key=None, http_client=client)
        with pytest.raises(AIProviderError) as exc_info:
            await provider_none.generate_insights(create_sample_evidence())
        assert "Groq API key is not configured" in str(exc_info.value)
        assert call_count == 0

        # 2. Empty string key
        provider_empty = GroqAIProvider(api_key="   ", http_client=client)
        with pytest.raises(AIProviderError) as exc_info2:
            await provider_empty.generate_insights(create_sample_evidence())
        assert "Groq API key is not configured" in str(exc_info2.value)
        assert call_count == 0

        # 3. Placeholder 'demo' key
        provider_demo = GroqAIProvider(api_key="demo", http_client=client)
        with pytest.raises(AIProviderError):
            await provider_demo.generate_insights(create_sample_evidence())
        assert call_count == 0


# ===========================================================================
# 3. Malformed JSON and Schema Invalidation Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_groq_malformed_non_json_raises_error():
    """Verifies that non-JSON output raises AIMalformedOutputError."""
    transport = httpx.MockTransport(
        lambda req: make_mock_groq_response("I am unable to analyze this portfolio as requested.")
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        with pytest.raises(AIMalformedOutputError) as exc_info:
            await provider.generate_insights(create_sample_evidence())
        assert "not valid JSON" in str(exc_info.value)


@pytest.mark.asyncio
async def test_groq_schema_invalid_missing_fields_raises_error():
    """Verifies that missing mandatory fields in the JSON raises AIMalformedOutputError."""
    # Missing executive_summary and confidence
    bad_dict = {"key_drivers": [], "risk_alerts": []}
    transport = httpx.MockTransport(
        lambda req: make_mock_groq_response(json.dumps(bad_dict))
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        with pytest.raises(AIMalformedOutputError) as exc_info:
            await provider.generate_insights(create_sample_evidence())
        assert "schema" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_groq_risk_driver_type_parsed_successfully():
    """
    Regression test: Verifies that when Groq produces a key driver with
    driver_type='RISK', the response is parsed cleanly into an AIInsightReport
    and successfully validates without schema errors.
    """
    payload_with_risk_driver = dict(MOCK_VALID_GROQ_INSIGHTS)
    payload_with_risk_driver["key_drivers"] = [
        {
            "driver_id": "driver-risk-1",
            "driver_type": "RISK",
            "title": "Composite Portfolio Risk Score",
            "statement": "Portfolio composite risk score is evaluated at 42.00.",
            "supporting_metric_key": "risk_assessment.composite_risk_score",
            "supporting_metric_value": 42.00,
            "source_reference": "analytics.risk_assessment",
            "is_grounded": True,
        }
    ]
    transport = httpx.MockTransport(
        lambda req: make_mock_groq_response(json.dumps(payload_with_risk_driver))
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        evidence = create_sample_evidence()
        report = await provider.generate_insights(evidence)

        assert isinstance(report, AIInsightReport)
        assert len(report.key_drivers) == 1
        assert report.key_drivers[0].driver_type == DriverType.RISK
        assert report.key_drivers[0].driver_id == "driver-risk-1"

        # Verify grounding validation runs cleanly
        validator = ClaimGroundingValidator()
        validated = validator.validate_report(report, evidence)
        assert validated.grounding_report.is_acceptable is True
        assert validated.review_status == ReviewStatus.VERIFIED


@pytest.mark.asyncio
async def test_groq_arbitrary_unallowlisted_driver_type_rejected():
    """
    Verifies that arbitrary, unallowlisted driver types are still strictly
    rejected with AIMalformedOutputError, preventing schema weakening.
    """
    bad_payload = dict(MOCK_VALID_GROQ_INSIGHTS)
    bad_payload["key_drivers"] = [
        {
            "driver_id": "driver-bad-1",
            "driver_type": "UNSUPPORTED_ARBITRARY_TYPE",
            "title": "Unsupported Driver Type",
            "statement": "Some statement.",
            "supporting_metric_key": "concentration.top_holding_weight_percent",
            "supporting_metric_value": 35.00,
            "source_reference": "analytics.concentration",
            "is_grounded": True,
        }
    ]
    transport = httpx.MockTransport(
        lambda req: make_mock_groq_response(json.dumps(bad_payload))
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        with pytest.raises(AIMalformedOutputError) as exc_info:
            await provider.generate_insights(create_sample_evidence())
        assert "schema" in str(exc_info.value).lower()


# ===========================================================================
# 4. HTTP Errors, Rate Limits, and Network Failures
# ===========================================================================

@pytest.mark.asyncio
async def test_groq_http_authentication_error_401():
    """Verifies HTTP 401 returns clear AIProviderError."""
    transport = httpx.MockTransport(
        lambda req: httpx.Response(401, json={"error": {"message": "Invalid API Key"}})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key="bad-key", http_client=client)
        with pytest.raises(AIProviderError) as exc_info:
            await provider.generate_insights(create_sample_evidence())
        assert "authentication failed" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_groq_http_rate_limit_429():
    """Verifies HTTP 429 returns clear AIProviderError."""
    transport = httpx.MockTransport(
        lambda req: httpx.Response(429, json={"error": {"message": "Rate limit exceeded"}})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        with pytest.raises(AIProviderError) as exc_info:
            await provider.generate_insights(create_sample_evidence())
        assert "rate limit exceeded" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_groq_http_server_error_500():
    """Verifies HTTP 500 server error raises AIProviderError."""
    transport = httpx.MockTransport(
        lambda req: httpx.Response(500, text="Internal Server Error")
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        with pytest.raises(AIProviderError) as exc_info:
            await provider.generate_insights(create_sample_evidence())
        assert "service error" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_groq_timeout_and_connection_failure():
    """Verifies network timeouts and connection dropped errors are caught and sanitized."""
    def timeout_handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Connection timed out", request=req)

    transport = httpx.MockTransport(timeout_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        with pytest.raises(AIProviderError) as exc_info:
            await provider.generate_insights(create_sample_evidence())
        assert "network error" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_groq_http_model_not_found_404():
    """Verifies HTTP 404 with structured model_not_found diagnostic is surfaced cleanly."""
    err_body = {
        "error": {
            "message": "The model `openai/gpt-oss-120b` does not exist or you do not have access to it.",
            "type": "invalid_request_error",
            "code": "model_not_found",
        }
    }
    transport = httpx.MockTransport(
        lambda req: httpx.Response(404, json=err_body)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key="mock-key", model="openai/gpt-oss-120b", http_client=client)
        with pytest.raises(AIProviderError) as exc_info:
            await provider.generate_insights(create_sample_evidence())

        err_msg = str(exc_info.value)
        assert "404" in err_msg
        assert "model_not_found" in err_msg
        assert "openai/gpt-oss-120b" in err_msg


@pytest.mark.asyncio
async def test_groq_http_recognized_error_code_404():
    """Verifies that recognized allowlisted error code is included in diagnostic."""
    err_body = {
        "error": {
            "code": "unrecognized_request_url",
            "message": "The path was not found on this service.",
        }
    }
    transport = httpx.MockTransport(
        lambda req: httpx.Response(404, json=err_body)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        with pytest.raises(AIProviderError) as exc_info:
            await provider.generate_insights(create_sample_evidence())

        err_msg = str(exc_info.value)
        assert "404" in err_msg
        assert "code: unrecognized_request_url" in err_msg
        assert "The path was not found" in err_msg


@pytest.mark.asyncio
async def test_groq_http_unknown_error_code_omitted():
    """
    Verifies that unknown or non-allowlisted error codes are omitted and
    fall back to a generic/sanitized diagnostic.
    """
    # 1. Unknown code with no message -> falls back to generic status 404
    err_body_no_msg = {
        "error": {
            "code": "unknown_custom_vendor_code_99",
        }
    }
    transport1 = httpx.MockTransport(
        lambda req: httpx.Response(404, json=err_body_no_msg)
    )
    async with httpx.AsyncClient(transport=transport1) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        with pytest.raises(AIProviderError) as exc_info:
            await provider.generate_insights(create_sample_evidence())
        assert "unknown_custom_vendor_code_99" not in str(exc_info.value)
        assert "Groq returned unexpected HTTP status 404." in str(exc_info.value)

    # 2. Unknown code with safe message -> code omitted, only sanitized message surfaced
    err_body_with_msg = {
        "error": {
            "code": "unknown_custom_vendor_code_99",
            "message": "Resource could not be located.",
        }
    }
    transport2 = httpx.MockTransport(
        lambda req: httpx.Response(404, json=err_body_with_msg)
    )
    async with httpx.AsyncClient(transport=transport2) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        with pytest.raises(AIProviderError) as exc_info2:
            await provider.generate_insights(create_sample_evidence())
        assert "unknown_custom_vendor_code_99" not in str(exc_info2.value)
        assert "Resource could not be located" in str(exc_info2.value)


@pytest.mark.asyncio
async def test_groq_http_malformed_error_code_handled():
    """
    Verifies that non-string or malformed error codes are handled safely
    without unhandled crashes and omitted from output.
    """
    for bad_code in [12345, True, ["code_in_list"], {"nested": "dict"}, "   "]:
        err_body = {
            "error": {
                "code": bad_code,
                "message": "Safe sanitized message",
            }
        }
        transport = httpx.MockTransport(
            lambda req: httpx.Response(404, json=err_body)
        )
        async with httpx.AsyncClient(transport=transport) as client:
            provider = GroqAIProvider(api_key="mock-key", http_client=client)
            with pytest.raises(AIProviderError) as exc_info:
                await provider.generate_insights(create_sample_evidence())
            err_msg = str(exc_info.value)
            assert "12345" not in err_msg
            assert "code_in_list" not in err_msg
            assert "Safe sanitized message" in err_msg


@pytest.mark.asyncio
async def test_groq_http_malformed_body_404():
    """Verifies HTTP 404 with HTML/non-JSON or malformed body falls back to generic status error."""
    # 1. Plain HTML 404
    transport_html = httpx.MockTransport(
        lambda req: httpx.Response(404, text="<html><body>404 Not Found</body></html>")
    )
    async with httpx.AsyncClient(transport=transport_html) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        with pytest.raises(AIProviderError) as exc_info:
            await provider.generate_insights(create_sample_evidence())
        assert "Groq returned unexpected HTTP status 404." in str(exc_info.value)

    # 2. Malformed JSON 404
    transport_malformed = httpx.MockTransport(
        lambda req: httpx.Response(404, text="{not-valid-json}")
    )
    async with httpx.AsyncClient(transport=transport_malformed) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        with pytest.raises(AIProviderError) as exc_info2:
            await provider.generate_insights(create_sample_evidence())
        assert "Groq returned unexpected HTTP status 404." in str(exc_info2.value)


@pytest.mark.asyncio
async def test_groq_exact_request_url_constructed():
    """
    Verifies that GroqAIProvider constructs and requests the exact expected URL:
    https://api.groq.com/openai/v1/chat/completions without duplicated or missing segments.
    """
    captured_urls = []

    def mock_handler(req: httpx.Request) -> httpx.Response:
        captured_urls.append(str(req.url))
        return make_mock_groq_response(json.dumps(MOCK_VALID_GROQ_INSIGHTS))

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        # Standard base URL
        provider = GroqAIProvider(
            api_key="mock-key",
            base_url="https://api.groq.com/openai/v1",
            http_client=client,
        )
        await provider.generate_insights(create_sample_evidence())

        # Base URL with trailing slash (should not cause double slashes)
        provider_trailing = GroqAIProvider(
            api_key="mock-key",
            base_url="https://api.groq.com/openai/v1/",
            http_client=client,
        )
        await provider_trailing.generate_insights(create_sample_evidence())

    assert len(captured_urls) == 2
    assert captured_urls[0] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured_urls[1] == "https://api.groq.com/openai/v1/chat/completions"


# ===========================================================================
# 5. Security & Redaction Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_groq_secret_redaction(caplog):
    """
    Security test: verifies that the raw Groq API key is never logged
    or leaked in error messages.
    """
    secret = "GROQ_SECRET_KEY_123456789"

    def error_handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"Failed connecting to {req.url}", request=req)

    transport = httpx.MockTransport(error_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key=secret, http_client=client)

        caplog.set_level(logging.DEBUG)
        with pytest.raises(AIProviderError) as exc_info:
            await provider.generate_insights(create_sample_evidence())

        # Secret must not be in exception message
        assert secret not in str(exc_info.value)

        # Secret must not be in logged output
        log_text = "\n".join(r.getMessage() for r in caplog.records)
        assert secret not in log_text


@pytest.mark.asyncio
async def test_groq_secret_redaction_in_diagnostics():
    """Verifies that secrets are redacted from any surfaced error diagnostics."""
    secret = "GROQ_SECRET_KEY_123456789"
    gsk_secret = "gsk_abcdef1234567890abcdef123456"
    err_body = {
        "error": {
            "code": "model_not_found",
            "message": f"Auth failed with {secret} and {gsk_secret}",
        }
    }
    transport = httpx.MockTransport(
        lambda req: httpx.Response(404, json=err_body)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key=secret, http_client=client)
        with pytest.raises(AIProviderError) as exc_info:
            await provider.generate_insights(create_sample_evidence())

        err_msg = str(exc_info.value)
        assert secret not in err_msg
        assert gsk_secret not in err_msg
        assert "[REDACTED]" in err_msg


@pytest.mark.asyncio
async def test_groq_secret_redaction_boundary_straddling():
    """
    Regression test (Fix 1): Verifies that credentials straddling the 160-char length
    truncation boundary are sanitized BEFORE truncation so that neither the full
    credential nor any partial credential fragment appears in the surfaced diagnostic.
    """
    secret = "SECRET_API_KEY_1234567890_STRADDLE"
    # Construct message where secret begins at char 141 and ends at char 175,
    # precisely straddling the 157-char truncation boundary
    prefix = "X" * 140
    raw_message = f"{prefix} {secret} {'Y' * 50}"

    err_body = {
        "error": {
            "code": "model_not_found",
            "message": raw_message,
        }
    }
    transport = httpx.MockTransport(
        lambda req: httpx.Response(404, json=err_body)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key=secret, http_client=client)
        with pytest.raises(AIProviderError) as exc_info:
            await provider.generate_insights(create_sample_evidence())

        err_msg = str(exc_info.value)

        # 1. Full secret must NOT appear
        assert secret not in err_msg

        # 2. No partial fragment of secret (e.g. first 5, 10, or 15 chars) must appear
        assert secret[:5] not in err_msg
        assert secret[:10] not in err_msg
        assert secret[:15] not in err_msg
        assert secret[:20] not in err_msg
        assert secret[-10:] not in err_msg

        # 3. Redaction token must appear
        assert "[REDACTED]" in err_msg


# ===========================================================================
# 6. Provider Selection & Safe Defaults Tests
# ===========================================================================

def test_ai_provider_selection_behavior():
    """
    Verifies that resolve_ai_provider strictly preserves demo defaults:
    - Default settings -> DeterministicDemoProvider
    - USE_MOCK_DATA=True with AI_PROVIDER='groq' -> DeterministicDemoProvider (mock policy wins)
    - USE_MOCK_DATA=False with AI_PROVIDER='groq' -> GroqAIProvider
    - USE_MOCK_DATA=False with AI_PROVIDER='demo' -> DeterministicDemoProvider
    """
    # 1. Default settings -> DeterministicDemoProvider
    default_p = resolve_ai_provider()
    assert isinstance(default_p, DeterministicDemoProvider)

    # 2. Mock mode forced -> DeterministicDemoProvider
    mock_forced = Settings(USE_MOCK_DATA=True, AI_PROVIDER="groq", GROQ_API_KEY="test-key")
    p1 = resolve_ai_provider(settings_override=mock_forced)
    assert isinstance(p1, DeterministicDemoProvider)

    # 3. Live Groq requested -> GroqAIProvider
    live_groq = Settings(
        USE_MOCK_DATA=False,
        AI_PROVIDER="groq",
        GROQ_API_KEY="test-key",
        GROQ_MODEL="openai/gpt-oss-120b",
    )
    p2 = resolve_ai_provider(settings_override=live_groq)
    assert isinstance(p2, GroqAIProvider)
    assert p2.api_key == "test-key"
    assert p2.model == "openai/gpt-oss-120b"

    # 4. Live demo requested -> DeterministicDemoProvider
    live_demo = Settings(USE_MOCK_DATA=False, AI_PROVIDER="demo")
    p3 = resolve_ai_provider(settings_override=live_demo)
    assert isinstance(p3, DeterministicDemoProvider)


def test_reasoning_service_resolve_provider_mock_guard(monkeypatch):
    """
    Verifies that AIReasoningService._resolve_provider enforces the mock-mode guard:
    - If USE_MOCK_DATA is True and provider_override='GROQ', raises ValueError.
    - If USE_MOCK_DATA is False and provider_override='GROQ', resolves GroqAIProvider.
    - Preserves demo provider when override is None or 'DEMO'.
    """
    from unittest.mock import MagicMock
    from app.core import config

    mock_session = MagicMock()
    service = AIReasoningService(session=mock_session)

    # 1. USE_MOCK_DATA=True -> provider_override="GROQ" raises ValueError
    monkeypatch.setattr(config.settings, "USE_MOCK_DATA", True)
    with pytest.raises(
        ValueError,
        match="Live AI provider 'GROQ' cannot be selected while USE_MOCK_DATA is true.",
    ):
        service._resolve_provider("GROQ")

    with pytest.raises(
        ValueError,
        match="Live AI provider 'GROQ' cannot be selected while USE_MOCK_DATA is true.",
    ):
        service._resolve_provider("groq")

    # 2. USE_MOCK_DATA=True -> DEMO override succeeds
    demo_p = service._resolve_provider("DEMO")
    assert isinstance(demo_p, DeterministicDemoProvider)

    # 3. None override retains self.provider
    none_p = service._resolve_provider(None)
    assert isinstance(none_p, DeterministicDemoProvider)

    # 4. USE_MOCK_DATA=False -> provider_override="GROQ" constructs GroqAIProvider
    monkeypatch.setattr(config.settings, "USE_MOCK_DATA", False)
    monkeypatch.setattr(config.settings, "GROQ_API_KEY", "mock-test-key")
    monkeypatch.setattr(config.settings, "GROQ_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(config.settings, "GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    resolved = service._resolve_provider("GROQ")
    assert isinstance(resolved, GroqAIProvider)
    assert resolved.api_key == "mock-test-key"
    assert resolved.model == "openai/gpt-oss-120b"
    assert resolved.base_url == "https://api.groq.com/openai/v1"


# ===========================================================================
# 7. Compatibility with ClaimGroundingValidator & AIReasoningService
# ===========================================================================

@pytest.mark.asyncio
async def test_groq_grounding_validation_integration():
    """
    Verifies that GroqAIProvider output passes through ClaimGroundingValidator cleanly.
    """
    content_json = json.dumps(MOCK_VALID_GROQ_INSIGHTS)
    transport = httpx.MockTransport(lambda req: make_mock_groq_response(content_json))

    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        evidence = create_sample_evidence()

        raw_report = await provider.generate_insights(evidence)
        assert raw_report.review_status == ReviewStatus.PENDING_REVIEW

        validator = ClaimGroundingValidator()
        validated = validator.validate_report(raw_report, evidence)

        # Grounding validator should pass the grounded report
        assert validated.grounding_report.is_acceptable is True
        assert validated.review_status == ReviewStatus.VERIFIED


@pytest.mark.asyncio
async def test_groq_unsupported_claims_flagged_by_grounding_validator():
    """
    Verifies that if Groq hallucinates a fake stock symbol or non-existent metric,
    the ClaimGroundingValidator catches it and marks the report REJECTED.
    """
    hallucinated_dict = dict(MOCK_VALID_GROQ_INSIGHTS)
    hallucinated_dict["key_drivers"] = [
        {
            "driver_id": "driver-hallucinated-1",
            "driver_type": "CONCENTRATION",
            "title": "Exposure to RELIANCE",
            "statement": "Portfolio has heavy exposure to RELIANCE.",
            "supporting_metric_key": "concentration.top_holding_weight_percent",
            "supporting_metric_value": 99.0,
            "source_reference": "analytics.unknown",
            "is_grounded": True,
        }
    ]
    hallucinated_dict["review_cards"] = [
        {
            "card_id": "card-fake-1",
            "category": "CONCENTRATION",
            "severity": "CRITICAL",
            "title": "Reliance Allocation",
            "description": "Huge stake in RELIANCE",
            "cited_metrics": {"concentration.top_holding_weight_percent": 99.0},
            "related_symbols": ["RELIANCE"],
            "review_status": "PENDING_REVIEW",
        }
    ]


    transport = httpx.MockTransport(
        lambda req: make_mock_groq_response(json.dumps(hallucinated_dict))
    )

    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        evidence = create_sample_evidence()  # Portfolio only has TCS, not FAKE_CORP

        raw_report = await provider.generate_insights(evidence)
        validator = ClaimGroundingValidator()
        validated = validator.validate_report(raw_report, evidence)

        # Must be rejected because FAKE_CORP is not in portfolio evidence
        assert validated.review_status == ReviewStatus.REJECTED
        assert validated.grounding_report.is_acceptable is False
        assert validated.grounding_report.rejected_count >= 1


@pytest.mark.asyncio
async def test_groq_user_prompt_formats_news_allowed_source_reference():
    """Verify that _build_user_prompt generates explicit allowed_source_reference and strict news rules."""
    provider = GroqAIProvider(api_key="mock-key")
    evidence = create_sample_evidence()
    evidence.news_articles = [
        NewsArticle(
            id="news-1",
            title="TCS Signs Major Cloud Deal",
            summary="Multi-year IT contract.",
            related_symbols=["TCS"],
        ),
        NewsArticle(
            id="news-2",
            title="Macro Economic Market Trends",
            summary="Broad market indicators update.",
            related_symbols=[],
        ),
    ]

    prompt = provider._build_user_prompt(evidence)

    # Verify news headline structure in JSON
    assert '"allowed_source_reference": "news.TCS"' in prompt
    assert '"allowed_source_reference": "news.MARKET"' in prompt
    # Verify strict guidance is present
    assert "NEVER invent source references such as 'news.simulated'" in prompt
    assert "supporting_metric_key MUST be 'news.title'" in prompt
    assert "not statistically calibrated" in prompt


@pytest.mark.asyncio
async def test_groq_news_simulated_rejected_by_grounding():
    """Verify that if Groq returns news.simulated, ClaimGroundingValidator rejects the report."""
    simulated_news_dict = dict(MOCK_VALID_GROQ_INSIGHTS)
    simulated_news_dict["key_drivers"] = [
        {
            "driver_id": "driver-news-sim",
            "driver_type": "NEWS",
            "title": "Simulated Market Update",
            "statement": "Simulated news update reported positive earnings trends.",
            "supporting_metric_key": "news.title",
            "supporting_metric_value": "TCS Signs Major Cloud Deal",
            "source_reference": "news.simulated",
            "is_grounded": True,
        }
    ]

    transport = httpx.MockTransport(
        lambda req: make_mock_groq_response(json.dumps(simulated_news_dict))
    )

    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        evidence = create_sample_evidence()
        evidence.news_articles = [
            NewsArticle(
                id="news-1",
                title="TCS Signs Major Cloud Deal",
                summary="Multi-year IT contract.",
                related_symbols=["TCS"],
            )
        ]

        raw_report = await provider.generate_insights(evidence)
        validator = ClaimGroundingValidator()
        validated = validator.validate_report(raw_report, evidence)

        assert validated.review_status == ReviewStatus.REJECTED
        assert validated.grounding_report.is_acceptable is False
        assert any(
            f.target_id == "driver-news-sim"
            and f.status == FindingStatus.REJECTED
            and f.details.get("unsupported_symbol") == "SIMULATED"
            for f in validated.grounding_report.findings
        )


@pytest.mark.asyncio
async def test_groq_valid_grounded_news_passes_grounding():
    """Verify that a valid Groq response citing allowed news.TCS passes grounding validation."""
    valid_news_dict = dict(MOCK_VALID_GROQ_INSIGHTS)
    valid_news_dict["key_drivers"] = [
        {
            "driver_id": "driver-news-valid",
            "driver_type": "NEWS",
            "title": "TCS Cloud Contract",
            "statement": "TCS announced a major multi-year cloud infrastructure contract.",
            "supporting_metric_key": "news.title",
            "supporting_metric_value": "TCS Signs Major Cloud Deal",
            "source_reference": "news.TCS",
            "is_grounded": True,
        }
    ]

    transport = httpx.MockTransport(
        lambda req: make_mock_groq_response(json.dumps(valid_news_dict))
    )

    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqAIProvider(api_key="mock-key", http_client=client)
        evidence = create_sample_evidence()
        evidence.news_articles = [
            NewsArticle(
                id="news-1",
                title="TCS Signs Major Cloud Deal",
                summary="Multi-year IT contract.",
                related_symbols=["TCS"],
            )
        ]

        raw_report = await provider.generate_insights(evidence)
        validator = ClaimGroundingValidator()
        validated = validator.validate_report(raw_report, evidence)

        assert validated.review_status == ReviewStatus.VERIFIED
        assert validated.grounding_report.is_acceptable is True
        driver = next(d for d in validated.key_drivers if d.driver_id == "driver-news-valid")
        assert driver.is_grounded is True
