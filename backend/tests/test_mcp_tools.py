import asyncio
import json
import os
from pathlib import Path
import sys
import uuid
from decimal import Decimal
from typing import Any, Dict, List
import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import ValidationError

from app.mcp.audit import (
    clear_audit_records,
    get_audit_records,
    record_audit_entry,
    sanitize_arguments,
)
from app.mcp.schemas import (
    APPROVED_TOOLS,
    GeneratePortfolioAIInsightsArgs,
    GetMarketSnapshotArgs,
    GetPortfolioArgs,
    MCPErrorCode,
    SearchNewsArgs,
)
from app.mcp.server import create_mcp_server
from app.mcp.tools import execute_governed_tool
from app.models.portfolio import Holding, Portfolio
from app.providers.base import BaseMarketDataProvider
from app.schemas.ai_reasoning import AIInsightReport, ReviewStatus
from app.schemas.market_data import BatchQuotesResponse, Quote, QuoteStatus
from app.services.ai.providers.base import BaseAIProvider
from app.services.market_data_service import MarketDataService
from app.services.portfolio_service import (
    CANONICAL_DEMO_NAME,
    DEMO_PORTFOLIO_ID,
    PortfolioService,
)


@pytest.fixture(autouse=True)
def reset_audit():
    """Ensure audit records are cleared before and after each test."""
    clear_audit_records()
    yield
    clear_audit_records()


@pytest.fixture
async def seeded_demo_db(test_db_setup):
    """Provides test database with seeded canonical demo portfolio."""
    session_factory, engine = test_db_setup
    async with session_factory() as session:
        service = PortfolioService(session)
        await service.seed_demo_portfolio()
    return session_factory, engine


# ---------------------------------------------------------------------------
# 1. Tool Registration & Discovery Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_server_tool_registration(test_db_setup):
    """
    Verifies that exactly seven approved read-only tools are registered on the FastMCP server,
    their names match the APPROVED_TOOLS allowlist, and readOnlyHint is set.
    """
    session_factory, _ = test_db_setup
    server = create_mcp_server(session_factory=session_factory)

    tools = await server.list_tools()
    tool_names = {t.name for t in tools}

    assert len(tools) == 8
    assert tool_names == APPROVED_TOOLS
    assert "generate_portfolio_ai_insights" in tool_names
    assert "delete_portfolio" not in tool_names
    assert "execute_order" not in tool_names

    for t in tools:
        assert t.annotations is not None
        assert t.annotations.readOnlyHint is True
        assert t.annotations.destructiveHint is False
        assert t.description is not None
        assert len(t.description) > 10


# ---------------------------------------------------------------------------
# 2. Governed Tool Execution Tests (Positive Cases)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_get_portfolio_success(seeded_demo_db):
    """Verifies get_portfolio retrieves holdings and details for a valid portfolio."""
    session_factory, _ = seeded_demo_db
    result = await execute_governed_tool(
        "get_portfolio",
        {"portfolio_id": DEMO_PORTFOLIO_ID},
        session_factory=session_factory,
    )

    assert result["id"] == DEMO_PORTFOLIO_ID
    assert result["name"] == CANONICAL_DEMO_NAME
    assert result["is_sample"] is True
    assert len(result["holdings"]) == 10
    symbols = [h["symbol"] for h in result["holdings"]]
    assert "RELIANCE" in symbols
    assert "TCS" in symbols


@pytest.mark.asyncio
async def test_tool_list_portfolios(seeded_demo_db):
    """Verifies list_portfolios returns portfolio summaries with sample filtering."""
    session_factory, _ = seeded_demo_db
    # List all
    all_res = await execute_governed_tool(
        "list_portfolios", {}, session_factory=session_factory
    )
    assert all_res["total_count"] >= 1
    assert any(p["id"] == DEMO_PORTFOLIO_ID for p in all_res["portfolios"])

    # Filter sample=True
    samples_res = await execute_governed_tool(
        "list_portfolios", {"is_sample": True}, session_factory=session_factory
    )
    assert any(p["id"] == DEMO_PORTFOLIO_ID for p in samples_res["portfolios"])

    # Filter sample=False
    customs_res = await execute_governed_tool(
        "list_portfolios", {"is_sample": False}, session_factory=session_factory
    )
    assert not any(p["id"] == DEMO_PORTFOLIO_ID for p in customs_res["portfolios"])


