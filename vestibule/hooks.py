"""
Pluggy hook specifications for Vestibule plugin system.

Plugins implement these hooks to register MCP tools, resources, and prompts
with the Vestibule server.
"""

import pluggy
from mcp.server.fastmcp import FastMCP
from pydantic import SecretStr

__all__ = ["hookspec", "hookimpl", "PluginMetadata", "SecretStr"]

hookspec = pluggy.HookspecMarker("vestibule")
hookimpl = pluggy.HookimplMarker("vestibule")


class PluginMetadata:
    """Metadata about a loaded plugin."""

    def __init__(
        self,
        name: str,
        version: str = "0.0.0",
        description: str = "",
        enabled: bool = True,
    ):
        self.name = name
        self.version = version
        self.description = description
        self.enabled = enabled


@hookspec(firstresult=True)
def vestibule_register_plugin_info() -> tuple[str, PluginMetadata]:
    """
    Hook spec for plugins to provide their metadata.

    Implementations should return a tuple of (plugin_name, PluginMetadata)
    with the plugin's name, version, description, and enabled status.

    Returns:
        tuple[str, PluginMetadata]: (plugin_name, metadata)

    Example:
        @hookimpl
        def vestibule_register_plugin_info():
            meta = PluginMetadata(
                name="email-whitelist",
                version="0.1.0",
                description="Email whitelisting plugin",
            )
            return "email-whitelist", meta
    """
    pass


@hookspec
def vestibule_register_tools(mcp_server: FastMCP) -> None:
    """
    Hook spec for plugins to register MCP tools.

    Implementations receive the FastMCP server instance and should register
    their tools using the server's tool registration mechanisms.

    Args:
        mcp_server: The FastMCP server instance to register tools with

    Example:
        @hookimpl
        def vestibule_register_tools(mcp_server: FastMCP):
            @mcp_server.tool()
            def send_email(recipient: str, body: str) -> str:
                \"\"\"Send an email to a recipient.\"\"\"
                return f"Email sent to {recipient}"
    """
    pass


@hookspec
def vestibule_register_resources(mcp_server: FastMCP) -> None:
    """
    Hook spec for plugins to register MCP resources.

    Implementations receive the FastMCP server instance and should register
    their resources using the server's resource registration mechanisms.

    Args:
        mcp_server: The FastMCP server instance to register resources with

    Example:
        @hookimpl
        def vestibule_register_resources(mcp_server: FastMCP):
            @mcp_server.resource("config://plugin/settings")
            def get_settings() -> dict:
                return {"key": "value"}
    """
    pass


@hookspec
def vestibule_register_prompts(mcp_server: FastMCP) -> None:
    """
    Hook spec for plugins to register MCP prompts.

    Implementations receive the FastMCP server instance and should register
    their prompts using the server's prompt registration mechanisms.

    Args:
        mcp_server: The FastMCP server instance to register prompts with

    Example:
        @hookimpl
        def vestibule_register_prompts(mcp_server: FastMCP):
            @mcp_server.prompt()
            def email_template(recipient: str) -> str:
                return f"Draft an email to {recipient}"
    """
    pass


@hookspec
def vestibule_validate_secrets() -> tuple[str, bool, str]:
    """
    Hook spec for plugins to validate their required secrets.

    Implementations should check that all required secrets are available
    and return a tuple of (plugin_name, is_valid, error_message).

    Returns:
        tuple[str, bool, str]: (plugin_name, is_valid, error_message) -
            error_message is only meaningful if is_valid is False

    Example:
        @hookimpl
        def vestibule_validate_secrets():
            if not os.getenv("SMTP_API_KEY"):
                return "email-plugin", False, "SMTP_API_KEY is required"
            return "email-plugin", True, ""
    """
    pass


@hookspec(firstresult=True)
def vestibule_config_schema() -> type:
    """
    Hook spec for plugins to declare their Pydantic config schema.

    Implementations should return a Pydantic BaseModel class that defines
    the plugin's configuration structure. The server uses this to validate
    TOML configuration before passing it to the plugin.

    Returns:
        type: A Pydantic BaseModel class for the plugin's config

    Example:
        from pydantic import BaseModel

        class EmailPluginConfig(BaseModel):
            smtp_host: str
            smtp_port: int = 587
            sender_email: str

        @hookimpl
        def vestibule_config_schema():
            return EmailPluginConfig
    """
    pass


@hookspec
def vestibule_init(config: type | None = None) -> None:
    """
    Hook spec for plugins to initialize with validated configuration.

    Implementations receive the validated Pydantic config model instance
    (or None if no config was provided). Use this to set up plugin state
    with the provided configuration.

    Args:
        config: The validated Pydantic config model instance, or None

    Example:
        @hookimpl
        def vestibule_init(config: EmailPluginConfig):
            global smtp_host
            smtp_host = config.smtp_host
    """
    pass
