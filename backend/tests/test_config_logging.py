import logging
import pytest
from httpx import AsyncClient
from app.core.config import Settings
from app.core.logging import SENSITIVE_HEADERS, SENSITIVE_QUERY_PARAMS

def test_cors_origins_parsing_json_array():
    """Verifies that CORS_ORIGINS parses valid JSON array strings."""
    parsed = Settings.parse_cors_origins('["http://localhost:5173", "http://127.0.0.1:5173"]')
    assert parsed == ["http://localhost:5173", "http://127.0.0.1:5173"]

def test_cors_origins_parsing_comma_separated():
    """Verifies that CORS_ORIGINS parses comma-separated origin strings."""
    parsed = Settings.parse_cors_origins("http://localhost:3000, http://127.0.0.1:3000")
    assert parsed == ["http://localhost:3000", "http://127.0.0.1:3000"]

def test_cors_origins_parsing_list_input():
    """Verifies that CORS_ORIGINS handles raw list inputs cleanly."""
    raw_list = ["http://frontend.local:5173", "http://dashboard.local:5173"]
    parsed = Settings.parse_cors_origins(raw_list)
    assert parsed == raw_list

def test_cors_origins_fallback_on_empty():
    """Verifies that CORS_ORIGINS falls back to safe default origins on None/empty inputs."""
    parsed = Settings.parse_cors_origins(None)
    assert len(parsed) >= 2
    assert "http://localhost:5173" in parsed

def test_isolated_settings_defaults():
    """Verifies default settings configuration on an isolated Settings instance."""
    # Create isolated settings bypassing local .env file
    settings_obj = Settings(_env_file=None)
    assert settings_obj.ENVIRONMENT == "development"
    assert settings_obj.DEBUG is True
    assert settings_obj.APP_HOST == "127.0.0.1"
    assert settings_obj.APP_PORT == 8000
    assert settings_obj.USE_MOCK_DATA is True
    assert "sqlite+aiosqlite" in settings_obj.DATABASE_URL
    # Alpha Vantage defaults
    assert settings_obj.ALPHA_VANTAGE_API_KEY is None
    assert settings_obj.ALPHA_VANTAGE_BASE_URL == "https://www.alphavantage.co/query"
    assert settings_obj.MARKET_DATA_PROVIDER == "demo"
    # Groq defaults
    assert settings_obj.GROQ_API_KEY is None
    assert settings_obj.GROQ_MODEL == "openai/gpt-oss-120b"
    assert settings_obj.GROQ_BASE_URL == "https://api.groq.com/openai/v1"
    assert settings_obj.AI_PROVIDER == "demo"

def test_custom_provider_settings_isolated():
    """Verifies that provider settings can be configured via environment or arguments."""
    custom_settings = Settings(
        _env_file=None,
        ALPHA_VANTAGE_API_KEY="mock-alpha-key",
        MARKET_DATA_PROVIDER="alpha_vantage",
        GROQ_API_KEY="mock-groq-key",
        GROQ_MODEL="llama-3.1-8b-instant",
        AI_PROVIDER="groq",
    )
    assert custom_settings.ALPHA_VANTAGE_API_KEY == "mock-alpha-key"
    assert custom_settings.MARKET_DATA_PROVIDER == "alpha_vantage"
    assert custom_settings.GROQ_API_KEY == "mock-groq-key"
    assert custom_settings.GROQ_MODEL == "llama-3.1-8b-instant"
    assert custom_settings.AI_PROVIDER == "groq"

def test_sensitive_keys_definitions():
    """Verifies that sensitive headers and query parameters sets contain critical security keys."""
    assert "authorization" in SENSITIVE_HEADERS
    assert "cookie" in SENSITIVE_HEADERS
    assert "x-api-key" in SENSITIVE_HEADERS

    assert "token" in SENSITIVE_QUERY_PARAMS
    assert "key" in SENSITIVE_QUERY_PARAMS
    assert "secret" in SENSITIVE_QUERY_PARAMS
    assert "password" in SENSITIVE_QUERY_PARAMS

@pytest.mark.asyncio
async def test_logging_query_redaction_in_captured_logs(client: AsyncClient, caplog):
    """
    Verifies that requests with sensitive query keys (token, key, secret)
    have their values redacted in actual captured logger output.
    """
    caplog.set_level(logging.INFO, logger="zerodha_backend")

    response = await client.get("/api/v1/health?token=secret_token_value&key=secret_api_key&safe_param=visible_data")
    assert response.status_code == 200

    backend_logs = [r.getMessage() for r in caplog.records if r.name == "zerodha_backend"]
    log_text = "\n".join(backend_logs)

    # Sensitive values must be masked in backend logs
    assert "token=[REDACTED]" in log_text
    assert "key=[REDACTED]" in log_text

    # Raw secrets must never appear in the backend logger output
    assert "secret_token_value" not in log_text
    assert "secret_api_key" not in log_text

    # Non-sensitive query parameters must remain intact
    assert "safe_param=visible_data" in log_text
