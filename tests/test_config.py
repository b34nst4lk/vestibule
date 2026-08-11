"""Tests for Vestibule configuration loading."""

import os
import tempfile
from pathlib import Path

import pytest
from pydantic import BaseModel

from vestibule.approval import ApprovalMode
from vestibule.config import ApprovalSettings, Config, LogLevel, Transport


@pytest.fixture(autouse=True)
def restore_env_and_cwd():
    """Restore environment and working directory after each test."""
    old_cwd = os.getcwd()
    old_home = os.environ.get("HOME")
    old_env = dict(os.environ)
    try:
        yield
    finally:
        os.chdir(old_cwd)
        if old_home:
            os.environ["HOME"] = old_home
        else:
            os.environ.pop("HOME", None)
        # Restore any other changed env vars
        for key in set(os.environ.keys()) - set(old_env.keys()):
            os.environ.pop(key, None)
        for key, value in old_env.items():
            os.environ[key] = value


class TestConfigDefaults:
    """Test default configuration values."""

    def test_default_values(self):
        """Test config has correct defaults."""
        config = Config()
        assert config.host == "127.0.0.1"
        assert config.port == 8080
        assert config.transport == "stdio"
        assert config.log_level == "info"
        assert config.plugins == {}

    def test_load_no_files(self):
        """Test load returns defaults when no config files exist."""
        # Use a temp dir to ensure no config files exist
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.environ["HOME"] = tmpdir
            config = Config.load()
            assert config.host == "127.0.0.1"
            assert config.port == 8080
            assert config.transport == "stdio"


class TestConfigFileLoading:
    """Test loading config from TOML files."""

    def test_load_user_config(self):
        """Test loading from ~/.vestibule/config.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.environ["HOME"] = tmpdir

            # Create user config
            user_config_dir = Path(tmpdir) / ".vestibule"
            user_config_dir.mkdir()
            user_config = user_config_dir / "config.toml"
            user_config.write_text("""
[tool.vestibule]
host = "0.0.0.0"
port = 9000
transport = "stdio"
log_level = "debug"
""")

            config = Config.load()
            assert config.host == "0.0.0.0"
            assert config.port == 9000
            assert config.transport == "stdio"
            assert config.log_level == "debug"

    def test_load_project_config(self):
        """Test loading from .vestibule/config.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.environ["HOME"] = "/nonexistent"  # Ensure no user config

            # Create project config
            project_config_dir = Path(tmpdir) / ".vestibule"
            project_config_dir.mkdir()
            project_config = project_config_dir / "config.toml"
            project_config.write_text("""
[tool.vestibule]
host = "127.0.0.1"
port = 8080
transport = "http-sse"
""")

            config = Config.load()
            assert config.host == "127.0.0.1"
            assert config.port == 8080
            assert config.transport == "http-sse"

    def test_cli_config_overrides(self):
        """Test CLI config file overrides project and user config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.environ["HOME"] = tmpdir

            # Create user config
            user_config_dir = Path(tmpdir) / ".vestibule"
            user_config_dir.mkdir()
            user_config = user_config_dir / "config.toml"
            user_config.write_text("""
[tool.vestibule]
host = "user.example.com"
port = 1111
""")

            # Create project config
            project_config_dir = Path(tmpdir) / ".vestibule"
            project_config_dir.mkdir(exist_ok=True)
            project_config = project_config_dir / "config.toml"
            project_config.write_text("""
[tool.vestibule]
host = "project.example.com"
port = 2222
""")

            # Create CLI config
            cli_config = Path(tmpdir) / "cli.toml"
            cli_config.write_text("""
[tool.vestibule]
host = "cli.example.com"
port = 3333
""")

            config = Config.load(str(cli_config))
            assert config.host == "cli.example.com"
            assert config.port == 3333

    def test_project_overrides_user(self):
        """Test project config overrides user config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.environ["HOME"] = tmpdir

            # Create user config
            user_config_dir = Path(tmpdir) / ".vestibule"
            user_config_dir.mkdir()
            user_config = user_config_dir / "config.toml"
            user_config.write_text("""
[tool.vestibule]
host = "user.example.com"
port = 1111
""")

            # Create project config
            project_config_dir = Path(tmpdir) / ".vestibule"
            project_config_dir.mkdir(exist_ok=True)
            project_config = project_config_dir / "config.toml"
            project_config.write_text("""
[tool.vestibule]
host = "project.example.com"
port = 2222
""")

            config = Config.load()
            assert config.host == "project.example.com"
            assert config.port == 2222


