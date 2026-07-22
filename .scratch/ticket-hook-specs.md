---
title: Define pluggy hook specs for the server
status: closed
labels: []
parent: .scratch/plugin-mcp-server-map.md
resolved: Created hooks.py with HookimplMarker/HookspecMarker and 5 hook specs
---

## Question

What are the hook specs the server defines that plugins must implement?

## Resolution

Created `portcullis/hooks.py` with:

- `hookspec` - HookspecMarker for marking hook specifications
- `hookimpl` - HookimplMarker for marking plugin implementations
- `PluginMetadata` - Data class for plugin information

### Hook Specifications

1. **portcullis_register_plugin_info** (firstresult=True) - Returns plugin metadata
2. **portcullis_register_tools** - Register MCP tools with the server
3. **portcullis_register_resources** - Register MCP resources with the server
4. **portcullis_register_prompts** - Register MCP prompts with the server
5. **portcullis_validate_secrets** - Validate required secrets on startup

Created `portcullis/plugin_manager.py` with PluginManager class that:
- Discovers plugins via entry points (`portcullis.plugins` group)
- Loads and registers plugins
- Coordinates hook calls for tool/resource/prompt registration
- Validates plugin secrets

Created `portcullis/__init__.py` exporting public API.

All hooks tested in `tests/test_hooks.py` (18 tests passing).