@pytest.mark.asyncio
async def test_tool_get_market_snapshot():
    """Verifies get_market_snapshot returns valid quotes with simulation flags."""
    result = await execute_governed_tool(
        "get_market_snapshot",
        {"symbols": ["RELIANCE", "INFY"], "exchange": "NSE"},
    )

    assert result["total_symbols"] == 2
    assert "RELIANCE" in result["quotes"]
    assert "INFY" in result["quotes"]

    reliance_quote = result["quotes"]["RELIANCE"]
    assert reliance_quote["status"] in ["AVAILABLE", "OK"]
    assert reliance_quote["is_simulated"] is True
    assert Decimal(str(reliance_quote["current_price"])) > Decimal("0")


@pytest.mark.asyncio
async def test_tool_search_news():
    """Verifies search_news returns articles with simulation and disclaimers."""
    # Filter by symbol
    result_sym = await execute_governed_tool(
        "search_news",
        {"symbols": ["TCS"], "limit": 5},
    )
    assert result_sym["is_simulated"] is True
    assert len(result_sym["articles"]) <= 5

    # General market news
    result_market = await execute_governed_tool(
        "search_news",
        {"limit": 3},
    )
    assert result_market["is_simulated"] is True
    assert len(result_market["articles"]) <= 3


@pytest.mark.asyncio
async def test_tool_calculate_portfolio_metrics(seeded_demo_db):
    """Verifies calculate_portfolio_metrics returns valuation, concentration, and historical status."""
    session_factory, _ = seeded_demo_db
    result = await execute_governed_tool(
        "calculate_portfolio_metrics",
        {"portfolio_id": DEMO_PORTFOLIO_ID},
        session_factory=session_factory,
    )

    assert result["status"] == "COMPLETE"
    assert Decimal(str(result["valuation"]["total_market_value"])) > Decimal("0")
    assert Decimal(str(result["concentration"]["herfindahl_index"])) > Decimal("0")
    assert result["historical_risk"]["data_status"] == "INSUFFICIENT_HISTORY"


@pytest.mark.asyncio
async def test_tool_score_portfolio_risk(seeded_demo_db):
    """Verifies score_portfolio_risk returns risk assessment, 4 component scores, and insights."""
    session_factory, _ = seeded_demo_db
    result = await execute_governed_tool(
        "score_portfolio_risk",
        {"portfolio_id": DEMO_PORTFOLIO_ID},
        session_factory=session_factory,
    )

    assert result["portfolio_id"] == DEMO_PORTFOLIO_ID
    risk = result["risk_assessment"]
    assert Decimal("0") <= Decimal(str(risk["composite_risk_score"])) <= Decimal("100")
    assert risk["risk_tier"] in ["LOW", "MODERATE", "ELEVATED", "HIGH"]

    components = risk["components"]
    assert "single_stock_concentration_score" in components
    assert "sector_concentration_score" in components
    assert "diversification_breadth_score" in components
    assert "data_quality_score" in components

    assert "insights" in result
    assert isinstance(result["insights"], list)
    assert result["total_insights"] == len(result["insights"])


@pytest.mark.asyncio
async def test_tool_get_evidence_bundle(seeded_demo_db):
    """Verifies get_evidence_bundle composes all services into a complete bundle."""
    session_factory, _ = seeded_demo_db
    bundle = await execute_governed_tool(
        "get_evidence_bundle",
        {"portfolio_id": DEMO_PORTFOLIO_ID},
        session_factory=session_factory,
    )

    assert bundle["portfolio_id"] == DEMO_PORTFOLIO_ID
    assert "portfolio" in bundle
    assert "market_snapshot" in bundle
    assert "analytics" in bundle
    assert "risk_assessment" in bundle
    assert "insights" in bundle
    assert "metadata" in bundle

    meta = bundle["metadata"]
    assert meta["is_simulated"] is True
    assert meta["completeness_status"] == "COMPLETE"
    assert meta["has_missing_prices"] is False
    assert meta["data_status"] == "INSUFFICIENT_HISTORY"


