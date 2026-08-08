"""
Common handlers for MCP transports.

Shared logic for JSON-RPC request handlers used by both
stdio and HTTP/SSE transports.
"""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

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
    from mcp.server.fastmcp.exceptions import ToolError

    from vestibule.approval import ApprovalRequired, check_approval
    from vestibule.audit import log_tool_call
    from vestibule.rate_limit import RateLimitExceeded, check_rate_limit

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

    try:
        if hasattr(mcp_server, "call_tool"):
            result = await mcp_server.call_tool(tool_name, arguments)

            # Extract text content from the result
            # FastMCP returns CallToolResult with content list
            if hasattr(result, "content") and result.content:
                # Get the text from TextContent objects
                text_parts = []
                for item in result.content:
                    if hasattr(item, "text"):
                        text_parts.append(item.text)
                    elif isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                text_content = "\n".join(text_parts) if text_parts else str(result.content)
            elif isinstance(result, dict):
                text_content = json.dumps(result, indent=2)
            else:
                text_content = str(result)

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

            # Tool not found - raise error
            raise ToolError(f"Tool not found: {tool_name}")

    except ToolError as e:
        # Audit log the failed tool call
        log_tool_call(
            tool_name=tool_name,
            arguments=arguments,
            success=False,
            error=str(e),
            session_id=session_id,
        )
        # Re-raise for caller to handle as JSON-RPC error
        raise e
    except TypeError as e:
        log_tool_call(
            tool_name=tool_name,
            arguments=arguments,
            success=False,
            error=f"Invalid arguments: {str(e)}",
            session_id=session_id,
        )
        raise ToolError(f"Invalid arguments: {str(e)}") from e
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
