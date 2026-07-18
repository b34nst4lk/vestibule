"""
HTTP/SSE transport for MCP server.

Implements the MCP Streamable HTTP transport with Server-Sent Events
for server-to-client streaming.
"""

import asyncio
import json
import uuid
from typing import Any, Callable, Dict

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

from mcp.server.fastmcp import FastMCP


# JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class JSONRPCError(Exception):
    """JSON-RPC protocol error."""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


class HTTPSSETransport:
    """
    HTTP/SSE transport for MCP server.

    Implements the MCP Streamable HTTP transport protocol:
    - POST /mcp for client->server messages
    - SSE stream for server->client messages
    """

    def __init__(self, mcp_server: FastMCP, host: str = "localhost", port: int = 8080):
        """
        Initialize the HTTP/SSE transport.

        Args:
            mcp_server: The FastMCP server instance with registered tools
            host: Host to bind to
            port: Port to listen on
        """
        self.mcp_server = mcp_server
        self.host = host
        self.port = port
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
        # Session management: session_id -> message queue
        self._sessions: Dict[str, asyncio.Queue] = {}
        self._app = self._create_app()

    def _create_app(self) -> Starlette:
        """Create the Starlette application with routes."""
        routes = [
            Route("/mcp", self._handle_mcp_post, methods=["POST"]),
            Route("/mcp", self._handle_mcp_sse, methods=["GET"]),
            Route("/health", self._handle_health, methods=["GET"]),
        ]
        return Starlette(routes=routes)

    async def _handle_health(self, request: Request) -> Response:
        """Health check endpoint."""
        return Response("OK", media_type="text/plain")

    async def _handle_mcp_post(self, request: Request) -> Response:
        """
        Handle POST requests to /mcp.

        Client sends JSON-RPC messages here. Server responds with either:
        - Direct response (for requests without SSE)
        - 202 Accepted (for SSE streaming)
        """
        try:
            body = await request.json()
        except json.JSONDecodeError as e:
            return self._json_error_response(PARSE_ERROR, f"Parse error: {str(e)}")

        # Validate JSON-RPC structure
        if not isinstance(body, dict):
            return self._json_error_response(
                INVALID_REQUEST, "Request must be an object"
            )

        if body.get("jsonrpc") != "2.0":
            return self._json_error_response(
                INVALID_REQUEST,
                f"Unsupported JSON-RPC version: {body.get('jsonrpc')}",
            )

        method = body.get("method")
        if not method:
            return self._json_error_response(INVALID_REQUEST, "Missing method")

        request_id = body.get("id")
        params = body.get("params", {})

        # Check if client wants SSE streaming (via Accept header or query param)
        accept_header = request.headers.get("accept", "")
        use_sse = "text/event-stream" in accept_header or request.query_params.get("sse") == "true"

        if use_sse and request_id is not None:
            # Create session for SSE streaming
            session_id = str(uuid.uuid4())
            queue: asyncio.Queue = asyncio.Queue()
            self._sessions[session_id] = queue

            # Process request and queue response
            try:
                result = await self._process_request(body)
                await queue.put({"type": "result", "data": result})
            except JSONRPCError as e:
                await queue.put({
                    "type": "error",
                    "data": self._json_error_dict(e.code, e.message, e.data)
                })
            except Exception as e:
                await queue.put({
                    "type": "error",
                    "data": self._json_error_dict(INTERNAL_ERROR, f"Internal error: {str(e)}")
                })

            # Signal end of messages
            await queue.put({"type": "end"})

            # Return session ID for client to connect SSE
            return Response(
                status_code=202,
                content=json.dumps({"sessionId": session_id}),
                media_type="application/json",
                headers={"Location": f"/mcp?session={session_id}"},
            )
        else:
            # Synchronous response
            try:
                result = await self._process_request(body)
                if request_id is not None:
                    return self._json_response(request_id, result)
                else:
                    # Notification - no response body
                    return Response(status_code=202)
            except JSONRPCError as e:
                return self._json_error_response(e.code, e.message, e.data, request_id)
            except Exception as e:
                return self._json_error_response(
                    INTERNAL_ERROR, f"Internal error: {str(e)}", request_id=request_id
                )

    async def _handle_mcp_sse(self, request: Request) -> StreamingResponse:
        """
        Handle SSE stream for server->client messages.

        Client connects to this endpoint to receive streamed responses.
        """
        session_id = request.query_params.get("session")

        if not session_id or session_id not in self._sessions:
            return StreamingResponse(
                self._sse_error_stream("Invalid or expired session"),
                media_type="text/event-stream",
            )

        queue = self._sessions[session_id]

        async def sse_generator():
            try:
                while True:
                    try:
                        message = await asyncio.wait_for(queue.get(), timeout=60.0)
                    except asyncio.TimeoutError:
                        # Send keepalive
                        yield ": keepalive\n\n"
                        continue

                    if message.get("type") == "end":
                        break

                    if message.get("type") == "result":
                        data = message["data"]
                        yield f"data: {json.dumps(data)}\n\n"
                    elif message.get("type") == "error":
                        data = message["data"]
                        yield f"data: {json.dumps(data)}\n\n"

            except asyncio.CancelledError:
                pass
            finally:
                # Clean up session
                self._sessions.pop(session_id, None)

        return StreamingResponse(
            sse_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    async def _process_request(self, request: dict[str, Any]) -> Any:
        """Process a JSON-RPC request and return the raw handler result."""
        method = request.get("method")
        params = request.get("params", {})

        handler = self._request_handlers.get(method)
        if handler is None:
            raise JSONRPCError(METHOD_NOT_FOUND, f"Method not found: {method}")

        return await handler(params)

    async def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the initialize request."""
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
        """Handle the initialized notification."""
        pass

    async def _handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the tools/list request."""
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
        """Handle the tools/call request."""
        from mcp.server.fastmcp.exceptions import ToolError

        tool_name = params.get("name")
        if not tool_name:
            raise JSONRPCError(INVALID_PARAMS, "Missing tool name")

        arguments = params.get("arguments", {})

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
                raise JSONRPCError(METHOD_NOT_FOUND, f"Tool not found: {tool_name}")

        except ToolError as e:
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
        """Handle the resources/list request."""
        return {"resources": []}

    async def _handle_resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the resources/read request."""
        uri = params.get("uri")
        if not uri:
            raise JSONRPCError(INVALID_PARAMS, "Missing resource URI")
        raise JSONRPCError(METHOD_NOT_FOUND, f"Resource not found: {uri}")

    async def _handle_prompts_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the prompts/list request."""
        return {"prompts": []}

    async def _handle_prompts_get(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the prompts/get request."""
        name = params.get("name")
        if not name:
            raise JSONRPCError(INVALID_PARAMS, "Missing prompt name")
        raise JSONRPCError(METHOD_NOT_FOUND, f"Prompt not found: {name}")

    async def _handle_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the ping request."""
        return {}

    def _json_response(self, request_id: Any, result: Any) -> Response:
        """Create a JSON-RPC success response."""
        return Response(
            content=json.dumps({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }),
            media_type="application/json",
        )

    def _json_error_response(
        self, code: int, message: str, data: Any = None, request_id: Any = None
    ) -> Response:
        """Create a JSON-RPC error response."""
        return Response(
            content=json.dumps(self._json_error_dict(code, message, data, request_id)),
            media_type="application/json",
            status_code=400 if code != METHOD_NOT_FOUND else 404,
        )

    def _json_error_dict(
        self, code: int, message: str, data: Any = None, request_id: Any = None
    ) -> dict[str, Any]:
        """Create a JSON-RPC error dictionary."""
        error = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }
        if data is not None:
            error["error"]["data"] = data
        return error

    async def run(self) -> None:
        """Run the HTTP/SSE server using uvicorn."""
        import uvicorn

        config = uvicorn.Config(
            self._app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()
