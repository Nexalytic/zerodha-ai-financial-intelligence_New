from fastapi import APIRouter
from app.api.v1.endpoints import health, market_data, news, portfolios

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(market_data.router, prefix="/market-data", tags=["Market Data"])
api_router.include_router(news.router, prefix="/news", tags=["News"])
api_router.include_router(portfolios.router, prefix="/portfolios", tags=["Portfolios"])


