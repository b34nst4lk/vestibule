"""
Tests for loading a user-managed .env file into the process environment.
"""

import os

from vestibule.envfile import load_env_file, load_env_into_environment


class TestLoadEnvFile:
    """Tests for parsing a .env file into a dict."""

    def test_loads_key_value_pairs(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("ALPHA=one\nBETA=two\n")
        assert load_env_file(env_path) == {"ALPHA": "one", "BETA": "two"}

    def test_export_prefix_and_inline_comment(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("export GREETING=hello world  # salutation\n")
        assert load_env_file(env_path) == {"GREETING": "hello world"}

    def test_double_quoted_value_with_comment(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text('HASH="a # not a comment"\n')
        assert load_env_file(env_path) == {"HASH": "a # not a comment"}

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_env_file(tmp_path / "absent.env") == {}


class TestLoadEnvIntoEnvironment:
    """Tests for loading a .env file into the process environment."""

    def test_loads_values_into_environment(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("ALPHA=one\nBETA=two\n")
        load_env_into_environment(env_path)
        assert os.getenv("ALPHA") == "one"
        assert os.getenv("BETA") == "two"

    def test_does_not_override_existing_environment(self, tmp_path, monkeypatch):
        env_path = tmp_path / ".env"
        env_path.write_text("BETA=file_value\n")
        monkeypatch.setenv("BETA", "pre_existing")
        load_env_into_environment(env_path)
        assert os.getenv("BETA") == "pre_existing"

    def test_missing_file_is_noop(self, tmp_path):
        load_env_into_environment(tmp_path / "absent.env")
        assert os.getenv("NOT_SET_BY_THIS_TEST") is None
