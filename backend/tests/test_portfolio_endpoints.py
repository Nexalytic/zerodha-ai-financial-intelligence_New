from decimal import Decimal
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_api_create_portfolio(client: AsyncClient):
    """Verifies creating a portfolio via POST /api/v1/portfolios."""
    response = await client.post(
        "/api/v1/portfolios",
        json={
            "name": "Alpha Generation Basket",
            "description": "Momentum strategy",
            "is_sample": False,
            "holdings": [
                {
                    "symbol": "RELIANCE",
                    "exchange": "NSE",
                    "quantity": 10,
                    "average_buy_price": "2850.50",
                    "sector": "Energy",
                }
            ],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["name"] == "Alpha Generation Basket"
    assert data["is_sample"] is False
    assert len(data["holdings"]) == 1
    assert data["holdings"][0]["symbol"] == "RELIANCE"

@pytest.mark.asyncio
async def test_api_get_portfolio_not_found(client: AsyncClient):
    """Verifies GET /api/v1/portfolios/{id} with invalid ID returns 404 error envelope."""
    response = await client.get("/api/v1/portfolios/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "PORTFOLIO_NOT_FOUND"
    assert "not found" in data["error"]["message"]
    assert "timestamp" in data

@pytest.mark.asyncio
async def test_api_list_portfolios_is_sample_filter(client: AsyncClient):
    """Verifies GET /api/v1/portfolios filters by is_sample flag."""
    # Create real portfolio
    await client.post(
        "/api/v1/portfolios",
        json={"name": "Real User Account", "is_sample": False},
    )
    # Create sample portfolio
    await client.post(
        "/api/v1/portfolios",
        json={"name": "Demo Sandbox", "is_sample": True},
    )

    # Filter is_sample=true
    res_sample = await client.get("/api/v1/portfolios?is_sample=true")
    assert res_sample.status_code == 200
    for p in res_sample.json():
        assert p["is_sample"] is True

    # Filter is_sample=false
    res_real = await client.get("/api/v1/portfolios?is_sample=false")
    assert res_real.status_code == 200
    for p in res_real.json():
        assert p["is_sample"] is False

@pytest.mark.asyncio
async def test_api_update_portfolio_validation(client: AsyncClient):
    """Verifies updating a portfolio, rejecting empty payloads with 422 envelope."""
    # Create
    create_res = await client.post(
        "/api/v1/portfolios",
        json={"name": "Original Name", "description": "Original Desc"},
    )
    port_id = create_res.json()["id"]

    # Valid update
    update_res = await client.put(
        f"/api/v1/portfolios/{port_id}",
        json={"name": "Updated Name", "description": "Updated Desc"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Updated Name"

    # Empty payload rejection
    empty_res = await client.put(f"/api/v1/portfolios/{port_id}", json={})
    assert empty_res.status_code == 422
    assert empty_res.json()["success"] is False
    assert empty_res.json()["error"]["code"] == "VALIDATION_ERROR"

    # 404 for non-existent portfolio
    missing_res = await client.put(
        "/api/v1/portfolios/00000000-0000-0000-0000-000000000000",
        json={"name": "No Exist"},
    )
    assert missing_res.status_code == 404
    assert missing_res.json()["error"]["code"] == "PORTFOLIO_NOT_FOUND"

@pytest.mark.asyncio
async def test_api_delete_portfolio(client: AsyncClient):
    """Verifies deleting a portfolio via DELETE /api/v1/portfolios/{id}."""
    create_res = await client.post(
        "/api/v1/portfolios",
        json={"name": "To Be Deleted"},
    )
    port_id = create_res.json()["id"]

    delete_res = await client.delete(f"/api/v1/portfolios/{port_id}")
    assert delete_res.status_code == 200
    assert delete_res.json()["deleted"] is True

    # Confirm it cannot be fetched
    get_res = await client.get(f"/api/v1/portfolios/{port_id}")
    assert get_res.status_code == 404

@pytest.mark.asyncio
async def test_api_import_portfolio_success(client: AsyncClient):
    """Verifies importing a portfolio with multiple holdings."""
    response = await client.post(
        "/api/v1/portfolios/import",
        json={
            "name": "Spreadsheet Import 2026",
            "description": "Verified import batch",
            "is_sample": False,
            "holdings": [
                {
                    "symbol": "INFY",
                    "exchange": "NSE",
                    "quantity": 50,
                    "average_buy_price": "1520.25",
                    "sector": "IT",
                },
                {
                    "symbol": "TCS",
                    "exchange": "NSE",
                    "quantity": 30,
                    "average_buy_price": "3920.00",
                    "sector": "IT",
                },
            ],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Spreadsheet Import 2026"
    assert len(data["holdings"]) == 2

@pytest.mark.asyncio
async def test_api_import_rejects_duplicate_symbols(client: AsyncClient):
    """
    Verifies that importing duplicate positions (same symbol and exchange)
    is rejected with a clear 422 validation error message.
    """
    response = await client.post(
        "/api/v1/portfolios/import",
        json={
            "name": "Invalid Duplicate Import",
            "holdings": [
                {
                    "symbol": "RELIANCE",
                    "exchange": "NSE",
                    "quantity": 10,
                    "average_buy_price": "2850.00",
                },
                {
                    "symbol": "RELIANCE",
                    "exchange": "NSE",
                    "quantity": 20,
                    "average_buy_price": "2870.00",
                },
            ],
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
    # Verify clear consolidation instruction in error
    details_str = str(data["error"]["details"])
    assert "Duplicate position for symbol 'RELIANCE'" in details_str
    assert "Please consolidate quantity and average buy price" in details_str

@pytest.mark.asyncio
async def test_api_import_rejects_invalid_values(client: AsyncClient):
    """Verifies that invalid holding values (negative quantities, zero price) are rejected."""
    # Negative quantity
    res_neg_qty = await client.post(
        "/api/v1/portfolios/import",
        json={
            "name": "Bad Qty Import",
            "holdings": [
                {"symbol": "TCS", "quantity": -5, "average_buy_price": "3900.00"}
            ],
        },
    )
    assert res_neg_qty.status_code == 422

    # Zero price
    res_zero_price = await client.post(
        "/api/v1/portfolios/import",
        json={
            "name": "Bad Price Import",
            "holdings": [
                {"symbol": "TCS", "quantity": 10, "average_buy_price": "0.00"}
            ],
        },
    )
    assert res_zero_price.status_code == 422

@pytest.mark.asyncio
async def test_api_seed_demo_idempotency(client: AsyncClient):
    """
    Verifies calling POST /api/v1/portfolios/seed-demo multiple times
    returns HTTP 200 with created=True on first call and created=False on second.
    """
    first_call = await client.post("/api/v1/portfolios/seed-demo")
    assert first_call.status_code == 200
    first_data = first_call.json()
    assert first_data["created"] is True
    assert first_data["portfolio"]["name"] == "Demo Indian Bluechip Portfolio"
    assert first_data["portfolio"]["is_sample"] is True
    assert len(first_data["portfolio"]["holdings"]) == 10

    # Second call (repeatable/idempotent)
    second_call = await client.post("/api/v1/portfolios/seed-demo")
    assert second_call.status_code == 200
    second_data = second_call.json()
    assert second_data["created"] is False
    assert second_data["portfolio"]["id"] == first_data["portfolio"]["id"]

@pytest.mark.asyncio
async def test_api_holding_subroutes(client: AsyncClient):
    """Verifies adding and deleting holdings via portfolio sub-endpoints."""
    # Create portfolio
    create_res = await client.post(
        "/api/v1/portfolios",
        json={"name": "Subroutes Test Basket"},
    )
    port_id = create_res.json()["id"]

    # Add holding
    add_res = await client.post(
        f"/api/v1/portfolios/{port_id}/holdings",
        json={
            "symbol": "LT",
            "exchange": "NSE",
            "quantity": 15,
            "average_buy_price": "3500.00",
            "sector": "Construction",
        },
    )
    assert add_res.status_code == 201
    holding_id = add_res.json()["id"]

    # Delete holding
    del_res = await client.delete(f"/api/v1/portfolios/{port_id}/holdings/{holding_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True
