# Portcullis Example Plugin

This is a minimal example plugin demonstrating the Portcullis plugin API. Use it as a starting point for your own plugins.

## Features

- Demonstrates all required plugin hooks
- In-memory whitelist (no persistence)
- Simple configuration via Pydantic

## Tools

| Tool | Description |
|------|-------------|
| `list_whitelist()` | List all whitelisted recipients |
| `add_to_whitelist(name, email)` | Add a recipient to the runtime whitelist |
| `remove_from_whitelist(name)` | Remove a recipient from the runtime whitelist |

## Installation

```bash
# From source (0.1.0)
uv sync  # Installs from workspace
```

## Configuration

Add to your `.portcullis/config.toml`:

```toml
[tool.portcullis.plugins.example]
initial_whitelist = { alice = "alice@example.com", bob = "bob@example.com" }
```

## Creating Your Own Plugin

1. **Create the package structure:**

```
portcullis_my_plugin/
  portcullis_my_plugin/
    __init__.py
  pyproject.toml
  README.md
```

2. **Add entry point to `pyproject.toml`:**

```toml
[project.entry-points."portcullis.plugins"]
my-plugin = "portcullis_my_plugin"
```

3. **Implement the hooks in `__init__.py`:**

```python
from portcullis import hooks
from pydantic import BaseModel

@hooks.hookimpl
def portcullis_register_plugin_info():
    return "my-plugin", hooks.PluginMetadata(
        name="my-plugin",
        version="1.0.0",
        description="My custom plugin"
    )

@hooks.hookimpl
def portcullis_config_schema():
    return MyPluginConfig  # Your Pydantic model

@hooks.hookimpl
def portcullis_register_tools(mcp_server):
    @mcp_server.tool()
    def my_tool(arg: str) -> str:
        return f"Result: {arg}"
```

4. **Install your plugin:**

```bash
uv pip install -e .
```

## Available Hooks

| Hook | Purpose | First Result |
|------|---------|--------------|
| `portcullis_register_plugin_info` | Return plugin metadata | Yes |
| `portcullis_config_schema` | Return Pydantic config schema | Yes |
| `portcullis_init` | Initialize with validated config | No |
| `portcullis_register_tools` | Register MCP tools | No |
| `portcullis_register_resources` | Register MCP resources | No |
| `portcullis_register_prompts` | Register MCP prompts | No |
| `portcullis_validate_secrets` | Validate required secrets | No |

For more details, see the main [Portcullis documentation](../../README.md).
