---
title: Implement audit logging infrastructure
status: closed
labels: [wayfinder:security]
parent: .scratch/portcullis-hardening-map.md
blocked_by: []
resolved: Created portcullis/audit.py with JSON logging to stdout, SecretStr masking, 10 tests. Integrated into handle_tools_call in common.py (both transports).
---

## Question

How should the audit logging infrastructure be implemented to log all tool calls with comprehensive detail while masking secrets via Pydantic's SecretStr?

## Resolution Notes

**Implementation:**

Created `portcullis/audit.py` with:
- `log_tool_call()` — Logs tool calls with timestamp, tool_name, arguments, success/failure, result_preview
- `mask_sensitive_data()` — Recursively masks SecretStr values and sensitive keys
- JSON format to stdout via dedicated `portcullis.audit` logger
- Result truncation (500 chars) to avoid log bloat

**Integration:**
- Modified `handle_tools_call()` in `portcullis/transports/common.py` to emit audit logs
- Both stdio and HTTP/SSE transports now log all tool calls
- Session ID supported (currently passed as None — can be extended)

**Plugin author guidance:**
- Exported `SecretStr` from `portcullis.hooks` and `portcullis.__init__`
- Plugin authors can use `SecretStr` for sensitive config fields — automatically masked in logs

**Tests:**
- 10 new tests in `tests/test_audit.py` — all passing
- Covers SecretStr masking, nested dicts, lists, successful/failed calls, truncation

**Files changed:**
- `portcullis/audit.py` — New audit logging module
- `portcullis/transports/common.py` — Integrated audit logging into handle_tools_call
- `portcullis/transports/stdio.py` — Updated to pass session_id (None for stdio)
- `portcullis/transports/http_sse.py` — Updated to pass session_id (None for now)
- `portcullis/hooks.py` — Exported SecretStr for plugin authors
- `portcullis/__init__.py` — Exported SecretStr in public API
- `tests/test_audit.py` — 10 tests for audit logging

**Example log output:**
```json
{
  "event_type": "tool_call",
  "timestamp": "2026-07-24T02:30:00.123456+00:00",
  "tool_name": "send_email",
  "arguments": {"recipient": "alice@example.com", "api_key": "***"},
  "success": true,
  "result_preview": "Email sent successfully",
  "session_id": null
}
```

## Next Step

Audit logging complete. Next: rate limiting or approval workflows.