class TestPluginConfig:
    """Test plugin configuration loading."""

    def test_plugin_config(self):
        """Test loading plugin configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.environ["HOME"] = tmpdir

            config_dir = Path(tmpdir) / ".vestibule"
            config_dir.mkdir()
            config_file = config_dir / "config.toml"
            config_file.write_text("""
[tool.vestibule]
host = "127.0.0.1"

[tool.vestibule.plugins.whitelisted_email]
smtp_host = "smtp.gmail.com"
smtp_port = 587
sender_email = "test@example.com"

[tool.vestibule.plugins.whitelisted_email.whitelist]
alice = "alice@example.com"
bob = "bob@example.com"

[tool.vestibule.plugins.calendar]
timezone = "UTC"
""")

            config = Config.load()
            assert "whitelisted_email" in config.plugins
            assert config.plugins["whitelisted_email"]["smtp_host"] == "smtp.gmail.com"
            assert config.plugins["whitelisted_email"]["smtp_port"] == 587
            assert config.plugins["whitelisted_email"]["whitelist"]["alice"] == "alice@example.com"
            assert "calendar" in config.plugins
            assert config.plugins["calendar"]["timezone"] == "UTC"

    def test_get_plugin_config(self):
        """Test get_plugin_config method."""
        config = Config()
        config.plugins["email"] = {"smtp_host": "smtp.example.com"}

        email_config = config.get_plugin_config("email")
        assert email_config["smtp_host"] == "smtp.example.com"

        # Non-existent plugin returns empty dict
        missing_config = config.get_plugin_config("missing")
        assert missing_config == {}


class TestConfigMerge:
    """Test configuration merging."""

    def test_merge_partial_config(self):
        """Test merging partial config updates only specified fields."""
        config = Config()
        config.host = "original.example.com"
        config.port = 8080

        # Merge partial config
        config._merge({"port": 9000})

        assert config.host == "original.example.com"  # Unchanged
        assert config.port == 9000  # Updated

    def test_merge_plugin_configs(self):
        """Test plugin configs are merged correctly."""
        config = Config()
        config.plugins["email"] = {"smtp_host": "smtp1.example.com"}

        config._merge(
            {
                "plugins": {
                    "email": {"smtp_port": 587},
                    "calendar": {"timezone": "UTC"},
                }
            }
        )

        assert config.plugins["email"]["smtp_host"] == "smtp1.example.com"
        assert config.plugins["email"]["smtp_port"] == 587
        assert config.plugins["calendar"]["timezone"] == "UTC"

    def test_merge_rate_limits(self):
        """Test rate limits are merged correctly."""
        config = Config()
        config._merge({"rate_limits": {"send_email": 10}})
        assert config.rate_limits == {"send_email": 10}

        # Later merge updates rather than replaces
        config._merge({"rate_limits": {"list_whitelist": 120}})
        assert config.rate_limits == {"send_email": 10, "list_whitelist": 120}


class TestConfigRateLimits:
    """Test loading rate limits from TOML."""

    def test_load_rate_limits(self):
        """Test loading [tool.vestibule.rate_limits] from config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.environ["HOME"] = "/nonexistent"

            project_config_dir = Path(tmpdir) / ".vestibule"
            project_config_dir.mkdir()
            project_config = project_config_dir / "config.toml"
            project_config.write_text("""
[tool.vestibule]
host = "127.0.0.1"

[tool.vestibule.rate_limits]
send_email = 10
list_whitelist = 120
""")

            config = Config.load()
            assert config.rate_limits == {"send_email": 10, "list_whitelist": 120}

    def test_no_rate_limits_defaults_empty(self):
        """Config without rate_limits defaults to empty dict."""
        config = Config()
        assert config.rate_limits == {}


class TestConfigApproval:
    """Test loading approval config from TOML."""

    def test_default_approval(self):
        """Config defaults to enabled with no overrides."""
        config = Config()
        assert config.approval_enabled is True
        assert config.approval_overrides == {}

    def test_load_approval(self):
        """Test loading [tool.vestibule.approval] from config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.environ["HOME"] = "/nonexistent"

            project_config_dir = Path(tmpdir) / ".vestibule"
            project_config_dir.mkdir()
            project_config = project_config_dir / "config.toml"
            project_config.write_text("""
