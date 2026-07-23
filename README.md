# Portcullis

> **v0.1.0 Beta** — Initial release. Installation via `uv` from source (not yet on PyPI).

A plugin-based MCP (Model Context Protocol) server using `pluggy` for extensibility.

## Overview

Portcullis provides a secure way to expose custom tools to AI agents while keeping sensitive information (credentials, email addresses, API keys) hidden from the agent. Plugins implement email whitelisting, calendar access, and other sensitive operations behind clean tool interfaces.

Think of it as a **gateway between AI and action** — the portcullis controls what passes through, ensuring only safe, validated operations proceed.

## Features

- **Plugin Architecture**: Discover and load plugins via entry points
- **Secrets Management**: Environment-based secrets with plugin-declared prefixes
- **TOML Configuration**: Multi-level config merging (CLI > project > user > defaults)
- **Pydantic Validation**: Plugin configs validated against declared schemas at startup
- **Fail-Fast**: Server exits with clear errors if config or secrets validation fails
- **MCP Protocol**: Full support for tools, resources, and prompts
- **Dual Transport**: Stdio and HTTP/SSE transports

## Quick Start

### Installation

Portcullis 0.1.0 is not yet published to PyPI. Install from source using `uv`:

```bash
# Clone the repository
git clone https://github.com/<your-org>/portcullis.git
cd portcullis

# Install the server and workspace plugins
uv sync
```

This installs:
- `portcullis` — the core MCP server
- `portcullis-email` — email whitelisting plugin (workspace only)
- `portcullis-example` — minimal example plugin for plugin authors

> **Note:** The `portcullis-email` plugin is included as a workspace package for testing. A standalone PyPI package will be available in a future release. The `portcullis-example` plugin demonstrates the plugin API and will be published to PyPI alongside the server.

### Configuration

Create `.portcullis/config.toml`:

```toml
[tool.portcullis]
host = "localhost"
port = 8080
transport = "stdio"

[tool.portcullis.plugins.email]
smtp_host = "smtp.gmail.com"
sender_email = "you@gmail.com"

[tool.portcullis.plugins.email.whitelist]
alice = "alice@example.com"
bob = "bob@example.com"
```

Set environment variables (or use `.env`):

```bash
EMAIL_SMTP_PASSWORD=your_app_password
EMAIL_SENDER_EMAIL=you@gmail.com
EMAIL_WHITELIST='{"alice": "alice@example.com", "bob": "bob@example.com"}'
```

### Running

```bash
# Run with stdio transport (for MCP clients)
uv run python main.py

# Or use the CLI
portcullis serve
```

## Available Plugins

### portcullis-email (workspace only)

Email whitelisting plugin that allows sending emails only to pre-approved recipients.

**Tools:**
- `send_email(recipient_name, subject, body, cc_recipient_name)` - Send an email
- `list_whitelist()` - List all whitelisted recipients
- `add_to_whitelist(name, email)` - Add a recipient to the runtime whitelist

**Note:** This plugin is included as a workspace package for testing. A standalone PyPI package will be available in a future release.

### portcullis-example

Minimal example plugin demonstrating the Portcullis plugin API. Use this as a template for creating your own plugins.

**Tools:**
- `list_whitelist()` - List all whitelisted recipients
- `add_to_whitelist(name, email)` - Add a recipient to the runtime whitelist
- `remove_from_whitelist(name)` - Remove a recipient from the runtime whitelist

**Note:** This plugin will be published to PyPI alongside Portcullis 0.1.0. See `packages/portcullis_example/README.md` for the plugin author guide.

## Plugin Development

### Creating a Plugin

1. Create a new package with entry point:

```toml
# pyproject.toml
[project.entry-points."portcullis.plugins"]
my-plugin = "portcullis_my_plugin"
```

2. Implement hooks in `__init__.py`:

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
    return MyPluginConfig  # Pydantic model

@hooks.hookimpl
def portcullis_register_tools(mcp_server):
    @mcp_server.tool()
    def my_tool(arg: str) -> str:
        return f"Result: {arg}"
```

### Available Hooks

| Hook | Purpose | First Result |
|------|---------|--------------|
| `portcullis_register_plugin_info` | Return plugin metadata | Yes |
| `portcullis_register_tools` | Register MCP tools | No |
| `portcullis_register_resources` | Register MCP resources | No |
| `portcullis_register_prompts` | Register MCP prompts | No |
| `portcullis_validate_secrets` | Validate required secrets | No |
| `portcullis_config_schema` | Return Pydantic config schema | Yes |
| `portcullis_init` | Initialize plugin with validated config | No |

## Project Structure

```
portcullis/
  portcullis/                 # Core server package
    __init__.py
    hooks.py                  # Pluggy hook specifications
    plugin_manager.py         # Plugin discovery and loading
    config.py                 # Configuration loading
    cli.py                    # CLI commands
    transports/
      stdio.py                # Stdio transport
      http_sse.py             # HTTP/SSE transport
      common.py               # Shared handlers
  packages/
    portcullis_email/         # Email whitelisting plugin
      portcullis_email/
        __init__.py
      tests/
  tests/                      # Server tests
  .portcullis/
    config.toml.example       # Example configuration
  .env.example                # Example environment variables
```

## Commands

```bash
# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=portcullis --cov=packages/portcullis_email

# Run the server
uv run python main.py

# CLI commands
portcullis serve              # Start the server
portcullis healthcheck        # Validate plugin secrets
portcullis plugins            # List loaded plugins
portcullis version            # Show version
```

## License

MIT