# ---------------------------------------------------------------------------
# 3. Missing Resource & Error Handling Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_get_portfolio_not_found(test_db_setup):
    """Verifies missing portfolio ID raises safe, structured ToolError."""
    session_factory, _ = test_db_setup
    non_existent_id = "00000000-0000-0000-0000-999999999999"

    with pytest.raises(ToolError) as exc_info:
        await execute_governed_tool(
            "get_portfolio",
            {"portfolio_id": non_existent_id},
            session_factory=session_factory,
        )

    assert MCPErrorCode.PORTFOLIO_NOT_FOUND.value in str(exc_info.value)
    assert non_existent_id in str(exc_info.value)


@pytest.mark.asyncio
async def test_tool_calculate_metrics_not_found(test_db_setup):
    """Verifies calculate_portfolio_metrics returns PORTFOLIO_NOT_FOUND for missing ID."""
    session_factory, _ = test_db_setup
    with pytest.raises(ToolError) as exc_info:
        await execute_governed_tool(
            "calculate_portfolio_metrics",
            {"portfolio_id": "missing-uuid"},
            session_factory=session_factory,
        )
    assert MCPErrorCode.PORTFOLIO_NOT_FOUND.value in str(exc_info.value)


@pytest.mark.asyncio
async def test_tool_score_risk_not_found(test_db_setup):
    """Verifies score_portfolio_risk returns PORTFOLIO_NOT_FOUND for missing ID."""
    session_factory, _ = test_db_setup
    with pytest.raises(ToolError) as exc_info:
        await execute_governed_tool(
            "score_portfolio_risk",
            {"portfolio_id": "missing-uuid"},
            session_factory=session_factory,
        )
    assert MCPErrorCode.PORTFOLIO_NOT_FOUND.value in str(exc_info.value)


@pytest.mark.asyncio
async def test_tool_evidence_bundle_not_found(test_db_setup):
    """Verifies get_evidence_bundle returns PORTFOLIO_NOT_FOUND for missing ID."""
    session_factory, _ = test_db_setup
    with pytest.raises(ToolError) as exc_info:
        await execute_governed_tool(
            "get_evidence_bundle",
            {"portfolio_id": "missing-uuid"},
            session_factory=session_factory,
        )
    assert MCPErrorCode.PORTFOLIO_NOT_FOUND.value in str(exc_info.value)


# ---------------------------------------------------------------------------
# 4. Input Validation & Schema Boundary Tests
# ---------------------------------------------------------------------------

def test_input_validation_empty_portfolio_id():
    """Verifies rejection of empty or whitespace portfolio_id."""
    with pytest.raises(ValidationError):
        GetPortfolioArgs(portfolio_id="")
    with pytest.raises(ValidationError):
        GetPortfolioArgs(portfolio_id="   ")


def test_input_validation_market_snapshot_symbols():
    """Verifies rejection of empty list, invalid symbols, and bad exchange."""
    with pytest.raises(ValidationError):
        GetMarketSnapshotArgs(symbols=[])

    with pytest.raises(ValidationError):
        GetMarketSnapshotArgs(symbols=["INVALID$SYMBOL!"])

    with pytest.raises(ValidationError):
        GetMarketSnapshotArgs(symbols=["RELIANCE"], exchange="NASDAQ")


def test_input_validation_search_news_limit():
    """Verifies bounded limit enforcement on news query."""
    with pytest.raises(ValidationError):
        SearchNewsArgs(limit=0)

    with pytest.raises(ValidationError):
        SearchNewsArgs(limit=100)


@pytest.mark.asyncio
async def test_extra_arguments_rejected_on_fastmcp_tool(test_db_setup):
    """Verifies that unexpected arguments trigger extra_forbidden validation error on FastMCP tool."""
    session_factory, _ = test_db_setup
    server = create_mcp_server(session_factory=session_factory)

    with pytest.raises(ToolError) as exc_info:
        await server.call_tool(
            "get_portfolio",
            {"portfolio_id": DEMO_PORTFOLIO_ID, "unexpected_extra_field": "dangerous"},
        )

    assert "extra_forbidden" in str(exc_info.value) or "Extra inputs are not permitted" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 5. Governance & Unapproved Tool Rejection Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unapproved_tool_rejection():
    """Verifies calling unapproved mutating tools raises UNAUTHORIZED_TOOL and logs error."""
    unapproved_tools = [
        "delete_portfolio",
        "execute_order",
        "buy_stock",
        "update_holding",
        "run_shell_command",
    ]

    for tool in unapproved_tools:
        with pytest.raises(ToolError) as exc_info:
            await execute_governed_tool(tool, {"some_arg": "value"})

        assert MCPErrorCode.UNAUTHORIZED_TOOL.value in str(exc_info.value)

    records = get_audit_records()
    assert len(records) == len(unapproved_tools)
    for r in records:
        assert r.status == "ERROR"
        assert r.error_code == MCPErrorCode.UNAUTHORIZED_TOOL.value


