import asyncio
import io
import logging
import re
import sys
from typing import Any, Dict
import httpx
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.logging import (
    SENSITIVE_HEADERS,
    SENSITIVE_QUERY_PARAMS,
    RequestLoggingMiddleware,
    logger,
    sanitize_log_message,
)
from app.mcp.audit import (
    SENSITIVE_KEYS,
    _SENSITIVE_STRING_PATTERN,
    _audit_logger,
    audit_tool_call,
    clear_audit_records,
    get_audit_records,
    sanitize_argument_value,
    sanitize_arguments,
)
from app.mcp.schemas import (
    APPROVED_TOOLS,
    GetPortfolioArgs,
    MCPErrorCode,
    SearchNewsArgs,
)
from app.mcp.server import create_mcp_server
from app.providers.alpha_vantage_market_data import AlphaVantageMarketDataProvider
from app.services.ai.providers.groq_provider import GroqAIProvider


# ===========================================================================
# Part B: Secret Redaction Tests
# ===========================================================================

def test_sanitize_log_message_redacts_explicit_secrets():
    """
    Verifies that sanitize_log_message replaces explicitly passed secret tokens
    with [REDACTED].
    """
    secret = "demo_secret_token_xyz987"
    raw = f"Error communicating with provider using key {secret} at endpoint"
    sanitized = sanitize_log_message(raw, secret=secret)

    assert secret not in sanitized
    assert "[REDACTED]" in sanitized
    assert "Error communicating with provider using key [REDACTED] at endpoint" == sanitized


def test_sanitize_log_message_redacts_sensitive_query_parameters():
    """
    Verifies that sanitize_log_message regex catches and redacts sensitive query
    parameter patterns: apikey, api_key, key, token, secret, password, auth.
    """
    test_urls = [
        ("https://api.example.com/v1?api_key=mySecretKey123&format=json", "api_key=[REDACTED]"),
        ("https://api.example.com/v1?apikey=anotherSecret456&limit=10", "apikey=[REDACTED]"),
        ("https://api.example.com/data?token=jwtToken789&user=analyst", "token=[REDACTED]"),
        ("https://api.example.com/auth?secret=topSecretPass&env=prod", "secret=[REDACTED]"),
        ("https://api.example.com/login?password=pass1234&user=admin", "password=[REDACTED]"),
        ("https://api.example.com/check?auth=bearerTokenXYZ", "auth=[REDACTED]"),
        ("https://api.example.com/data?key=alphanumericKey99", "key=[REDACTED]"),
    ]

    for raw_url, expected_substr in test_urls:
        sanitized = sanitize_log_message(raw_url)
        assert expected_substr in sanitized, f"Failed for {raw_url}"
        assert "mySecretKey123" not in sanitized
        assert "anotherSecret456" not in sanitized
        assert "jwtToken789" not in sanitized
        assert "topSecretPass" not in sanitized
        assert "pass1234" not in sanitized


def test_sanitize_log_message_handles_edge_cases():
    """
    Verifies edge case resilience:
    - Empty strings return empty string.
    - None or falsy message returns empty string.
    - Short secret (< 3 chars) is not replaced everywhere to avoid corrupting text.
    - Multiline diagnostic strings with newlines are properly redacted.
    """
    assert sanitize_log_message("") == ""
    assert sanitize_log_message(None) == ""

    # Short secret guard (< 3 chars)
    short_secret = "ab"
    text = "about the absolute path ab"
    # Should not replace 'ab' within 'about' or 'absolute'
    sanitized_short = sanitize_log_message(text, secret=short_secret)
    assert sanitized_short == text

    # Multiline diagnostic
    multiline = (
        "Traceback (most recent call last):\n"
        "  File 'provider.py', line 42, in connect\n"
        "  httpx.HTTPError: Failed to connect with api_key=superSecretLine1\n"
        "Additional context: token=superSecretLine2"
    )
    sanitized_multi = sanitize_log_message(multiline)
    assert "superSecretLine1" not in sanitized_multi
    assert "superSecretLine2" not in sanitized_multi
    assert "api_key=[REDACTED]" in sanitized_multi
    assert "token=[REDACTED]" in sanitized_multi


