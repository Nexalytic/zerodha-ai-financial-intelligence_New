from typing import AsyncGenerator
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.main import app

@pytest.mark.asyncio
async def test_health_success(client: AsyncClient):
    """Verifies that GET /api/v1/health returns HTTP 200 with healthy database details."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["environment"] == "development"
    assert data["database"]["status"] == "connected"
    assert data["database"]["engine"] == "sqlite"
    assert data["database"]["foreign_keys_enabled"] is True
    assert data["database"]["journal_mode"] == "wal"

@pytest.mark.asyncio
async def test_health_database_failure(client: AsyncClient):
    """
    Verifies that GET /api/v1/health returns HTTP 503 and unhealthy status
    when the database connection fails.
    """
    class FailingSession:
        async def execute(self, *args, **kwargs):
            raise ConnectionError("Simulated database connection failure")

    async def failing_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield FailingSession()

    app.dependency_overrides[get_db] = failing_get_db
    try:
        response = await client.get("/api/v1/health")
        assert response.status_code == 503

        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"]["status"] == "disconnected"
        assert "error" in data["database"]
    finally:
        # Restore normal client fixture dependency override
        app.dependency_overrides.pop(get_db, None)

@pytest.mark.asyncio
async def test_cors_preflight(client: AsyncClient):
    """
    Verifies that CORS preflight requests from an approved origin succeed
    and enforce allow_credentials=False.
    """
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Content-Type",
    }
    response = await client.options("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") is None

@pytest.mark.asyncio
async def test_cors_disallowed_origin(client: AsyncClient):
    """Verifies that CORS preflight from an unauthorized origin does not return CORS allow headers."""
    headers = {
        "Origin": "http://malicious-external-site.com",
        "Access-Control-Request-Method": "GET",
    }
    response = await client.options("/api/v1/health", headers=headers)
    assert response.headers.get("access-control-allow-origin") is None

@pytest.mark.asyncio
async def test_standard_404_envelope(client: AsyncClient):
    """Verifies that non-existent routes return a sanitized 404 error envelope."""
    response = await client.get("/api/v1/nonexistent-route")
    assert response.status_code == 404

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"
    assert "Resource not found" in data["error"]["message"] or "Not Found" in data["error"]["message"]
    assert "timestamp" in data

@pytest.mark.asyncio
async def test_sqlite_pragmas_active(test_db_setup):
    """Directly verifies that WAL mode and Foreign Keys are active on the SQLite connection."""
    session_factory, _ = test_db_setup
    async with session_factory() as session:
        fk_result = await session.execute(text("PRAGMA foreign_keys;"))
        fk_enabled = fk_result.scalar()
        assert fk_enabled == 1, "Foreign keys PRAGMA was not enabled"

        jm_result = await session.execute(text("PRAGMA journal_mode;"))
        journal_mode = str(jm_result.scalar()).lower()
        assert journal_mode == "wal", f"Journal mode expected 'wal', got '{journal_mode}'"
