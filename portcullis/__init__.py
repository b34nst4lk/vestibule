"""Portcullis - A plugin-based MCP server."""

from .hooks import hookimpl, hookspec, PluginMetadata
from .plugin_manager import PluginManager

__all__ = [
    "hookimpl",
    "hookspec",
    "PluginMetadata",
    "PluginManager",
]
