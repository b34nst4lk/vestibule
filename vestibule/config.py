"""
Configuration loading for Vestibule MCP server.

Handles TOML configuration file loading with multi-level merge:
CLI --config > .vestibule/config.toml > ~/.vestibule/config.toml > defaults

Configuration is standardized on Pydantic models. The ``Config`` model is the
schema for server settings (``[tool.vestibule]``) and is the source of truth
for their typing/validation. Plugin configs
(``[tool.vestibule.plugins.<name>]``) are validated by each plugin's declared
Pydantic schema via the ``vestibule_config_schema`` hook.
"""

import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from .approval import ApprovalMode


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


class ApprovalSettings(BaseModel):
    """The ``[tool.vestibule.approval]`` section."""

    enabled: bool = True
    overrides: dict[str, ApprovalMode] = Field(default_factory=dict)


class Config(BaseModel):
    """Vestibule configuration.

    Standardized on Pydantic; the model's fields are the schema for the
    ``[tool.vestibule]`` section and are the source of truth for the typing and
    validation of server settings.
    """

    # Coerce raw TOML values (e.g. str transport -> Transport enum) on
    # assignment so `_merge` can assign them without manual conversion.
    model_config = ConfigDict(validate_assignment=True)

    host: str = "127.0.0.1"
    port: int = 8080
    transport: Transport = Transport.STDIO
    log_level: LogLevel = LogLevel.INFO
    plugins: dict[str, dict[str, Any]] = Field(default_factory=dict)
    rate_limits: dict[str, int] = Field(default_factory=dict)
    approval: ApprovalSettings = Field(default_factory=ApprovalSettings)

    # Runtime-only: plugin config schemas registered via the config schema hook.
    _plugin_schemas: dict[str, type] = PrivateAttr(default_factory=dict)

    # Backward-compatible accessors for the flattened approval fields.
    @property
    def approval_enabled(self) -> bool:
        return self.approval.enabled

    @property
    def approval_overrides(self) -> dict[str, ApprovalMode]:
        return self.approval.overrides

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
        """Load a single TOML config file into a flat dict for merging."""
        with open(path, "rb") as f:
            data = tomllib.load(f)
        vestibule = data.get("tool", {}).get("vestibule", {})

        result: dict[str, Any] = {}

        # Server settings + plugins + rate_limits + approval from
        # [tool.vestibule]. Values pass through raw; Pydantic coerces str ->
        # enums and builds the nested model on assignment in `_merge`
        # (Config.validate_assignment).
        for key in ("host", "port", "transport", "log_level", "plugins", "rate_limits", "approval"):
            if key in vestibule:
                result[key] = vestibule[key]

        return result

    def _merge(self, other: dict[str, Any]) -> None:
        """Merge another config dict into this config."""
        # Scalar/enum fields: plain assignment; validate_assignment coerces raw
        # TOML strings (e.g. "http" -> Transport.HTTP) to the field type.
        for field in ("host", "port", "transport", "log_level"):
            if field in other:
                setattr(self, field, other[field])
        if "plugins" in other:
            # Merge plugin configs
            for plugin_name, plugin_config in other["plugins"].items():
                if plugin_name not in self.plugins:
                    self.plugins[plugin_name] = {}
                self.plugins[plugin_name].update(plugin_config)
        if "rate_limits" in other:
            self.rate_limits.update(other["rate_limits"])
        if "approval" in other:
            self.approval = other["approval"]

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
