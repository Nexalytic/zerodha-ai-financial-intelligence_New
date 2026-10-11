import logging
import re
import time
import traceback
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
    # Redact query parameters and assignments: key=val, api_key=val, etc.
    sanitized = re.sub(
        r"(apikey|api_key|api-key|key|token|secret|password|auth)=([^&\s'\"]+)",
        r"\1=[REDACTED]",
        sanitized,
        flags=re.IGNORECASE,
    )
    # Redact Authorization Bearer header patterns
    sanitized = re.sub(
        r"Bearer\s+[a-zA-Z0-9_\-\.]+",
        "Bearer [REDACTED]",
        sanitized,
        flags=re.IGNORECASE,
    )
    # Redact Groq API keys if embedded
    sanitized = re.sub(
        r"gsk_[a-zA-Z0-9]{20,}",
        "[REDACTED]",
        sanitized,
    )
    return sanitized


class SanitizingLogFilter(logging.Filter):
    """
    Logging filter that intercepts all LogRecord instances before emission,
    sanitizing record messages, arguments, and formatted exception tracebacks.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_log_message(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    sanitize_log_message(str(a)) if isinstance(a, (str, Exception)) else a
                    for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: sanitize_log_message(str(v)) if isinstance(v, (str, Exception)) else v
                    for k, v in record.args.items()
                }
        if record.exc_info and not record.exc_text:
            try:
                tb_lines = traceback.format_exception(*record.exc_info)
                record.exc_text = sanitize_log_message("".join(tb_lines))
            except Exception:
                pass
        elif record.exc_text:
            record.exc_text = sanitize_log_message(record.exc_text)
        return True


# Attach the sanitizing filter to zerodha_backend and root handlers
_sanitizing_filter = SanitizingLogFilter()
logger.addFilter(_sanitizing_filter)
logging.getLogger().addFilter(_sanitizing_filter)
for _h in logging.root.handlers:
    _h.addFilter(_sanitizing_filter)


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
            sanitized_exc = sanitize_log_message(str(exc))
            logger.error(
                f"<-- Unhandled error in {request.method} {request.url.path} "
                f"({process_time_ms:.2f}ms): {sanitized_exc}",
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content=build_error_envelope(
                    code="INTERNAL_SERVER_ERROR",
                    message="An unexpected internal server error occurred.",
                ),
            )
