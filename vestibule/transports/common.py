"""
Common handlers for MCP transports.

Shared logic for JSON-RPC request handlers used by both
stdio and HTTP/SSE transports.
"""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from vestibule.approval import ApprovalRequired, check_approval
from vestibule.audit import log_tool_call
from vestibule.rate_limit import RateLimitExceeded, check_rate_limit

# JSON-RPC error codes (shared by both transports)
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


async def handle_tools_list(mcp_server: FastMCP) -> dict[str, Any]:
    """
    Handle the tools/list request.

    Args:
        mcp_server: The FastMCP server instance

    Returns:
        Dictionary with "tools" key containing list of tool info dicts
    """
    tools_result = await mcp_server.list_tools()

    # Handle different return types
    if isinstance(tools_result, list):
        # FastMCP returns list of Tool objects
        tools = []
        for tool in tools_result:
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.inputSchema,
                }
            )
    elif hasattr(tools_result, "tools"):
        # Wrapped result
        tools = []
        for tool in tools_result.tools:
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.inputSchema,
                }
            )
    else:
        tools = []

    return {"tools": tools}


async def _tool_exists(mcp_server: FastMCP, tool_name: str) -> bool:
    """Return True if a tool with the given name is registered.

    Uses the public ``list_tools()`` API so the check is robust against
    FastMCP internal changes (rather than reaching into private attributes).
    """
    try:
        tools = await mcp_server.list_tools()
    except Exception:
        return False
    return any(tool.name == tool_name for tool in tools)


def _iter_content_nodes(obj: Any):
    """Yield all nested content nodes (lists, tuples, dicts, or objects).

    Recursively descends into lists/tuples and dict values. A dict that carries
    a ``text`` key is treated as a leaf so its text is collected; other dicts
    are walked for their values.
    """
    if isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _iter_content_nodes(item)
    elif isinstance(obj, dict):
        if "text" in obj:
            yield obj
        else:
            for value in obj.values():
                yield from _iter_content_nodes(value)
    else:
        yield obj


def _collect_text(items: Any) -> list[str]:
    """Collect ``text`` from TextContent objects or dicts in a sequence.

    Separates tree traversal (``_iter_content_nodes``) from text extraction so
    text-bearing parts nested in non-sequence elements are still found.
    """
    parts = []
    for node in _iter_content_nodes(items):
        if hasattr(node, "text"):
            parts.append(node.text)
        elif isinstance(node, dict) and "text" in node:
            parts.append(node["text"])
    return parts


def _extract_text_content(result: Any) -> str:
    """Extract human-readable text from a tool result of various shapes.

    Handles CallToolResult, FastMCP's default ``(unstructured, structured)``
    tuple wrap, the ``list[TextContent]`` returned with ``structured_output=False``,
    plain dicts, and fallback ``str()``.
    """
    # CallToolResult (or any object exposing .content)
    content = getattr(result, "content", None)
    if content is not None:
        parts = _collect_text(content)
        if parts:
            return "\n".join(parts)
    # FastMCP default output wrap returns (unstructured, structured) tuple,
    # and structured_output=False success returns a list of TextContent.
    if isinstance(result, (tuple, list)):
        parts = _collect_text(result)
        if parts:
            return "\n".join(parts)
    if isinstance(result, dict):
        return json.dumps(result, indent=2)
    return str(result)


