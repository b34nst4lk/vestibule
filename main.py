"""
Bulwark MCP Server - Main Entry Point

Runs the MCP server with stdio transport, loading all discovered plugins.
"""

import asyncio
import sys

from mcp.server.fastmcp import FastMCP

from bulwark import PluginManager
from bulwark.transports.stdio import StdioTransport


def create_server() -> FastMCP:
    """Create and configure the FastMCP server."""
    return FastMCP("bulwark")


async def main() -> int:
    """
    Main entry point for the Bulwark MCP server.

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    print("Starting Bulwark MCP Server...", file=sys.stderr)

    # Create the MCP server
    mcp_server = create_server()

    # Initialize plugin manager and load plugins
    plugin_manager = PluginManager()
    plugin_manager.load_all()

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

    # Create and run the stdio transport
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


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
