"""
Plugin manager for Vestibule MCP server.

Handles plugin discovery, loading, and coordination of hook calls.
"""

import importlib.metadata
from typing import Any

import pluggy
from mcp.server.fastmcp import FastMCP

from . import hooks
from .hooks import PluginMetadata


class _NamespacedServer:
    """Thin FastMCP proxy that prefixes tool/prompt names with a plugin name.

    Plugins register tools with bare names; the plugin manager wraps the real
    server so each tool is exposed as ``<plugin_name>.<tool_name>``. This makes
    tool names globally unique across plugins and lets approval policies and
    operator overrides target a specific plugin's tool unambiguously.

    A shared ``registry`` (set of full names) is passed to every wrapper so a
    duplicate name across plugins fails loudly instead of silently overwriting.
    """

    def __init__(self, server: FastMCP, prefix: str, registry: set[str]):
        self._server = server
        self._prefix = prefix
        self._registry = registry

    def tool(self, name: str | None = None, **kwargs):
        """Register a tool under ``<prefix>.<name>``."""

        def deco(fn):
            full = f"{self._prefix}.{name or fn.__name__}"
            self._claim(full, "tool")
            return self._server.tool(name=full, **kwargs)(fn)

        return deco

    def prompt(self, name: str | None = None, **kwargs):
        """Register a prompt under ``<prefix>.<name>``."""

        def deco(fn):
            full = f"{self._prefix}.{name or fn.__name__}"
            self._claim(full, "prompt")
            return self._server.prompt(name=full, **kwargs)(fn)

        return deco

    def _claim(self, full: str, kind: str) -> None:
        if full in self._registry:
            raise ValueError(
                f"Duplicate {kind} name '{full}' across plugins. "
                f"{kind.capitalize()} names are namespaced by plugin and must be unique."
            )
        self._registry.add(full)

    def __getattr__(self, item):
        # Delegate everything else (e.g. resource registration) unchanged.
        return getattr(self._server, item)