async def handle_tools_call(
    mcp_server: FastMCP,
    tool_name: str,
    arguments: dict[str, Any],
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Handle the tools/call request.

    Args:
        mcp_server: The FastMCP server instance
        tool_name: Name of the tool to call
        arguments: Arguments to pass to the tool
        session_id: Optional session identifier for audit logging

    Returns:
        Tool execution result with content and isError fields
    """
    # Enforce per-tool rate limiting before executing the call
    try:
        check_rate_limit(tool_name)
    except RateLimitExceeded as e:
        log_tool_call(
            tool_name=tool_name,
            arguments=arguments,
            success=False,
            error=str(e),
            session_id=session_id,
        )
        return {
            "content": [{"type": "text", "text": str(e)}],
            "isError": True,
        }

    # Enforce human-in-the-loop approval before executing the call
    try:
        check_approval(tool_name)
    except ApprovalRequired as e:
        log_tool_call(
            tool_name=tool_name,
            arguments=arguments,
            success=False,
            error=str(e),
            session_id=session_id,
        )
        return {
            "content": [{"type": "text", "text": str(e)}],
            "isError": False,
            "structuredContent": {
                "approval_required": True,
                "tool": tool_name,
                "arguments": arguments,
            },
        }

    # Protocol-level check: an unknown tool is a JSON-RPC "method not found"
    # error, not a tool execution result. Reject it here so the transport maps
    # it to METHOD_NOT_FOUND rather than treating it as a business error.
    if not await _tool_exists(mcp_server, tool_name):
        raise ToolError(f"Tool not found: {tool_name}")

    try:
        if hasattr(mcp_server, "call_tool"):
            result = await mcp_server.call_tool(tool_name, arguments)

            text_content = _extract_text_content(result)

            response = {
                "content": [{"type": "text", "text": text_content}],
                "isError": getattr(result, "isError", False),
            }

            # Audit log the tool call
            log_tool_call(
                tool_name=tool_name,
                arguments=arguments,
                success=True,
                result=text_content,
                session_id=session_id,
            )

            return response
        else:
            # Fallback: try to call the tool function directly
            if hasattr(mcp_server, "_tool_registry"):
                registry = mcp_server._tool_registry
                if tool_name in registry.tools:
                    tool = registry.tools[tool_name]
                    result = await tool.handler(**arguments)
                    response = {
                        "content": [{"type": "text", "text": str(result)}],
                        "isError": False,
                    }

                    # Audit log the tool call
                    log_tool_call(
                        tool_name=tool_name,
                        arguments=arguments,
                        success=True,
                        result=str(result),
                        session_id=session_id,
                    )

                    return response

            # Defensive: existence was pre-checked above, so this is unreachable.
            raise ToolError(f"Tool not found: {tool_name}")

    except ToolError as e:
        # A ToolError during execution means the plugin raised (an expected
        # business error or an unexpected crash). Surface it as a graceful
        # isError content result, not a JSON-RPC protocol error.
        log_tool_call(
            tool_name=tool_name,
            arguments=arguments,
            success=False,
            error=str(e),
            session_id=session_id,
        )
        return {
            "content": [{"type": "text", "text": str(e)}],
            "isError": True,
        }
    except TypeError as e:
        # Bad arguments raised during plugin execution / argument validation.
        log_tool_call(
            tool_name=tool_name,
            arguments=arguments,
            success=False,
            error=f"Invalid arguments: {str(e)}",
            session_id=session_id,
        )
        return {
            "content": [{"type": "text", "text": f"Invalid arguments: {str(e)}"}],
            "isError": True,
        }
    except Exception as e:
        log_tool_call(
            tool_name=tool_name,
            arguments=arguments,
            success=False,
            error=str(e),
            session_id=session_id,
        )
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "isError": True,
        }


# -----------------------------------------------------------------------------
# Shared JSON-RPC Request Handlers
# -----------------------------------------------------------------------------
# These handlers are identical in both stdio and http_sse transports.
# They are pure functions that take an mcp_server and params, returning results.


async def handle_initialize(params: dict[str, Any]) -> dict[str, Any]:
    """
    Handle the initialize request.

    Args:
        params: Initialize request parameters (protocolVersion, capabilities, clientInfo)

    Returns:
        Server capabilities and info
    """
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {},
            "resources": {},
            "prompts": {},
        },
        "serverInfo": {
            "name": "vestibule",
            "version": "0.1.0",
        },
    }


async def handle_initialized(params: dict[str, Any]) -> None:
    """
    Handle the initialized notification.

    This is a notification (no response expected).
    """
    pass


async def handle_resources_list(params: dict[str, Any]) -> dict[str, Any]:
    """
    Handle the resources/list request.

    Returns:
        Empty resources list (no resources implemented yet)
    """
    return {"resources": []}


async def handle_resources_read(params: dict[str, Any]) -> dict[str, Any]:
    """
    Handle the resources/read request.

    Args:
        params: Resource read parameters with uri

    Returns:
        Raises METHOD_NOT_FOUND error (no resources implemented)
    """
    uri = params.get("uri")
    if not uri:
        raise ValueError("Missing resource URI")
    raise ValueError(f"Resource not found: {uri}")


async def handle_prompts_list(params: dict[str, Any]) -> dict[str, Any]:
    """
    Handle the prompts/list request.

    Returns:
        Empty prompts list (no prompts implemented yet)
    """
    return {"prompts": []}


async def handle_prompts_get(params: dict[str, Any]) -> dict[str, Any]:
    """
    Handle the prompts/get request.

    Args:
        params: Prompt get parameters with name

    Returns:
        Raises METHOD_NOT_FOUND error (no prompts implemented)
    """
    name = params.get("name")
    if not name:
        raise ValueError("Missing prompt name")
    raise ValueError(f"Prompt not found: {name}")


async def handle_ping(params: dict[str, Any]) -> dict[str, Any]:
    """
    Handle the ping request.

    Returns:
        Empty response (pong)
    """
    return {}