def test_groq_provider_sanitizer_redacts_gsk_and_bearer_tokens():
    """
    Verifies that GroqAIProvider._sanitize redacts:
    1. Generic query parameter secrets.
    2. Explicit Groq API key (gsk_...).
    3. Bearer authorization header values.
    """
    fake_key = "gsk_testKEY1234567890abcdefghijklmnopqrstuvwxyz"
    provider = GroqAIProvider(api_key=fake_key)

    # 1. GSK token embedded in raw error
    msg1 = f"Failed Groq request with key {fake_key} to endpoint"
    sanitized1 = provider._sanitize(msg1)
    assert fake_key not in sanitized1
    assert "[REDACTED]" in sanitized1

    # 2. Bearer token format
    bearer_msg = "Headers: {'Authorization': 'Bearer gsk_99999999999999999999999999'}"
    sanitized2 = provider._sanitize(bearer_msg)
    assert "Bearer [REDACTED]" in sanitized2
    assert "gsk_9999999999" not in sanitized2

    # 3. Arbitrary Bearer token
    custom_bearer = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz"
    sanitized3 = provider._sanitize(custom_bearer)
    assert "Bearer [REDACTED]" in sanitized3


def test_alpha_vantage_provider_sanitizer_redacts_api_key_and_urls():
    """
    Verifies that AlphaVantageMarketDataProvider._sanitize masks the configured
    API key and sensitive query parameters in URL strings.
    """
    test_key = "AV_SECRET_KEY_12345678"
    provider = AlphaVantageMarketDataProvider(api_key=test_key)

    raw_diagnostic = f"Request to https://www.alphavantage.co/query?function=GLOBAL_QUOTE&apikey={test_key} failed"
    sanitized = provider._sanitize(raw_diagnostic)

    assert test_key not in sanitized
    assert "apikey=[REDACTED]" in sanitized


def test_mcp_audit_sanitizer_redacts_sensitive_keys_and_embedded_tokens():
    """
    Verifies that app.mcp.audit.sanitize_arguments:
    1. Masks dictionary entries matching SENSITIVE_KEYS.
    2. Redacts embedded Bearer tokens and sensitive regex patterns in string values.
    """
    raw_args = {
        "portfolio_id": "port-001",
        "api_key": "raw_secret_key_to_mask",
        "auth_token": "token_12345",
        "notes": "User provided Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test for sync",
        "nested": {
            "password": "secretPassword123",
            "normal_field": "safe_value",
        },
    }

    sanitized = sanitize_arguments(raw_args)

    assert sanitized["portfolio_id"] == "port-001"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["auth_token"] == "[REDACTED]"
    assert sanitized["nested"]["password"] == "[REDACTED]"
    assert sanitized["nested"]["normal_field"] == "safe_value"
    # Embedded Bearer token pattern is completely redacted
    assert "[REDACTED]" in sanitized["notes"]
    assert "eyJhbGciOi" not in sanitized["notes"]


def test_mcp_audit_sanitizer_truncates_large_payloads_and_lists():
    """
    Verifies that MCP audit arguments avoid logging massive payloads:
    - Lists with more than 10 items are summarized to first 5 items + count notice.
    - Strings exceeding 200 characters are safely truncated.
    """
    large_list = [f"item_{i}" for i in range(25)]
    sanitized_list = sanitize_argument_value(large_list)

    assert len(sanitized_list) == 6
    assert sanitized_list[0] == "item_0"
    assert sanitized_list[4] == "item_4"
    assert "... (20 more items)" in sanitized_list[5]

    long_str = "A" * 350
    sanitized_str = sanitize_argument_value(long_str)
    assert len(sanitized_str) < 250
    assert "... [truncated]" in sanitized_str


# ===========================================================================
# Part C: Privacy-Safe Diagnostic Logging
# ===========================================================================

