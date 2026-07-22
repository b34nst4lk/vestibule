"""
Stdio transport for MCP server.

Implements JSON-RPC 2.0 over stdin/stdout following the MCP specification.
"""

import asyncio
import json
import sys
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from .common import (
    handle_initialize,
    handle_initialized,
    handle_ping,
    handle_prompts_get,
    handle_prompts_list,
    handle_resources_list,
    handle_resources_read,
    handle_tools_call,
    handle_tools_list,
)


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

                line = line.decode("utf-8").strip()
                if not line:
                    continue

                # Parse and handle the message
                try:
                    request = json.loads(line)
                except json.JSONDecodeError as e:
                    await self._send_error(None, PARSE_ERROR, f"Parse error: {str(e)}")
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
            raise JSONRPCError(METHOD_NOT_FOUND, f"Method not found: {method}")

        # Call the handler
        result = await handler(params)

        # Send response (only if there's an id - notifications don't get responses)
        if request_id is not None:
            await self._send_response(request_id, result)

    async def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the initialize request."""
        return await handle_initialize(params)

    async def _handle_initialized(self, params: dict[str, Any]) -> None:
        """Handle the initialized notification."""
        await handle_initialized(params)

    async def _handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the tools/list request."""
        return await handle_tools_list(self.mcp_server)

    async def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the tools/call request."""
        tool_name = params.get("name")
        if not tool_name:
            raise JSONRPCError(INVALID_PARAMS, "Missing tool name")

        arguments = params.get("arguments", {})

        try:
            return await handle_tools_call(self.mcp_server, tool_name, arguments)
        except ToolError as e:
            raise JSONRPCError(METHOD_NOT_FOUND, str(e)) from e
        except TypeError as e:
            raise JSONRPCError(INVALID_PARAMS, f"Invalid arguments: {str(e)}") from e

    async def _handle_resources_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the resources/list request."""
        return await handle_resources_list(params)

    async def _handle_resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the resources/read request."""
        try:
            return await handle_resources_read(params)
        except ValueError as e:
            raise JSONRPCError(METHOD_NOT_FOUND, str(e)) from e

    async def _handle_prompts_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the prompts/list request."""
        return await handle_prompts_list(params)

    async def _handle_prompts_get(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the prompts/get request."""
        try:
            return await handle_prompts_get(params)
        except ValueError as e:
            raise JSONRPCError(METHOD_NOT_FOUND, str(e)) from e

    async def _handle_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the ping request."""
        return await handle_ping(params)

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
