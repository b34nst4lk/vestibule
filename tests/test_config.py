"""Tests for Bulwark configuration loading."""

import os
import tempfile
from pathlib import Path

import pytest

from portcullis.config import Config


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
        """Test loading from ~/.portcullis/config.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.environ["HOME"] = tmpdir

            # Create user config
            user_config_dir = Path(tmpdir) / ".portcullis"
            user_config_dir.mkdir()
            user_config = user_config_dir / "config.toml"
            user_config.write_text("""
[tool.portcullis]
host = "0.0.0.0"
port = 9000
transport = "stdio"
log-level = "debug"
""")

            config = Config.load()
            assert config.host == "0.0.0.0"
            assert config.port == 9000
            assert config.transport == "stdio"
            assert config.log_level == "debug"

    def test_load_project_config(self):
        """Test loading from .portcullis/config.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.environ["HOME"] = "/nonexistent"  # Ensure no user config

            # Create project config
            project_config_dir = Path(tmpdir) / ".portcullis"
            project_config_dir.mkdir()
            project_config = project_config_dir / "config.toml"
            project_config.write_text("""
[tool.portcullis]
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
            user_config_dir = Path(tmpdir) / ".portcullis"
            user_config_dir.mkdir()
            user_config = user_config_dir / "config.toml"
            user_config.write_text("""
[tool.portcullis]
host = "user.example.com"
port = 1111
""")

            # Create project config
            project_config_dir = Path(tmpdir) / ".portcullis"
            project_config_dir.mkdir(exist_ok=True)
            project_config = project_config_dir / "config.toml"
            project_config.write_text("""
[tool.portcullis]
host = "project.example.com"
port = 2222
""")

            # Create CLI config
            cli_config = Path(tmpdir) / "cli.toml"
            cli_config.write_text("""
[tool.portcullis]
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
            user_config_dir = Path(tmpdir) / ".portcullis"
            user_config_dir.mkdir()
            user_config = user_config_dir / "config.toml"
            user_config.write_text("""
[tool.portcullis]
host = "user.example.com"
port = 1111
""")

            # Create project config
            project_config_dir = Path(tmpdir) / ".portcullis"
            project_config_dir.mkdir(exist_ok=True)
            project_config = project_config_dir / "config.toml"
            project_config.write_text("""
[tool.portcullis]
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

            config_dir = Path(tmpdir) / ".portcullis"
            config_dir.mkdir()
            config_file = config_dir / "config.toml"
            config_file.write_text("""
[tool.portcullis]
host = "127.0.0.1"

[tool.portcullis.plugins.email]
smtp_host = "smtp.gmail.com"
smtp_port = 587
sender_email = "test@example.com"

[tool.portcullis.plugins.email.whitelist]
alice = "alice@example.com"
bob = "bob@example.com"

[tool.portcullis.plugins.calendar]
timezone = "UTC"
""")

            config = Config.load()
            assert "email" in config.plugins
            assert config.plugins["email"]["smtp_host"] == "smtp.gmail.com"
            assert config.plugins["email"]["smtp_port"] == 587
            assert config.plugins["email"]["whitelist"]["alice"] == "alice@example.com"
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
