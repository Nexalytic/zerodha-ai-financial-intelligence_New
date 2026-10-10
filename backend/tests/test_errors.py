import pytest
from fastapi import APIRouter
from httpx import AsyncClient
from app.main import app

# Register isolated test routes on the app dynamically for error testing
error_test_router = APIRouter(prefix="/_test_errors")

@error_test_router.get("/raise-500")
async def _endpoint_raise_500():
    raise RuntimeError("SensitiveDatabasePassword_XYZ123")

@error_test_router.get("/validate-422")
async def _endpoint_validate_422(number: int):
    return {"number": number}

# Include into the test application
app.include_router(error_test_router)

@pytest.mark.asyncio
async def test_validation_422_envelope(client: AsyncClient):
    """
    Verifies that invalid request parameters produce HTTP 422 with the standardized
    validation error envelope and structured detail list.
    """
    response = await client.get("/_test_errors/validate-422?number=not-an-integer")
    assert response.status_code == 422

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["message"] == "Request input validation failed"
    assert isinstance(data["error"]["details"], list)
    assert len(data["error"]["details"]) > 0

    first_detail = data["error"]["details"][0]
    assert "query -> number" in first_detail["location"]
    assert "timestamp" in data

@pytest.mark.asyncio
async def test_unhandled_500_sanitized_envelope(client: AsyncClient):
    """
    Verifies that unhandled internal exceptions produce HTTP 500 with a generic,
    sanitized error envelope that does not leak internal error details or stack traces.
    """
    response = await client.get("/_test_errors/raise-500")
    assert response.status_code == 500

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert data["error"]["message"] == "An unexpected internal server error occurred."
    assert data["error"]["details"] == []
    assert "timestamp" in data

    # Strict sanitization assertion: internal sensitive string must not be leaked to client
    assert "SensitiveDatabasePassword_XYZ123" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text
