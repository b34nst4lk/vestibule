---
title: Implement HTTP/SSE transport for MCP
status: closed
labels: []
parent: .scratch/plugin-mcp-server-map.md
blocked_by:
  - .scratch/ticket-hook-specs.md
resolved: Implemented Streamable HTTP transport with Starlette, SSE streaming, session management, and 29 tests
---

## Question

How is the HTTP/SSE transport implemented?

Decisions needed:
- HTTP server library choice (e.g., `httpx`, `fastapi`, `aiohttp`)
- SSE stream handling for server→client messages
- Port configuration
- Whether stdio and HTTP share the same request handler

Output: Working HTTP/SSE transport that connects to the same plugin backend as stdio.

## Resolution

### Implementation

Created `portcullis/transports/http_sse.py` with:

| Component | Decision |
|-----------|----------|
| HTTP server | **Starlette** — lightweight, async, built-in SSE support |
| SSE streaming | Server-Sent Events via `StreamingResponse` with `text/event-stream` |
| Session management | In-memory dict mapping session_id → asyncio.Queue |
| Request handlers | Shared with stdio (same 9 handlers) |
| Port configuration | Configurable via CLI (`--port`, default 8080) |

### MCP Streamable HTTP Protocol

```
Client sends POST /mcp:
  {"jsonrpc": "2.0", "method": "tools/call", "params": {...}, "id": 1}

Server responds:
  - 200 OK with JSON-RPC response (synchronous)
  - 202 Accepted + Location header (for SSE streaming)

Client connects GET /mcp?session=<id>:
  SSE stream: data: {"jsonrpc": "2.0", "id": 1, "result": {...}}
```

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/mcp` | POST | Client → server JSON-RPC messages |
| `/mcp?session=<id>` | GET | Server → client SSE stream |
| `/health` | GET | Health check |

### Files Created

```
portcullis/transports/http_sse.py    # Main transport implementation
tests/transports/test_http_sse.py # 29 tests
```

### Dependencies Added

- `starlette>=0.30` — ASGI web framework
- `uvicorn>=0.25` — ASGI server
- `httpx>=0.25` — HTTP client (for tests)

### Usage

```bash
# Run with stdio (default)
python main.py

# Run with HTTP/SSE
python main.py --transport http --port 8080

# Test health endpoint
curl http://localhost:8080/health
```
