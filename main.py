"""
Vestibule MCP Server - Main Entry Point

Runs the MCP server with stdio or HTTP/SSE transport, loading all discovered plugins.

Usage:
    python main.py                    # stdio transport (default)
    python main.py --transport http   # HTTP/SSE transport
    python main.py --transport http --port 8080  # HTTP/SSE on custom port
"""

import argparse
import asyncio
import sys

from mcp.server.fastmcp import FastMCP

from vestibule import PluginManager
from vestibule.approval import APPROVE_TOOL_NAME, configure_approval, grant_approval
from vestibule.config import Config
from vestibule.transports.http_sse import HTTPSSETransport
from vestibule.transports.stdio import StdioTransport


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Vestibule MCP Server - Plugin-based MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1, only for http transport)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080, only for http transport)",
    )
    return parser.parse_args()


def create_server() -> FastMCP:
    """Create and configure the FastMCP server."""
    return FastMCP("vestibule")


async def run_stdio(mcp_server: FastMCP) -> int:
    """Run the server with stdio transport."""
    transport = StdioTransport(mcp_server)
    print("Server ready. Waiting for requests on stdin...", file=sys.stderr)

    try:
        await transport.run()
    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        return 1

    return 0


async def run_http_sse(mcp_server: FastMCP, host: str, port: int) -> int:
    """Run the server with HTTP/SSE transport."""
    transport = HTTPSSETransport(mcp_server, host=host, port=port)
    print(f"Server ready. Listening on http://{host}:{port}", file=sys.stderr)
    print("  - POST /mcp for JSON-RPC messages", file=sys.stderr)
    print("  - GET /mcp?session=<id> for SSE stream", file=sys.stderr)
    print("  - GET /health for health check", file=sys.stderr)

    try:
        await transport.run()
    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        return 1

    return 0


async def main() -> int:
    """
    Main entry point for the Vestibule MCP server.

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    args = parse_args()

    print(f"Starting Vestibule MCP Server ({args.transport} transport)...", file=sys.stderr)

    # Create the MCP server
    mcp_server = create_server()

    # Initialize plugin manager and load plugins
    plugin_manager = PluginManager()
    plugin_manager.load_all()

    # Configure the shared approval tracker from plugin-declared policies
    # plus operator overrides. Plugins must be loaded first so their
    # vestibule_approval_policy hooks are available.
    cfg = Config.load()
    policies = plugin_manager.collect_approval_policies()
    configure_approval(cfg.approval_enabled, policies, cfg.approval_overrides)

    # Register the built-in approval tool so clients can grant approval
    @mcp_server.tool(name=APPROVE_TOOL_NAME)
    def approve_tool(tool_name: str) -> str:
        """Approve a tool for execution (grants human-in-the-loop approval)."""
        grant_approval(tool_name)
        return f"Approved tool '{tool_name}'."

    # Register tools, resources, and prompts from plugins
    plugin_manager.register_tools(mcp_server)
    plugin_manager.register_resources(mcp_server)
    plugin_manager.register_prompts(mcp_server)

    # Validate plugin secrets
    errors = plugin_manager.validate_secrets()
    if errors:
        print("Secret validation errors:", file=sys.stderr)
        for plugin_name, error_msg in errors:
            print(f"  - {plugin_name}: {error_msg}", file=sys.stderr)
        print("Continuing anyway (some tools may fail)...", file=sys.stderr)

    # Report loaded plugins
    loaded_plugins = plugin_manager.get_loaded_plugins()
    if loaded_plugins:
        print(f"Loaded plugins: {', '.join(loaded_plugins)}", file=sys.stderr)
    else:
        print("No plugins loaded.", file=sys.stderr)

    # Run the appropriate transport
    if args.transport == "stdio":
        return await run_stdio(mcp_server)
    elif args.transport == "http":
        return await run_http_sse(mcp_server, args.host, args.port)
    else:
        print(f"Unknown transport: {args.transport}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
