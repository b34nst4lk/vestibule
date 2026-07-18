"""
Configuration loading for Bulwark MCP server.

Handles TOML configuration file loading with multi-level merge:
CLI --config > .bulwark/config.toml > ~/.bulwark/config.toml > defaults
"""

import os
from pathlib import Path
from typing import Any

import tomllib


class Config:
    """Bulwark configuration."""

    def __init__(self):
        self.host: str = "127.0.0.1"
        self.port: int = 8080
        self.transport: str = "stdio"
        self.log_level: str = "info"
        self.plugins: dict[str, dict[str, Any]] = {}

    @classmethod
    def load(cls, config_path: str | None = None) -> "Config":
        """
        Load configuration from TOML files with multi-level merge.

        Priority (highest to lowest):
        1. CLI --config argument
        2. .bulwark/config.toml (project config)
        3. ~/.bulwark/config.toml (user config)
        4. Built-in defaults

        Args:
            config_path: Optional explicit config file path from CLI

        Returns:
            Config: Merged configuration object
        """
        config = cls()

        # Load configs in reverse priority order (lowest first, so higher priority overwrites)
        user_config_path = Path.home() / ".bulwark" / "config.toml"
        project_config_path = Path.cwd() / ".bulwark" / "config.toml"

        config_files = [
            user_config_path,
            project_config_path,
        ]

        # CLI config has highest priority
        if config_path:
            config_files.append(Path(config_path))

        for file_path in config_files:
            if file_path.exists():
                file_config = cls._load_file(file_path)
                config._merge(file_config)

        return config

    @classmethod
    def _load_file(cls, path: Path) -> dict[str, Any]:
        """Load a single TOML config file."""
        with open(path, "rb") as f:
            data = tomllib.load(f)

        result = {}

        # Extract server settings from [tool.bulwark]
        if "tool" in data and "bulwark" in data["tool"]:
            bulwark_config = data["tool"]["bulwark"]

            if "host" in bulwark_config:
                result["host"] = bulwark_config["host"]
            if "port" in bulwark_config:
                result["port"] = bulwark_config["port"]
            if "transport" in bulwark_config:
                result["transport"] = bulwark_config["transport"]
            if "log-level" in bulwark_config:
                result["log_level"] = bulwark_config["log-level"]

        # Extract plugin configs from [tool.bulwark.plugins.<name>]
        if "tool" in data and "bulwark" in data["tool"]:
            bulwark_config = data["tool"]["bulwark"]
            if "plugins" in bulwark_config:
                result["plugins"] = bulwark_config["plugins"]

        return result

    def _merge(self, other: dict[str, Any]) -> None:
        """Merge another config dict into this config."""
        if "host" in other:
            self.host = other["host"]
        if "port" in other:
            self.port = other["port"]
        if "transport" in other:
            self.transport = other["transport"]
        if "log_level" in other:
            self.log_level = other["log_level"]
        if "plugins" in other:
            # Merge plugin configs
            for plugin_name, plugin_config in other["plugins"].items():
                if plugin_name not in self.plugins:
                    self.plugins[plugin_name] = {}
                self.plugins[plugin_name].update(plugin_config)

    def get_plugin_config(self, plugin_name: str) -> dict[str, Any]:
        """Get configuration for a specific plugin."""
        return self.plugins.get(plugin_name, {})
