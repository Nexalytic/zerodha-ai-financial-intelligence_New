import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from app.core.logging import logger
from app.db.session import async_session_factory
from app.mcp.audit import audit_tool_call
from app.mcp.schemas import (
    APPROVED_TOOLS,
    CalculatePortfolioMetricsArgs,
    EvidenceBundle,
    EvidenceBundleMetadata,
    GeneratePortfolioAIInsightsArgs,
    GetEvidenceBundleArgs,
    GetMarketSnapshotArgs,
    GetPortfolioArgs,
    ListPortfoliosArgs,
    MCPErrorCode,
    PortfolioRiskScoreResponse,
    ScorePortfolioRiskArgs,
    SearchNewsArgs,
)
from app.schemas.analytics import ValuationStatus
from app.schemas.market_data import BatchQuotesResponse
from app.schemas.portfolio import PortfolioDetailResponse, PortfolioResponse
from app.services.ai import (
    AIMalformedOutputError,
    AIProviderError,
    AIReasoningError,
    AIReasoningService,
)
from app.services.ai.providers.base import BaseAIProvider
from app.services.analytics_service import AnalyticsService
from app.services.market_data_service import MarketDataService
from app.services.news_service import NewsService
from app.services.portfolio_service import PortfolioService

# Explicit read-only annotations for all governed MCP tools
READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
)


