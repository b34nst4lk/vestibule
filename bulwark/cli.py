"""
Bulwark CLI - Plugin-based MCP server.

Commands:
    serve       - Start the MCP server with loaded plugins
    healthcheck - Validate plugin secrets and configuration
    plugins     - Manage plugins (list, info)
"""

import sys
from typing import Annotated

import typer
from mcp.server.fastmcp import FastMCP

from .plugin_manager import PluginManager

app = typer.Typer(help="Bulwark - Plugin-based MCP server")


def get_version() -> str:
    """Get the Bulwark version."""
    try:
        import importlib.metadata
        return importlib.metadata.version("bulwark")
    except importlib.metadata.PackageNotFoundError:
        return "0.1.0 (dev)"


@app.command()
def version() -> None:
    """Show Bulwark version."""
    typer.echo(f"bulwark {get_version()}")


@app.command()
def serve(
    host: Annotated[str | None, typer.Option("--host", "-h")] = None,
    port: Annotated[int | None, typer.Option("--port", "-p")] = None,
    transport: Annotated[str, typer.Option("--transport", "-t")] = "stdio",
    config: Annotated[str | None, typer.Option("--config", "-c")] = None,
) -> None:
    """
    Start the MCP server with loaded plugins.

    By default, runs on stdio transport. Use --transport http-sse for HTTP/SSE.
    """
    pm = PluginManager()
    pm.load_all()

    if not pm.get_loaded_plugins():
        typer.echo("Warning: No plugins loaded", err=True)

    # Create the MCP server
    server = FastMCP("Bulwark")

    # Register plugin tools, resources, and prompts
    pm.register_tools(server)
    pm.register_resources(server)
    pm.register_prompts(server)

    # Validate secrets
    errors = pm.validate_secrets()
    if errors:
        typer.echo("Secret validation failed:", err=True)
        for plugin_name, error_msg in errors:
            typer.echo(f"  - {plugin_name}: {error_msg}", err=True)
        sys.exit(1)

    # Run the server
    typer.echo(f"Starting Bulwark server on {transport} transport...")

    if transport == "stdio":
        server.run(transport="stdio")
    elif transport == "http-sse":
        server.run(transport="streamable-http", host=host or "127.0.0.1", port=port or 8000)
    else:
        typer.echo(f"Unknown transport: {transport}", err=True)
        sys.exit(1)


@app.command()
def healthcheck(
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """
    Validate plugin secrets and configuration.

    Checks that all required environment variables are set for loaded plugins.
    """
    pm = PluginManager()
    pm.load_all()

    loaded = pm.get_loaded_plugins()
    if not loaded:
        typer.echo("No plugins loaded.")
        sys.exit(0)

    typer.echo("Loading plugins...")
    typer.echo()

    errors = pm.validate_secrets()
    total_checks = len(loaded)
    failed_count = len(errors)
    passed_count = total_checks - failed_count

    # Display results per plugin
    for plugin_name in loaded:
        meta = pm.get_metadata(plugin_name)
        display_name = meta.name if meta else plugin_name
        typer.echo(f"{display_name} ({plugin_name}):")

        # Check if this plugin has validation errors
        plugin_errors = [e for e in errors if e[0] == plugin_name]
        if plugin_errors:
            for _, error_msg in plugin_errors:
                typer.echo(f"  ✗ {error_msg}", err=True)
        else:
            typer.echo("  ✓ Secrets validated")
        typer.echo()

    # Summary
    typer.echo(f"Summary: {failed_count} failed, {passed_count} passed.")

    if errors:
        sys.exit(1)


@app.command()
def plugins(
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """
    List loaded plugins.

    Shows all plugins discovered via entry points.
    """
    pm = PluginManager()
    discovered = pm.discover_plugins()

    if not discovered:
        typer.echo("No plugins discovered.")
        typer.echo()
        typer.echo("Install plugins with:")
        typer.echo("  pip install bulwark-<name>")
        return

    typer.echo(f"Discovered {len(discovered)} plugin(s):")
    typer.echo()

    for name in discovered:
        loaded = pm.load_plugin(name)
        if loaded:
            meta = pm.get_metadata(name)
            if meta:
                typer.echo(f"  • {meta.name} v{meta.version}")
                if verbose and meta.description:
                    typer.echo(f"    {meta.description}")
            else:
                typer.echo(f"  • {name}")
        else:
            typer.echo(f"  • {name} (failed to load)", err=True)


def main() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
