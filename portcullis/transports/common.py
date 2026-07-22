"""
Common handlers for MCP transports.

Shared logic for tools/list and tools/call handlers used by both
stdio and HTTP/SSE transports.
"""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP


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
            tools.append({
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": tool.inputSchema,
            })
    elif hasattr(tools_result, "tools"):
        # Wrapped result
        tools = []
        for tool in tools_result.tools:
            tools.append({
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": tool.inputSchema,
            })
    else:
        tools = []

    return {"tools": tools}


async def handle_tools_call(
    mcp_server: FastMCP, tool_name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """
    Handle the tools/call request.

    Args:
        mcp_server: The FastMCP server instance
        tool_name: Name of the tool to call
        arguments: Arguments to pass to the tool

    Returns:
        Tool execution result with content and isError fields
    """
    from mcp.server.fastmcp.exceptions import ToolError

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

            return {
                "content": [
                    {"type": "text", "text": text_content}
                ],
                "isError": getattr(result, "isError", False),
            }
        else:
            # Fallback: try to call the tool function directly
            if hasattr(mcp_server, "_tool_registry"):
                registry = mcp_server._tool_registry
                if tool_name in registry.tools:
                    tool = registry.tools[tool_name]
                    result = await tool.handler(**arguments)
                    return {
                        "content": [
                            {"type": "text", "text": str(result)}
                        ],
                        "isError": False,
                    }

            # Tool not found - raise error
            raise ToolError(f"Tool not found: {tool_name}")

    except ToolError as e:
        # Re-raise for caller to handle as JSON-RPC error
        raise e
    except TypeError as e:
        raise ToolError(f"Invalid arguments: {str(e)}")
    except Exception as e:
        return {
            "content": [
                {"type": "text", "text": f"Error: {str(e)}"}
            ],
            "isError": True,
        }
