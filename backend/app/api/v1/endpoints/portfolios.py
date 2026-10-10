from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.ai_reasoning import AIInsightReport, GenerateAIInsightsRequest
from app.schemas.analytics import PortfolioAnalyticsResponse
from app.schemas.common import build_error_envelope
from app.schemas.insight import PortfolioInsightsResponse
from app.schemas.portfolio import (
    HoldingCreate,
    HoldingResponse,
    PortfolioCreate,
    PortfolioDeleteResponse,
    PortfolioDetailResponse,
    PortfolioImportRequest,
    PortfolioResponse,
    PortfolioUpdate,
    SeedDemoResponse,
)
from app.services.ai import AIReasoningError, AIReasoningService
from app.services.analytics_service import AnalyticsService
from app.services.portfolio_service import PortfolioService

router = APIRouter()

def get_portfolio_service(session: AsyncSession = Depends(get_db)) -> PortfolioService:
    return PortfolioService(session)

def get_analytics_service(session: AsyncSession = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(session)

def get_ai_reasoning_service(session: AsyncSession = Depends(get_db)) -> AIReasoningService:
    return AIReasoningService(session)

@router.get("", response_model=List[PortfolioResponse])
async def list_portfolios(
    is_sample: Annotated[Optional[bool], Query(description="Filter by sample/demo status")] = None,
    service: PortfolioService = Depends(get_portfolio_service),
) -> List[PortfolioResponse]:
    """
    List all portfolios with optional filtering by sample status.
    Returns portfolio summaries including total holdings count.
    """
    return await service.list_portfolios(is_sample=is_sample)

@router.post("", response_model=PortfolioDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    data: PortfolioCreate,
    service: PortfolioService = Depends(get_portfolio_service),
):
    """
    Create a new investment portfolio with optional initial holdings.
    """
    try:
        portfolio = await service.create_portfolio(data)
        return portfolio
    except ValueError as err:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=build_error_envelope(
                code="VALIDATION_ERROR",
                message=str(err),
            ),
        )

@router.post("/import", response_model=PortfolioDetailResponse, status_code=status.HTTP_201_CREATED)
async def import_portfolio(
    data: PortfolioImportRequest,
    service: PortfolioService = Depends(get_portfolio_service),
):
    """
    Import an external portfolio with strict position validation and duplicate checking.
    Executes in a single atomic transaction.
    """
    try:
        portfolio = await service.import_portfolio(data)
        return portfolio
    except ValueError as err:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=build_error_envelope(
                code="VALIDATION_ERROR",
                message=str(err),
            ),
        )

@router.post("/seed-demo", response_model=SeedDemoResponse, status_code=status.HTTP_200_OK)
async def seed_demo_portfolio(
    service: PortfolioService = Depends(get_portfolio_service),
):
    """
    Idempotent and concurrency-safe demo portfolio seeder.
    Creates or retrieves the canonical 'Demo Indian Bluechip Portfolio'.
    """
    portfolio, created = await service.seed_demo_portfolio()
    message = (
        "Demo portfolio seeded successfully."
        if created
        else "Demo portfolio already exists. Returned existing portfolio."
    )
    return SeedDemoResponse(
        portfolio=PortfolioDetailResponse.model_validate(portfolio),
        created=created,
        message=message,
    )

@router.get("/{portfolio_id}", response_model=PortfolioDetailResponse)
async def get_portfolio(
    portfolio_id: str,
    service: PortfolioService = Depends(get_portfolio_service),
):
    """
    Retrieve a single portfolio with all its holdings by ID.
    """
    portfolio = await service.get_portfolio(portfolio_id)
    if portfolio is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=build_error_envelope(
                code="PORTFOLIO_NOT_FOUND",
                message=f"Portfolio with ID '{portfolio_id}' not found",
            ),
        )
    return portfolio

@router.put("/{portfolio_id}", response_model=PortfolioDetailResponse)
async def update_portfolio(
    portfolio_id: str,
    data: PortfolioUpdate,
    service: PortfolioService = Depends(get_portfolio_service),
):
    """
    Update portfolio metadata (name and/or description).
    """
    try:
        portfolio = await service.update_portfolio(portfolio_id, data)
        if portfolio is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=build_error_envelope(
                    code="PORTFOLIO_NOT_FOUND",
                    message=f"Portfolio with ID '{portfolio_id}' not found",
                ),
            )
        return portfolio
    except ValueError as err:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=build_error_envelope(
                code="VALIDATION_ERROR",
                message=str(err),
            ),
        )

