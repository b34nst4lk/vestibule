---
title: Implement per-tool rate limiting
status: open
labels: [wayfinder:security]
parent: .scratch/portcullis-hardening-map.md
blocked_by: []
---

## Question

How should per-tool rate limiting be implemented without session tracking overhead?

## Resolution Notes

**Decision:**
- Per-tool limits only (no per-session tracking)
- Configurable via TOML: `[tool.portcullis.rate_limits]` with tool_name: limit pairs
- Default: 60 requests/minute per tool (configurable)
- Use token bucket or sliding window algorithm
- Return JSON-RPC error when rate limited

**Implementation approach:**
1. Add rate limiting dependency (or implement simple token bucket)
2. Store limits in config module
3. Wrap tool call handlers with rate limit check
4. Return error: "Rate limit exceeded for tool X. Try again in Y seconds."

## Next Step

Implement a simple token bucket rate limiter and integrate into the common.py tool call handler.
