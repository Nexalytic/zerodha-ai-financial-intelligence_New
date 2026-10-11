from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import RequestLoggingMiddleware, logger, sanitize_log_message
from app.db.base import Base
from app.db.session import close_database, engine, ping_database
from app.schemas.common import ErrorDetail, ErrorEnvelope, build_error_envelope
import app.models  # Register all models on Base.metadata

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup lifecycle hook: verify database connectivity and initialize tables
    logger.info("Starting up Zerodha AI Intelligence Backend...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        db_status = await ping_database()
        logger.info(
            f"Database connectivity verified (WAL: {db_status.get('journal_mode')}, "
            f"Foreign Keys: {db_status.get('foreign_keys')})"
        )
    except Exception as exc:
        logger.error(f"Database startup verification failed: {exc}", exc_info=True)
    yield
    # Shutdown lifecycle hook: cleanly dispose database engine and connections
    logger.info("Shutting down Zerodha AI Intelligence Backend...")
    await close_database()
    logger.info("Database engine disposed cleanly.")

app = FastAPI(
    title="Zerodha AI Financial Intelligence Platform API",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Structured request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Strict CORS middleware (stateless REST: allow_credentials=False)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# API router
app.include_router(api_router, prefix="/api/v1")



@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    code_map = {
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        403: "FORBIDDEN",
        401: "UNAUTHORIZED",
    }
    error_code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_envelope(code=error_code, message=str(exc.detail)),
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = []
    for error in exc.errors():
        loc = " -> ".join(str(item) for item in error.get("loc", []))
        details.append({
            "location": loc,
            "message": error.get("msg", "Invalid value"),
            "type": error.get("type", "value_error"),
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_error_envelope(
            code="VALIDATION_ERROR",
            message="Request input validation failed",
            details=details,
        ),
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    sanitized_exc = sanitize_log_message(str(exc))
    logger.error(
        f"Unhandled server error on {request.method} {request.url.path}: {sanitized_exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=build_error_envelope(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal server error occurred.",
        ),
    )
