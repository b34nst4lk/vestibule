"""Tests for shared transport tool-call error handling.

Covers the error-message convention (ticket #5 / #11):
- unknown tool -> protocol error (ToolError -> transport maps to method_not_found)
- plugin business error (returned CallToolResult with isError) -> isError: true content
- plugin crash (raises) -> graceful isError: true content
"""

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import CallToolResult, TextContent

from vestibule.transports.common import handle_tools_call


def _make_server() -> FastMCP:
    """Build a server with representative tools."""
    server = FastMCP("test")

    @server.tool(structured_output=False)
    def greet(name: str) -> str:
        return f"Hello, {name}"

    @server.tool(structured_output=False)
    def bizerr(name: str) -> str:
        return CallToolResult(
            content=[TextContent(type="text", text="recipient not in whitelist")],
            isError=True,
        )

    @server.tool()
    def boom(name: str) -> str:
        raise RuntimeError("boom")

    return server


@pytest.mark.asyncio
async def test_success_result():
    """A successful tool call returns content with isError False."""
    server = _make_server()
    await server.list_tools()  # ensure tools are registered
    result = await handle_tools_call(server, "greet", {"name": "alice"})
    assert result["isError"] is False
    assert result["content"][0]["text"] == "Hello, alice"


@pytest.mark.asyncio
async def test_business_error_is_error_content():
    """A plugin-returned CallToolResult(isError=True) -> isError: true content."""
    server = _make_server()
    await server.list_tools()
    result = await handle_tools_call(server, "bizerr", {"name": "alice"})
    assert result["isError"] is True
    assert "whitelist" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_crash_is_error_content():
    """A plugin that raises surfaces as a graceful isError: true content result."""
    server = _make_server()
    await server.list_tools()
    result = await handle_tools_call(server, "boom", {"name": "alice"})
    assert result["isError"] is True
    assert "boom" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_unknown_tool_raises_tool_error():
    """An unknown tool raises ToolError (mapped to method_not_found by transports)."""
    server = _make_server()
    await server.list_tools()
    with pytest.raises(ToolError):
        await handle_tools_call(server, "missing", {})