class PluginManager:
    """Manages plugin discovery, loading, and hook coordination."""

    ENTRY_POINT_GROUP = "vestibule.plugins"

    def __init__(self):
        self.pm = pluggy.PluginManager("vestibule")
        self.pm.add_hookspecs(hooks)
        self._plugins: dict[str, Any] = {}
        self._metadata: dict[str, PluginMetadata] = {}

    def discover_plugins(self) -> list[str]:
        """
        Discover plugins via entry points.

        Returns:
            list[str]: List of discovered plugin names
        """
        discovered = []
        try:
            entry_points = importlib.metadata.entry_points()
            # Handle both old and new entry_points API
            if hasattr(entry_points, "select"):
                plugin_eps = entry_points.select(group=self.ENTRY_POINT_GROUP)
            else:
                plugin_eps = entry_points.get(self.ENTRY_POINT_GROUP, [])

            for ep in plugin_eps:
                discovered.append(ep.name)
        except Exception:
            pass  # No plugins installed yet

        return discovered

    def load_plugin(self, name: str) -> bool:
        """
        Load a plugin by name.

        Args:
            name: The plugin name (entry point name)

        Returns:
            bool: True if loaded successfully, False otherwise
        """
        try:
            entry_points = importlib.metadata.entry_points()
            if hasattr(entry_points, "select"):
                plugin_eps = entry_points.select(group=self.ENTRY_POINT_GROUP)
            else:
                plugin_eps = entry_points.get(self.ENTRY_POINT_GROUP, [])

            ep = next((e for e in plugin_eps if e.name == name), None)
            if ep is None:
                return False

            plugin = ep.load()
            self.pm.register(plugin, name=name)
            self._plugins[name] = plugin

            # Get plugin metadata (firstresult=True returns tuple directly)
            metadata_result = self.pm.hook.vestibule_register_plugin_info()
            if metadata_result and isinstance(metadata_result, tuple):
                plugin_name, meta = metadata_result
                if isinstance(meta, PluginMetadata):
                    self._metadata[plugin_name] = meta

            return True
        except Exception:
            return False

    def load_all(self) -> None:
        """Load all discovered plugins."""
        for name in self.discover_plugins():
            self.load_plugin(name)

    def register_tools(self, mcp_server: FastMCP) -> None:
        """
        Call vestibule_register_tools hook on all loaded plugins.

        Each plugin's tools are registered under a ``<plugin_name>.<tool>``
        namespace so names are globally unique across plugins.

        Args:
            mcp_server: The FastMCP server instance
        """
        registry: set[str] = set()
        for plugin_name in self._plugins:
            plugin = self._plugins[plugin_name]
            if hasattr(plugin, "vestibule_register_tools"):
                plugin.vestibule_register_tools(
                    _NamespacedServer(mcp_server, plugin_name, registry)
                )

    def register_resources(self, mcp_server: FastMCP) -> None:
        """
        Call vestibule_register_resources hook on all loaded plugins.

        Args:
            mcp_server: The FastMCP server instance
        """
        for plugin_name in self._plugins:
            plugin = self._plugins[plugin_name]
            if hasattr(plugin, "vestibule_register_resources"):
                plugin.vestibule_register_resources(
                    _NamespacedServer(mcp_server, plugin_name, set())
                )

    def register_prompts(self, mcp_server: FastMCP) -> None:
        """
        Call vestibule_register_prompts hook on all loaded plugins.

        Each plugin's prompts are registered under a ``<plugin_name>.<prompt>``
        namespace so names are globally unique across plugins.

        Args:
            mcp_server: The FastMCP server instance
        """
        registry: set[str] = set()
        for plugin_name in self._plugins:
            plugin = self._plugins[plugin_name]
            if hasattr(plugin, "vestibule_register_prompts"):
                plugin.vestibule_register_prompts(
                    _NamespacedServer(mcp_server, plugin_name, registry)
                )

    def validate_secrets(self) -> list[tuple[str, str]]:
        """
        Call vestibule_validate_secrets hook on all loaded plugins.

        Returns:
            list[tuple[str, str]]: List of (plugin_name, error_message) for
                plugins that failed validation
        """
        errors = []
        results = self.pm.hook.vestibule_validate_secrets()

        for result in results:
            if isinstance(result, tuple) and len(result) == 3:
                plugin_name, is_valid, error_msg = result
                if not is_valid:
                    errors.append((plugin_name, error_msg))

        return errors

    def get_loaded_plugins(self) -> list[str]:
        """Return list of loaded plugin names."""
        return list(self._plugins.keys())

    def get_metadata(self, name: str) -> PluginMetadata | None:
        """Get metadata for a loaded plugin."""
        return self._metadata.get(name)

    def get_plugin_config_schemas(self) -> dict[str, type]:
        """
        Collect config schemas from all loaded plugins.

        Returns:
            dict[str, type]: Mapping of plugin_name -> Pydantic schema class
        """
        schemas = {}

        # Iterate plugins and call their vestibule_config_schema hook
        for plugin_name in self._plugins:
            plugin = self._plugins[plugin_name]
            if hasattr(plugin, "vestibule_config_schema"):
                try:
                    schema = plugin.vestibule_config_schema()
                    if schema:
                        schemas[plugin_name] = schema
                except Exception:
                    pass  # Plugin doesn't define config schema

        return schemas

    def collect_approval_policies(self) -> dict[str, str]:
        """
        Collect per-tool approval policies from all loaded plugins.

        Each plugin's ``vestibule_approval_policy`` hook returns a dict
        mapping bare tool name -> approval mode. Results are merged across
        plugins, with each tool namespaced as ``<plugin_name>.<tool>`` so
        policies are unambiguous across plugins.

        Returns:
            dict[str, str]: Mapping of namespaced tool name -> approval mode.
        """
        policies: dict[str, str] = {}
        for plugin_name in self._plugins:
            plugin = self._plugins[plugin_name]
            if hasattr(plugin, "vestibule_approval_policy"):
                try:
                    result = plugin.vestibule_approval_policy()
                    if result:
                        for tool, mode in result.items():
                            policies[f"{plugin_name}.{tool}"] = mode
                except Exception:
                    pass  # Plugin doesn't declare an approval policy
        return policies
