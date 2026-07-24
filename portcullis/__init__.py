"""Portcullis - A plugin-based MCP server."""

from .hooks import PluginMetadata, SecretStr, hookimpl, hookspec
from .plugin_manager import PluginManager

__all__ = [
    "hookimpl",
    "hookspec",
    "PluginMetadata",
    "PluginManager",
    "SecretStr",
]