# ---------------------------------------------------------------------------
# 6. Audit Logging & Redaction Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_logging_records_duration_and_correlation_id(seeded_demo_db):
    """Verifies audit entries capture valid correlation IDs, duration, and status."""
    session_factory, _ = seeded_demo_db
    clear_audit_records()

    await execute_governed_tool(
        "get_portfolio",
        {"portfolio_id": DEMO_PORTFOLIO_ID},
        session_factory=session_factory,
    )

    records = get_audit_records()
    assert len(records) == 1
    r = records[0]
    assert r.tool_name == "get_portfolio"
    assert r.status == "SUCCESS"
    assert r.duration_ms >= 0.0
    uuid_obj = uuid.UUID(r.correlation_id)
    assert str(uuid_obj) == r.correlation_id


def test_audit_sanitization_redacts_sensitive_keys():
    """Verifies sanitize_arguments masks API keys, secrets, and passwords."""
    raw_args = {
        "portfolio_id": "12345",
        "api_key": "my-secret-key-12345",
        "auth_token": "bearer-token-abcde",
        "password": "super-secret-password",
        "regular_field": "NSE",
    }

    sanitized = sanitize_arguments(raw_args)
    assert sanitized["portfolio_id"] == "12345"
    assert sanitized["regular_field"] == "NSE"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["auth_token"] == "[REDACTED]"
    assert sanitized["password"] == "[REDACTED]"


# ---------------------------------------------------------------------------
# 7. Provider Resilience & Partial Evidence Handling Tests
# ---------------------------------------------------------------------------

class FailingMarketDataProvider(BaseMarketDataProvider):
    """Test double simulating provider failure with no network/database."""
    PROVIDER_NAME = "FAILING_TEST_PROVIDER"

    async def get_quote(self, symbol: str, exchange: str = "NSE") -> Quote:
        raise RuntimeError("Simulated remote provider connection outage")

    async def get_quotes(self, symbols: List[str], exchange: str = "NSE") -> BatchQuotesResponse:
        raise RuntimeError("Simulated remote provider connection outage")


@pytest.mark.asyncio
async def test_provider_failure_returns_error_quote_without_crashing():
    """Verifies market data service handles provider failure gracefully without crashing."""
    md_service = MarketDataService(provider=FailingMarketDataProvider(), default_ttl_seconds=60)
    result = await execute_governed_tool(
        "get_market_snapshot",
        {"symbols": ["TCS"], "exchange": "NSE"},
        market_data_service=md_service,
    )

    assert "TCS" in result["quotes"]
    quote = result["quotes"]["TCS"]
    assert quote["status"] == "ERROR"
    assert quote["current_price"] is None
    assert "provider failed" in quote["explanation"].lower()