@router.delete("/{portfolio_id}", response_model=PortfolioDeleteResponse)
async def delete_portfolio(
    portfolio_id: str,
    service: PortfolioService = Depends(get_portfolio_service),
):
    """
    Delete a portfolio and cascade deletion to all associated holdings.
    """
    deleted = await service.delete_portfolio(portfolio_id)
    if not deleted:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=build_error_envelope(
                code="PORTFOLIO_NOT_FOUND",
                message=f"Portfolio with ID '{portfolio_id}' not found",
            ),
        )
    return PortfolioDeleteResponse(
        id=portfolio_id,
        deleted=True,
        message="Portfolio and associated holdings deleted successfully",
    )

@router.post("/{portfolio_id}/holdings", response_model=HoldingResponse, status_code=status.HTTP_201_CREATED)
async def add_holding(
    portfolio_id: str,
    data: HoldingCreate,
    service: PortfolioService = Depends(get_portfolio_service),
):
    """
    Add a holding to an existing portfolio.
    """
    holding = await service.add_holding(portfolio_id, data)
    if holding is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=build_error_envelope(
                code="PORTFOLIO_NOT_FOUND",
                message=f"Portfolio with ID '{portfolio_id}' not found",
            ),
        )
    return holding

@router.delete("/{portfolio_id}/holdings/{holding_id}", status_code=status.HTTP_200_OK)
async def delete_holding(
    portfolio_id: str,
    holding_id: str,
    service: PortfolioService = Depends(get_portfolio_service),
):
    """
    Delete an individual holding from a portfolio.
    """
    deleted = await service.delete_holding(portfolio_id, holding_id)
    if not deleted:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=build_error_envelope(
                code="HOLDING_NOT_FOUND",
                message=f"Holding with ID '{holding_id}' not found in portfolio '{portfolio_id}'",
            ),
        )
    return {"deleted": True, "id": holding_id}

@router.get("/{portfolio_id}/analytics", response_model=PortfolioAnalyticsResponse)
async def get_portfolio_analytics(
    portfolio_id: str,
    service: AnalyticsService = Depends(get_analytics_service),
):
    """
    Compute comprehensive portfolio analytics, valuations, sector exposure,
    and concentration with graceful missing-price handling.
    """
    analytics = await service.calculate_portfolio_analytics(portfolio_id)
    if analytics is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=build_error_envelope(
                code="PORTFOLIO_NOT_FOUND",
                message=f"Portfolio with ID '{portfolio_id}' not found",
            ),
        )
    return analytics

@router.get("/{portfolio_id}/insights", response_model=PortfolioInsightsResponse)
async def get_portfolio_insights(
    portfolio_id: str,
    service: AnalyticsService = Depends(get_analytics_service),
):
    """
    Compute deterministic, explainable insights and risk observations for a portfolio.
    """
    insights_response = await service.get_portfolio_insights(portfolio_id)
    if insights_response is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=build_error_envelope(
                code="PORTFOLIO_NOT_FOUND",
                message=f"Portfolio with ID '{portfolio_id}' not found",
            ),
        )
    return insights_response


@router.post(
    "/{portfolio_id}/ai-insights",
    response_model=AIInsightReport,
    status_code=status.HTTP_200_OK,
    summary="Generate evidence-grounded AI intelligence insights for a portfolio",
)
async def generate_ai_portfolio_insights(
    portfolio_id: str,
    request_data: Optional[GenerateAIInsightsRequest] = None,
    service: AIReasoningService = Depends(get_ai_reasoning_service),
):
    """
    Generate evidence-grounded, reviewable financial intelligence insights for a portfolio.
    Orchestrates verified evidence assembly, deterministic reasoning, and claim grounding verification.
    """
    opts = request_data or GenerateAIInsightsRequest()
    try:
        report = await service.generate_portfolio_insights(
            portfolio_id=portfolio_id,
            include_news=opts.include_news,
            news_limit=opts.news_limit,
            provider_override=opts.provider_override,
        )
        if report is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=build_error_envelope(
                    code="PORTFOLIO_NOT_FOUND",
                    message=f"Portfolio with ID '{portfolio_id}' not found",
                ),
            )
        return report
    except ValueError as err:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=build_error_envelope(
                code="VALIDATION_ERROR",
                message=str(err),
            ),
        )
    except AIReasoningError as err:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=build_error_envelope(
                code=err.code,
                message=err.message,
            ),
        )