@pytest.mark.asyncio
async def test_request_logging_middleware_redacts_sensitive_query_params(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
):
    """
    Verifies that RequestLoggingMiddleware replaces sensitive query parameters
    (e.g., token, key, secret) with [REDACTED] in incoming request logging,
    while leaving non-sensitive parameters (e.g., symbols, limit) intact.
    Captures emitted logs using caplog to assert redaction in actual log output.
    """
    secret_token = "superSecretToken99"
    secret_key = "syntheticSecretKey42"

    with caplog.at_level(logging.INFO):
        res = await client.get(
            f"/api/v1/health?token={secret_token}&key={secret_key}&service=market_data"
        )
    assert res.status_code == 200

    # Ensure sensitive credentials do not appear in emitted logs
    assert secret_token not in caplog.text
    assert secret_key not in caplog.text

    # Ensure redaction markers are present in incoming request log
    assert "token=[REDACTED]" in caplog.text
    assert "key=[REDACTED]" in caplog.text

    # Ensure non-sensitive query values remain visible
    assert "service=market_data" in caplog.text
    assert "Incoming GET /api/v1/health" in caplog.text

    # Ensure SENSITIVE_QUERY_PARAMS set includes the standard sensitive names
    expected_sensitive = {"key", "token", "secret", "password", "api_key", "apikey", "auth"}
    assert expected_sensitive.issubset(SENSITIVE_QUERY_PARAMS)


def test_sensitive_headers_constant_contains_standard_auth_headers():
    """
    Verifies that SENSITIVE_HEADERS contains authorization, cookie, x-api-key.
    """
    assert "authorization" in SENSITIVE_HEADERS
    assert "cookie" in SENSITIVE_HEADERS
    assert "x-api-key" in SENSITIVE_HEADERS
    assert "proxy-authorization" in SENSITIVE_HEADERS


@pytest.mark.asyncio
async def test_client_facing_404_error_omits_database_details(client: AsyncClient):
    """
    Verifies that 404 responses for nonexistent resources:
    1. Use the standardized ErrorEnvelope format.
    2. Omit database query text, table names, or internal stack traces.
    """
    res = await client.get("/api/v1/portfolios/00000000-0000-0000-0000-000000000999")
    assert res.status_code == 404

    data = res.json()
    assert data["success"] is False
    assert "error" in data
    assert data["error"]["code"] == "PORTFOLIO_NOT_FOUND"
    assert "traceback" not in str(data).lower()
    assert "sqlite" not in str(data).lower()
    assert "select" not in str(data).lower()


@pytest.mark.asyncio
async def test_client_facing_422_error_omits_internal_filesystem_paths(client: AsyncClient):
    """
    Verifies that 422 validation errors:
    1. Use the standardized ErrorEnvelope format with details list.
    2. Omit internal server filesystem paths (e.g. C:\\Users\\... or /app/...).
    """
    res = await client.post(
        "/api/v1/portfolios",
        json={"name": "Test", "holdings": [{"symbol": "INVALID$$$SYMBOL"}]},
    )
    assert res.status_code == 422

    data = res.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
    body_str = str(data)
    assert "c:\\" not in body_str.lower()
    assert "/backend/app/" not in body_str.lower()


@pytest.mark.asyncio
async def test_unhandled_exception_returns_clean_500_envelope(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
):
    """
    Verifies that when an unexpected server exception occurs, the system:
    1. Returns HTTP 500 with a clean, standardized ErrorEnvelope.
    2. Completely omits tracebacks, internal filesystem paths, database details,
       or synthetic secrets from the client response.
    3. Emits sanitized server logs where raw secrets are replaced with [REDACTED],
       while preserving diagnostic error summaries.
    """
    from app.main import app

    test_route_path = "/api/v1/test-controlled-failure"
    synthetic_secret = "SYNTHETIC_TEST_TOKEN_500_CRASH"

    @app.get(test_route_path)
    async def _failing_route():
        raise RuntimeError(
            f"Unexpected database failure connecting to /var/data/secret.db with apikey={synthetic_secret}"
        )

    try:
        with caplog.at_level(logging.INFO):
            res = await client.get(test_route_path)

        # 1. Assert HTTP 500 status and structured envelope
        assert res.status_code == 500
        data = res.json()
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert data["error"]["message"] == "An unexpected internal server error occurred."
        assert "timestamp" in data

        # 2. Assert client response completely omits internal stack traces, paths, or secrets
        body_str = str(data).lower()
        assert "traceback" not in body_str
        assert "secret.db" not in body_str
        assert synthetic_secret.lower() not in body_str
        assert "runtimeerror" not in body_str

        # 3. Assert captured server logs do NOT contain the raw synthetic secret
        assert synthetic_secret not in caplog.text

        # 4. Assert captured server logs contain the sanitized marker
        assert "apikey=[REDACTED]" in caplog.text

        # 5. Assert useful sanitized diagnostic logging remains available
        assert (
            "Unhandled error in GET" in caplog.text
            or "Unhandled server error on GET" in caplog.text
        )
    finally:
        app.routes[:] = [r for r in app.routes if getattr(r, "path", None) != test_route_path]


