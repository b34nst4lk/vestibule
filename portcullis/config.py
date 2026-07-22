"""
Configuration loading for Bulwark MCP server.

Handles TOML configuration file loading with multi-level merge:
CLI --config > .portcullis/config.toml > ~/.portcullis/config.toml > defaults
"""

from enum import Enum
from pathlib import Path
from typing import Any

import tomllib


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    pass


class Transport(str, Enum):
    """Supported transport types."""

    STDIO = "stdio"
    HTTP_SSE = "http-sse"
    HTTP = "http"


class LogLevel(str, Enum):
    """Supported log levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Config:
    """Bulwark configuration."""

    def __init__(self):
        self.host: str = "127.0.0.1"
        self.port: int = 8080
        self.transport: Transport = Transport.STDIO
        self.log_level: LogLevel = LogLevel.INFO
        self.plugins: dict[str, dict[str, Any]] = {}
        self._plugin_schemas: dict[str, type] = {}

    @classmethod
    def load(cls, config_path: str | None = None) -> "Config":
        """
        Load configuration from TOML files with multi-level merge.

        Priority (highest to lowest):
        1. CLI --config argument
        2. .portcullis/config.toml (project config)
        3. ~/.portcullis/config.toml (user config)
        4. Built-in defaults

        Args:
            config_path: Optional explicit config file path from CLI

        Returns:
            Config: Merged configuration object
        """
        config = cls()

        # Load configs in reverse priority order (lowest first, so higher priority overwrites)
        user_config_path = Path.home() / ".portcullis" / "config.toml"
        project_config_path = Path.cwd() / ".portcullis" / "config.toml"

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

        # Extract server settings from [tool.portcullis]
        if "tool" in data and "portcullis" in data["tool"]:
            portcullis_config = data["tool"]["portcullis"]

            if "host" in portcullis_config:
                result["host"] = portcullis_config["host"]
            if "port" in portcullis_config:
                result["port"] = portcullis_config["port"]
            if "transport" in portcullis_config:
                # Convert string to Transport enum
                transport_val = portcullis_config["transport"]
                if isinstance(transport_val, str):
                    try:
                        result["transport"] = Transport(transport_val.lower())
                    except ValueError:
                        result["transport"] = transport_val  # Keep as string, validate later
                else:
                    result["transport"] = transport_val
            if "log-level" in portcullis_config:
                # Convert string to LogLevel enum
                log_level_val = portcullis_config["log-level"]
                if isinstance(log_level_val, str):
                    try:
                        result["log_level"] = LogLevel(log_level_val.lower())
                    except ValueError:
                        result["log_level"] = log_level_val  # Keep as string, validate later
                else:
                    result["log_level"] = log_level_val

        # Extract plugin configs from [tool.portcullis.plugins.<name>]
        if "tool" in data and "portcullis" in data["tool"]:
            portcullis_config = data["tool"]["portcullis"]
            if "plugins" in portcullis_config:
                result["plugins"] = portcullis_config["plugins"]

        return result

    def _merge(self, other: dict[str, Any]) -> None:
        """Merge another config dict into this config."""
        if "host" in other:
            self.host = other["host"]
        if "port" in other:
            self.port = other["port"]
        if "transport" in other:
            val = other["transport"]
            self.transport = val if isinstance(val, Transport) else Transport(val)
        if "log_level" in other:
            val = other["log_level"]
            self.log_level = val if isinstance(val, LogLevel) else LogLevel(val)
        if "plugins" in other:
            # Merge plugin configs
            for plugin_name, plugin_config in other["plugins"].items():
                if plugin_name not in self.plugins:
                    self.plugins[plugin_name] = {}
                self.plugins[plugin_name].update(plugin_config)

    def get_plugin_config(self, plugin_name: str) -> dict[str, Any]:
        """Get configuration for a specific plugin."""
        return self.plugins.get(plugin_name, {})

    def register_plugin_schema(self, plugin_name: str, schema: type) -> None:
        """
        Register a Pydantic schema for a plugin's configuration.

        Args:
            plugin_name: The plugin name
            schema: Pydantic BaseModel class for validation
        """
        self._plugin_schemas[plugin_name] = schema

    def validate(self) -> list[str]:
        """
        Validate the configuration.

        Returns:
            list[str]: List of validation error messages (empty if valid)

        Validates:
        - Port is in valid range (1-65535)
        - Plugin configs match their registered schemas
        """
        errors = []

        # Validate port
        if not (1 <= self.port <= 65535):
            errors.append(f"Port must be between 1 and 65535, got {self.port}")

        # Transport and log_level are now enums, validated at assignment time

        # Validate plugin configs against schemas
        for plugin_name, config in self.plugins.items():
            if plugin_name in self._plugin_schemas:
                try:
                    schema = self._plugin_schemas[plugin_name]
                    schema(**config)
                except Exception as e:
                    errors.append(f"Plugin '{plugin_name}' config validation failed: {e}")

        return errors
