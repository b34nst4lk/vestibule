---
title: Select MCP library or implementation approach
status: closed
labels: []
parent: .scratch/plugin-mcp-server-map.md
resolved: Use official `mcp` package from Anthropic
---

## Question

Which MCP library should we use, or should we implement the protocol directly?

## Resolution

**Decision:** Use the official [`mcp`](https://pypi.org/project/mcp/) package from Anthropic.

**Why:**
- Mature (23k+ stars, official Anthropic backing)
- Both stdio and Streamable HTTP/SSE transports built-in
- `FastMCP` API provides clean decorator-based tool registration
- Maps cleanly to pluggy hook system where each plugin registers tools

**Install:** `uv add "mcp[cli]"`

**Constraint for dependents:** `mcp>=1.27,<2`

See `.scratch/research-mcp-library.md` for full research.