def test_groq_error_extraction_bounds_length_and_sanitizes():
    """
    Verifies that GroqAIProvider._extract_error_detail:
    1. Bounds error message length to <= 160 characters.
    2. Sanitizes messages to prevent leaking credentials.
    3. Strictly checks error codes against an allowlist.
    """
    secret = "gsk_sensitiveKeyToHide1234567890"
    raw_long_msg = f"Model overloaded during request with {secret}. " + ("Extra details " * 20)

    # 1. Recognized code from RECOGNIZED_ERROR_CODES allowlist
    mock_response = httpx.Response(
        status_code=404,
        json={"error": {"code": "model_not_found", "message": raw_long_msg}},
        request=httpx.Request("POST", "https://api.groq.com"),
    )

    provider = GroqAIProvider(api_key=secret)
    code, msg = provider._extract_error_detail(mock_response)

    assert code == "model_not_found"
    assert secret not in msg
    assert len(msg) <= 160
    assert "[REDACTED]" in msg

    # 2. Unrecognized code is safely filtered to None
    mock_unrecognized = httpx.Response(
        status_code=400,
        json={"error": {"code": "arbitrary_external_code_123", "message": "Standard error"}},
        request=httpx.Request("POST", "https://api.groq.com"),
    )
    unrec_code, unrec_msg = provider._extract_error_detail(mock_unrecognized)
    assert unrec_code is None
    assert unrec_msg == "Standard error"


# ===========================================================================
# Part D: Authorization and Data Isolation Boundaries
# ===========================================================================

@pytest.mark.asyncio
async def test_portfolio_retrieval_unknown_id_returns_clean_404(client: AsyncClient):
    """
    Verifies that unknown portfolio identifiers return clean 404 responses
    across all portfolio sub-resources (details, analytics, insights).
    """
    unknown_id = "11111111-1111-1111-1111-111111111111"

    # 1. Portfolio details
    res1 = await client.get(f"/api/v1/portfolios/{unknown_id}")
    assert res1.status_code == 404
    assert res1.json()["error"]["code"] == "PORTFOLIO_NOT_FOUND"

    # 2. Analytics
    res2 = await client.get(f"/api/v1/portfolios/{unknown_id}/analytics")
    assert res2.status_code == 404
    assert res2.json()["error"]["code"] == "PORTFOLIO_NOT_FOUND"

    # 3. AI Insights
    res3 = await client.post(f"/api/v1/portfolios/{unknown_id}/ai-insights")
    assert res3.status_code == 404
    assert res3.json()["error"]["code"] == "PORTFOLIO_NOT_FOUND"


@pytest.mark.asyncio
async def test_portfolio_sql_injection_fragments_handled_by_parameterized_orm(client: AsyncClient):
    """
    Verifies that SQL injection fragments in portfolio route parameters
    do not cause unhandled crashes or SQL syntax errors, returning clean 404s.
    """
    sql_payloads = [
        "' OR 1=1 --",
        "admin'--",
        "00000000-0000-0000-0000-000000000001' UNION SELECT 1,2,3--",
    ]

    for payload in sql_payloads:
        res = await client.get(f"/api/v1/portfolios/{payload}")
        assert res.status_code in (404, 422)
        data = res.json()
        assert data["success"] is False
        assert "syntax error" not in str(data).lower()
        assert "operationalerror" not in str(data).lower()


