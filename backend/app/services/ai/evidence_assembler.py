from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.schemas.ai_reasoning import PortfolioEvidenceBundle
from app.schemas.analytics import (
    HistoricalRiskMetrics,
    PortfolioAnalyticsResponse,
    ValuationStatus,
)
from app.schemas.market_data import BatchQuotesResponse, NewsArticle, Quote, QuoteStatus
from app.services.analytics_service import AnalyticsService
from app.services.market_data_service import MarketDataService
from app.services.news_service import NewsService
from app.services.portfolio_service import PortfolioService


class EvidenceAssemblerService:
    """
    Evidence Assembly & Freshness Service for AI reasoning and financial intelligence.
    Orchestrates portfolio lookup, deterministic analytics, market quotes, news,
    and provenance metadata into an immutable, grounded PortfolioEvidenceBundle.

    Guarantees:
    - Never fabricates metrics, prices, news, or sources.
    - Preserves provider attribution, simulation flags, and cache timestamps.
    - Explicitly distinguishes unavailable data from zero values.
    - Gracefully handles empty, unpriced, partial, stale, or unavailable data states.
    - Treats retrieved news as untrusted data, never instructions.
    """

    def __init__(
        self,
        session: AsyncSession,
        market_data_service: Optional[MarketDataService] = None,
        news_service: Optional[NewsService] = None,
        analytics_service: Optional[AnalyticsService] = None,
        portfolio_service: Optional[PortfolioService] = None,
    ):
        self.session = session
        self.market_data_service = market_data_service or MarketDataService()
        self.news_service = news_service or NewsService()
        self.portfolio_service = portfolio_service or PortfolioService(session)
        self.analytics_service = analytics_service or AnalyticsService(
            session=session,
            market_data_service=self.market_data_service,
        )

    async def assemble_portfolio_evidence(
        self,
        portfolio_id: str,
        include_news: bool = True,
        news_limit: int = 10,
    ) -> Optional[PortfolioEvidenceBundle]:
        """
        Assemble comprehensive evidence bundle for a portfolio by ID.
        Returns None if portfolio does not exist or analytics cannot be computed.
        """
        portfolio = await self.portfolio_service.get_portfolio(portfolio_id)
        if portfolio is None:
            return None

        analytics = await self.analytics_service.calculate_portfolio_analytics(portfolio_id)
        if analytics is None:
            return None

        # Build market snapshot quotes using holding exchange context
        holdings = portfolio.holdings or []
        quotes: Dict[str, Quote] = {}
        for h in holdings:
            sym = h.symbol.strip().upper() if h.symbol else ""
            if sym and sym not in quotes:
                exchange = (h.exchange or "NSE").strip().upper()
                quotes[sym] = await self.market_data_service.get_quote(sym, exchange=exchange)

        cache_hits_count = sum(
            1 for q in quotes.values()
            if q.cache_hit and not q.is_stale and q.status != QuoteStatus.ERROR
        )
        cache_misses_count = len(quotes) - cache_hits_count

        market_snapshot = BatchQuotesResponse(
            quotes=quotes,
            total_symbols=len(quotes),
            cache_hits_count=cache_hits_count,
            cache_misses_count=cache_misses_count,
            fetched_at=datetime.now(timezone.utc),
        )

        # Retrieve news articles if requested and portfolio has active symbols
        news_articles: List[NewsArticle] = []
        unique_symbols = list(quotes.keys())
        if include_news and unique_symbols:
            try:
                news_resp = await self.news_service.get_news_for_symbols(unique_symbols, limit=news_limit)
                news_articles = news_resp.articles or []
            except Exception as exc:
                logger.warning(
                    "News retrieval failed during evidence assembly for portfolio %s: %s",
                    portfolio_id,
                    exc,
                )
                news_articles = []

        now = datetime.now(timezone.utc)
        logger.info(
            "Assembled portfolio evidence bundle for portfolio %s (holdings: %d, priced: %d, news: %d)",
            portfolio_id,
            analytics.completeness.total_holdings_count,
            analytics.completeness.priced_holdings_count,
            len(news_articles),
        )

        return PortfolioEvidenceBundle(
            portfolio_id=portfolio.id,
            portfolio_name=portfolio.name,
            is_sample_portfolio=portfolio.is_sample,
            valuation=analytics.valuation,
            completeness=analytics.completeness,
            concentration=analytics.concentration,
            sector_allocations=analytics.sector_allocations,
            risk_assessment=analytics.risk_assessment,
            market_snapshot=market_snapshot,
            news_articles=news_articles,
            historical_risk=analytics.historical_risk,
            evidence_timestamp=now,
        )

    async def assemble_from_analytics(
        self,
        analytics: PortfolioAnalyticsResponse,
        symbols_with_exchange: Optional[List[Tuple[str, str]]] = None,
        include_news: bool = True,
        news_limit: int = 10,
    ) -> PortfolioEvidenceBundle:
        """
        Assemble evidence bundle directly from existing analytics response and symbol context.
        """
        quotes: Dict[str, Quote] = {}
        target_pairs = symbols_with_exchange or [
            (h.symbol, h.exchange) for h in analytics.holdings
        ]

        for sym, ex in target_pairs:
            cleaned_sym = sym.strip().upper() if sym else ""
            if cleaned_sym and cleaned_sym not in quotes:
                quotes[cleaned_sym] = await self.market_data_service.get_quote(
                    cleaned_sym, exchange=(ex or "NSE").strip().upper()
                )

        cache_hits_count = sum(
            1 for q in quotes.values()
            if q.cache_hit and not q.is_stale and q.status != QuoteStatus.ERROR
        )
        cache_misses_count = len(quotes) - cache_hits_count

        market_snapshot = BatchQuotesResponse(
            quotes=quotes,
            total_symbols=len(quotes),
            cache_hits_count=cache_hits_count,
            cache_misses_count=cache_misses_count,
            fetched_at=datetime.now(timezone.utc),
        )

        news_articles: List[NewsArticle] = []
        unique_symbols = list(quotes.keys())
        if include_news and unique_symbols:
            try:
                news_resp = await self.news_service.get_news_for_symbols(unique_symbols, limit=news_limit)
                news_articles = news_resp.articles or []
            except Exception as exc:
                logger.warning(
                    "News retrieval failed during evidence assembly from analytics for portfolio %s: %s",
                    analytics.portfolio_id,
                    exc,
                )
                news_articles = []

        now = datetime.now(timezone.utc)

        return PortfolioEvidenceBundle(
            portfolio_id=analytics.portfolio_id,
            portfolio_name=analytics.portfolio_name,
            is_sample_portfolio=analytics.is_sample,
            valuation=analytics.valuation,
            completeness=analytics.completeness,
            concentration=analytics.concentration,
            sector_allocations=analytics.sector_allocations,
            risk_assessment=analytics.risk_assessment,
            market_snapshot=market_snapshot,
            news_articles=news_articles,
            historical_risk=analytics.historical_risk,
            evidence_timestamp=now,
        )
