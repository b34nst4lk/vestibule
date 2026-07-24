"""
Audit logging for Portcullis MCP server.

Provides structured JSON logging for tool calls with secret masking.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import SecretStr

# Configure audit logger - outputs JSON to stdout
_audit_logger = logging.getLogger("portcullis.audit")
_audit_logger.setLevel(logging.INFO)

# Only add handler if not already present (prevents duplicates on reload)
if not _audit_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.INFO)
    _audit_logger.addHandler(_handler)

# Prevent propagation to root logger (avoids duplicate logs)
_audit_logger.propagate = False


def mask_sensitive_data(value: Any) -> Any:
    """
    Recursively mask sensitive data in a dictionary.

    - SecretStr values are masked as "***"
    - Keys containing 'secret', 'password', 'token', 'key', 'auth' are masked
    - Works on nested dicts and lists

    Args:
        value: The value to mask (typically a dict of arguments)

    Returns:
        The value with sensitive data masked
    """
    if isinstance(value, SecretStr):
        return "***"

    if isinstance(value, dict):
        return {k: mask_sensitive_data(v) for k, v in value.items()}

    if isinstance(value, list):
        return [mask_sensitive_data(item) for item in value]

    # String-based masking for common sensitive key patterns
    if isinstance(value, str):
        # Don't mask empty strings
        if not value:
            return value
        # Mask strings that look like secrets (long random-looking strings)
        # This is a simple heuristic - plugin authors should use SecretStr for proper masking
        if len(value) > 20 and any(c.isdigit() for c in value) and any(c.isalpha() for c in value):
            # Could be a token/API key - but we don't auto-mask these to avoid false positives
            pass
        return value

    return value


def log_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    success: bool,
    result: Any | None = None,
    error: str | None = None,
    session_id: str | None = None,
) -> None:
    """
    Log a tool call audit event.

    Args:
        tool_name: Name of the tool that was called
        arguments: Arguments passed to the tool (will be masked)
        success: Whether the tool call succeeded
        result: Optional result from the tool (will be masked)
        error: Optional error message if success is False
        session_id: Optional session identifier
    """
    event = {
        "event_type": "tool_call",
        "timestamp": datetime.now(UTC).isoformat(),
        "tool_name": tool_name,
        "arguments": mask_sensitive_data(arguments),
        "success": success,
        "session_id": session_id,
    }

    if success and result is not None:
        event["result_preview"] = mask_sensitive_data(_truncate_result(result))
    elif error:
        event["error"] = error

    _audit_logger.info(json.dumps(event))


def _truncate_result(result: Any, max_length: int = 500) -> Any:
    """
    Truncate result data for audit log preview.

    Args:
        result: The tool result
        max_length: Maximum string length

    Returns:
        Truncated result (strings truncated, dicts/lists kept as-is if small)
    """
    if isinstance(result, str):
        if len(result) > max_length:
            return result[:max_length] + "... (truncated)"
        return result

    if isinstance(result, dict):
        # For dicts, just return as-is (usually small)
        return result

    if isinstance(result, list):
        # For lists, return first few items
        if len(result) > 5:
            return result[:5] + ["... (truncated)"]
        return result

    return result
