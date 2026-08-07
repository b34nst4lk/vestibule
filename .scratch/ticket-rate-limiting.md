---
title: Implement per-tool rate limiting
status: closed
labels: [wayfinder:security]
parent: .scratch/portcullis-hardening-map.md
blocked_by: []
resolved: Token-bucket rate limiter implemented in portcullis/rate_limit.py, wired into shared handle_tools_call, configurable per-tool via TOML
---

## Question

How should per-tool rate limiting be implemented without session tracking overhead?

## Resolution Notes

**Decision:**
- Per-tool limits only (no per-session tracking)
- Configurable via TOML: `[tool.portcullis.rate_limits]` with tool_name: limit pairs
- Default: 60 requests/minute per tool (configurable)
- Token bucket algorithm
- Return error content with `isError: true` when rate limited

**Implemented:**
- `portcullis/rate_limit.py` — thread-safe `TokenBucket` + `RateLimiter`, module-level shared limiter
- `config.py` — parses `[tool.portcullis.rate_limits]` into `Config.rate_limits`
- `transports/common.py` — `handle_tools_call` checks the limiter before executing; on `RateLimitExceeded` returns `isError: true` with a "Try again in N seconds" message and audit-logs the rejection
- `cli.py` — `serve` configures the shared limiter from `cfg.rate_limits` at startup
- Tests: `tests/test_rate_limit.py` (token bucket + limiter) and `tests/test_config.py` (TOML parsing/merge)

**Next Step**

None — resolved. 101 tests pass, ruff clean.
