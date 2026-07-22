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
from .config import Config, Transport

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
    transport: Annotated[str | None, typer.Option("--transport", "-t")] = None,
    config: Annotated[str | None, typer.Option("--config", "-c")] = None,
) -> None:
    """
    Start the MCP server with loaded plugins.

    By default, runs on stdio transport. Use --transport http-sse for HTTP/SSE.
    Configuration is loaded from:
      1. CLI arguments (highest priority)
      2. .bulwark/config.toml (project config)
      3. ~/.bulwark/config.toml (user config)
      4. Built-in defaults
    """
    # Load configuration from TOML files
    cfg = Config.load(config)

    # CLI args override config file settings
    final_host = host or cfg.host
    final_port = port or cfg.port
    final_transport = transport or cfg.transport

    pm = PluginManager()
    pm.load_all()

    if not pm.get_loaded_plugins():
        typer.echo("Warning: No plugins loaded", err=True)

    # Register plugin config schemas for validation
    schemas = pm.get_plugin_config_schemas()
    for plugin_name, schema in schemas.items():
        cfg.register_plugin_schema(plugin_name, schema)

    # Validate configuration (fail-fast)
    validation_errors = cfg.validate()
    if validation_errors:
        typer.echo("Configuration validation failed:", err=True)
        for error in validation_errors:
            typer.echo(f"  - {error}", err=True)
        sys.exit(1)

    # Create the MCP server
    server = FastMCP("Bulwark")

    # Register plugin tools, resources, and prompts
    pm.register_tools(server)
    pm.register_resources(server)
    pm.register_prompts(server)

    # Initialize plugins with validated configs
    for plugin_name in pm.get_loaded_plugins():
        plugin_config = cfg.get_plugin_config(plugin_name)
        if plugin_name in schemas:
            # Validate and instantiate the Pydantic model
            schema = schemas[plugin_name]
            try:
                typed_config = schema(**plugin_config)
                pm.pm.hook.bulwark_init(config=typed_config)
            except Exception as e:
                typer.echo(f"Plugin '{plugin_name}' initialization failed: {e}", err=True)
                sys.exit(1)
        else:
            # Plugin has no schema, pass raw config
            pm.pm.hook.bulwark_init(config=plugin_config if plugin_config else None)

    # Validate secrets
    errors = pm.validate_secrets()
    if errors:
        typer.echo("Secret validation failed:", err=True)
        for plugin_name, error_msg in errors:
            typer.echo(f"  - {plugin_name}: {error_msg}", err=True)
        sys.exit(1)

    # Run the server
    typer.echo(f"Starting Bulwark server on {final_transport} transport...")

    if final_transport == Transport.STDIO:
        server.run(transport="stdio")
    elif final_transport in (Transport.HTTP_SSE, Transport.HTTP):
        server.run(transport="streamable-http", host=final_host, port=final_port)
    else:
        typer.echo(f"Unknown transport: {final_transport}", err=True)
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
