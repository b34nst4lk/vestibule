"""
Configuration loading for Vestibule MCP server.

Handles TOML configuration file loading with multi-level merge:
CLI --config > .vestibule/config.toml > ~/.vestibule/config.toml > defaults
"""

import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Any

from .approval import ApprovalMode, normalize_approval_modes


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    pass


class Transport(StrEnum):
    """Supported transport types."""

    STDIO = "stdio"
    HTTP_SSE = "http-sse"
    HTTP = "http"


class LogLevel(StrEnum):
    """Supported log levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Config:
    """Vestibule configuration."""

    def __init__(self):
        self.host: str = "127.0.0.1"
        self.port: int = 8080
        self.transport: Transport = Transport.STDIO
        self.log_level: LogLevel = LogLevel.INFO
        self.plugins: dict[str, dict[str, Any]] = {}
        self.rate_limits: dict[str, int] = {}
        self.approval_enabled: bool = True
        self.approval_overrides: dict[str, ApprovalMode] = {}
        self._plugin_schemas: dict[str, type] = {}

    @classmethod
    def load(cls, config_path: str | None = None) -> "Config":
        """
        Load configuration from TOML files with multi-level merge.

        Priority (highest to lowest):
        1. CLI --config argument
        2. .vestibule/config.toml (project config)
        3. ~/.vestibule/config.toml (user config)
        4. Built-in defaults

        Args:
            config_path: Optional explicit config file path from CLI

        Returns:
            Config: Merged configuration object
        """
        config = cls()

        # Load configs in reverse priority order (lowest first, so higher priority overwrites)
        user_config_path = Path.home() / ".vestibule" / "config.toml"
        project_config_path = Path.cwd() / ".vestibule" / "config.toml"

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

        # Extract server settings from [tool.vestibule]
        if "tool" in data and "vestibule" in data["tool"]:
            vestibule_config = data["tool"]["vestibule"]

            if "host" in vestibule_config:
                result["host"] = vestibule_config["host"]
            if "port" in vestibule_config:
                result["port"] = vestibule_config["port"]
            if "transport" in vestibule_config:
                # Convert string to Transport enum
                transport_val = vestibule_config["transport"]
                if isinstance(transport_val, str):
                    try:
                        result["transport"] = Transport(transport_val.lower())
                    except ValueError:
                        result["transport"] = transport_val  # Keep as string, validate later
                else:
                    result["transport"] = transport_val
            if "log-level" in vestibule_config:
                # Convert string to LogLevel enum
                log_level_val = vestibule_config["log-level"]
                if isinstance(log_level_val, str):
                    try:
                        result["log_level"] = LogLevel(log_level_val.lower())
                    except ValueError:
                        result["log_level"] = log_level_val  # Keep as string, validate later
                else:
                    result["log_level"] = log_level_val

        # Extract plugin configs from [tool.vestibule.plugins.<name>]
        if "tool" in data and "vestibule" in data["tool"]:
            vestibule_config = data["tool"]["vestibule"]
            if "plugins" in vestibule_config:
                result["plugins"] = vestibule_config["plugins"]

        # Extract rate limits from [tool.vestibule.rate_limits]
        if "tool" in data and "vestibule" in data["tool"]:
            vestibule_config = data["tool"]["vestibule"]
            if "rate_limits" in vestibule_config:
                result["rate_limits"] = vestibule_config["rate_limits"]

        # Extract approval config from [tool.vestibule.approval]
        if "tool" in data and "vestibule" in data["tool"]:
            vestibule_config = data["tool"]["vestibule"]
            if "approval" in vestibule_config:
                approval_config = vestibule_config["approval"]
                if "enabled" in approval_config:
                    result["approval_enabled"] = approval_config["enabled"]
                if "overrides" in approval_config:
                    result["approval_overrides"] = approval_config["overrides"]

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
        if "rate_limits" in other:
            self.rate_limits.update(other["rate_limits"])
        if "approval_enabled" in other:
            self.approval_enabled = other["approval_enabled"]
        if "approval_overrides" in other:
            self.approval_overrides = normalize_approval_modes(other["approval_overrides"])

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
