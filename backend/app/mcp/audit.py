import json
import logging
import re
import sys
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.mcp.schemas import AuditLogRecord, MCPErrorCode

# Sensitive keys that must always be masked in audit logs
SENSITIVE_KEYS = {
    "key",
    "token",
    "secret",
    "password",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "cookie",
    "proxy-authorization",
    "credential",
    "access_token",
    "refresh_token",
}

# Regex pattern to redact secrets embedded inside arbitrary string values (SEC-01)
_SENSITIVE_STRING_PATTERN = re.compile(
    r"(?i)\b(?:bearer\s+[a-z0-9_\-\.]{8,}|(?:api[_-]?key|access[_-]?token|secret|password|auth[_-]?token)\s*[:=]\s*[^\s,;]+)"
)

# Dedicated audit logger writing EXCLUSIVELY to sys.stderr to avoid stdio corruption
_audit_logger = logging.getLogger("zerodha_mcp_audit")
_audit_logger.propagate = False
_audit_logger.setLevel(logging.INFO)

# Ensure handler is attached once to sys.stderr
if not _audit_logger.handlers:
    _stderr_handler = logging.StreamHandler(sys.stderr)
    _stderr_handler.setFormatter(
        logging.Formatter("[%(asctime)s] [MCP_AUDIT] %(message)s")
    )
    _audit_logger.addHandler(_stderr_handler)

# In-memory circular buffer for test inspection and audit diagnostics (max 1000 records)
_audit_buffer: deque[AuditLogRecord] = deque(maxlen=1000)


def sanitize_argument_value(val: Any) -> Any:
    """
    Sanitizes an argument value, ensuring large structures (like holdings lists)
    or sensitive nested dictionaries are safely represented.
    Also redacts sensitive credential patterns embedded in strings (SEC-01).
    """
    if isinstance(val, dict):
        return sanitize_arguments(val)
    elif isinstance(val, (list, tuple, set)):
        # If list contains more than 10 items, summarize length
        items = list(val)
        if len(items) > 10:
            return [sanitize_argument_value(x) for x in items[:5]] + [f"... ({len(items) - 5} more items)"]
        return [sanitize_argument_value(x) for x in items]
    elif isinstance(val, str):
        masked = _SENSITIVE_STRING_PATTERN.sub("[REDACTED]", val)
        if len(masked) > 200:
            return masked[:200] + "... [truncated]"
        return masked
    return val


def sanitize_arguments(args: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Recursively redacts sensitive keys and masks credentials from arguments.
    Ensures full portfolio records or raw tokens are never logged.
    """
    if not args:
        return {}
    sanitized: Dict[str, Any] = {}
    for key, val in args.items():
        key_lower = str(key).lower()
        if any(sens in key_lower for sens in SENSITIVE_KEYS):
            sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = sanitize_argument_value(val)
    return sanitized


def record_audit_entry(
    tool_name: str,
    arguments: Optional[Dict[str, Any]],
    duration_ms: float,
    status: str,
    correlation_id: str,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> AuditLogRecord:
    """
    Creates, logs (to stderr), and stores a structured audit record.
    """
    record = AuditLogRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        correlation_id=correlation_id,
        tool_name=tool_name,
        arguments_sanitized=sanitize_arguments(arguments),
        duration_ms=round(duration_ms, 2),
        status=status,
        error_code=error_code,
        error_message=error_message,
    )

    # Store in diagnostic buffer
    _audit_buffer.append(record)

    # Emit JSON record to stderr
    try:
        json_log = json.dumps(record.model_dump(), default=str)
        _audit_logger.info(json_log)
    except Exception:
        _audit_logger.info(f"Tool {tool_name} status={status} duration={duration_ms:.2f}ms")

    return record


def get_audit_records() -> List[AuditLogRecord]:
    """Returns a snapshot copy of captured audit records."""
    return list(_audit_buffer)


def clear_audit_records() -> None:
    """Clears the in-memory audit record buffer."""
    _audit_buffer.clear()


@asynccontextmanager
async def audit_tool_call(
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Context manager that times tool execution and records an audit log entry
    for both successful calls and errors. Yields the correlation ID.
    """
    cid = correlation_id or str(uuid.uuid4())
    start_time = time.perf_counter()
    status = "SUCCESS"
    err_code: Optional[str] = None
    err_msg: Optional[str] = None

    try:
        yield cid
    except Exception as exc:
        status = "ERROR"
        # Determine error code if tagged
        exc_str = str(exc)
        if any(code.value in exc_str for code in MCPErrorCode):
            for code in MCPErrorCode:
                if code.value in exc_str:
                    err_code = code.value
                    break
            # Governed ToolError messages with tagged error codes are safe, structured messages
            err_msg = exc_str[:300]
        else:
            err_code = MCPErrorCode.INTERNAL_ERROR.value
            # For untagged/unexpected exceptions, avoid logging raw traces/paths/database internals (SEC-02)
            err_msg = "An unexpected internal error occurred."
        raise
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        record_audit_entry(
            tool_name=tool_name,
            arguments=arguments,
            duration_ms=duration_ms,
            status=status,
            correlation_id=cid,
            error_code=err_code,
            error_message=err_msg,
        )
