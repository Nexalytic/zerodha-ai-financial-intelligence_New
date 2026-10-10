from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query
from app.schemas.market_data import NewsResponse
from app.services.news_service import NewsService

router = APIRouter()

_default_news_service = NewsService()

def get_news_service() -> NewsService:
    return _default_news_service

@router.get("", response_model=NewsResponse)
async def get_financial_news(
    symbols: Annotated[Optional[str], Query(description="Optional comma-separated ticker symbols to filter news")] = None,
    limit: Annotated[int, Query(ge=1, le=50, description="Maximum number of articles to return")] = 10,
    service: NewsService = Depends(get_news_service),
) -> NewsResponse:
    """
    Get simulated financial news articles, optionally filtered by stock symbols.
    Articles are explicitly labelled simulated and attributed to the demo engine.
    """
    if symbols:
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        return await service.get_news_for_symbols(symbols=symbol_list, limit=limit)
    return await service.get_market_news(limit=limit)
