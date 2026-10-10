from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

class DatabaseHealth(BaseModel):
    status: str
    engine: str = "sqlite"
    journal_mode: str | None = None
    foreign_keys_enabled: bool | None = None
    error: str | None = None

class HealthResponse(BaseModel):
    status: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    environment: str
    database: DatabaseHealth

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)

class ErrorEnvelope(BaseModel):
    success: bool = False
    error: ErrorDetail
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

def build_error_envelope(code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return ErrorEnvelope(
        success=False,
        error=ErrorDetail(
            code=code,
            message=message,
            details=details or [],
        ),
        timestamp=datetime.now(timezone.utc).isoformat(),
    ).model_dump()
