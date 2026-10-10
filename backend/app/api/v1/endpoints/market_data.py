from typing import Annotated
from fastapi import APIRouter, Depends, Query
from app.schemas.market_data import BatchQuotesResponse, Quote
from app.services.market_data_service import MarketDataService

router = APIRouter()

# Default singleton service instance for request routing
_default_market_data_service = MarketDataService()

def get_market_data_service() -> MarketDataService:
    return _default_market_data_service

@router.get("/quote", response_model=Quote)
async def get_single_quote(
    symbol: Annotated[str, Query(min_length=1, max_length=20, description="Ticker symbol (e.g. RELIANCE)")],
    exchange: Annotated[str, Query(min_length=1, max_length=10, description="Exchange (NSE or BSE)")] = "NSE",
    service: MarketDataService = Depends(get_market_data_service),
) -> Quote:
    """
    Get a market quote for a single symbol.
    Returns simulated price data for demo symbols, or current_price=null for unknown symbols.
    """
    return await service.get_quote(symbol=symbol, exchange=exchange)

@router.get("/quotes", response_model=BatchQuotesResponse)
async def get_batch_quotes(
    symbols: Annotated[str, Query(min_length=1, description="Comma-separated ticker symbols (e.g. RELIANCE,TCS)")],
    exchange: Annotated[str, Query(min_length=1, max_length=10, description="Exchange (NSE or BSE)")] = "NSE",
    service: MarketDataService = Depends(get_market_data_service),
) -> BatchQuotesResponse:
    """
    Get market quotes for multiple symbols with batch and per-quote cache metrics.
    """
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    return await service.get_quotes(symbols=symbol_list, exchange=exchange)
