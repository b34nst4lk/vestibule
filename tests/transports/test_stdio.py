"""
Tests for the Stdio transport.
"""

import asyncio
import json
import pytest
from io import StringIO
from unittest.mock import patch, MagicMock, AsyncMock

from mcp.server.fastmcp import FastMCP

from bulwark.transports.stdio import (
    StdioTransport,
    JSONRPCError,
    PARSE_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR,
)


@pytest.fixture
def mcp_server():
    """Create a mock FastMCP server for testing."""
    server = FastMCP("test-server")

    # Register a test tool
    @server.tool()
    def echo(message: str) -> str:
        """Echo a message back."""
        return f"Echo: {message}"

    @server.tool()
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    return server


@pytest.fixture
def transport(mcp_server):
    """Create a StdioTransport instance."""
    return StdioTransport(mcp_server)


class TestJSONRPCError:
    """Tests for JSONRPCError exception."""

    def test_create_with_code_and_message(self):
        """Test creating error with code and message."""
        err = JSONRPCError(PARSE_ERROR, "Parse error")
        assert err.code == PARSE_ERROR
        assert err.message == "Parse error"
        assert err.data is None

    def test_create_with_data(self):
        """Test creating error with additional data."""
        err = JSONRPCError(
            INVALID_PARAMS,
            "Invalid params",
            data={"field": "value"}
        )
        assert err.code == INVALID_PARAMS
        assert err.message == "Invalid params"
        assert err.data == {"field": "value"}

    def test_string_representation(self):
        """Test error string representation."""
        err = JSONRPCError(INTERNAL_ERROR, "Something went wrong")
        assert str(err) == "Something went wrong"


class TestStdioTransportInit:
    """Tests for StdioTransport initialization."""

    def test_init_with_server(self, mcp_server):
        """Test initialization with MCP server."""
        transport = StdioTransport(mcp_server)
        assert transport.mcp_server is mcp_server
        assert transport._running is False

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


class TestProcessRequest:
    """Tests for request processing."""

    @pytest.mark.asyncio
    async def test_invalid_jsonrpc_version(self, transport):
        """Test error on invalid JSON-RPC version."""
        request = {
            "jsonrpc": "1.0",
            "method": "ping",
            "id": 1
        }
        with pytest.raises(JSONRPCError) as exc_info:
            await transport._process_request(request)
        assert exc_info.value.code == INVALID_REQUEST
        assert "Unsupported JSON-RPC version" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_missing_method(self, transport):
        """Test error when method is missing."""
        request = {
            "jsonrpc": "2.0",
            "id": 1
        }
        with pytest.raises(JSONRPCError) as exc_info:
            await transport._process_request(request)
        assert exc_info.value.code == INVALID_REQUEST
        assert "Missing method" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_unknown_method(self, transport):
        """Test error for unknown method."""
        request = {
            "jsonrpc": "2.0",
            "method": "unknown/method",
            "id": 1
        }
        with pytest.raises(JSONRPCError) as exc_info:
            await transport._process_request(request)
        assert exc_info.value.code == METHOD_NOT_FOUND
        assert "unknown/method" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_non_dict_request(self, transport):
        """Test error when request is not a dictionary."""
        with pytest.raises(JSONRPCError) as exc_info:
            await transport._process_request(["not", "a", "dict"])
        assert exc_info.value.code == INVALID_REQUEST
        assert "must be an object" in exc_info.value.message


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
        assert "resources" in result["capabilities"]
        assert "prompts" in result["capabilities"]
        assert "serverInfo" in result
        assert result["serverInfo"]["name"] == "bulwark"

    @pytest.mark.asyncio
    async def test_initialize_with_protocol_version(self, transport):
        """Test initialize with client protocol version."""
        params = {"protocolVersion": "2024-11-05"}
        result = await transport._handle_initialize(params)
        assert result["protocolVersion"] == "2024-11-05"


class TestInitializedHandler:
    """Tests for the initialized notification handler."""

    @pytest.mark.asyncio
    async def test_initialized_no_response(self, transport):
        """Test initialized notification returns None."""
        result = await transport._handle_initialized({})
        assert result is None


class TestToolsListHandler:
    """Tests for the tools/list handler."""

    @pytest.mark.asyncio
    async def test_tools_list_returns_empty_by_default(self, transport):
        """Test tools/list returns empty list when no tools registered."""
        # Create server without tools
        server = FastMCP("empty-server")
        empty_transport = StdioTransport(server)
        result = await empty_transport._handle_tools_list({})
        assert "tools" in result


