# Bulwark

A plugin-based MCP (Model Context Protocol) server using `pluggy` for extensibility.

## Overview

Bulwark provides a secure way to expose custom tools to AI agents while keeping sensitive information (credentials, email addresses, API keys) hidden from the agent. Plugins implement email whitelisting, calendar access, and other sensitive operations behind clean tool interfaces.

## Features

- **Plugin Architecture**: Discover and load plugins via entry points
- **Secrets Management**: Environment-based secrets with plugin-declared prefixes
- **TOML Configuration**: Multi-level config merging (CLI > project > user > defaults)
- **MCP Protocol**: Full support for tools, resources, and prompts
- **Dual Transport**: Stdio and HTTP/SSE transports (stdio implemented, HTTP/SSE coming soon)

## Quick Start

### Installation

```bash
# Install the server
pip install bulwark

# Install plugins
pip install bulwark-email
```

### Development Setup

```bash
# Clone and install with uv
git clone <repository>
cd bulwark
uv sync

# Install a plugin in development mode
uv pip install -e packages/bulwark_email
```

### Configuration

Create `.bulwark/config.toml`:

```toml
[tool.bulwark]
host = "localhost"
port = 8080
transport = "stdio"

[tool.bulwark.plugins.email]
smtp_host = "smtp.gmail.com"
sender_email = "you@gmail.com"

[tool.bulwark.plugins.email.whitelist]
alice = "alice@example.com"
bob = "bob@example.com"
```

Set environment variables (or use `.env`):

```bash
EMAIL_SMTP_PASSWORD=your_app_password
EMAIL_SENDER_EMAIL=you@gmail.com
EMAIL_WHITELIST={"alice": "alice@example.com", "bob": "bob@example.com"}
```

### Running

```bash
# Run with stdio transport (for MCP clients)
uv run python main.py

# Or use the CLI (coming soon)
bulwark serve
```

## Available Plugins

### bulwark-email

Email whitelisting plugin that allows sending emails only to pre-approved recipients.

**Tools:**
- `send_email(recipient_name, subject, body, cc_recipient_name)` - Send an email
- `list_whitelist()` - List all whitelisted recipients
- `add_to_whitelist(name, email)` - Add a recipient to the runtime whitelist

**Installation:**
```bash
pip install bulwark-email
```

## Plugin Development

### Creating a Plugin

1. Create a new package with entry point:

```toml
# pyproject.toml
[project.entry-points."bulwark.plugins"]
my-plugin = "bulwark_my_plugin"
```

2. Implement hooks in `__init__.py`:

```python
from bulwark import hooks
from pydantic import BaseModel

@hooks.hookimpl
def bulwark_register_plugin_info():
    return "my-plugin", hooks.PluginMetadata(
        name="my-plugin",
        version="1.0.0",
        description="My custom plugin"
    )

@hooks.hookimpl
def bulwark_config_schema():
    return MyPluginConfig  # Pydantic model

@hooks.hookimpl
def bulwark_register_tools(mcp_server):
    @mcp_server.tool()
    def my_tool(arg: str) -> str:
        return f"Result: {arg}"
```

### Available Hooks

| Hook | Purpose | First Result |
|------|---------|--------------|
| `bulwark_register_plugin_info` | Return plugin metadata | Yes |
| `bulwark_register_tools` | Register MCP tools | No |
| `bulwark_register_resources` | Register MCP resources | No |
| `bulwark_register_prompts` | Register MCP prompts | No |
| `bulwark_validate_secrets` | Validate required secrets | No |

## Project Structure

```
bulwark/
  bulwark/                    # Core server package
    __init__.py
    hooks.py                  # Pluggy hook specifications
    plugin_manager.py         # Plugin discovery and loading
  packages/
    bulwark_email/            # Email whitelisting plugin
      bulwark_email/
        __init__.py
      tests/
  tests/                      # Server tests
  .bulwark/
    config.toml.example       # Example configuration
  .env.example                # Example environment variables
```

## Commands

```bash
# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=bulwark --cov=packages/bulwark_email

# Run the server
uv run python main.py
```

## License

MIT
