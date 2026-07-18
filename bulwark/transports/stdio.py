"""
Stdio transport for MCP server.

Implements JSON-RPC 2.0 over stdin/stdout following the MCP specification.
"""

import asyncio
import json
import sys
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError


class JSONRPCError(Exception):
    """JSON-RPC protocol error."""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


# JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class StdioTransport:
    """
    Stdio transport for MCP server.

    Reads JSON-RPC messages from stdin and writes responses to stdout.
    """

    def __init__(self, mcp_server: FastMCP):
        """
        Initialize the stdio transport.

        Args:
            mcp_server: The FastMCP server instance with registered tools
        """
        self.mcp_server = mcp_server
        self._running = False
        self._request_handlers: dict[str, Callable] = {
            "initialize": self._handle_initialize,
            "initialized": self._handle_initialized,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
            "ping": self._handle_ping,
        }

    async def run(self) -> None:
        """
        Run the stdio transport server.

        Reads JSON-RPC messages from stdin and writes responses to stdout.
        """
        self._running = True

        # Use asyncio.StreamReader for non-blocking stdin
        loop = asyncio.get_event_loop()
        stdin_stream = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(stdin_stream)

        # Connect stdin to the stream reader
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        while self._running:
            try:
                # Read a line from stdin (non-blocking)
                line = await stdin_stream.readline()
                if not line:
                    # EOF - client disconnected
                    break

                line = line.decode('utf-8').strip()
                if not line:
                    continue

                # Parse and handle the message
                try:
                    request = json.loads(line)
                except json.JSONDecodeError as e:
                    await self._send_error(
                        None, PARSE_ERROR, f"Parse error: {str(e)}"
                    )
                    continue

                # Process the request
                try:
                    await self._process_request(request)
                except JSONRPCError as e:
                    await self._send_error(request.get("id"), e.code, e.message, e.data)
                except Exception as e:
                    await self._send_error(
                        request.get("id"),
                        INTERNAL_ERROR,
                        f"Internal error: {str(e)}",
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but keep running
                print(f"Stdio transport error: {e}", file=sys.stderr)
                break

        self._running = False

    async def _process_request(self, request: dict[str, Any]) -> None:
        """
        Process a JSON-RPC request.

        Args:
            request: Parsed JSON-RPC request dictionary
        """
        # Validate basic JSON-RPC structure
        if not isinstance(request, dict):
            raise JSONRPCError(INVALID_REQUEST, "Request must be an object")

        jsonrpc_version = request.get("jsonrpc")
        if jsonrpc_version != "2.0":
            raise JSONRPCError(
                INVALID_REQUEST,
                f"Unsupported JSON-RPC version: {jsonrpc_version}",
            )

        method = request.get("method")
        if not method:
            raise JSONRPCError(INVALID_REQUEST, "Missing method")

        request_id = request.get("id")
        params = request.get("params", {})

        # Find and call the handler
        handler = self._request_handlers.get(method)
        if handler is None:
            raise JSONRPCError(
                METHOD_NOT_FOUND, f"Method not found: {method}"
            )

        # Call the handler
        result = await handler(params)

        # Send response (only if there's an id - notifications don't get responses)
        if request_id is not None:
            await self._send_response(request_id, result)

    async def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Handle the initialize request.

        Args:
            params: Initialize request parameters

        Returns:
            Server capabilities and info
        """
        # Extract client info
        client_info = params.get("protocolVersion", "1.0")

        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {},
            },
            "serverInfo": {
                "name": "bulwark",
                "version": "0.1.0",
            },
        }

    async def _handle_initialized(self, params: dict[str, Any]) -> None:
        """
        Handle the initialized notification.

        This is a notification (no response expected).
        """
        # Server is now fully initialized
        pass

    async def _handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Handle the tools/list request.

        Returns:
            List of available tools
        """
        # Get tools from the FastMCP server using list_tools method
        tools_result = await self.mcp_server.list_tools()

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

    async def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Handle the tools/call request.

        Args:
            params: Tool call parameters with name and arguments

        Returns:
            Tool execution result
        """
        tool_name = params.get("name")
        if not tool_name:
            raise JSONRPCError(INVALID_PARAMS, "Missing tool name")

        arguments = params.get("arguments", {})

        # Call the tool using FastMCP
        try:
            if hasattr(self.mcp_server, "call_tool"):
                result = await self.mcp_server.call_tool(tool_name, arguments)

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
                if hasattr(self.mcp_server, "_tool_registry"):
                    registry = self.mcp_server._tool_registry
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
                raise JSONRPCError(METHOD_NOT_FOUND, f"Tool not found: {tool_name}")

        except ToolError as e:
            # FastMCP raises ToolError for unknown tools
            raise JSONRPCError(METHOD_NOT_FOUND, str(e))
        except TypeError as e:
            raise JSONRPCError(INVALID_PARAMS, f"Invalid arguments: {str(e)}")
        except Exception as e:
            return {
                "content": [
                    {"type": "text", "text": f"Error: {str(e)}"}
                ],
                "isError": True,
            }

    async def _handle_resources_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Handle the resources/list request.

        Returns:
            List of available resources
        """
        return {"resources": []}

    async def _handle_resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Handle the resources/read request.

        Args:
            params: Resource read parameters with uri

        Returns:
            Resource content
        """
        uri = params.get("uri")
        if not uri:
            raise JSONRPCError(INVALID_PARAMS, "Missing resource URI")

        raise JSONRPCError(METHOD_NOT_FOUND, f"Resource not found: {uri}")

    async def _handle_prompts_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Handle the prompts/list request.

        Returns:
            List of available prompts
        """
        return {"prompts": []}

    async def _handle_prompts_get(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Handle the prompts/get request.

        Args:
            params: Prompt get parameters with name

        Returns:
            Prompt content
        """
        name = params.get("name")
        if not name:
            raise JSONRPCError(INVALID_PARAMS, "Missing prompt name")

        raise JSONRPCError(METHOD_NOT_FOUND, f"Prompt not found: {name}")

    async def _handle_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Handle the ping request.

        Returns:
            Empty response (pong)
        """
        return {}

    async def _send_response(self, request_id: Any, result: Any) -> None:
        """
        Send a JSON-RPC response.

        Args:
            request_id: The request ID to match
            result: The response result
        """
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }
        await self._send_message(response)

    async def _send_error(
        self,
        request_id: Any,
        code: int,
        message: str,
        data: Any = None,
    ) -> None:
        """
        Send a JSON-RPC error response.

        Args:
            request_id: The request ID to match (or None)
            code: Error code
            message: Error message
            data: Optional error data
        """
        error = {
            "code": code,
            "message": message,
        }
        if data is not None:
            error["data"] = data

        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": error,
        }
        await self._send_message(response)

    async def _send_message(self, message: dict[str, Any]) -> None:
        """
        Send a JSON-RPC message to stdout.

        Args:
            message: The message dictionary to send
        """
        line = json.dumps(message) + "\n"
        loop = asyncio.get_event_loop()
        # run_in_executor returns the result of the function, which we don't need
        await loop.run_in_executor(None, sys.stdout.write, line)
        await loop.run_in_executor(None, sys.stdout.flush)