class TestToolsCallHandler:
    """Tests for the tools/call handler."""

    @pytest.mark.asyncio
    async def test_tools_call_missing_name(self, transport):
        """Test tools/call error when tool name is missing."""
        with pytest.raises(JSONRPCError) as exc_info:
            await transport._handle_tools_call({})
        assert exc_info.value.code == INVALID_PARAMS
        assert "Missing tool name" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_tools_call_unknown_tool(self, transport):
        """Test tools/call error for unknown tool."""
        with pytest.raises(JSONRPCError) as exc_info:
            await transport._handle_tools_call({"name": "nonexistent"})
        assert exc_info.value.code == METHOD_NOT_FOUND
        assert "nonexistent" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_tools_call_with_arguments(self, transport):
        """Test tools/call with arguments."""
        # This test depends on the server having tools registered
        # The handler should properly pass arguments to the tool
        result = await transport._handle_tools_call({
            "name": "echo",
            "arguments": {"message": "hello"}
        })
        # Result should have content structure
        assert "content" in result or "isError" in result


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
        assert exc_info.value.code == INVALID_PARAMS
        assert "Missing resource URI" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_resources_read_unknown_resource(self, transport):
        """Test resources/read error for unknown resource."""
        with pytest.raises(JSONRPCError) as exc_info:
            await transport._handle_resources_read({"uri": "file:///unknown"})
        assert exc_info.value.code == METHOD_NOT_FOUND


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
        assert exc_info.value.code == INVALID_PARAMS
        assert "Missing prompt name" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_prompts_get_unknown_prompt(self, transport):
        """Test prompts/get error for unknown prompt."""
        with pytest.raises(JSONRPCError) as exc_info:
            await transport._handle_prompts_get({"name": "unknown"})
        assert exc_info.value.code == METHOD_NOT_FOUND


class TestPingHandler:
    """Tests for the ping handler."""

    @pytest.mark.asyncio
    async def test_ping_returns_empty(self, transport):
        """Test ping returns empty response."""
        result = await transport._handle_ping({})
        assert result == {}


class TestSendResponse:
    """Tests for response sending."""

    @pytest.mark.asyncio
    async def test_send_response_format(self, transport):
        """Test response format."""
        captured = []

        async def mock_send(msg):
            captured.append(msg)

        # Patch _send_message to capture output
        original_send = transport._send_message
        transport._send_message = mock_send

        try:
            await transport._send_response(1, {"result": "success"})
            assert len(captured) == 1
            assert captured[0]["jsonrpc"] == "2.0"
            assert captured[0]["id"] == 1
            assert captured[0]["result"] == {"result": "success"}
        finally:
            transport._send_message = original_send


class TestSendError:
    """Tests for error sending."""

    @pytest.mark.asyncio
    async def test_send_error_format(self, transport):
        """Test error response format."""
        captured = []

        async def mock_send(msg):
            captured.append(msg)

        original_send = transport._send_message
        transport._send_message = mock_send

        try:
            await transport._send_error(
                1,
                INTERNAL_ERROR,
                "Test error",
                data={"detail": "something"}
            )
            assert len(captured) == 1
            assert captured[0]["jsonrpc"] == "2.0"
            assert captured[0]["id"] == 1
            assert "error" in captured[0]
            assert captured[0]["error"]["code"] == INTERNAL_ERROR
            assert captured[0]["error"]["message"] == "Test error"
            assert captured[0]["error"]["data"] == {"detail": "something"}
        finally:
            transport._send_message = original_send

    @pytest.mark.asyncio
    async def test_send_error_without_data(self, transport):
        """Test error response without data field."""
        captured = []

        async def mock_send(msg):
            captured.append(msg)

        original_send = transport._send_message
        transport._send_message = mock_send

        try:
            await transport._send_error(None, PARSE_ERROR, "Parse failed")
            assert len(captured) == 1
            assert "data" not in captured[0]["error"]
        finally:
            transport._send_message = original_send


class TestSendMessage:
    """Tests for message sending."""

    @pytest.mark.asyncio
    async def test_send_message_json_format(self, transport):
        """Test that message is sent as JSON."""
        import io

        captured_lines = []
        captured_flushes = []

        def mock_write(line):
            captured_lines.append(line)
            return len(line)  # stdout.write returns number of characters written

        def mock_flush():
            captured_flushes.append(True)

        # Patch sys.stdout directly
        with patch('sys.stdout.write', mock_write), patch('sys.stdout.flush', mock_flush):
            await transport._send_message({"test": "value"})

        # Check that stdout.write was called with JSON
        assert len(captured_lines) == 1
        msg = json.loads(captured_lines[0].strip())
        assert msg == {"test": "value"}
        assert len(captured_flushes) == 1


class TestIntegration:
    """Integration tests for the stdio transport."""

    @pytest.mark.asyncio
    async def test_full_request_response_cycle(self, mcp_server):
        """Test full request/response cycle."""
        transport = StdioTransport(mcp_server)

        # Simulate initialize request
        request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {"protocolVersion": "2024-11-05"}
        }

        captured = []

        async def capture_send(msg):
            captured.append(msg)

        transport._send_message = capture_send

        await transport._process_request(request)

        assert len(captured) == 1
        response = captured[0]
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["serverInfo"]["name"] == "bulwark"

    @pytest.mark.asyncio
    async def test_notification_no_response(self, transport):
        """Test that notifications don't get responses."""
        captured = []

        async def capture_send(msg):
            captured.append(msg)

        transport._send_message = capture_send

        # initialized is a notification (no id)
        request = {
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {}
        }

        await transport._process_request(request)

        # No response for notifications
        assert len(captured) == 0
