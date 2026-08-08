# Vestibule

> **v0.1.0 Beta** — Initial release. Installation via `uv` from source (not yet on PyPI).

A plugin-based MCP (Model Context Protocol) server using `pluggy` for extensibility.

## Overview

Vestibule provides a secure way to expose custom tools to AI agents while keeping sensitive information (credentials, email addresses, API keys) hidden from the agent. Plugins implement email whitelisting, calendar access, and other sensitive operations behind clean tool interfaces.

Think of it as a **gateway between AI and action** — the vestibule controls what passes through, ensuring only safe, validated operations proceed.

## Features

- **Plugin Architecture**: Discover and load plugins via entry points
- **Secrets Management**: Environment-based secrets with plugin-declared prefixes
- **TOML Configuration**: Multi-level config merging (CLI > project > user > defaults)
- **Pydantic Validation**: Plugin configs validated against declared schemas at startup
- **Human-in-the-Loop Approval**: Gate sensitive tools behind an approval workflow (`never` / `first_only` / `always`)
- **Fail-Fast**: Server exits with clear errors if config or secrets validation fails
- **MCP Protocol**: Full support for tools, resources, and prompts
- **Dual Transport**: Stdio and HTTP/SSE transports

## Quick Start

### Installation

Vestibule 0.1.0 is not yet published to PyPI. Install from source using `uv`:

```bash
# Clone the repository
git clone https://github.com/b34nst4lk/vestibule.git
cd vestibule

# Install the server and workspace plugins
uv sync
```

This installs:
- `vestibule` — the core MCP server
- `vestibule-email` — email whitelisting plugin (workspace only)
- `vestibule-example` — minimal example plugin for plugin authors

> **Note:** The `vestibule-email` plugin is included as a workspace package for testing. A standalone PyPI package will be available in a future release. The `vestibule-example` plugin demonstrates the plugin API but is **not** published to PyPI.

### Configuration

Create `.vestibule/config.toml`:

```toml
[tool.vestibule]
host = "localhost"
port = 8080
transport = "stdio"

[tool.vestibule.approval]
mode = "first_only"
tools = ["send_email"]

[tool.vestibule.plugins.email]
smtp_host = "smtp.gmail.com"
sender_email = "you@gmail.com"

[tool.vestibule.plugins.email.whitelist]
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
vestibule serve
```

## Approval Workflow

Sensitive tools can be gated behind a human-in-the-loop approval check. Configure it under `[tool.vestibule.approval]`:

```toml
[tool.vestibule.approval]
mode = "first_only"   # never | first_only | always
tools = ["send_email"]
```

- **`never`** — no approval required.
- **`first_only`** (default) — the first call to a gated tool requires approval; once approved, subsequent calls skip.
- **`always`** — every call to a gated tool requires approval.

When a gated tool is called and approval is required, the server returns a structured `approval_required` response instead of executing the tool. The client grants approval by calling the built-in **`approve_tool`** tool, then retries the call. Approval state is held in memory only (runtime, not persistent).

## Available Plugins

### vestibule-email (workspace only)

Email whitelisting plugin that allows sending emails only to pre-approved recipients.

**Tools:**
- `send_email(recipient_name, subject, body, cc_recipient_name)` - Send an email
- `list_whitelist()` - List all whitelisted recipients
- `add_to_whitelist(name, email)` - Add a recipient to the runtime whitelist

**Note:** This plugin is included as a workspace package for testing. A standalone PyPI package will be available in a future release.

### vestibule-example

Minimal example plugin demonstrating the Vestibule plugin API. Use this as a template for creating your own plugins.

**Tools:**
- `list_whitelist()` - List all whitelisted recipients
- `add_to_whitelist(name, email)` - Add a recipient to the runtime whitelist
- `remove_from_whitelist(name)` - Remove a recipient from the runtime whitelist

**Note:** This plugin is included for plugin authors as a template. It is **not** published to PyPI — only the `vestibule` server is released. See `packages/vestibule_example/README.md` for the plugin author guide.

## Plugin Development

### Creating a Plugin

1. Create a new package with entry point:

```toml
# pyproject.toml
[project.entry-points."vestibule.plugins"]
my-plugin = "vestibule_my_plugin"
```

2. Implement hooks in `__init__.py`:

```python
from vestibule import hooks
from pydantic import BaseModel

@hooks.hookimpl
def vestibule_register_plugin_info():
    return "my-plugin", hooks.PluginMetadata(
        name="my-plugin",
        version="1.0.0",
        description="My custom plugin"
    )

@hooks.hookimpl
def vestibule_config_schema():
    return MyPluginConfig  # Pydantic model

@hooks.hookimpl
def vestibule_register_tools(mcp_server):
    @mcp_server.tool()
    def my_tool(arg: str) -> str:
        return f"Result: {arg}"
```

### Available Hooks

| Hook | Purpose | First Result |
|------|---------|--------------|
| `vestibule_register_plugin_info` | Return plugin metadata | Yes |
| `vestibule_register_tools` | Register MCP tools | No |
| `vestibule_register_resources` | Register MCP resources | No |
| `vestibule_register_prompts` | Register MCP prompts | No |
| `vestibule_validate_secrets` | Validate required secrets | No |
| `vestibule_config_schema` | Return Pydantic config schema | Yes |
| `vestibule_init` | Initialize plugin with validated config | No |

## Project Structure

```
vestibule/
  vestibule/                 # Core server package
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
    vestibule_email/         # Email whitelisting plugin
      vestibule_email/
        __init__.py
      tests/
  tests/                      # Server tests
  .vestibule/
    config.toml.example       # Example configuration
  .env.example                # Example environment variables
```

## Commands

```bash
# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=vestibule --cov=packages/vestibule_email

# Run the server
uv run python main.py

# CLI commands
vestibule serve              # Start the server
vestibule healthcheck        # Validate plugin secrets
vestibule plugins            # List loaded plugins
vestibule version            # Show version
```

## License

MIT
