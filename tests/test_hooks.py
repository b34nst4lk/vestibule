"""Tests for Portcullis hook specifications and plugin manager."""

from mcp.server.fastmcp import FastMCP

from portcullis.hooks import (
    PluginMetadata,
    hookimpl,
    portcullis_register_plugin_info,
    portcullis_register_prompts,
    portcullis_register_resources,
    portcullis_register_tools,
    portcullis_validate_secrets,
)
from portcullis.plugin_manager import PluginManager


class TestPluginMetadata:
    """Tests for PluginMetadata class."""

    def test_create_with_defaults(self):
        """Test creating PluginMetadata with default values."""
        meta = PluginMetadata(name="test-plugin")
        assert meta.name == "test-plugin"
        assert meta.version == "0.0.0"
        assert meta.description == ""
        assert meta.enabled is True

    def test_create_with_values(self):
        """Test creating PluginMetadata with all values specified."""
        meta = PluginMetadata(
            name="email-whitelist",
            version="1.0.0",
            description="Email whitelisting plugin",
            enabled=False,
        )
        assert meta.name == "email-whitelist"
        assert meta.version == "1.0.0"
        assert meta.description == "Email whitelisting plugin"
        assert meta.enabled is False


class TestHookSpecs:
    """Tests for hook specifications."""

    def test_hookspec_markers_exist(self):
        """Test that hookspec and hookimpl markers are defined."""
        assert hookimpl is not None
        assert callable(hookimpl)

    def test_portcullis_register_plugin_info_hook(self):
        """Test that portcullis_register_plugin_info hook spec exists."""
        assert portcullis_register_plugin_info is not None

    def test_portcullis_register_tools_hook(self):
        """Test that portcullis_register_tools hook spec exists."""
        assert portcullis_register_tools is not None

    def test_portcullis_register_resources_hook(self):
        """Test that portcullis_register_resources hook spec exists."""
        assert portcullis_register_resources is not None

    def test_portcullis_register_prompts_hook(self):
        """Test that portcullis_register_prompts hook spec exists."""
        assert portcullis_register_prompts is not None

    def test_portcullis_validate_secrets_hook(self):
        """Test that portcullis_validate_secrets hook spec exists."""
        assert portcullis_validate_secrets is not None


class MockPlugin:
    """Mock plugin for testing."""

    @hookimpl
    def portcullis_register_plugin_info(self):
        meta = PluginMetadata(
            name="mock-plugin",
            version="0.1.0",
            description="A mock plugin for testing",
        )
        return "mock-plugin", meta

    @hookimpl
    def portcullis_register_tools(self, mcp_server: FastMCP) -> None:
        @mcp_server.tool()
        def mock_tool(x: int) -> int:
            """A mock tool that doubles the input."""
            return x * 2

    @hookimpl
    def portcullis_register_resources(self, mcp_server: FastMCP) -> None:
        @mcp_server.resource("mock://config")
        def get_config() -> dict:
            return {"key": "value"}

    @hookimpl
    def portcullis_register_prompts(self, mcp_server: FastMCP) -> None:
        @mcp_server.prompt()
        def mock_prompt(name: str) -> str:
            return f"Hello, {name}!"

    @hookimpl
    def portcullis_validate_secrets(self):
        return "mock", True, ""


class MockPluginWithMissingSecrets:
    """Mock plugin that fails secret validation."""

    @hookimpl
    def portcullis_register_plugin_info(self):
        meta = PluginMetadata(name="broken-plugin", version="0.1.0")
        return "broken-plugin", meta

    @hookimpl
    def portcullis_validate_secrets(self):
        return "broken", False, "MISSING_SECRET is required"


class TestPluginManager:
    """Tests for PluginManager class."""

    def test_create_plugin_manager(self):
        """Test creating a PluginManager instance."""
        pm = PluginManager()
        assert pm is not None
        assert pm.pm is not None

    def test_discover_plugins_empty(self):
        """Test discovering plugins when none are installed."""
        pm = PluginManager()
        plugins = pm.discover_plugins()
        assert isinstance(plugins, list)
        # May be empty if no plugins are installed via entry points

    def test_get_loaded_plugins_empty(self):
        """Test getting loaded plugins when none are loaded."""
        pm = PluginManager()
        assert pm.get_loaded_plugins() == []

    def test_register_tools(self):
        """Test registering tools via plugin manager."""
        pm = PluginManager()
        pm.pm.register(MockPlugin(), "mock")

        server = FastMCP("test-server")
        pm.register_tools(server)

        # Check that tools were registered
        tools = server._tool_manager.list_tools()
        assert len(tools) > 0
        tool_names = [t.name for t in tools]
        assert "mock_tool" in tool_names

    def test_register_resources(self):
        """Test registering resources via plugin manager."""
        pm = PluginManager()
        pm.pm.register(MockPlugin(), "mock")

        server = FastMCP("test-server")
        pm.register_resources(server)

        # Check that resources were registered
        resources = server._resource_manager._resources
        assert len(resources) > 0

    def test_register_prompts(self):
        """Test registering prompts via plugin manager."""
        pm = PluginManager()
        pm.pm.register(MockPlugin(), "mock")

        server = FastMCP("test-server")
        pm.register_prompts(server)

        # Check that prompts were registered
        prompts = server._prompt_manager.list_prompts()
        assert len(prompts) > 0
        prompt_names = [p.name for p in prompts]
        assert "mock_prompt" in prompt_names

    def test_validate_secrets_success(self):
        """Test successful secret validation."""
        pm = PluginManager()
        pm.pm.register(MockPlugin(), "mock")

        errors = pm.validate_secrets()
        assert errors == []

    def test_validate_secrets_failure(self):
        """Test failed secret validation."""
        pm = PluginManager()
        pm.pm.register(MockPluginWithMissingSecrets(), "broken")

        errors = pm.validate_secrets()
        assert len(errors) > 0
        plugin_name, error_msg = errors[0]
        assert plugin_name == "broken"
        assert "MISSING_SECRET" in error_msg

    def test_get_metadata(self):
        """Test getting plugin metadata."""
        pm = PluginManager()
        pm.pm.register(MockPlugin(), "mock")

        # Trigger metadata collection directly (firstresult=True returns tuple)
        result = pm.pm.hook.portcullis_register_plugin_info()
        if result and isinstance(result, tuple):
            plugin_name, meta = result
            pm._metadata[plugin_name] = meta

        meta = pm.get_metadata("mock-plugin")
        assert meta is not None
        assert meta.name == "mock-plugin"
        assert meta.version == "0.1.0"

    def test_get_metadata_not_found(self):
        """Test getting metadata for non-existent plugin."""
        pm = PluginManager()
        meta = pm.get_metadata("non-existent")
        assert meta is None