def _rebuild_tool_arg_model_forbid_extra(server: FastMCP, tool_name: str) -> None:
    """
    Configures the tool's internal Pydantic argument model to forbid extra arguments,
    ensuring unexpected inputs are strictly rejected at the schema validation boundary.
    """
    try:
        tool = server._tool_manager.get_tool(tool_name)
        if tool and hasattr(tool, "fn_metadata") and hasattr(tool.fn_metadata, "arg_model"):
            tool.fn_metadata.arg_model.model_config["extra"] = "forbid"
            tool.fn_metadata.arg_model.model_rebuild(force=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Governed Tool Implementations
# ---------------------------------------------------------------------------

async def tool_get_portfolio(
    portfolio_id: str,
    session_factory=None,
) -> Dict[str, Any]:
    """
    Retrieve one portfolio and its associated holdings by ID.
    Validates identifier and raises structured error if not found.
    """
    args = GetPortfolioArgs(portfolio_id=portfolio_id)
    factory = session_factory or async_session_factory

    async with audit_tool_call("get_portfolio", {"portfolio_id": args.portfolio_id}) as cid:
        async with factory() as session:
            portfolio_service = PortfolioService(session)
            portfolio = await portfolio_service.get_portfolio(args.portfolio_id)
            if not portfolio:
                raise ToolError(
                    f"[{MCPErrorCode.PORTFOLIO_NOT_FOUND.value}] "
                    f"Portfolio with ID '{args.portfolio_id}' not found. (CID: {cid})"
                )

            detail = PortfolioDetailResponse.model_validate(portfolio)
            return detail.model_dump(mode="json")


async def tool_list_portfolios(
    is_sample: Optional[bool] = None,
    session_factory=None,
) -> Dict[str, Any]:
    """
    List portfolio summaries with optional sample/demo filtering.
    """
    args = ListPortfoliosArgs(is_sample=is_sample)
    factory = session_factory or async_session_factory

    async with audit_tool_call("list_portfolios", {"is_sample": args.is_sample}) as _:
        async with factory() as session:
            portfolio_service = PortfolioService(session)
            portfolios = await portfolio_service.list_portfolios(is_sample=args.is_sample)
            return {
                "portfolios": [p.model_dump(mode="json") for p in portfolios],
                "total_count": len(portfolios),
            }


async def tool_get_market_snapshot(
    symbols: List[str],
    exchange: str = "NSE",
    market_data_service: Optional[MarketDataService] = None,
) -> Dict[str, Any]:
    """
    Retrieve current market quotes for a non-empty, bounded list of symbols.
    Preserves simulation, cache freshness, staleness, and unpriced indicators.
    """
    args = GetMarketSnapshotArgs(symbols=symbols, exchange=exchange)
    md_service = market_data_service or MarketDataService()

    async with audit_tool_call(
        "get_market_snapshot", {"symbols": args.symbols, "exchange": args.exchange}
    ) as _:
        quotes_resp = await md_service.get_quotes(symbols=args.symbols, exchange=args.exchange)
        return quotes_resp.model_dump(mode="json")


async def tool_search_news(
    symbols: Optional[List[str]] = None,
    limit: int = 10,
    news_service: Optional[NewsService] = None,
) -> Dict[str, Any]:
    """
    Retrieve financial news for symbols or general market news.
    Preserves simulation disclaimers and source attribution.
    """
    args = SearchNewsArgs(symbols=symbols, limit=limit)
    n_service = news_service or NewsService()

    async with audit_tool_call("search_news", {"symbols": args.symbols, "limit": args.limit}) as _:
        if args.symbols:
            news_resp = await n_service.get_news_for_symbols(symbols=args.symbols, limit=args.limit)
        else:
            news_resp = await n_service.get_market_news(limit=args.limit)
        return news_resp.model_dump(mode="json")


async def tool_calculate_portfolio_metrics(
    portfolio_id: str,
    session_factory=None,
    market_data_service: Optional[MarketDataService] = None,
) -> Dict[str, Any]:
    """
    Calculate comprehensive portfolio metrics: valuation, allocation,
    concentration, sector exposure, completeness, and historical risk status.
    """
    args = CalculatePortfolioMetricsArgs(portfolio_id=portfolio_id)
    factory = session_factory or async_session_factory

    async with audit_tool_call("calculate_portfolio_metrics", {"portfolio_id": args.portfolio_id}) as cid:
        async with factory() as session:
            analytics_service = AnalyticsService(session=session, market_data_service=market_data_service)
            analytics = await analytics_service.calculate_portfolio_analytics(args.portfolio_id)
            if not analytics:
                raise ToolError(
                    f"[{MCPErrorCode.PORTFOLIO_NOT_FOUND.value}] "
                    f"Portfolio with ID '{args.portfolio_id}' not found. (CID: {cid})"
                )
            return analytics.model_dump(mode="json")


async def tool_score_portfolio_risk(
    portfolio_id: str,
    session_factory=None,
    market_data_service: Optional[MarketDataService] = None,
) -> Dict[str, Any]:
    """
    Return portfolio risk assessment with 4 component scores, methodology scope,
    and supporting explainable insights.
    """
    args = ScorePortfolioRiskArgs(portfolio_id=portfolio_id)
    factory = session_factory or async_session_factory

    async with audit_tool_call("score_portfolio_risk", {"portfolio_id": args.portfolio_id}) as cid:
        async with factory() as session:
            analytics_service = AnalyticsService(session=session, market_data_service=market_data_service)
            analytics = await analytics_service.calculate_portfolio_analytics(args.portfolio_id)
            if not analytics:
                raise ToolError(
                    f"[{MCPErrorCode.PORTFOLIO_NOT_FOUND.value}] "
                    f"Portfolio with ID '{args.portfolio_id}' not found. (CID: {cid})"
                )

            insights_resp = await analytics_service.get_portfolio_insights(args.portfolio_id)
            insights = insights_resp.insights if insights_resp else []

            response = PortfolioRiskScoreResponse(
                portfolio_id=args.portfolio_id,
                risk_assessment=analytics.risk_assessment,
                insights=insights,
                total_insights=len(insights),
                is_sample_portfolio=analytics.is_sample,
                calculated_at=datetime.now(timezone.utc),
            )
            return response.model_dump(mode="json")


async def tool_get_evidence_bundle(
    portfolio_id: str,
    session_factory=None,
    market_data_service: Optional[MarketDataService] = None,
) -> Dict[str, Any]:
    """
    Compose portfolio details, market quotes, analytics, risk assessment,
    and insights into a unified bounded evidence bundle for AI reasoning.
    Avoids duplicating financial calculations and handles partial data honestly.
    """
    args = GetEvidenceBundleArgs(portfolio_id=portfolio_id)
    factory = session_factory or async_session_factory
    md_service = market_data_service or MarketDataService()

    async with audit_tool_call("get_evidence_bundle", {"portfolio_id": args.portfolio_id}) as cid:
        async with factory() as session:
            portfolio_service = PortfolioService(session)
            portfolio = await portfolio_service.get_portfolio(args.portfolio_id)
            if not portfolio:
                raise ToolError(
                    f"[{MCPErrorCode.PORTFOLIO_NOT_FOUND.value}] "
                    f"Portfolio with ID '{args.portfolio_id}' not found. (CID: {cid})"
                )

            analytics_service = AnalyticsService(session=session, market_data_service=md_service)
            analytics = await analytics_service.calculate_portfolio_analytics(args.portfolio_id)
            if not analytics:
                raise ToolError(
                    f"[{MCPErrorCode.PORTFOLIO_NOT_FOUND.value}] "
                    f"Failed to calculate analytics for portfolio '{args.portfolio_id}'. (CID: {cid})"
                )

            symbols = [h.symbol for h in portfolio.holdings] if portfolio.holdings else []
            if symbols:
                unique_symbols = sorted(list(set(symbols)))
                market_snapshot = await md_service.get_quotes(unique_symbols)
            else:
                market_snapshot = BatchQuotesResponse(
                    quotes={},
                    total_symbols=0,
                    cache_hits_count=0,
                    cache_misses_count=0,
                    fetched_at=datetime.now(timezone.utc),
                )

            insights_resp = await analytics_service.get_portfolio_insights(args.portfolio_id)
            insights = insights_resp.insights if insights_resp else []

            has_missing = analytics.completeness.unpriced_holdings_count > 0
            has_stale = any(q.is_stale for q in market_snapshot.quotes.values())

            warning = None
            if has_missing:
                warning = (
                    f"Portfolio contains {analytics.completeness.unpriced_holdings_count} unpriced "
                    f"holding(s). Valuation and concentration reflect priced assets only."
                )

            metadata = EvidenceBundleMetadata(
                generated_at=datetime.now(timezone.utc),
                completeness_status=analytics.status,
                has_missing_prices=has_missing,
                has_stale_data=has_stale,
                is_simulated=True,
                data_status=analytics.historical_risk.data_status if analytics.historical_risk else "INSUFFICIENT_HISTORY",
                partial_data_warning=warning,
            )

            bundle = EvidenceBundle(
                portfolio_id=args.portfolio_id,
                portfolio=PortfolioDetailResponse.model_validate(portfolio),
                market_snapshot=market_snapshot,
                analytics=analytics,
                risk_assessment=analytics.risk_assessment,
                insights=insights,
                metadata=metadata,
            )
            return bundle.model_dump(mode="json")


async def tool_generate_portfolio_ai_insights(
    portfolio_id: str,
    include_news: bool = True,
    news_limit: int = 10,
    session_factory=None,
    market_data_service: Optional[MarketDataService] = None,
    news_service: Optional[NewsService] = None,
    ai_provider: Optional[BaseAIProvider] = None,
    ai_reasoning_service_factory=None,
) -> Dict[str, Any]:
    """
    Generate evidence-grounded AI insights, key drivers, risk alerts,
    and claim verification status for a portfolio.
    Reuses existing AIReasoningService with deterministic demo provider by default.
    """
    args = GeneratePortfolioAIInsightsArgs(
        portfolio_id=portfolio_id,
        include_news=include_news,
        news_limit=news_limit,
    )
    factory = session_factory or async_session_factory

    async with audit_tool_call(
        "generate_portfolio_ai_insights",
        {
            "portfolio_id": args.portfolio_id,
            "include_news": args.include_news,
            "news_limit": args.news_limit,
        },
    ) as cid:
        async with factory() as session:
            if ai_reasoning_service_factory:
                reasoning_service = ai_reasoning_service_factory(session)
            else:
                reasoning_service = AIReasoningService(
                    session=session,
                    provider=ai_provider,
                    market_data_service=market_data_service,
                    news_service=news_service,
                )

            try:
                report = await reasoning_service.generate_portfolio_insights(
                    portfolio_id=args.portfolio_id,
                    include_news=args.include_news,
                    news_limit=args.news_limit,
                )
            except AIProviderError:
                raise ToolError(
                    f"[{MCPErrorCode.PROVIDER_ERROR.value}] "
                    f"AI reasoning provider failed to generate insights. (CID: {cid})"
                ) from None
            except AIMalformedOutputError:
                raise ToolError(
                    f"[{MCPErrorCode.PROVIDER_ERROR.value}] "
                    f"AI reasoning provider produced invalid report structure. (CID: {cid})"
                ) from None
            except AIReasoningError as exc:
                raise ToolError(
                    f"[{MCPErrorCode.INTERNAL_ERROR.value}] "
                    f"AI reasoning pipeline error: {exc.message}. (CID: {cid})"
                ) from None
            except Exception as exc:
                logger.error(
                    "Unexpected failure in tool_generate_portfolio_ai_insights for %s: %s",
                    args.portfolio_id,
                    exc,
                    exc_info=True,
                )
                raise ToolError(
                    f"[{MCPErrorCode.INTERNAL_ERROR.value}] "
                    f"Failed to generate AI insights for portfolio '{args.portfolio_id}'. (CID: {cid})"
                ) from None

            if not report:
                raise ToolError(
                    f"[{MCPErrorCode.PORTFOLIO_NOT_FOUND.value}] "
                    f"Portfolio with ID '{args.portfolio_id}' not found. (CID: {cid})"
                )

            return report.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Tool Registration & Governance Allowlist Enforcement
# ---------------------------------------------------------------------------

def register_mcp_tools(
    server: FastMCP,
    session_factory=None,
    market_data_service: Optional[MarketDataService] = None,
    news_service: Optional[NewsService] = None,
    ai_provider: Optional[BaseAIProvider] = None,
    ai_reasoning_service_factory=None,
) -> None:
    """
    Registers exactly the eight approved read-only tools on the FastMCP server.
    Applies strict read-only annotations and forbids unexpected argument keys.
    """

    @server.tool(
        name="get_portfolio",
        description="Retrieve one portfolio and its associated holdings by portfolio ID.",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    async def get_portfolio(portfolio_id: str) -> Dict[str, Any]:
        return await tool_get_portfolio(portfolio_id=portfolio_id, session_factory=session_factory)

    @server.tool(
        name="list_portfolios",
        description="List portfolio summaries with optional sample/demo filtering.",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    async def list_portfolios(is_sample: Optional[bool] = None) -> Dict[str, Any]:
        return await tool_list_portfolios(is_sample=is_sample, session_factory=session_factory)

    @server.tool(
        name="get_market_snapshot",
        description="Retrieve current market quotes for a bounded list of symbols, preserving simulation and cache freshness flags.",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    async def get_market_snapshot(symbols: List[str], exchange: str = "NSE") -> Dict[str, Any]:
        return await tool_get_market_snapshot(
            symbols=symbols, exchange=exchange, market_data_service=market_data_service
        )

    @server.tool(
        name="search_news",
        description="Retrieve financial news for symbols or market overview, preserving educational simulation disclaimers.",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    async def search_news(symbols: Optional[List[str]] = None, limit: int = 10) -> Dict[str, Any]:
        return await tool_search_news(symbols=symbols, limit=limit, news_service=news_service)

    @server.tool(
        name="calculate_portfolio_metrics",
        description="Calculate comprehensive portfolio metrics: valuation, allocation, concentration, sector exposure, completeness, and historical risk status.",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    async def calculate_portfolio_metrics(portfolio_id: str) -> Dict[str, Any]:
        return await tool_calculate_portfolio_metrics(
            portfolio_id=portfolio_id,
            session_factory=session_factory,
            market_data_service=market_data_service,
        )

    @server.tool(
        name="score_portfolio_risk",
        description="Return portfolio risk assessment across 4 deterministic dimensions with component scores and supporting insights.",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    async def score_portfolio_risk(portfolio_id: str) -> Dict[str, Any]:
        return await tool_score_portfolio_risk(
            portfolio_id=portfolio_id,
            session_factory=session_factory,
            market_data_service=market_data_service,
        )

    @server.tool(
        name="get_evidence_bundle",
        description="Compose portfolio details, market quotes, analytics, risk assessment, and insights into a unified bounded evidence bundle for AI reasoning.",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    async def get_evidence_bundle(portfolio_id: str) -> Dict[str, Any]:
        return await tool_get_evidence_bundle(
            portfolio_id=portfolio_id,
            session_factory=session_factory,
            market_data_service=market_data_service,
        )

    @server.tool(
        name="generate_portfolio_ai_insights",
        description="Generate evidence-grounded AI insights, key drivers, risk alerts, and claim verification status for a portfolio.",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    async def generate_portfolio_ai_insights(
        portfolio_id: str,
        include_news: bool = True,
        news_limit: int = 10,
    ) -> Dict[str, Any]:
        return await tool_generate_portfolio_ai_insights(
            portfolio_id=portfolio_id,
            include_news=include_news,
            news_limit=news_limit,
            session_factory=session_factory,
            market_data_service=market_data_service,
            news_service=news_service,
            ai_provider=ai_provider,
            ai_reasoning_service_factory=ai_reasoning_service_factory,
        )

    # Forbid unexpected argument keys on all registered tools
    for tool_name in APPROVED_TOOLS:
        _rebuild_tool_arg_model_forbid_extra(server, tool_name)


async def execute_governed_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    session_factory=None,
    market_data_service: Optional[MarketDataService] = None,
    news_service: Optional[NewsService] = None,
    ai_provider: Optional[BaseAIProvider] = None,
    ai_reasoning_service_factory=None,
) -> Any:
    """
    Direct in-process tool executor enforcing the approved tool allowlist.
    Rejects any unapproved or mutating tool before execution.
    """
    if tool_name not in APPROVED_TOOLS:
        async with audit_tool_call(tool_name, arguments) as _:
            raise ToolError(
                f"[{MCPErrorCode.UNAUTHORIZED_TOOL.value}] "
                f"Tool '{tool_name}' is not in the approved tool allowlist. "
                f"Mutating, trading, or unapproved operations are strictly prohibited."
            )

    if tool_name == "get_portfolio":
        args = GetPortfolioArgs.model_validate(arguments)
        return await tool_get_portfolio(portfolio_id=args.portfolio_id, session_factory=session_factory)
    elif tool_name == "list_portfolios":
        args = ListPortfoliosArgs.model_validate(arguments)
        return await tool_list_portfolios(is_sample=args.is_sample, session_factory=session_factory)
    elif tool_name == "get_market_snapshot":
        args = GetMarketSnapshotArgs.model_validate(arguments)
        return await tool_get_market_snapshot(
            symbols=args.symbols, exchange=args.exchange, market_data_service=market_data_service
        )
    elif tool_name == "search_news":
        args = SearchNewsArgs.model_validate(arguments)
        return await tool_search_news(symbols=args.symbols, limit=args.limit, news_service=news_service)
    elif tool_name == "calculate_portfolio_metrics":
        args = CalculatePortfolioMetricsArgs.model_validate(arguments)
        return await tool_calculate_portfolio_metrics(
            portfolio_id=args.portfolio_id,
            session_factory=session_factory,
            market_data_service=market_data_service,
        )
    elif tool_name == "score_portfolio_risk":
        args = ScorePortfolioRiskArgs.model_validate(arguments)
        return await tool_score_portfolio_risk(
            portfolio_id=args.portfolio_id,
            session_factory=session_factory,
            market_data_service=market_data_service,
        )
    elif tool_name == "get_evidence_bundle":
        args = GetEvidenceBundleArgs.model_validate(arguments)
        return await tool_get_evidence_bundle(
            portfolio_id=args.portfolio_id,
            session_factory=session_factory,
            market_data_service=market_data_service,
        )
    elif tool_name == "generate_portfolio_ai_insights":
        args = GeneratePortfolioAIInsightsArgs.model_validate(arguments)
        return await tool_generate_portfolio_ai_insights(
            portfolio_id=args.portfolio_id,
            include_news=args.include_news,
            news_limit=args.news_limit,
            session_factory=session_factory,
            market_data_service=market_data_service,
            news_service=news_service,
            ai_provider=ai_provider,
            ai_reasoning_service_factory=ai_reasoning_service_factory,
        )
    else:
        raise ToolError(f"[{MCPErrorCode.UNAUTHORIZED_TOOL.value}] Unhandled tool '{tool_name}'")
