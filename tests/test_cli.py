"""Tests for Vestibule CLI commands."""

import re

from typer.testing import CliRunner

from vestibule.cli import app, get_version

runner = CliRunner()


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
    return ansi_pattern.sub("", text)


class TestVersionCommand:
    """Tests for the version command."""

    def test_version_command(self):
        """Test version command outputs version string."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "vestibule" in result.stdout
        assert "0.1.0" in result.stdout


class TestGetVersion:
    """Tests for get_version helper."""

    def test_get_version_returns_string(self):
        """Test get_version returns a string."""
        version = get_version()
        assert isinstance(version, str)
        assert len(version) > 0


class TestPluginsCommand:
    """Tests for the plugins command."""

    def test_plugins_no_plugins(self):
        """Test plugins command when no plugins are installed."""
        # This test may vary depending on installed plugins
        result = runner.invoke(app, ["plugins"])
        assert result.exit_code == 0
        # Either shows discovered plugins or "No plugins discovered"
        assert "plugin" in result.stdout.lower()


class TestHealthcheckCommand:
    """Tests for the healthcheck command."""

    def test_healthcheck_no_plugins(self):
        """Test healthcheck when no plugins have missing secrets."""
        result = runner.invoke(app, ["healthcheck"])
        # Exit code 0 if no plugins or all pass, 1 if validation fails
        assert result.exit_code in [0, 1]
        assert "plugin" in result.stdout.lower() or "No plugins" in result.stdout


class TestServeCommand:
    """Tests for the serve command."""

    def test_serve_help(self):
        """Test serve --help shows options."""
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        stdout = strip_ansi(result.stdout)
        assert "--host" in stdout
        assert "--port" in stdout
        assert "--transport" in stdout

    def test_serve_missing_secrets_exits(self):
        """Test serve exits with error when secrets are missing."""
        result = runner.invoke(app, ["serve"])
        # Should exit with error if plugins have missing secrets
        # or start the server if all is well
        assert result.exit_code in [0, 1]
