# Research: Python MCP Libraries

## Summary

**Recommended approach:** Use the **official `mcp` package** from Anthropic for production. It's mature, well-documented, and supports both stdio and HTTP/SSE transports out of the box.

---

## Official MCP SDK

### `mcp` (modelcontextprotocol/python-sdk)

- **PyPI:** [`mcp`](https://pypi.org/project/mcp/) — latest stable: 1.28.1
- **GitHub:** [`modelcontextprotocol/python-sdk`](https://github.com/modelcontextprotocol/python-sdk) — 23,617 stars
- **Documentation:** https://py.sdk.modelcontextprotocol.io/
- **License:** MIT
- **Python:** 3.10+

**Version status:**
- v1.x = stable, production-ready
- v2.x = pre-release beta (do not use in production)

**Transports supported:**
- ✅ stdio
- ✅ Streamable HTTP
- ✅ SSE

**Key features:**
- `FastMCP` high-level API for quick server creation
- Tools, resources, and prompts support
- Built-in CLI for development
- Depends on `pydantic-core` (Rust-based)

**Example server:**
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MyServer")

@mcp.tool()
def send_email(recipient: str, body: str) -> str:
    """Send an email to a recipient."""
    # Implementation here
    return f"Email sent to {recipient}"

if __name__ == "__main__":
    mcp.run()  # defaults to stdio, or use transport="streamable-http"
```

**Install:**
```bash
uv add "mcp[cli]"
# or
pip install "mcp[cli]"
```

**Constraint for dependents:** `mcp>=1.27,<2`

---

## Alternatives (No Rust Dependencies)

### `anodize-mcp`

- **GitHub:** [`msradam/anodize-mcp`](https://github.com/msradam/anodize-mcp)
- **License:** MIT
- **Python:** 3.9+

**Key features:**
- Zero Rust dependencies — pure Python only
- FastMCP-compatible API
- Only runtime dependency: `uvicorn`
- Implements MCP protocol revision 2025-06-18

**Best for:** Platforms where pydantic-core can't install (z/OS, s390x, ARMv6)

---

### `micro_mcp`

- **GitHub:** [`shredinjohn/micro_mcp`](https://github.com/shredinjohn/micro_mcp)
- **License:** MIT
- **Python:** 3.8+

**Key features:**
- 100% Python standard library — zero dependencies
- FastMCP-style decorator API
- Auto JSON Schema from type hints
- Supports stdio and SSE
- 79 tests included

**Best for:** Minimal/portable deployments

---

### `local-mcp-server`

- **GitHub:** [`Emmimal/local-mcp-server`](https://github.com/Emmimal/local-mcp-server)
- **License:** MIT
- **Python:** 3.8+

**Key features:**
- Zero dependencies (stdlib only)
- Secure local file system access
- Both stdio and HTTP/SSE transports
- 4 built-in tools for file operations

**Best for:** Local file access use cases

---

### `mcp_arena`

- **GitHub:** [`PREMO625/mcp_arena`](https://github.com/PREMO625/mcp_arena)
- **PyPI:** `mcp-arena`
- **License:** MIT
- **Python:** 3.12+

**Key features:**
- 17+ pre-built MCP server presets (GitHub, Slack, Notion, AWS)
- Intelligent agent orchestration
- LangChain integration

**Best for:** Pre-built integrations, not custom plugin servers

---

## Recommendation for [Pp]ortcullis

**Use the official `mcp` package** because:

1. **Both transports built-in** — stdio and Streamable HTTP/SSE supported natively
2. **FastMCP API** — clean decorator-based tool registration that aligns well with pluggy hooks
3. **Mature and documented** — 23k+ stars, official Anthropic backing, active maintenance
4. **Plugin-friendly** — the `FastMCP` pattern maps cleanly to a plugin hook system where each plugin registers its tools

**Installation:**
```bash
uv add "mcp[cli]"
```

**For plugin authors:**
Each plugin will depend on `mcp>=1.27,<2` to register tools via the server's hook system.

---

## Sources

1. [MCP PyPI Package](https://pypi.org/project/mcp/)
2. [modelcontextprotocol/python-sdk GitHub](https://github.com/modelcontextprotocol/python-sdk)
3. [MCP Python SDK Documentation](https://py.sdk.modelcontextprotocol.io/)
4. [anodize-mcp GitHub](https://github.com/msradam/anodize-mcp)
5. [micro_mcp GitHub](https://github.com/shredinjohn/micro_mcp)
6. [local-mcp-server GitHub](https://github.com/Emmimal/local-mcp-server)
7. [mcp_arena GitHub](https://github.com/PREMO625/mcp_arena)
