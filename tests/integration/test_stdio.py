"""
Integration tests for Portcullis stdio transport.

Tests the full JSON-RPC over stdio stack with real process boundaries.
Uses subprocess-based approach for direct JSON-RPC testing.
"""

import json
import subprocess
import threading
import queue
import pytest
from typing import Optional


class MCPStdioProcess:
    """Low-level stdio client for integration testing."""

    def __init__(self, cmd: list[str], env: dict, verbose: bool = False):
        self.cmd = cmd
        self.env = env
        self.verbose = verbose
        self.proc: Optional[subprocess.Popen] = None
        self.out_queue: queue.Queue = queue.Queue()
        self._id_counter = 0
        self._reader_thread = None
        self._stop_reader = threading.Event()

    def start(self) -> None:
        """Start the subprocess and begin reading stdout."""
        self.proc = subprocess.Popen(
            self.cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self.env,
        )
        # Pump stdout to queue in background thread
        def pump():
            while not self._stop_reader.is_set():
                line = self.proc.stdout.readline()
                if line:
                    self.out_queue.put(line.strip())
                else:
                    break
        self._reader_thread = threading.Thread(target=pump, daemon=True)
        self._reader_thread.start()

    def next_id(self) -> int:
        self._id_counter += 1
        return self._id_counter

    def send(self, payload: dict) -> None:
        """Send a JSON-RPC message."""
        msg = json.dumps(payload) + "\n"
        self.proc.stdin.write(msg)
        self.proc.stdin.flush()

    def recv(self, timeout: float = 5.0) -> dict:
        """Receive a JSON-RPC response."""
        line = self.out_queue.get(timeout=timeout)
        return json.loads(line)

    def recv_all(self, timeout: float = 2.0) -> list[dict]:
        """Receive all available responses."""
        results = []
        while True:
            try:
                line = self.out_queue.get(timeout=timeout)
                results.append(json.loads(line))
            except queue.Empty:
                break
        return results

    def jsonrpc_request(self, method: str, params: dict = None) -> dict:
        """Send a JSON-RPC request and return the response."""
        payload = {
            "jsonrpc": "2.0",
            "id": self.next_id(),
            "method": method,
        }
        if params:
            payload["params"] = params
        self.send(payload)
        return self.recv()

    def close(self) -> None:
        """Close the subprocess."""
        self._stop_reader.set()
        if self.proc:
            try:
                self.proc.stdin.close()
            except Exception:
                pass
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()


@pytest.fixture
def stdio_server(env_config: dict):
    """Start portcullis server via stdio and yield a client."""
    client = MCPStdioProcess(
        cmd=["uv", "run", "python", "main.py"],
        env=env_config,
    )
    client.start()
    try:
        yield client
    finally:
        client.close()


@pytest.mark.integration
class TestStdioTransport:
    """Integration tests for stdio transport."""

    def test_initialize(self, stdio_server: MCPStdioProcess):
        """Test server initialization."""
        result = stdio_server.jsonrpc_request(
            "initialize",
            {"protocolVersion": "2024-11-05"}
        )
        assert result["jsonrpc"] == "2.0"
        assert "result" in result
        assert result["result"]["serverInfo"]["name"] == "portcullis"

    def test_list_tools(self, stdio_server: MCPStdioProcess):
        """Verify email plugin tools are registered."""
        # First initialize
        init_result = stdio_server.jsonrpc_request("initialize", {"protocolVersion": "2024-11-05"})
        print(f"Init result: {init_result}")

        # Then list tools
        result = stdio_server.jsonrpc_request("tools/list", {})
        print(f"Tools result: {result}")

        # Check for error response
        if "error" in result:
            pytest.fail(f"Error from tools/list: {result['error']}")

        tools = result["result"]["tools"]
        tool_names = {t["name"] for t in tools}

        assert "send_email" in tool_names
        assert "list_whitelist" in tool_names
        assert "add_to_whitelist" in tool_names

    def test_ping(self, stdio_server: MCPStdioProcess):
        """Test ping request/response."""
        stdio_server.jsonrpc_request("initialize", {"protocolVersion": "2024-11-05"})
        result = stdio_server.jsonrpc_request("ping", {})
        assert result["result"] == {}

    def test_list_whitelist(self, stdio_server: MCPStdioProcess):
        """Test list_whitelist tool returns configured recipients."""
        stdio_server.jsonrpc_request("initialize", {"protocolVersion": "2024-11-05"})

        # Use tools/call protocol to invoke plugin tools
        result = stdio_server.jsonrpc_request(
            "tools/call",
            {"name": "list_whitelist", "arguments": {}}
        )
        print(f"list_whitelist result: {result}")

        # Handle both success and error responses
        if "error" in result:
            pytest.fail(f"Error from list_whitelist: {result['error']}")

        assert result["result"]["isError"] is False
        content_text = result["result"]["content"][0]["text"]
        assert "alice@example.com" in content_text
        assert "bob@example.com" in content_text

    def test_send_email_recipient_not_found(self, stdio_server: MCPStdioProcess):
        """Test send_email error when recipient is not in whitelist."""
        stdio_server.jsonrpc_request("initialize", {"protocolVersion": "2024-11-05"})

        result = stdio_server.jsonrpc_request(
            "tools/call",
            {
                "name": "send_email",
                "arguments": {
                    "recipient_name": "Unknown",
                    "subject": "Test Subject",
                    "body": "Test body",
                }
            }
        )
        print(f"send_email result: {result}")

        # Check that the error message is in the content
        content_text = result["result"]["content"][0]["text"]
        assert "Unknown" in content_text
        assert "whitelist" in content_text.lower()

    def test_add_to_whitelist(self, stdio_server: MCPStdioProcess):
        """Test adding a new recipient to the whitelist."""
        stdio_server.jsonrpc_request("initialize", {"protocolVersion": "2024-11-05"})

        result = stdio_server.jsonrpc_request(
            "tools/call",
            {
                "name": "add_to_whitelist",
                "arguments": {
                    "name": "Charlie",
                    "email": "charlie@example.com",
                }
            }
        )
        print(f"add_to_whitelist result: {result}")

        assert result["result"]["isError"] is False
        content_text = result["result"]["content"][0]["text"]
        assert "Charlie" in content_text
        assert "charlie@example.com" in content_text

    def test_add_to_whitelist_invalid_email(self, stdio_server: MCPStdioProcess):
        """Test add_to_whitelist rejects invalid email format."""
        stdio_server.jsonrpc_request("initialize", {"protocolVersion": "2024-11-05"})

        result = stdio_server.jsonrpc_request(
            "tools/call",
            {
                "name": "add_to_whitelist",
                "arguments": {
                    "name": "Invalid",
                    "email": "notanemail",
                }
            }
        )
        print(f"add_to_whitelist invalid result: {result}")

        # Check that the error message is in the content
        content_text = result["result"]["content"][0]["text"]
        assert "Invalid" in content_text or "invalid" in content_text.lower()
        assert "email" in content_text.lower()
