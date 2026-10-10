from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.db.session import get_db
from app.schemas.common import DatabaseHealth, HealthResponse

router = APIRouter()

@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"model": HealthResponse, "description": "System and database are healthy"},
        503: {"model": HealthResponse, "description": "Database connectivity check failed"},
    },
)
async def health_check(db: AsyncSession = Depends(get_db)):
    iso_timestamp = datetime.now(timezone.utc).isoformat()
    try:
        await db.execute(text("SELECT 1"))
        fk_result = await db.execute(text("PRAGMA foreign_keys;"))
        fk_val = fk_result.scalar()
        jm_result = await db.execute(text("PRAGMA journal_mode;"))
        jm_val = jm_result.scalar()

        data = HealthResponse(
            status="healthy",
            timestamp=iso_timestamp,
            environment=settings.ENVIRONMENT,
            database=DatabaseHealth(
                status="connected",
                engine="sqlite",
                journal_mode=str(jm_val).lower() if jm_val else "unknown",
                foreign_keys_enabled=bool(fk_val),
            ),
        )
        return data
    except Exception as exc:
        data = HealthResponse(
            status="unhealthy",
            timestamp=iso_timestamp,
            environment=settings.ENVIRONMENT,
            database=DatabaseHealth(
                status="disconnected",
                engine="sqlite",
                error="Database connectivity check failed",
            ),
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=data.model_dump(),
        )
