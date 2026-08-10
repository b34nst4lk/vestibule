"""
Integration tests for Vestibule HTTP/SSE transport.

Tests the Streamable HTTP transport with real HTTP endpoints.
"""

import httpx
import pytest


@pytest.fixture
def http_client(http_server: str):
    """
    Create an HTTP client for the Vestibule server.

    This fixture provides a sync httpx.Client for making HTTP requests.
    """
    with httpx.Client(base_url=http_server, timeout=30.0) as client:
        yield client


@pytest.mark.integration
@pytest.mark.http
def test_health_endpoint(http_server: str):
    """Test the health check endpoint."""
    with httpx.Client() as client:
        response = client.get(f"{http_server}/health", timeout=5.0)
        assert response.status_code == 200
        assert response.text == "OK"


@pytest.mark.integration
@pytest.mark.http
def test_initialize_http(http_client: httpx.Client):
    """Test server initialization via HTTP/SSE."""
    # Send initialize request
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        },
    }
    response = http_client.post("/mcp", json=request, timeout=5.0)
    assert response.status_code == 200
    result = response.json()
    assert "result" in result


@pytest.mark.integration
@pytest.mark.http
def test_list_tools_http(http_client: httpx.Client):
    """Verify email plugin tools are registered via HTTP."""
    # First initialize
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        },
    }
    http_client.post("/mcp", json=init_request, timeout=5.0)

    # List tools
    tools_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    response = http_client.post("/mcp", json=tools_request, timeout=5.0)
    assert response.status_code == 200
    result = response.json()
    tools = result["result"]["tools"]
    tool_names = {t["name"] for t in tools}

    assert "email.send_email" in tool_names
    assert "email.list_whitelist" in tool_names
    assert "email.add_to_whitelist" in tool_names


@pytest.mark.integration
@pytest.mark.http
def test_list_whitelist_http(http_client: httpx.Client):
    """Test list_whitelist tool via HTTP."""
    # Initialize first
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        },
    }
    http_client.post("/mcp", json=init_request, timeout=5.0)

    # Call tool
    call_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "email.list_whitelist", "arguments": {}},
    }
    response = http_client.post("/mcp", json=call_request, timeout=5.0)
    assert response.status_code == 200
    result = response.json()
    assert "result" in result
    assert result["result"].get("isError") is False or result["result"].get("isError") is None
    content = result["result"]["content"][0]["text"]
    assert "alice@example.com" in content


@pytest.mark.integration
@pytest.mark.http
def test_send_email_recipient_not_found_http(http_client: httpx.Client):
    """Test send_email error when recipient is not in whitelist via HTTP."""
    # Initialize first
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        },
    }
    http_client.post("/mcp", json=init_request, timeout=5.0)

    # Grant approval for the gated send_email tool.
    http_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "approve_tool",
                "arguments": {"tool_name": "email.send_email"},
            },
        },
        timeout=5.0,
    )

    # Call tool
    call_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "email.send_email",
            "arguments": {
                "recipient_name": "Unknown",
                "subject": "Test Subject",
                "body": "Test body",
            },
        },
    }
    response = http_client.post("/mcp", json=call_request, timeout=5.0)
    assert response.status_code == 200
    result = response.json()
    assert "result" in result
    content = result["result"]["content"][0]["text"]
    # A whitelist rejection is a business error -> isError: true content.
    assert result["result"]["isError"] is True
    assert "whitelist" in content.lower()
    assert "Unknown" in content


@pytest.mark.integration
@pytest.mark.http
def test_approval_flow_http(http_client: httpx.Client):
    """Gated tool requires approval; approve_tool grants it; retry executes."""
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        },
    }
    http_client.post("/mcp", json=init_request, timeout=5.0)

    # First call to the gated email.send_email tool requires approval.
    gated = http_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "email.send_email",
                "arguments": {
                    "recipient_name": "alice",
                    "subject": "Hello",
                    "body": "Approval flow test",
                },
            },
        },
        timeout=5.0,
    ).json()
    assert "result" in gated
    structured = gated["result"]["structuredContent"]
    assert structured["approval_required"] is True
    assert structured["tool"] == "email.send_email"
    assert structured["arguments"]["recipient_name"] == "alice"

    # Grant approval via the built-in approve_tool.
    approved = http_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "approve_tool",
                "arguments": {"tool_name": "email.send_email"},
            },
        },
        timeout=5.0,
    ).json()
    assert "result" in approved

    # Retry the original call: it should now execute.
    retry = http_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "email.send_email",
                "arguments": {
                    "recipient_name": "alice",
                    "subject": "Hello",
                    "body": "Approval flow test",
                },
            },
        },
        timeout=5.0,
    ).json()
    assert "result" in retry
    assert retry["result"]["isError"] is True
    # The tool executed (gate bypassed); the fake SMTP host fails to send,
    # so the send surfaces as a graceful isError: true content result.
    content = retry["result"]["content"][0]["text"]
    assert "Approval required" not in content
