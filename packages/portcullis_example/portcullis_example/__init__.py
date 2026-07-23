"""
Portcullis Example Plugin

This is a minimal example plugin demonstrating the Portcullis plugin API.
It provides a simple in-memory whitelist that plugin authors can use as
a starting point for their own plugins.

The plugin demonstrates:
- Plugin metadata registration
- Configuration schema with Pydantic
- Tool registration
- Runtime-only state (no persistence)
"""

from typing import Any

from pydantic import BaseModel, Field

from portcullis import hooks

# -----------------------------------------------------------------------------
# Configuration Schema
# -----------------------------------------------------------------------------


class ExamplePluginConfig(BaseModel):
    """Configuration schema for the example plugin."""

    # Initial whitelist entries (runtime only, not persisted)
    initial_whitelist: dict[str, str] = Field(
        default_factory=dict,
        description="Initial whitelist entries: {'friendly_name': 'email@example.com'}",
    )


# -----------------------------------------------------------------------------
# Runtime State (in-memory, not persisted)
# -----------------------------------------------------------------------------

# This is a simple in-memory whitelist
# In a real plugin, you might use a database or file persistence
_runtime_whitelist: dict[str, str] = {}


# -----------------------------------------------------------------------------
# Plugin Metadata
# -----------------------------------------------------------------------------


@hooks.hookimpl
def portcullis_register_plugin_info() -> tuple[str, hooks.PluginMetadata]:
    """Return plugin metadata."""
    meta = hooks.PluginMetadata(
        name="example",
        version="0.1.0",
        description="Example plugin demonstrating the Portcullis plugin API",
    )
    return "example", meta


# -----------------------------------------------------------------------------
# Configuration Schema Hook
# -----------------------------------------------------------------------------


@hooks.hookimpl
def portcullis_config_schema() -> type[BaseModel]:
    """Return the Pydantic config schema for this plugin."""
    return ExamplePluginConfig


# -----------------------------------------------------------------------------
# Initialization Hook (optional - called after config validation)
# -----------------------------------------------------------------------------


@hooks.hookimpl
def portcullis_init(config: ExamplePluginConfig) -> None:
    """
    Initialize the plugin with validated configuration.

    This is where you would set up connections, load data, etc.
    For this example, we just populate the initial whitelist.
    """
    global _runtime_whitelist
    _runtime_whitelist = config.initial_whitelist.copy()


# -----------------------------------------------------------------------------
# Tool Registration Hook
# -----------------------------------------------------------------------------


@hooks.hookimpl
def portcullis_register_tools(mcp_server: Any) -> None:
    """Register MCP tools with the server."""

    @mcp_server.tool()
    def list_whitelist() -> str:
        """
        List all whitelisted recipients.

        Returns:
            str: Formatted list of friendly names and their email addresses
        """
        if not _runtime_whitelist:
            return "No recipients in the whitelist."

        lines = ["Whitelisted recipients:"]
        for name, email in sorted(_runtime_whitelist.items()):
            lines.append(f"  - {name}: {email}")
        return "\n".join(lines)

    @mcp_server.tool()
    def add_to_whitelist(name: str, email: str) -> str:
        """
        Add a recipient to the whitelist.

        Note: This only adds to the runtime whitelist. The whitelist
        is NOT persisted and will be lost when the server restarts.

        Args:
            name: Friendly name for the recipient
            email: Actual email address

        Returns:
            str: Confirmation message or error description
        """
        # Validate email format (simple check)
        if "@" not in email or "." not in email.split("@")[-1]:
            return f"Error: Invalid email address format: {email}"

        # Add to runtime whitelist
        _runtime_whitelist[name.lower()] = email

        return f"Added '{name}' ({email}) to the whitelist."

    @mcp_server.tool()
    def remove_from_whitelist(name: str) -> str:
        """
        Remove a recipient from the whitelist.

        Args:
            name: Friendly name to remove

        Returns:
            str: Confirmation message or error description
        """
        name_lower = name.lower()
        if name_lower not in _runtime_whitelist:
            return f"Error: '{name}' is not in the whitelist."

        email = _runtime_whitelist.pop(name_lower)
        return f"Removed '{name}' ({email}) from the whitelist."
