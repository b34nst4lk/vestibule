---
title: Fix HTTP/SSE session memory leak
status: closed
labels: [wayfinder:code-quality, wayfinder:security]
parent: .scratch/portcullis-hardening-map.md
blocked_by: []
resolved: Implemented SessionInfo dataclass with queue/created_at/last_activity, 100 session hard limit, 5-minute TTL cleanup via background task (60s interval) + lazy cleanup on creation. HTTP 429 returned when limit reached. All 66 tests pass.
---

## Question

How should the HTTP/SSE session memory leak be fixed with hard limits and TTL cleanup?

## Resolution Notes

**Decision:**
- Hard limit: 100 concurrent sessions max
- TTL: 5-minute inactivity timeout
- Return HTTP 429 when session limit reached
- Cleanup: Background task (every 60s) + lazy cleanup on session creation

**Implementation:**
- Added `SessionInfo` dataclass with `queue`, `created_at`, `last_activity`
- Added `is_expired()` and `touch()` methods for TTL tracking
- Added `_cleanup_sessions_periodically()` background task
- Added `_cleanup_expired_sessions()` lazy cleanup method
- Added `_check_session_limit()` to reject new sessions when full
- Updated `_handle_mcp_post` to check limit and store SessionInfo
- Updated `_handle_mcp_sse` to touch session on connect and read
- All 66 tests pass

**Files changed:**
- `portcullis/transports/http_sse.py` — Added SessionInfo, cleanup logic, limit check
