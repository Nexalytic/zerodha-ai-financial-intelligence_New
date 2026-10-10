import logging
import re
import time
from typing import Callable, Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.schemas.common import build_error_envelope

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Silence noisy HTTP client loggers to prevent leaking query parameters in request URLs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger("zerodha_backend")

def sanitize_log_message(message: str, secret: Optional[str] = None) -> str:
    """
    Sanitize text to redact any sensitive query parameters, keys, or secret tokens.
    """
    if not message:
        return ""
    sanitized = str(message)
    if secret and len(secret) >= 3:
        sanitized = sanitized.replace(secret, "[REDACTED]")
    return re.sub(
        r"(apikey|api_key|key|token|secret|password|auth)=([^&\s'\"]+)",
        r"\1=[REDACTED]",
        sanitized,
        flags=re.IGNORECASE,
    )


SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "x-api-key",
    "proxy-authorization",
    "set-cookie",
}

SENSITIVE_QUERY_PARAMS = {
    "key",
    "token",
    "secret",
    "password",
    "api_key",
    "apikey",
    "auth",
}

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        sanitized_params = []
        for key, value in request.query_params.multi_items():
            if key.lower() in SENSITIVE_QUERY_PARAMS:
                sanitized_params.append(f"{key}=[REDACTED]")
            else:
                sanitized_params.append(f"{key}={value}")
        query_str = f"?{'&'.join(sanitized_params)}" if sanitized_params else ""

        client_host = request.client.host if request.client else "unknown"

        logger.info(
            f"--> Incoming {request.method} {request.url.path}{query_str} from {client_host}"
        )

        try:
            response = await call_next(request)
            process_time_ms = (time.perf_counter() - start_time) * 1000.0
            logger.info(
                f"<-- Completed {request.method} {request.url.path} - "
                f"Status: {response.status_code} ({process_time_ms:.2f}ms)"
            )
            return response
        except Exception as exc:
            process_time_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                f"<-- Unhandled error in {request.method} {request.url.path} "
                f"({process_time_ms:.2f}ms): {exc}",
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content=build_error_envelope(
                    code="INTERNAL_SERVER_ERROR",
                    message="An unexpected internal server error occurred.",
                ),
            )