[tool.vestibule]
host = "127.0.0.1"

[tool.vestibule.approval]
enabled = true

[tool.vestibule.approval.overrides]
send_email = "never"
other_plugin_tool = "always"
""")

            config = Config.load()
            assert config.approval_enabled is True
            assert config.approval_overrides == {
                "send_email": "never",
                "other_plugin_tool": "always",
            }

    def test_load_approval_disabled(self):
        """Test loading approval with enabled = false."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.environ["HOME"] = "/nonexistent"

            project_config_dir = Path(tmpdir) / ".vestibule"
            project_config_dir.mkdir()
            project_config = project_config_dir / "config.toml"
            project_config.write_text("""
[tool.vestibule.approval]
enabled = false
""")

            config = Config.load()
            assert config.approval_enabled is False

    def test_merge_approval(self):
        """Test approval config is merged correctly."""
        config = Config()
        config._merge(
            {
                "approval_enabled": False,
                "approval_overrides": {"other_tool": "always"},
            }
        )
        assert config.approval_enabled is False
        assert config.approval_overrides == {"other_tool": "always"}

    def test_load_approval_overrides_are_approval_mode(self):
        """TOML-loaded override values are normalized to ApprovalMode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.environ["HOME"] = "/nonexistent"

            project_config_dir = Path(tmpdir) / ".vestibule"
            project_config_dir.mkdir()
            project_config = project_config_dir / "config.toml"
            project_config.write_text("""
[tool.vestibule.approval]
enabled = true

[tool.vestibule.approval.overrides]
send_email = "never"
""")

            config = Config.load()
            assert config.approval_overrides["send_email"] is ApprovalMode.NEVER

    def test_merge_approval_overrides_are_approval_mode(self):
        """Merged override values are normalized to ApprovalMode."""
        config = Config()
        config._merge({"approval_overrides": {"send_email": "first_only"}})
        assert config.approval_overrides["send_email"] is ApprovalMode.FIRST_ONLY

    def test_invalid_approval_override_raises(self):
        """An unknown override mode raises a clear error at load time."""
        config = Config()
        with pytest.raises(ValueError, match="Invalid approval mode"):
            config._merge({"approval_overrides": {"send_email": "sometimes"}})


class TestConfigPydanticModel:
    """Test that server settings are standardized on a Pydantic model."""

    def test_config_is_pydantic_model(self):
        """Config is a Pydantic BaseModel (schema as source of truth)."""
        assert issubclass(Config, BaseModel)

    def test_server_settings_fields(self):
        """Config declares the server-setting fields with their types."""
        fields = Config.model_fields
        assert set(fields) >= {
            "host",
            "port",
            "transport",
            "log_level",
            "plugins",
            "rate_limits",
            "approval",
        }
        assert fields["host"].annotation is str
        assert fields["port"].annotation is int
        assert fields["transport"].annotation is Transport
        assert fields["log_level"].annotation is LogLevel

    def test_approval_nested_model(self):
        """Approval is a nested Pydantic model mirroring the TOML section."""
        config = Config()
        assert isinstance(config.approval, ApprovalSettings)
        assert config.approval.enabled is True
        assert config.approval.overrides == {}

    def test_approval_overrides_coerced_via_model(self):
        """Setting approval_overrides (via setter) coerces strings to ApprovalMode."""
        config = Config()
        config.approval_overrides = {"send_email": "never"}
        assert config.approval.overrides["send_email"] is ApprovalMode.NEVER

    def test_backward_compat_approval_accessors(self):
        """Flattened approval_enabled/approval_overrides still work."""
        config = Config()
        assert config.approval_enabled is True
        config.approval_enabled = False
        assert config.approval.enabled is False

        config.approval_overrides = {"send_email": "first_only"}
        assert config.approval_overrides["send_email"] is ApprovalMode.FIRST_ONLY

    def test_log_level_snake_case(self):
        """[tool.vestibule] log_level (snake_case) is read from TOML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.environ["HOME"] = "/nonexistent"

            project_config_dir = Path(tmpdir) / ".vestibule"
            project_config_dir.mkdir()
            project_config = project_config_dir / "config.toml"
            project_config.write_text("""
[tool.vestibule]
log_level = "warning"
""")

            config = Config.load()
            assert config.log_level is LogLevel.WARNING
