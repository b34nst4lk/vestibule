"""Tests for the ``vestibule config`` command family (get/set/unset/list)."""

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vestibule.cli import app

runner = CliRunner()


@pytest.fixture
def config_dir(monkeypatch):
    """A scratch cwd with a writable project config, isolated HOME."""
    with tempfile.TemporaryDirectory() as tmpdir:
        proj = Path(tmpdir) / ".vestibule"
        proj.mkdir()
        (proj / "config.toml").write_text(
            """
# top comment
[tool.vestibule]
host = "localhost"
port = 8080
log_level = "info"  # keep me

[tool.vestibule.rate_limits]
send_email = 10  # per minute
"""
        )
        monkeypatch.chdir(tmpdir)
        monkeypatch.setenv("HOME", str(Path(tmpdir) / "nohome"))
        yield proj / "config.toml"


def run_config(*args, config_file=None):
    """Invoke the config subcommand in-process."""
    return runner.invoke(app, ["config", *args])


class TestGet:
    def test_get_effective_value(self, config_dir):
        r = run_config("get", "tool.vestibule.host")
        assert r.exit_code == 0
        assert r.output.strip() == "localhost"

    def test_get_default_when_unset(self, config_dir):
        r = run_config("get", "tool.vestibule.transport")
        assert r.exit_code == 0
        assert r.output.strip() == "stdio"

    def test_get_unknown_key_fails(self, config_dir):
        r = run_config("get", "tool.vestibule.nope")
        assert r.exit_code == 1
        assert "Unknown config key" in r.output

    def test_get_missing_value_not_set(self, config_dir):
        r = run_config("get", "tool.vestibule.rate_limits.does_not_exist")
        assert r.exit_code == 1
        assert "not set" in r.output


class TestSet:
    def test_set_and_roundtrip_preserves_comments(self, config_dir):
        r = run_config("set", "tool.vestibule.port", "9000", "--file", str(config_dir))
        assert r.exit_code == 0
        text = config_dir.read_text()
        assert "# top comment" in text
        assert 'log_level = "info"  # keep me' in text
        assert "port = 9000" in text

    def test_set_coerces_bool_and_int(self, config_dir):
        run_config("set", "tool.vestibule.approval.enabled", "false", "--file", str(config_dir))
        run_config(
            "set", "tool.vestibule.rate_limits.list_whitelist", "120", "--file", str(config_dir)
        )
        text = config_dir.read_text()
        assert "enabled = false" in text
        assert "list_whitelist = 120" in text

    def test_set_invalid_value_fails(self, config_dir):
        r = run_config("set", "tool.vestibule.port", "notanumber", "--file", str(config_dir))
        assert r.exit_code == 1
        assert "Invalid value" in r.output

    def test_set_unknown_key_fails(self, config_dir):
        r = run_config("set", "tool.vestibule.nope", "x", "--file", str(config_dir))
        assert r.exit_code == 1
        assert "Unknown config key" in r.output

    def test_set_schema_less_plugin_refused(self, config_dir):
        r = run_config(
            "set", "tool.vestibule.plugins.not_a_plugin.x", "y", "--file", str(config_dir)
        )
        assert r.exit_code == 1
        assert "no config schema" in r.output

    def test_set_plugin_unknown_field_refused(self, config_dir):
        r = run_config(
            "set",
            "tool.vestibule.plugins.whitelisted_email.smtp_host",
            "smtp.gmail.com",
            "--file",
            str(config_dir),
        )
        assert r.exit_code == 0
        r = run_config(
            "set",
            "tool.vestibule.plugins.whitelisted_email.nope",
            "x",
            "--file",
            str(config_dir),
        )
        assert r.exit_code == 1
        assert "Unknown config key" in r.output


class TestUnset:
    def test_unset_removes_key(self, config_dir):
        r = run_config("unset", "tool.vestibule.rate_limits.send_email", "--file", str(config_dir))
        assert r.exit_code == 0
        assert "send_email" not in config_dir.read_text()

    def test_unset_missing_is_noop(self, config_dir):
        r = run_config("unset", "tool.vestibule.rate_limits.nope", "--file", str(config_dir))
        assert r.exit_code == 0
        assert "no-op" in r.output

    def test_unset_section(self, config_dir):
        run_config("set", "tool.vestibule.rate_limits.foo", "1", "--file", str(config_dir))
        r = run_config(
            "unset", "--section", "tool.vestibule.rate_limits", "--file", str(config_dir)
        )
        assert r.exit_code == 0
        assert "rate_limits" not in config_dir.read_text()


class TestList:
    def test_list_shows_merged_with_source(self, config_dir):
        r = run_config("list")
        assert r.exit_code == 0
        assert "host = localhost  (project)" in r.output
        assert "transport = stdio  (default)" in r.output
        assert "Config sources:" in r.output
