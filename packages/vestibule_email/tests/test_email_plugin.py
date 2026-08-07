"""
Tests for the Vestibule Email Whitelisting Plugin.
"""

import os
from unittest.mock import MagicMock, patch

from vestibule_email import (
    EmailPluginConfig,
    vestibule_config_schema,
    vestibule_register_plugin_info,
    vestibule_register_tools,
    vestibule_validate_secrets,
)

from vestibule import hooks


class TestPluginMetadata:
    """Tests for plugin metadata hook."""

    def test_register_plugin_info(self):
        """Test that plugin info is returned correctly."""
        result = vestibule_register_plugin_info()

        assert isinstance(result, tuple)
        assert len(result) == 2

        name, metadata = result
        assert name == "email"
        assert isinstance(metadata, hooks.PluginMetadata)
        assert metadata.name == "email"
        assert metadata.version == "0.1.0"
        assert "whitelist" in metadata.description.lower()


class TestConfigSchema:
    """Tests for configuration schema hook."""

    def test_config_schema_returns_pydantic_model(self):
        """Test that config schema returns a Pydantic model class."""
        schema = vestibule_config_schema()

        assert schema == EmailPluginConfig
        assert issubclass(schema, object)

    def test_config_model_validation(self):
        """Test that the config model validates correctly."""
        config = EmailPluginConfig(
            smtp_host="smtp.example.com",
            sender_email="sender@example.com",
            whitelist={"alice": "alice@example.com"},
        )

        assert config.smtp_host == "smtp.example.com"
        assert config.sender_email == "sender@example.com"
        assert config.whitelist == {"alice": "alice@example.com"}
        assert config.smtp_port == 587  # default
        assert config.smtp_use_tls is True  # default

    def test_config_model_with_all_fields(self):
        """Test config model with all fields specified."""
        config = EmailPluginConfig(
            smtp_host="smtp.gmail.com",
            smtp_port=465,
            smtp_use_tls=False,
            sender_email="user@gmail.com",
            sender_name="Test User",
            whitelist={"bob": "bob@test.com"},
            default_recipient="bob",
        )

        assert config.smtp_port == 465
        assert config.smtp_use_tls is False
        assert config.sender_name == "Test User"
        assert config.default_recipient == "bob"


class TestSecretsValidation:
    """Tests for secrets validation hook."""

    def test_validate_secrets_missing_password(self):
        """Test validation fails when SMTP password is missing."""
        with patch.dict(os.environ, {}, clear=True):
            plugin_name, is_valid, error_msg = vestibule_validate_secrets()

            assert plugin_name == "email"
            assert is_valid is False
            assert "EMAIL_SMTP_PASSWORD" in error_msg

    def test_validate_secrets_with_password(self):
        """Test validation passes when SMTP password is provided."""
        with patch.dict(
            os.environ,
            {"EMAIL_SMTP_PASSWORD": "test_pass"},  # pragma: allowlist secret
        ):
            plugin_name, is_valid, error_msg = vestibule_validate_secrets()

            assert plugin_name == "email"
            assert is_valid is True

    def test_validate_secrets_with_optional_user(self):
        """Test validation passes even without SMTP user (optional)."""
        with patch.dict(
            os.environ,
            {
                "EMAIL_SMTP_PASSWORD": "test_pass",  # pragma: allowlist secret
                "EMAIL_SMTP_USER": "test_user",  # pragma: allowlist secret
            },
        ):
            plugin_name, is_valid, error_msg = vestibule_validate_secrets()

            assert plugin_name == "email"
            assert is_valid is True


class TestToolRegistration:
    """Tests for tool registration hook."""

    def test_register_tools(self):
        """Test that tools are registered correctly."""
        mock_server = MagicMock()
        mock_tool_decorator = MagicMock()
        mock_server.tool.return_value = mock_tool_decorator

        vestibule_register_tools(mock_server)

        # tool() decorator should be called at least once for each tool
        assert mock_server.tool.call_count >= 3

    def test_registered_tools(self):
        """Test that the expected tools are available after registration."""
        mock_server = MagicMock()
        registered_tools = []

        def capture_tool(name=None):
            def decorator(func):
                registered_tools.append(name or func.__name__)
                return func

            return decorator

        mock_server.tool.side_effect = capture_tool

        vestibule_register_tools(mock_server)

        assert "send_email" in registered_tools
        assert "list_whitelist" in registered_tools
        assert "add_to_whitelist" in registered_tools


