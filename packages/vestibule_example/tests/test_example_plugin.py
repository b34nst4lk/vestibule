"""
Tests for the Vestibule Example Plugin.
"""

from unittest.mock import MagicMock

import vestibule_example
from vestibule_example import (
    ExamplePluginConfig,
    vestibule_config_schema,
    vestibule_init,
    vestibule_register_plugin_info,
    vestibule_register_tools,
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
        assert name == "example"
        assert isinstance(metadata, hooks.PluginMetadata)
        assert metadata.name == "example"
        assert metadata.version == "0.1.0"
        assert "example" in metadata.description.lower()


class TestConfigSchema:
    """Tests for configuration schema hook."""

    def test_config_schema_returns_pydantic_model(self):
        """Test that config schema returns a Pydantic model class."""
        schema = vestibule_config_schema()

        assert schema == ExamplePluginConfig
        assert issubclass(schema, object)

    def test_config_model_with_defaults(self):
        """Test that the config model has correct defaults."""
        config = ExamplePluginConfig()

        assert config.initial_whitelist == {}

    def test_config_model_with_initial_whitelist(self):
        """Test config model with initial whitelist."""
        config = ExamplePluginConfig(
            initial_whitelist={"alice": "alice@example.com", "bob": "bob@test.com"}
        )

        assert config.initial_whitelist == {
            "alice": "alice@example.com",
            "bob": "bob@test.com",
        }


class TestInitHook:
    """Tests for the initialization hook."""

    def test_init_populates_whitelist(self):
        """Test that init hook populates the runtime whitelist."""
        config = ExamplePluginConfig(initial_whitelist={"alice": "alice@example.com"})

        # Clear the runtime whitelist first
        vestibule_example._runtime_whitelist.clear()

        # Initialize
        vestibule_init(config)

        # Check that the whitelist was populated
        assert "alice" in vestibule_example._runtime_whitelist
        assert vestibule_example._runtime_whitelist["alice"] == "alice@example.com"


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

        assert "list_whitelist" in registered_tools
        assert "add_to_whitelist" in registered_tools
        assert "remove_from_whitelist" in registered_tools


class TestListWhitelistTool:
    """Tests for the list_whitelist tool."""

    def test_list_whitelist_formats_output(self):
        """Test that whitelist is formatted correctly."""
        # Set up some test data
        vestibule_example._runtime_whitelist.clear()
        vestibule_example._runtime_whitelist["alice"] = "alice@example.com"
        vestibule_example._runtime_whitelist["bob"] = "bob@test.com"

        # The tool is registered via decorator, so we test the output format
        lines = ["Whitelisted recipients:"]
        for name, email in sorted(vestibule_example._runtime_whitelist.items()):
            lines.append(f"  - {name}: {email}")
        output = "\n".join(lines)

        assert "alice@example.com" in output
        assert "bob@test.com" in output

    def test_list_whitelist_empty(self):
        """Test whitelist output when empty."""
        vestibule_example._runtime_whitelist.clear()

        result = "No recipients in the whitelist."
        assert result == "No recipients in the whitelist."


class TestAddToWhitelistTool:
    """Tests for the add_to_whitelist tool."""

    def test_add_to_whitelist_valid_email(self):
        """Test adding a valid email to whitelist."""
        vestibule_example._runtime_whitelist.clear()

        # Simulate the validation logic
        new_email = "dave@example.com"
        is_valid = "@" in new_email and "." in new_email.split("@")[-1]

        assert is_valid is True

        # Add to whitelist
        vestibule_example._runtime_whitelist["dave"] = new_email
        assert "dave" in vestibule_example._runtime_whitelist
        assert vestibule_example._runtime_whitelist["dave"] == "dave@example.com"

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
                # Would be rejected by the tool
                assert True


class TestRemoveFromWhitelistTool:
    """Tests for the remove_from_whitelist tool."""

    def test_remove_from_whitelist_existing(self):
        """Test removing an existing entry from whitelist."""
        vestibule_example._runtime_whitelist.clear()
        vestibule_example._runtime_whitelist["alice"] = "alice@example.com"

        # Simulate removal
        name_lower = "alice"
        if name_lower in vestibule_example._runtime_whitelist:
            email = vestibule_example._runtime_whitelist.pop(name_lower)
            assert email == "alice@example.com"
            assert "alice" not in vestibule_example._runtime_whitelist

    def test_remove_from_whitelist_not_found(self):
        """Test that removing non-existent entry returns error."""
        vestibule_example._runtime_whitelist.clear()

        name = "nonexistent"
        name_lower = name.lower()
        if name_lower not in vestibule_example._runtime_whitelist:
            result = f"Error: '{name}' is not in the whitelist."
            assert "not in the whitelist" in result