@pytest.mark.asyncio
async def test_evidence_bundle_handles_partially_unpriced_portfolio(test_db_setup):
    """
    Verifies that a portfolio containing an unpriced holding generates an honest
    partial completeness flag and warning message in evidence bundle metadata.
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        p = Portfolio(name="Partial Portfolio", is_sample=False)
        p.holdings.append(
            Holding(
                symbol="RELIANCE",
                exchange="NSE",
                quantity=10,
                average_buy_price=Decimal("2500.00"),
                sector="Energy",
            )
        )
        p.holdings.append(
            Holding(
                symbol="UNPRICEDTICKER",
                exchange="NSE",
                quantity=20,
                average_buy_price=Decimal("100.00"),
                sector="Special",
            )
        )
        session.add(p)
        await session.commit()
        await session.refresh(p)
        partial_id = p.id

    bundle = await execute_governed_tool(
        "get_evidence_bundle",
        {"portfolio_id": partial_id},
        session_factory=session_factory,
    )

    meta = bundle["metadata"]
    assert meta["completeness_status"] == "PARTIAL"
    assert meta["has_missing_prices"] is True
    assert meta["partial_data_warning"] is not None
    assert "unpriced" in meta["partial_data_warning"].lower()


@pytest.mark.asyncio
async def test_failure_isolation_preserves_subsequent_calls(seeded_demo_db):
    """Verifies that a failed tool invocation does not prevent subsequent successful calls."""
    session_factory, _ = seeded_demo_db

    # 1. Failed call
    with pytest.raises(ToolError):
        await execute_governed_tool(
            "get_portfolio",
            {"portfolio_id": "non-existent-portfolio"},
            session_factory=session_factory,
        )

    # 2. Subsequent valid call must succeed immediately
    valid_res = await execute_governed_tool(
        "get_portfolio",
        {"portfolio_id": DEMO_PORTFOLIO_ID},
        session_factory=session_factory,
    )
    assert valid_res["id"] == DEMO_PORTFOLIO_ID


# ---------------------------------------------------------------------------
# 8. Real SDK MCP Client/Server Interoperability Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_real_mcp_client_interoperability_in_memory(seeded_demo_db):
    """
    Demonstrates full end-to-end MCP protocol interoperability using the official
    SDK's ClientSession and FastMCP lowlevel server over async memory streams.
    Verifies initialization, tool listing, successful tool call, and safe error handling.
    """
    session_factory, _ = seeded_demo_db
    server = create_mcp_server(session_factory=session_factory)

    send_to_server, recv_by_server = anyio.create_memory_object_stream(10)
    send_to_client, recv_by_client = anyio.create_memory_object_stream(10)

    async with anyio.create_task_group() as tg:
        tg.start_soon(
            server._mcp_server.run,
            recv_by_server,
            send_to_client,
            server._mcp_server.create_initialization_options(),
        )

        async with ClientSession(recv_by_client, send_to_server) as client:
            # 1. Initialize session
            init_res = await client.initialize()
            assert init_res.serverInfo.name == "zerodha-ai-intelligence"

            # 2. List tools
            tools_res = await client.list_tools()
            tool_names = [t.name for t in tools_res.tools]
            assert len(tool_names) == 8
            assert "get_portfolio" in tool_names
            assert "get_evidence_bundle" in tool_names
            assert "generate_portfolio_ai_insights" in tool_names

            # 3. Successful tool call
            call_res = await client.call_tool("list_portfolios", {})
            assert call_res.isError is False
            assert len(call_res.content) == 1
            portfolios_data = json.loads(call_res.content[0].text)
            assert any(p["id"] == DEMO_PORTFOLIO_ID for p in portfolios_data["portfolios"])

            # 4. Successful call to new AI reasoning tool
            ai_res = await client.call_tool(
                "generate_portfolio_ai_insights",
                {"portfolio_id": DEMO_PORTFOLIO_ID, "include_news": False},
            )
            assert ai_res.isError is False
            assert len(ai_res.content) == 1
            ai_data = json.loads(ai_res.content[0].text)
            assert ai_data["portfolio_id"] == DEMO_PORTFOLIO_ID
            assert ai_data["review_status"] == "VERIFIED"
            assert "key_drivers" in ai_data

            # 5. Safe error for non-existent portfolio
            err_res = await client.call_tool("get_portfolio", {"portfolio_id": "non-existent-id"})
            assert err_res.isError is True
            assert len(err_res.content) == 1
            assert MCPErrorCode.PORTFOLIO_NOT_FOUND.value in err_res.content[0].text

            tg.cancel_scope.cancel()


@pytest.mark.asyncio
async def test_real_mcp_client_stdio_subprocess():
    """
    Spawns the MCP server as a real OS subprocess running `python -m app.mcp.server`,
    connects over stdio using `stdio_client`, initializes session, lists tools,
    and calls `get_market_snapshot`.
    """
    backend_path = Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    env["PYTHONPATH"] = str(backend_path)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp.server"],
        env=env,
        cwd=str(backend_path),
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # 1. Initialize
            init_res = await session.initialize()
            assert init_res.serverInfo.name == "zerodha-ai-intelligence"

            # 2. List tools
            tools_res = await session.list_tools()
            tool_names = [t.name for t in tools_res.tools]
            assert len(tool_names) == 8
            assert "get_portfolio" in tool_names
            assert "score_portfolio_risk" in tool_names
            assert "generate_portfolio_ai_insights" in tool_names

            # 3. Call tool
            call_res = await session.call_tool("get_market_snapshot", {"symbols": ["TCS"], "exchange": "NSE"})
            assert call_res.isError is False
            snapshot_data = json.loads(call_res.content[0].text)
            assert "TCS" in snapshot_data["quotes"]
            assert snapshot_data["quotes"]["TCS"]["status"] in ["AVAILABLE", "OK"]

            # 4. Call generate_portfolio_ai_insights over stdio subprocess
            ai_call_res = await session.call_tool(
                "generate_portfolio_ai_insights",
                {"portfolio_id": "non-existent-portfolio-id", "include_news": False},
            )
            assert ai_call_res.isError is True
            assert MCPErrorCode.PORTFOLIO_NOT_FOUND.value in ai_call_res.content[0].text


# ---------------------------------------------------------------------------
# 9. Governed AI Reasoning MCP Tool Tests (generate_portfolio_ai_insights)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_generate_ai_insights_success(seeded_demo_db):
    """Verifies generate_portfolio_ai_insights returns typed report with VERIFIED review status."""
    session_factory, _ = seeded_demo_db
    result = await execute_governed_tool(
        "generate_portfolio_ai_insights",
        {"portfolio_id": DEMO_PORTFOLIO_ID, "include_news": True, "news_limit": 5},
        session_factory=session_factory,
    )

    assert result["portfolio_id"] == DEMO_PORTFOLIO_ID
    assert result["review_status"] == "VERIFIED"
    assert result["grounding_report"]["is_acceptable"] is True
    assert len(result["key_drivers"]) >= 1
    assert isinstance(result["risk_alerts"], list)
    assert len(result["review_cards"]) >= 1
    assert result["provider_name"] == "DETERMINISTIC_DEMO_REASONER"


@pytest.mark.asyncio
async def test_tool_generate_ai_insights_portfolio_not_found(test_db_setup):
    """Verifies missing portfolio ID produces safe, structured ToolError with correlation ID."""
    session_factory, _ = test_db_setup
    with pytest.raises(ToolError) as exc_info:
        await execute_governed_tool(
            "generate_portfolio_ai_insights",
            {"portfolio_id": "non-existent-uuid"},
            session_factory=session_factory,
        )
    assert MCPErrorCode.PORTFOLIO_NOT_FOUND.value in str(exc_info.value)
    assert "non-existent-uuid" in str(exc_info.value)


@pytest.mark.asyncio
async def test_tool_generate_ai_insights_empty_and_unpriced(test_db_setup):
    """Verifies empty and wholly unpriced portfolios preserve uncertainty statements and disclosures."""
    session_factory, _ = test_db_setup

    # 1. Empty portfolio
    async with session_factory() as session:
        empty_p = Portfolio(name="Empty Test Portfolio", is_sample=False)
        session.add(empty_p)
        await session.commit()
        await session.refresh(empty_p)
        empty_id = empty_p.id

    empty_res = await execute_governed_tool(
        "generate_portfolio_ai_insights",
        {"portfolio_id": empty_id},
        session_factory=session_factory,
    )
    assert empty_res["review_status"] == "VERIFIED"
    assert any("zero" in u.lower() or "unavailable" in u.lower() for u in empty_res["uncertainty_and_gaps"])

    # 2. Wholly unpriced portfolio
    async with session_factory() as session:
        unpriced_p = Portfolio(name="Unpriced Test Portfolio", is_sample=False)
        unpriced_p.holdings.append(
            Holding(
                symbol="UNKNOWNSTOCK",
                exchange="NSE",
                quantity=10,
                average_buy_price=Decimal("100.00"),
                sector="Special",
            )
        )
        session.add(unpriced_p)
        await session.commit()
        await session.refresh(unpriced_p)
        unpriced_id = unpriced_p.id

    unpriced_res = await execute_governed_tool(
        "generate_portfolio_ai_insights",
        {"portfolio_id": unpriced_id},
        session_factory=session_factory,
    )
    assert unpriced_res["review_status"] == "VERIFIED"
    assert any("quotes" in u.lower() or "unavailable" in u.lower() for u in unpriced_res["uncertainty_and_gaps"])


@pytest.mark.asyncio
async def test_tool_generate_ai_insights_stale_and_news_resilience(seeded_demo_db):
    """Verifies pipeline succeeds safely even when external/news service fails."""
    session_factory, _ = seeded_demo_db

    class FailingNewsService:
        async def get_news_for_symbols(self, symbols, limit=10):
            raise RuntimeError("News network provider timeout")

        async def get_market_news(self, limit=10):
            raise RuntimeError("News network provider timeout")

    result = await execute_governed_tool(
        "generate_portfolio_ai_insights",
        {"portfolio_id": DEMO_PORTFOLIO_ID, "include_news": True},
        session_factory=session_factory,
        news_service=FailingNewsService(),
    )
    assert result["review_status"] == "VERIFIED"
    assert result["portfolio_id"] == DEMO_PORTFOLIO_ID


@pytest.mark.asyncio
async def test_tool_generate_ai_insights_rejected_grounding_not_verified(seeded_demo_db):
    """Verifies that a report failing claim grounding is returned as REJECTED, NEVER VERIFIED."""
    session_factory, _ = seeded_demo_db

    class HallucinatingProvider(BaseAIProvider):
        @property
        def provider_name(self) -> str:
            return "HALLUCINATOR"

        async def generate_insights(self, evidence):
            from app.services.ai.providers.demo_provider import DeterministicDemoProvider
            base = DeterministicDemoProvider()
            rep = await base.generate_insights(evidence)
            rep.review_cards[0].related_symbols = ["FABRICATED_GHOST_CORP"]
            return rep

    result = await execute_governed_tool(
        "generate_portfolio_ai_insights",
        {"portfolio_id": DEMO_PORTFOLIO_ID},
        session_factory=session_factory,
        ai_provider=HallucinatingProvider(),
    )
    assert result["review_status"] == "REJECTED"
    assert result["grounding_report"]["is_acceptable"] is False
    assert result["grounding_report"]["rejected_count"] >= 1


@pytest.mark.asyncio
async def test_tool_generate_ai_insights_warnings_visible(test_db_setup):
    """Verifies that non-critical grounding warnings remain visible in response."""
    session_factory, _ = test_db_setup
    async with session_factory() as session:
        p = Portfolio(name="Partial Portfolio For Warnings", is_sample=False)
        p.holdings.append(
            Holding(symbol="RELIANCE", exchange="NSE", quantity=10, average_buy_price=Decimal("2500.00"), sector="Energy")
        )
        p.holdings.append(
            Holding(symbol="UNPRICEDTICKER", exchange="NSE", quantity=20, average_buy_price=Decimal("100.00"), sector="Special")
        )
        session.add(p)
        await session.commit()
        await session.refresh(p)
        p_id = p.id

    result = await execute_governed_tool(
        "generate_portfolio_ai_insights",
        {"portfolio_id": p_id},
        session_factory=session_factory,
    )
    assert result["review_status"] in ["VERIFIED", "FLAGGED_WITH_WARNINGS"]
    assert len(result["uncertainty_and_gaps"]) >= 1


def test_input_validation_generate_ai_insights_args():
    """Verifies argument boundaries and validation rules."""
    with pytest.raises(ValidationError):
        GeneratePortfolioAIInsightsArgs(portfolio_id="")
    with pytest.raises(ValidationError):
        GeneratePortfolioAIInsightsArgs(portfolio_id="   ")
    with pytest.raises(ValidationError):
        GeneratePortfolioAIInsightsArgs(portfolio_id="valid-id", news_limit=0)
    with pytest.raises(ValidationError):
        GeneratePortfolioAIInsightsArgs(portfolio_id="valid-id", news_limit=25)


@pytest.mark.asyncio
async def test_extra_arguments_rejected_on_ai_insights_tool(test_db_setup):
    """Verifies unexpected argument keys are forbidden on generate_portfolio_ai_insights."""
    session_factory, _ = test_db_setup
    server = create_mcp_server(session_factory=session_factory)

    with pytest.raises(ToolError) as exc_info:
        await server.call_tool(
            "generate_portfolio_ai_insights",
            {"portfolio_id": DEMO_PORTFOLIO_ID, "arbitrary_function": "exec('rm -rf /')"},
        )
    assert "extra_forbidden" in str(exc_info.value) or "Extra inputs are not permitted" in str(exc_info.value)


@pytest.mark.asyncio
async def test_tool_generate_ai_insights_provider_error_no_raw_leakage(seeded_demo_db):
    """Verifies unexpected provider exceptions do not leak raw exception text or internals."""
    session_factory, _ = seeded_demo_db

    class CrashingProvider(BaseAIProvider):
        @property
        def provider_name(self) -> str:
            return "CRASHING_PROVIDER"

        async def generate_insights(self, evidence):
            raise RuntimeError("Database connection string postgresql://admin:secretPass@internal-db:5432 failed")

    with pytest.raises(ToolError) as exc_info:
        await execute_governed_tool(
            "generate_portfolio_ai_insights",
            {"portfolio_id": DEMO_PORTFOLIO_ID},
            session_factory=session_factory,
            ai_provider=CrashingProvider(),
        )

    err_text = str(exc_info.value)
    assert MCPErrorCode.PROVIDER_ERROR.value in err_text
    assert "secretPass" not in err_text
    assert "postgresql://" not in err_text

    records = get_audit_records()
    assert len(records) >= 1
    last_rec = records[-1]
    assert last_rec.status == "ERROR"
    assert "secretPass" not in str(last_rec.error_message)


@pytest.mark.asyncio
async def test_audit_logging_ai_insights_and_redaction(seeded_demo_db):
    """Verifies audit entries contain valid correlation IDs, duration, and masked credentials."""
    session_factory, _ = seeded_demo_db
    clear_audit_records()

    await execute_governed_tool(
        "generate_portfolio_ai_insights",
        {"portfolio_id": DEMO_PORTFOLIO_ID, "include_news": False},
        session_factory=session_factory,
    )

    records = get_audit_records()
    assert len(records) == 1
    r = records[0]
    assert r.tool_name == "generate_portfolio_ai_insights"
    assert r.status == "SUCCESS"
    assert r.duration_ms >= 0.0
    uuid.UUID(r.correlation_id)

    # Test SEC-01 string regex masking directly
    raw_args = {"notes": "Authorization header Bearer supersecrettoken12345678 was provided"}
    sanitized = sanitize_arguments(raw_args)
    assert "supersecrettoken12345678" not in sanitized["notes"]
    assert "[REDACTED]" in sanitized["notes"]


@pytest.mark.asyncio
async def test_tool_generate_ai_insights_read_only_invariant(seeded_demo_db):
    """Verifies executing AI reasoning tool performs zero database mutations."""
    session_factory, _ = seeded_demo_db

    async with session_factory() as session:
        service = PortfolioService(session)
        p_before = await service.get_portfolio(DEMO_PORTFOLIO_ID)
        holdings_before = len(p_before.holdings)
        portfolios_before = len(await service.list_portfolios())

    await execute_governed_tool(
        "generate_portfolio_ai_insights",
        {"portfolio_id": DEMO_PORTFOLIO_ID},
        session_factory=session_factory,
    )

    async with session_factory() as session:
        service = PortfolioService(session)
        p_after = await service.get_portfolio(DEMO_PORTFOLIO_ID)
        holdings_after = len(p_after.holdings)
        portfolios_after = len(await service.list_portfolios())

    assert holdings_before == holdings_after
    assert portfolios_before == portfolios_after


@pytest.mark.asyncio
async def test_tool_generate_ai_insights_deterministic_reproducibility(seeded_demo_db):
    """Verifies repeated calls to the default deterministic demo engine produce identical insights."""
    session_factory, _ = seeded_demo_db

    res1 = await execute_governed_tool(
        "generate_portfolio_ai_insights",
        {"portfolio_id": DEMO_PORTFOLIO_ID, "include_news": False},
        session_factory=session_factory,
    )
    res2 = await execute_governed_tool(
        "generate_portfolio_ai_insights",
        {"portfolio_id": DEMO_PORTFOLIO_ID, "include_news": False},
        session_factory=session_factory,
    )

    assert res1["review_status"] == res2["review_status"]
    assert res1["executive_summary"] == res2["executive_summary"]
    assert len(res1["key_drivers"]) == len(res2["key_drivers"])
    assert len(res1["risk_alerts"]) == len(res2["risk_alerts"])
    assert res1["key_drivers"][0]["statement"] == res2["key_drivers"][0]["statement"]