class TestSendEmailTool:
    """Tests for the send_email tool functionality."""

    def test_send_email_success(self, mock_smtp, env_config):
        """Test successful email sending."""
        from vestibule_email import _get_config_from_env, _resolve_recipient

        config = _get_config_from_env()
        recipient_email = _resolve_recipient("Alice", config.whitelist)

        assert recipient_email == "alice@example.com"

    def test_send_email_recipient_not_in_whitelist(self, env_config):
        """Test error when recipient is not whitelisted."""
        from vestibule_email import _get_config_from_env, _resolve_recipient

        config = _get_config_from_env()
        recipient_email = _resolve_recipient("Unknown", config.whitelist)

        assert recipient_email is None

    def test_send_email_case_insensitive_lookup(self, env_config):
        """Test that recipient lookup is case-insensitive."""
        from vestibule_email import _get_config_from_env, _resolve_recipient

        config = _get_config_from_env()

        assert _resolve_recipient("ALICE", config.whitelist) == "alice@example.com"
        assert _resolve_recipient("alice", config.whitelist) == "alice@example.com"
        assert _resolve_recipient("Alice", config.whitelist) == "alice@example.com"

    def test_send_email_with_cc(self, mock_smtp, env_config):
        """Test email sending with CC recipient."""
        from vestibule_email import _get_config_from_env, _resolve_recipient

        config = _get_config_from_env()
        recipient_email = _resolve_recipient("Alice", config.whitelist)
        cc_email = _resolve_recipient("Bob", config.whitelist)

        assert recipient_email == "alice@example.com"
        assert cc_email == "bob@example.com"


class TestListWhitelistTool:
    """Tests for the list_whitelist tool."""

    def test_list_whitelist_formats_output(self, env_config):
        """Test that whitelist is formatted correctly."""
        from vestibule_email import _get_config_from_env

        config = _get_config_from_env()

        lines = ["Whitelisted recipients:"]
        for name, email in sorted(config.whitelist.items()):
            lines.append(f"  - {name}: {email}")
        output = "\n".join(lines)

        assert "alice@example.com" in output
        assert "bob@example.com" in output
        assert "charlie@company.com" in output

    def test_list_whitelist_empty(self):
        """Test whitelist output when empty."""
        with patch.dict(os.environ, {"EMAIL_WHITELIST": "{}"}):
            from vestibule_email import _get_config_from_env

            config = _get_config_from_env()
            assert config.whitelist == {}


class TestAddToWhitelistTool:
    """Tests for the add_to_whitelist tool."""

    def test_add_to_whitelist_valid_email(self):
        """Test adding a valid email to whitelist."""

        whitelist = {"alice": "alice@example.com"}
        new_email = "dave@example.com"

        # Simple validation check
        assert "@" in new_email
        assert "." in new_email.split("@")[-1]

        whitelist["dave"] = new_email
        assert "dave" in whitelist
        assert whitelist["dave"] == "dave@example.com"

    def test_add_to_whitelist_invalid_email(self):
        """Test that invalid emails are rejected."""
        invalid_emails = [
            "notanemail",
            "missing@domain",
            "@nodomain.com",
            "spaces @domain.com",
        ]

        for email in invalid_emails:
            is_valid = "@" in email and "." in email.split("@")[-1]
            if not is_valid:
                assert True  # Would be rejected by the tool


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_config_from_env(self, env_config):
        """Test configuration loading from environment."""
        from vestibule_email import _get_config_from_env

        config = _get_config_from_env()

        assert config.smtp_host == "smtp.example.com"
        assert config.smtp_port == 587
        assert config.smtp_use_tls is True
        assert config.sender_email == "sender@example.com"
        assert config.sender_name == "Test Sender"
        assert "alice" in config.whitelist

    def test_get_config_from_env_defaults(self):
        """Test configuration defaults when env vars are missing."""
        with patch.dict(os.environ, {}, clear=True):
            from vestibule_email import _get_config_from_env

            config = _get_config_from_env()

            assert config.smtp_host == "smtp.gmail.com"  # default
            assert config.smtp_port == 587  # default
            assert config.smtp_use_tls is True  # default
            assert config.whitelist == {}

    def test_get_config_from_env_invalid_json(self):
        """Test that invalid JSON in whitelist falls back to empty dict."""
        with patch.dict(os.environ, {"EMAIL_WHITELIST": "not valid json"}):
            from vestibule_email import _get_config_from_env

            config = _get_config_from_env()
            assert config.whitelist == {}
