"""
Tests for the HTTP/SSE transport.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp.server.fastmcp import FastMCP

from bulwark.transports.http_sse import (
    HTTPSSETransport,
    JSONRPCError,
)


@pytest.fixture
def mcp_server():
    """Create a mock FastMCP server for testing."""
    server = FastMCP("test-server")

    @server.tool()
    def echo(message: str) -> str:
        """Echo a message back."""
        return f"Echo: {message}"

    return server


@pytest.fixture
def transport(mcp_server):
    """Create an HTTPSSETransport instance."""
    return HTTPSSETransport(mcp_server, host="localhost", port=8080)


class TestJSONRPCError:
    """Tests for JSONRPCError exception."""

    def test_create_with_code_and_message(self):
        """Test creating error with code and message."""
        err = JSONRPCError(-32600, "Invalid request")
        assert err.code == -32600
        assert err.message == "Invalid request"
        assert err.data is None

    def test_create_with_data(self):
        """Test creating error with additional data."""
        err = JSONRPCError(-32602, "Invalid params", data={"field": "value"})
        assert err.data == {"field": "value"}


class TestHTTPSSETransportInit:
    """Tests for HTTPSSETransport initialization."""

    def test_init_with_server(self, mcp_server):
        """Test initialization with MCP server."""
        transport = HTTPSSETransport(mcp_server, host="127.0.0.1", port=9000)
        assert transport.mcp_server is mcp_server
        assert transport.host == "127.0.0.1"
        assert transport.port == 9000

    def test_request_handlers_registered(self, transport):
        """Test that request handlers are registered."""
        expected_handlers = [
            "initialize",
            "initialized",
            "tools/list",
            "tools/call",
            "resources/list",
            "resources/read",
            "prompts/list",
            "prompts/get",
            "ping",
        ]
        for handler in expected_handlers:
            assert handler in transport._request_handlers

    def test_app_created(self, transport):
        """Test that Starlette app is created."""
        assert transport._app is not None
        assert hasattr(transport._app, "routes")


class TestInitializeHandler:
    """Tests for the initialize handler."""

    @pytest.mark.asyncio
    async def test_initialize_returns_capabilities(self, transport):
        """Test initialize returns server capabilities."""
        result = await transport._handle_initialize({})

        assert "protocolVersion" in result
        assert result["protocolVersion"] == "2024-11-05"
        assert "capabilities" in result
        assert "tools" in result["capabilities"]
        assert "serverInfo" in result
        assert result["serverInfo"]["name"] == "bulwark"


class TestToolsListHandler:
    """Tests for the tools/list handler."""

    @pytest.mark.asyncio
    async def test_tools_list_returns_tools(self, transport, mcp_server):
        """Test tools/list returns registered tools."""
        result = await transport._handle_tools_list({})
        assert "tools" in result
        assert isinstance(result["tools"], list)


class TestToolsCallHandler:
    """Tests for the tools/call handler."""

    @pytest.mark.asyncio
    async def test_tools_call_missing_name(self, transport):
        """Test tools/call error when tool name is missing."""
        with pytest.raises(JSONRPCError) as exc_info:
            await transport._handle_tools_call({})
        assert exc_info.value.code == -32602  # INVALID_PARAMS
        assert "Missing tool name" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_tools_call_unknown_tool(self, transport):
        """Test tools/call error for unknown tool."""
        with pytest.raises(JSONRPCError) as exc_info:
            await transport._handle_tools_call({"name": "nonexistent"})
        assert exc_info.value.code == -32601  # METHOD_NOT_FOUND

    @pytest.mark.asyncio
    async def test_tools_call_with_arguments(self, transport, mcp_server):
        """Test tools/call with arguments."""
        result = await transport._handle_tools_call({
            "name": "echo",
            "arguments": {"message": "hello"}
        })
        assert "content" in result
        assert result["isError"] is False


class TestResourcesHandlers:
    """Tests for resources handlers."""

    @pytest.mark.asyncio
    async def test_resources_list_empty(self, transport):
        """Test resources/list returns empty list."""
        result = await transport._handle_resources_list({})
        assert result == {"resources": []}

    @pytest.mark.asyncio
    async def test_resources_read_missing_uri(self, transport):
        """Test resources/read error when URI is missing."""
        with pytest.raises(JSONRPCError) as exc_info:
            await transport._handle_resources_read({})
        assert exc_info.value.code == -32602

    @pytest.mark.asyncio
    async def test_resources_read_unknown_resource(self, transport):
        """Test resources/read error for unknown resource."""
        with pytest.raises(JSONRPCError) as exc_info:
            await transport._handle_resources_read({"uri": "file:///unknown"})
        assert exc_info.value.code == -32601


class TestPromptsHandlers:
    """Tests for prompts handlers."""

    @pytest.mark.asyncio
    async def test_prompts_list_empty(self, transport):
        """Test prompts/list returns empty list."""
        result = await transport._handle_prompts_list({})
        assert result == {"prompts": []}

    @pytest.mark.asyncio
    async def test_prompts_get_missing_name(self, transport):
        """Test prompts/get error when name is missing."""
        with pytest.raises(JSONRPCError) as exc_info:
            await transport._handle_prompts_get({})
        assert exc_info.value.code == -32602

    @pytest.mark.asyncio
    async def test_prompts_get_unknown_prompt(self, transport):
        """Test prompts/get error for unknown prompt."""
        with pytest.raises(JSONRPCError) as exc_info:
            await transport._handle_prompts_get({"name": "unknown"})
        assert exc_info.value.code == -32601


class TestPingHandler:
    """Tests for the ping handler."""

    @pytest.mark.asyncio
    async def test_ping_returns_empty(self, transport):
        """Test ping returns empty response."""
        result = await transport._handle_ping({})
        assert result == {}


class TestJsonResponseHelpers:
    """Tests for JSON response helper methods."""

    def test_json_response(self, transport):
        """Test JSON response creation."""
        response = transport._json_response(1, {"result": "success"})
        assert response.status_code == 200
        assert response.media_type == "application/json"

        import json
        data = json.loads(response.body)
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert data["result"] == {"result": "success"}

    def test_json_error_response(self, transport):
        """Test JSON error response creation."""
        response = transport._json_error_response(-32600, "Invalid request", request_id=1)
        assert response.status_code == 400
        assert response.media_type == "application/json"

        import json
        data = json.loads(response.body)
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "error" in data
        assert data["error"]["code"] == -32600

    def test_json_error_response_not_found(self, transport):
        """Test 404 for method not found."""
        response = transport._json_error_response(-32601, "Not found")
        assert response.status_code == 404

    def test_json_error_dict_with_data(self, transport):
        """Test error dict with additional data."""
        error_dict = transport._json_error_dict(
            -32602, "Invalid params", data={"field": "value"}, request_id=1
        )
        assert error_dict["error"]["data"] == {"field": "value"}


class TestSessionManagement:
    """Tests for session management."""

    def test_session_created(self, transport):
        """Test that sessions are created properly."""
        import asyncio
        queue = asyncio.Queue()
        transport._sessions["test-session"] = queue
        assert "test-session" in transport._sessions

    def test_session_cleaned_up(self, transport):
        """Test that sessions are cleaned up."""
        import asyncio
        queue = asyncio.Queue()
        transport._sessions["test-session"] = queue
        transport._sessions.pop("test-session", None)
        assert "test-session" not in transport._sessions


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, transport):
        """Test health endpoint returns OK."""
        from starlette.testclient import TestClient

        with TestClient(transport._app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.text == "OK"


class TestIntegration:
    """Integration tests using TestClient."""

    def test_initialize_request(self, transport):
        """Test full initialize request/response cycle."""
        from starlette.testclient import TestClient

        with TestClient(transport._app) as client:
            request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {}
            }
            response = client.post("/mcp", json=request)
            assert response.status_code == 200
            data = response.json()
            assert data["jsonrpc"] == "2.0"
            assert data["id"] == 1
            assert "result" in data
            assert data["result"]["serverInfo"]["name"] == "bulwark"

    def test_ping_request(self, transport):
        """Test ping request/response."""
        from starlette.testclient import TestClient

        with TestClient(transport._app) as client:
            request = {
                "jsonrpc": "2.0",
                "method": "ping",
                "id": 1,
                "params": {}
            }
            response = client.post("/mcp", json=request)
            assert response.status_code == 200
            data = response.json()
            assert data["result"] == {}

    def test_unknown_method_error(self, transport):
        """Test error response for unknown method."""
        from starlette.testclient import TestClient

        with TestClient(transport._app) as client:
            request = {
                "jsonrpc": "2.0",
                "method": "unknown/method",
                "id": 1,
                "params": {}
            }
            response = client.post("/mcp", json=request)
            assert response.status_code == 404
            data = response.json()
            assert "error" in data
            assert data["error"]["code"] == -32601

    def test_invalid_jsonrpc_version(self, transport):
        """Test error for invalid JSON-RPC version."""
        from starlette.testclient import TestClient

        with TestClient(transport._app) as client:
            request = {
                "jsonrpc": "1.0",
                "method": "ping",
                "id": 1
            }
            response = client.post("/mcp", json=request)
            assert response.status_code == 400
            data = response.json()
            assert "error" in data
            assert "Unsupported JSON-RPC version" in data["error"]["message"]

    def test_notification_no_response(self, transport):
        """Test that notifications don't get response body."""
        from starlette.testclient import TestClient

        with TestClient(transport._app) as client:
            request = {
                "jsonrpc": "2.0",
                "method": "initialized",
                "params": {}
            }
            response = client.post("/mcp", json=request)
            assert response.status_code == 202