def test_single_tenant_prototype_architecture_invariants():
    """
    Explicitly documents and asserts single-tenant prototype architecture invariants:
    - Portfolio model does not have a user_id or multi-tenant partition key.
    - System relies on local SQLite database with zero-cost demo defaults.
    - No JWT authentication or multi-user access control is claimed.
    """
    from app.models.portfolio import Portfolio
    # Model fields: id, name, description, is_sample, created_at, updated_at, holdings
    column_names = {c.name for c in Portfolio.__table__.columns}
    assert "user_id" not in column_names
    assert "tenant_id" not in column_names
    assert "id" in column_names
    assert "name" in column_names


# ===========================================================================
# Part E: MCP Security and Privacy
# ===========================================================================

def test_mcp_approved_tools_strictly_read_only_and_whitelist_enforced():
    """
    Verifies that MCP server exposes exactly the 8 approved read-only tools
    and that no order execution, account mutation, or file write tools exist.
    """
    server = create_mcp_server()
    registered_tools = set(server._tool_manager._tools.keys())

    # Exactly 8 approved tools
    assert len(registered_tools) == 8
    assert registered_tools == APPROVED_TOOLS

    # Confirm dangerous / mutating operations are absent
    forbidden_tool_names = {
        "place_order",
        "execute_trade",
        "buy_stock",
        "sell_stock",
        "modify_holding",
        "delete_portfolio",
        "create_portfolio",
        "execute_command",
        "write_file",
        "read_file",
    }
    assert registered_tools.isdisjoint(forbidden_tool_names)


def test_mcp_rejects_extra_unexpected_arguments():
    """
    Verifies that MCP tool argument models enforce extra='forbid',
    strictly rejecting unexpected inputs at schema boundary.
    """
    # 1. GetPortfolioArgs forbids extra
    with pytest.raises(Exception):
        GetPortfolioArgs(portfolio_id="port-01", unexpected_field="malicious_input")

    # 2. SearchNewsArgs forbids extra
    with pytest.raises(Exception):
        SearchNewsArgs(symbols=["RELIANCE"], limit=5, injection_param="bad")


@pytest.mark.asyncio
async def test_mcp_audit_logs_written_exclusively_to_stderr():
    """
    Verifies that MCP audit logger is configured to write exclusively to sys.stderr,
    preserving sys.stdout purity for JSON-RPC MCP messages.
    """
    clear_audit_records()

    # Capture and verify stderr handler on _audit_logger
    assert _audit_logger.propagate is False
    assert len(_audit_logger.handlers) >= 1
    stream_handler = _audit_logger.handlers[0]
    assert isinstance(stream_handler, logging.StreamHandler)
    assert stream_handler.stream == sys.stderr


@pytest.mark.asyncio
async def test_mcp_audit_records_store_sanitized_arguments_and_clean_errors():
    """
    Verifies that audit_tool_call:
    1. Records execution duration, tool_name, and status.
    2. Sanitizes input arguments in stored audit records.
    3. Masks unexpected internal exceptions with a generic message.
    """
    clear_audit_records()

    # Successful call with sensitive argument
    async with audit_tool_call(
        tool_name="get_portfolio",
        arguments={"portfolio_id": "port-sec-01", "api_key": "raw_secret_key"},
    ) as cid:
        pass

    records = get_audit_records()
    assert len(records) == 1
    rec = records[0]
    assert rec.tool_name == "get_portfolio"
    assert rec.status == "SUCCESS"
    assert rec.arguments_sanitized["portfolio_id"] == "port-sec-01"
    assert rec.arguments_sanitized["api_key"] == "[REDACTED]"
    assert rec.duration_ms >= 0.0

    # Error call with unexpected exception (must NOT leak raw stack or paths)
    with pytest.raises(RuntimeError):
        async with audit_tool_call(
            tool_name="score_portfolio_risk",
            arguments={"portfolio_id": "port-sec-02"},
        ):
            raise RuntimeError("Internal database exception at /var/data/secret.db")

    records_after_error = get_audit_records()
    assert len(records_after_error) == 2
    err_rec = records_after_error[1]
    assert err_rec.status == "ERROR"
    assert err_rec.error_code == MCPErrorCode.INTERNAL_ERROR.value
    assert "/var/data" not in err_rec.error_message
    assert "secret.db" not in err_rec.error_message
    assert err_rec.error_message == "An unexpected internal error occurred."
