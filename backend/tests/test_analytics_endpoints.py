import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_api_analytics_canonical_demo(client: AsyncClient):
    """
    Verifies GET /api/v1/portfolios/{id}/analytics on the canonical demo portfolio.
    Asserts 200 OK, COMPLETE status, is_sample=True, and valid valuation.
    """
    # 1. Seed demo portfolio
    seed_res = await client.post("/api/v1/portfolios/seed-demo")
    assert seed_res.status_code == 200
    demo_id = seed_res.json()["portfolio"]["id"]

    # 2. Query analytics
    res = await client.get(f"/api/v1/portfolios/{demo_id}/analytics")
    assert res.status_code == 200

    data = res.json()
    assert data["portfolio_id"] == demo_id
    assert data["portfolio_name"] == "Demo Indian Bluechip Portfolio"
    assert data["is_sample"] is True
    assert data["status"] == "COMPLETE"

    # Completeness
    assert data["completeness"]["is_complete"] is True
    assert data["completeness"]["completeness_ratio"] == "1.0000"
    assert data["completeness"]["total_holdings_count"] == 10
    assert data["completeness"]["priced_holdings_count"] == 10
    assert data["completeness"]["unpriced_holdings_count"] == 0
    assert data["completeness"]["has_simulated_prices"] is True

    # Valuation
    valuation = data["valuation"]
    assert float(valuation["total_cost_basis"]) > 0.0
    assert float(valuation["total_market_value"]) > 0.0
    assert valuation["unrealized_pnl"] is not None
    assert valuation["unrealized_pnl_percent"] is not None

    # Concentration
    assert data["concentration"]["top_holding_symbol"] is not None
    assert float(data["concentration"]["herfindahl_index"]) > 0.0

    # Holdings count
    assert len(data["holdings"]) == 10

@pytest.mark.asyncio
async def test_api_analytics_not_found(client: AsyncClient):
    """
    Verifies that querying analytics for a non-existent portfolio UUID
    returns a 404 response adhering to the standardized error envelope.
    """
    res = await client.get("/api/v1/portfolios/00000000-0000-0000-0000-000000000000/analytics")
    assert res.status_code == 404

    data = res.json()
    assert data["success"] is False
    assert data["error"]["code"] == "PORTFOLIO_NOT_FOUND"
    assert "not found" in data["error"]["message"].lower()
    assert "timestamp" in data

@pytest.mark.asyncio
async def test_api_analytics_empty_portfolio(client: AsyncClient):
    """
    Verifies that an empty portfolio returns HTTP 200 with status=EMPTY,
    is_complete=False, completeness_ratio=0.0000, and null unrealized_pnl.
    """
    create_res = await client.post(
        "/api/v1/portfolios",
        json={"name": "Empty API Test Basket"},
    )
    assert create_res.status_code == 201
    port_id = create_res.json()["id"]

    res = await client.get(f"/api/v1/portfolios/{port_id}/analytics")
    assert res.status_code == 200

    data = res.json()
    assert data["status"] == "EMPTY"
    assert data["completeness"]["is_complete"] is False
    assert data["completeness"]["completeness_ratio"] == "0.0000"
    assert data["completeness"]["total_holdings_count"] == 0
    assert data["completeness"]["priced_holdings_count"] == 0

    assert data["valuation"]["total_cost_basis"] == "0.00"
    assert data["valuation"]["total_market_value"] == "0.00"
    assert data["valuation"]["unrealized_pnl"] is None
    assert data["valuation"]["unrealized_pnl_percent"] is None

@pytest.mark.asyncio
async def test_api_analytics_partial_pricing(client: AsyncClient):
    """
    Verifies that a partially priced portfolio returns HTTP 200 with status=PARTIAL,
    is_complete=False, and clear unpriced position details.
    """
    import_res = await client.post(
        "/api/v1/portfolios/import",
        json={
            "name": "Partial API Basket",
            "holdings": [
                {
                    "symbol": "RELIANCE",
                    "exchange": "NSE",
                    "quantity": 10,
                    "average_buy_price": "2850.00",
                },
                {
                    "symbol": "MISSING-TICKER",
                    "exchange": "NSE",
                    "quantity": 25,
                    "average_buy_price": "100.00",
                },
            ],
        },
    )
    assert import_res.status_code == 201
    port_id = import_res.json()["id"]

    res = await client.get(f"/api/v1/portfolios/{port_id}/analytics")
    assert res.status_code == 200

    data = res.json()
    assert data["status"] == "PARTIAL"
    assert data["completeness"]["is_complete"] is False
    assert data["completeness"]["total_holdings_count"] == 2
    assert data["completeness"]["priced_holdings_count"] == 1
    assert data["completeness"]["unpriced_holdings_count"] == 1

    assert len(data["completeness"]["unpriced_positions"]) == 1
    unp = data["completeness"]["unpriced_positions"][0]
    assert unp["symbol"] == "MISSING-TICKER"
    assert unp["pricing_status"] == "UNAVAILABLE"
