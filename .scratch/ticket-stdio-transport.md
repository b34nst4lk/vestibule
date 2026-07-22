---
title: Implement stdio transport for MCP
status: closed
labels: []
parent: .scratch/plugin-mcp-server-map.md
blocked_by:
  - .scratch/ticket-hook-specs.md
resolved: Implemented JSON-RPC 2.0 over stdin/stdout with 9 request handlers, FastMCP integration, and 29 passing tests
---

## Question

How is the stdio transport implemented?

Decisions needed:
- JSON-RPC message format over stdin/stdout
- How messages map to plugin hook calls
- Error handling and response formatting

Output: Working stdio transport that connects to the plugin system.

## Resolution

### Implementation

Created `portcullis/transports/stdio.py` with:

| Component | Description |
|-----------|-------------|
| `StdioTransport` class | Async JSON-RPC 2.0 server over stdin/stdout |
| Request handlers | 9 handlers: initialize, initialized, tools/list, tools/call, resources/list, resources/read, prompts/list, prompts/get, ping |
| Error handling | JSONRPCError with standard codes (-32700 to -32603) |
| FastMCP integration | Delegates tool calls to FastMCP server's `call_tool` method |

### JSON-RPC Message Format

```json
// Request
{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "send_email", "arguments": {...}}, "id": 1}

// Response
{"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "..."}], "isError": false}}

// Error
{"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "Method not found"}}
```

### Files Created

```
portcullis/transports/
  __init__.py
  stdio.py              # Main transport implementation
tests/transports/
  test_stdio.py         # 29 tests
```

### Tests

29 tests covering:
- JSONRPCError exception
- Transport initialization
- Request processing (invalid version, missing method, unknown method)
- All 9 request handlers
- Response/error sending
- Full integration cycle

### Usage

```bash
# Run the server
uv run python main.py

# Server reads JSON-RPC from stdin, writes responses to stdout
# Logs and diagnostics go to stderr
```
