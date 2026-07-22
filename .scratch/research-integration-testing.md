# MCP Integration Testing Research

Research date: 2026-07-17
Focus: Integration testing patterns for MCP servers against a running portcullis server

---

## Executive Summary

For the **portcullis** project, the recommended approach is:

1. **Unit/Component Tests**: Use **FastMCP with in-memory transport** (`FastMCPTransport`) - fastest, no subprocess/network overhead
2. **Integration Tests**: Use **stdio transport** with `stdio_client` from the official `mcp` package - tests real process boundaries
3. **HTTP/SSE Tests**: Use `streamable_http_client` for testing Streamable HTTP transport endpoints
4. **CI Helper**: Consider `pytest-mcp-plugin` for reusable fixtures and conformance testing

---

## 1. MCP Client Libraries

### Official `mcp` Package (Anthropic)

**Package**: [`mcp`](https://pypi.org/project/mcp/) on PyPI
**Repository**: [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)
**Documentation**: [py.sdk.modelcontextprotocol.io](https://py.sdk.modelcontextprotocol.io/)

**Installation**:
```bash
# Stable v1.x
uv add mcp

# Or with CLI tools
uv add "mcp[cli]"

# v2 (pre-release/beta as of 2026-07)
uv add "mcp>=2.0.0b1"
```

**Key Modules**:
- `mcp.client.stdio` - StdioServerParameters, stdio_client
- `mcp.client.streamable_http` - streamable_http_client
- `mcp` - ClientSession, types

### Third-Party Testing Libraries

#### pytest-mcp-plugin

**Package**: [`pytest-mcp-plugin`](https://pypi.org/project/pytest-mcp-plugin/)
**Repository**: [yagna-1/mcp-test](https://github.com/yagna-1/mcp-test)

**Installation**:
```bash
uv add --dev pytest-mcp-plugin

# For HTTP/FastMCP support
uv add --dev 'pytest-mcp-plugin[fastmcp]'
```

**Auto-registered Fixtures**:
| Fixture | Scope | Purpose |
|---------|-------|---------|
| `mcp_client` | session | One server process for whole test run |
| `mcp_client_fresh` | function | Clean state per test |
| `sandboxed_client` | function | Fresh server with tmp_path isolation |
| `snapshot` | function | Snapshot testing helper |

**Example**:
```python
from mcp_test import assert_tool_ok, assert_tool_error

def test_search_returns_results(mcp_client):
    result = mcp_client.call_tool("search", query="machine learning")
    assert_tool_ok(result)
    assert len(result.content) > 0
```

**CLI Commands**:
```bash
mcp-test demo      # Run bundled demo server + tests
mcp-test init      # Scaffold tests/ with example MCP tests
mcp-test run       # Run pytest against your server
mcp-test conformance  # Run Anthropic's conformance suite
```

#### mcp-testclient

**Package**: [`mcp-testclient`](https://pypi.org/project/mcp-testclient/)
**Repository**: [peytongreen-dev/mcp-testclient](https://github.com/peytongreen-dev/mcp-testclient)

Uses `anyio` memory streams to wire Server directly to ClientSession in-process.

---

## 2. Stdio Testing Patterns

### Official stdio_client Pattern

**Source**: [examples/snippets/clients/stdio_client.py](https://github.com/modelcontextprotocol/python-sdk/blob/main/examples/snippets/clients/stdio_client.py)

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run():
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "server", "fastmcp_quickstart", "stdio"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List tools
            tools = await session.list_tools()

            # Call a tool
            result = await session.call_tool("add", {"a": 5, "b": 3})
```

### StdioServerParameters

```python
from mcp import StdioServerParameters

server_params = StdioServerParameters(
    command="python",           # Executable to run
    args=["server.py"],         # Command line arguments
    env={"DEBUG": "true"},      # Extra environment variables
    cwd="/path/to/server",      # Working directory (optional)
    encoding="utf-8",           # Text encoding (default: utf-8)
    encoding_error_handler="strict",  # Error handler strategy
)
```

### Pytest Fixture for Stdio Testing

```python
# conftest.py
import pytest
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

@pytest.fixture
async def mcp_stdio_client(tmp_path: Path):
    """Spawn MCP server via stdio and yield initialized client session."""
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "main.py", "stdio"],
        env={"PORTCULLIS_DATA_DIR": str(tmp_path / "data")},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
```

### Test Example

```python
# tests/test_stdio_integration.py
import pytest
from mcp.types import TextContent

@pytest.mark.anyio
async def test_list_tools(mcp_stdio_client):
    tools_response = await mcp_stdio_client.list_tools()
    tool_names = {t.name for t in tools_response.tools}
    assert "portcullis_scan" in tool_names
    assert "portcullis_analyze" in tool_names

@pytest.mark.anyio
async def test_call_tool(mcp_stdio_client):
    result = await mcp_stdio_client.call_tool(
        "portcullis_scan",
        {"target": "test_target"}
    )
    assert result.isError is False
    assert len(result.content) > 0
```

### Low-Level subprocess Pattern (Alternative)

For more control, use direct subprocess management:

```python
import subprocess
import json
import threading
import queue
from typing import Optional

class MCPStdioClient:
    """Low-level stdio client with direct JSON-RPC control."""

    def __init__(self, cmd: list[str], verbose: bool = False):
        self.cmd = cmd
        self.verbose = verbose
        self.proc: Optional[subprocess.Popen] = None
        self.out_queue: queue.Queue = queue.Queue()
        self._id_counter = 0

    def start(self) -> None:
        self.proc = subprocess.Popen(
            self.cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Pump stdout to queue in background thread
        def pump():
            for line in self.proc.stdout:
                self.out_queue.put(line.strip())
        threading.Thread(target=pump, daemon=True).start()

    def next_id(self) -> int:
        self._id_counter += 1
        return self._id_counter

    def send(self, payload: dict) -> None:
        msg = json.dumps(payload) + "\n"
        self.proc.stdin.write(msg)
        self.proc.stdin.flush()

    def recv(self, timeout: float = 5.0) -> dict:
        line = self.out_queue.get(timeout=timeout)
        return json.loads(line)

    def rpc_request(self, method: str, params: dict = None) -> dict:
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
        if self.proc:
            self.proc.stdin.close()
            self.proc.wait(timeout=5)
```

---

## 3. HTTP/SSE Testing Patterns (Streamable HTTP Transport)

### Official streamable_http_client

**Source**: [examples/snippets/clients/streamable_basic.py](https://github.com/modelcontextprotocol/python-sdk/blob/main/examples/snippets/clients/streamable_basic.py)

```python
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main():
    async with streamable_http_client("http://localhost:8000/mcp") as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # List tools
            tools = await session.list_tools()
            print(f"Available tools: {[tool.name for tool in tools.tools]}")

            # Call a tool
            result = await session.call_tool("my_tool", {"arg": "value"})

if __name__ == "__main__":
    asyncio.run(main())
```

### With Custom httpx Client

```python
import asyncio
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main():
    http_client = httpx.AsyncClient(
        headers={"Authorization": "Bearer your-token"},
        timeout=httpx.Timeout(30, read=300),
        follow_redirects=True,
    )

    async with http_client:
        async with streamable_http_client(
            url="http://localhost:8000/mcp",
            http_client=http_client,
        ) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
```

### Capturing Session ID via httpx Event Hooks

In v2 SDK, `get_session_id` callback was removed. Use httpx event hooks:

```python
captured_session_ids = []

async def capture_session_id(response: httpx.Response) -> None:
    session_id = response.headers.get("mcp-session-id")
    if session_id:
        captured_session_ids.append(session_id)

http_client = httpx.AsyncClient(
    event_hooks={"response": [capture_session_id]},
    follow_redirects=True,
)
```

### Pytest Fixture for HTTP Testing

```python
# conftest.py
import pytest
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

@pytest.fixture
async def mcp_http_client():
    """Connect to running MCP HTTP server."""
    http_client = httpx.AsyncClient(
        base_url="http://localhost:8000",
        timeout=30.0,
    )

    async with http_client:
        async with streamable_http_client(
            url="http://localhost:8000/mcp",
            http_client=http_client,
        ) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session
```

### Direct httpx Testing (Lower Level)

For testing raw HTTP endpoints:

```python
import httpx
import pytest

@pytest.mark.asyncio
async def test_mcp_http_endpoint():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Initialize
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["protocolVersion"]

        # List tools
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            },
        )
        assert response.status_code == 200
```

---

## 4. MCP SDK Test Utilities

### In-Memory Transport (FastMCP)

**Source**: [FastMCP Testing Docs](https://gofastmcp.com/patterns/testing)

For FastMCP-based servers, use the built-in in-memory transport:

```python
from fastmcp import FastMCP, Client
from fastmcp.client.transports import FastMCPTransport

# Create server
server = FastMCP("TestServer")

@server.tool
def greet(name: str) -> str:
    return f"Hello, {name}!"

# Connect client directly (in-memory, no network/subprocess)
async with Client(transport=FastMCPTransport(server)) as client:
    result = await client.call_tool("greet", {"name": "World"})
    assert result.data == "Hello, World!"
```

### Official SDK Testing Guide

**Source**: [modelcontextprotocol/python-sdk/docs/testing.md](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/testing.md)

```python
from mcp import Client
from inline_snapshot import snapshot

@pytest.fixture
async def client():
    async with Client(app, raise_exceptions=True) as c:
        yield c

@pytest.mark.anyio
async def test_call_tool(client: Client):
    result = await client.call_tool("add", {"a": 1, "b": 2})
    assert result == snapshot(
        CallToolResult(
            content=[TextContent(type="text", text="3")],
            structuredContent={"result": 3},
        )
    )
```

### Official stdio Test Examples

**Source**: [tests/client/test_stdio.py](https://github.com/modelcontextprotocol/python-sdk/blob/main/tests/client/test_stdio.py)

Key test patterns from the official SDK:

```python
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

@pytest.mark.anyio
async def test_stdio_client():
    """Test sending/receiving JSON-RPC messages through stdio."""
    server_params = StdioServerParameters(
        command="python",
        args=["-c", "import sys; sys.stdin.read()"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Test initialization
            await session.initialize()

@pytest.mark.anyio
async def test_stdio_client_nonexistent_command():
    """Test error handling for non-existent commands."""
    server_params = StdioServerParameters(
        command="/nonexistent/command",
    )

    with pytest.raises(Exception):
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
```

### Child Process Cleanup Tests

Tests for `_terminate_process_tree()` verify entire process trees are killed:

```python
from mcp.client.stdio import _terminate_process_tree
import subprocess

def test_basic_child_process_cleanup():
    """Test parent with single child cleanup."""
    proc = subprocess.Popen(["sleep", "100"])
    _terminate_process_tree(proc)
    assert proc.poll() is not None
```

---

## 5. Recommended Approach for portcullis

### Project Setup

```bash
# Add testing dependencies
uv add --dev pytest pytest-asyncio anyio
uv add --dev pytest-mcp-plugin  # Optional but recommended
uv add --dev inline-snapshot     # For schema snapshot testing
```

### pytest Configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "unit: Unit tests (fast, no I/O)",
    "integration: Integration tests (stdio/HTTP)",
    "slow: Slow running tests",
]
```

### Directory Structure

```
portcullis/
├── main.py              # portcullis server entry point
├── tests/
│   ├── conftest.py      # Shared fixtures
│   ├── unit/            # Fast in-memory tests
│   │   └── test_tools.py
│   └── integration/     # Stdio/HTTP tests
│       ├── test_stdio.py
│       └── test_http.py
```

### conftest.py Template

```python
# tests/conftest.py
import pytest
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create isolated data directory per test."""
    data = tmp_path / "data"
    data.mkdir()
    return data

@pytest.fixture
async def mcp_stdio_client(data_dir: Path):
    """Spawn portcullis server via stdio and yield initialized client."""
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "main.py", "stdio"],
        env={"PORTCULLIS_DATA_DIR": str(data_dir)},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
```

### Example Test File

```python
# tests/integration/test_stdio.py
import pytest
from mcp.types import TextContent

@pytest.mark.integration
@pytest.mark.anyio
async def test_list_tools(mcp_stdio_client):
    """Verify expected tools are registered."""
    response = await mcp_stdio_client.list_tools()
    tool_names = {t.name for t in response.tools}

    # Adjust based on actual portcullis tools
    assert "portcullis_scan" in tool_names

@pytest.mark.integration
@pytest.mark.anyio
async def test_scan_tool(mcp_stdio_client):
    """Test the scan tool with valid input."""
    result = await mcp_stdio_client.call_tool(
        "portcullis_scan",
        {"target": "example.com"}
    )

    assert result.isError is False
    assert len(result.content) > 0
    assert isinstance(result.content[0], TextContent)

@pytest.mark.integration
@pytest.mark.anyio
async def test_scan_tool_invalid_input(mcp_stdio_client):
    """Test scan tool handles invalid input gracefully."""
    result = await mcp_stdio_client.call_tool(
        "portcullis_scan",
        {"target": ""}  # Invalid: empty target
    )

    assert result.isError is True
```

---

## 6. Gotchas and Pitfalls

### stdout Pollution

**Problem**: Every line on stdout MUST be valid JSON-RPC. Logging to stdout breaks the protocol.

**Solution**: Route all logging to stderr:
```python
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    stream=sys.stderr,  # NOT stdout
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

### Process Cleanup

**Problem**: Child processes may not be killed when parent exits.

**Solution**: Use the SDK's `_terminate_process_tree()` or ensure proper signal handling:
```python
import signal
import os

def handle_sigterm(signum, frame):
    # Cleanup resources
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_sigterm)
```

### Test Isolation

**Problem**: Tests sharing state cause flaky failures.

**Solution**: Use `tmp_path` fixture for per-test isolation:
```python
@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    return data
```

### Timeout Management

**Problem**: Tests hang waiting for responses.

**Solution**: Set reasonable timeouts:
```python
# In conftest.py or test file
@pytest.fixture
async def mcp_stdio_client(data_dir: Path):
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "main.py", "stdio"],
        env={"PORTCULLIS_DATA_DIR": str(data_dir)},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
    # Context manager exit handles cleanup with 2s timeout
```

### Environment Variable Inheritance

**Problem**: Server may not inherit expected environment variables.

**Solution**: Explicitly pass required env vars:
```python
server_params = StdioServerParameters(
    command="uv",
    args=["run", "python", "main.py", "stdio"],
    env={
        **os.environ,  # Inherit current env
        "PORTCULLIS_DATA_DIR": str(data_dir),
        "DEBUG": "true",
    },
)
```

### Protocol Version Negotiation

**Problem**: Client and server may use incompatible protocol versions.

**Solution**: Let the SDK handle negotiation automatically during `initialize()`:
```python
await session.initialize()  # Handles protocol negotiation
```

---

## 7. CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v3
        with:
          python-version: "3.13"

      - name: Install dependencies
        run: uv sync --dev

      - name: Run unit tests
        run: uv run pytest tests/unit -v -m "not integration"

      - name: Run integration tests
        run: uv run pytest tests/integration -v -m "integration"
```

### Test Markers for CI Scheduling

```python
# Run fast tests on every commit
uv run pytest tests/unit -v

# Run integration tests on PR merge
uv run pytest tests/integration -v -m "integration"

# Run all tests including slow ones
uv run pytest -v
```

---

## Sources

| Source | URL |
|--------|-----|
| MCP Python SDK | https://github.com/modelcontextprotocol/python-sdk |
| MCP Python SDK Docs | https://py.sdk.modelcontextprotocol.io/ |
| MCP Testing Guide | https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/testing.md |
| stdio Client Example | https://github.com/modelcontextprotocol/python-sdk/blob/main/examples/snippets/clients/stdio_client.py |
| Streamable HTTP Example | https://github.com/modelcontextprotocol/python-sdk/blob/main/examples/snippets/clients/streamable_basic.py |
| stdio Tests | https://github.com/modelcontextprotocol/python-sdk/blob/main/tests/client/test_stdio.py |
| Streamable HTTP Tests | https://github.com/modelcontextprotocol/python-sdk/blob/main/tests/shared/test_streamable_http.py |
| pytest-mcp-plugin | https://pypi.org/project/pytest-mcp-plugin/ |
| FastMCP Testing | https://gofastmcp.com/patterns/testing |
| Build MCP Client Tutorial | https://modelcontextprotocol.io/docs/develop/build-client |
| NiteAgent Testing Guide | https://niteagent.com/blog/mcp-server-testing-debugging-guide/ |
| ChatForest Testing Strategies | https://chatforest.com/guides/mcp-testing-strategies/ |

---

## Package Versions (as of 2026-07)

| Package | Version | Notes |
|---------|---------|-------|
| mcp | 1.28.1 (stable), 2.0.0b2 (beta) | Official SDK |
| pytest-mcp-plugin | 0.3.0 | Testing fixtures |
| mcp-testclient | 0.1.0 | In-memory testing |
| fastmcp | 3.4.2 | High-level API |
| pytest | 8.x | Test framework |
| pytest-asyncio | 0.24.x | Async test support |
