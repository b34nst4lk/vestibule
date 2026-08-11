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
- `vestibule-whitelisted-email` — whitelisted email plugin (workspace only)
- `vestibule-example` — minimal example plugin for plugin authors

> **Note:** The `vestibule-whitelisted-email` plugin is included as a workspace package for testing. A standalone PyPI package will be available in a future release. The `vestibule-example` plugin demonstrates the plugin API but is **not** published to PyPI.

### Configuration

Create `.vestibule/config.toml`:

```toml
[tool.vestibule]
host = "localhost"
port = 8080
transport = "stdio"

[tool.vestibule.approval]
enabled = true

[tool.vestibule.plugins.whitelisted_email]
smtp_host = "smtp.gmail.com"
sender_email = "you@gmail.com"

[tool.vestibule.plugins.whitelisted_email.whitelist]
alice = "alice@example.com"
bob = "bob@example.com"
```

Set environment variables (or use `.env`):

```bash
EMAIL_SMTP_PASSWORD=your_app_password
EMAIL_SENDER_EMAIL=you@gmail.com
EMAIL_WHITELIST='{"alice": "alice@example.com", "bob": "bob@example.com"}'
```

### The `vestibule config` command

`vestibule config` manages non-secret configuration without hand-editing the
TOML file. Keys are full dotted paths under `tool.vestibule.` (the same
prefix as the file), e.g. `tool.vestibule.host` or
`tool.vestibule.plugins.whitelisted_email.smtp_host`.

```bash
# Read the effective value (merged across layers; distinguishes unset from empty)
vestibule config get tool.vestibule.host

# Set / remove a key. Values are validated and coerced against the schema.
vestibule config set tool.vestibule.port 9000
vestibule config unset tool.vestibule.rate_limits.send_email

# Remove a whole section (unset refuses a section without this flag)
vestibule config unset --section tool.vestibule.rate_limits

# List effective config annotated with its source layer (project/user/default)
vestibule config list
vestibule config list --all   # also show unset keys with their defaults
```

Edits are atomic and preserve comments/formatting (tomlkit round-trip).

**Write target.** `set`/`unset` edit the project file (`.vestibule/config.toml`)
by default. Scope flags redirect the write:

```bash
vestibule config set tool.vestibule.port 9000 --user     # ~/.vestibule/config.toml
vestibule config set tool.vestibule.port 9000 --file /path/to/config.toml
```

The Pydantic schema is the source of truth: unknown keys are rejected, and a
plugin that declares no config schema cannot be configured via `set`.

**Secrets are out of scope.** `vestibule config` manages non-secret settings
only; credentials live in `.env`/environment variables (see above) and are
never written to the config file.

### Running

```bash
# Run with stdio transport (for MCP clients)
uv run python main.py

# Or use the CLI
vestibule serve
```

## Approval Workflow

Sensitive tools can be gated behind a human-in-the-loop approval check. The **approval policy is declared by each plugin** (co-located with the tools it governs) via the `vestibule_approval_policy` hook. The operator just enables approval globally and can override individual tools:

```toml
[tool.vestibule.approval]
enabled = true

[tool.vestibule.approval.overrides]
whitelisted_email.send_email = "never"   # always allow (operator override)
```

- **`never`** — no approval required.
- **`first_only`** — the first call to a gated tool requires approval; once approved, subsequent calls skip.
- **`always`** — every call to a gated tool requires approval.

Plugins declare their default policy. For example, the whitelisted email plugin declares:

```python
@hooks.hookimpl
def vestibule_approval_policy():
    return {
        "send_email": "first_only",  # sending is a write action
        "list_whitelist": "never",   # read-only
    }
```

The effective mode for a tool is: **operator override → plugin policy → not gated**. `[tool.vestibule.approval.overrides]` lets the operator tighten or loosen any tool in either direction, even across plugins. Tools with no declared policy and no override are not gated. Setting `enabled = false` disables all approval gating.

**Tool names are namespaced by plugin** (`<plugin_name>.<tool>`), so the same tool name in two plugins never collides. Plugins register tools with bare names; the server exposes them as `whitelisted_email.send_email`, `whitelisted_email.list_whitelist`, etc. Approval policies and operator overrides use the full namespaced name.

When a gated tool is called and approval is required, the server returns a structured `approval_required` response instead of executing the tool. The client grants approval by calling the built-in **`approve_tool`** tool, then retries the call. Approval state is held in memory only (runtime, not persistent).

## Error Handling Conventions

Tool results and errors follow a single convention across both transports:

- **Protocol/transport errors** — unknown tool, malformed request, method not found, invalid request — are returned as **JSON-RPC error objects** (e.g. `method_not_found`). These are not tool answers.
- **Tool business errors** — a tool that runs but cannot complete (a recipient not in the whitelist, an invalid argument, a rate-limit hit, an approval requirement, an unexpected crash) — are returned as a normal tool **`content` with `isError: true`**. The message is human/LLM-readable so a client can react (e.g. recover by retrying with a whitelisted recipient).
- **Approval requirements** additionally include `structuredContent` (`approval_required: true`) for replay, and use `isError: false` (a soft-stop, not an error).

This split matters for AI clients: an LLM reads tool `content`, but a `tools/call` **JSON-RPC error** is often swallowed by the client framework before it reaches the model. So business failures must never be encoded as JSON-RPC errors.

**For plugin authors:** to report a business error, **return** a `CallToolResult` with `isError: true` instead of raising or returning an `"Error: …"` string:

```python
from mcp.types import CallToolResult, TextContent

@mcp_server.tool(structured_output=False)
def send_whitelisted_email(recipient: str) -> str:
    if recipient not in WHITELIST:
        return CallToolResult(
            content=[TextContent(type="text", text=f"{recipient!r} is not in the whitelist")],
            isError=True,
        )
    return "sent"
```

Raise an exception only for genuine crashes; the server wraps it into a graceful `isError: true` content result. Register plain-string tools with `structured_output=False` so a returned `CallToolResult` flows through FastMCP unchanged.

## Available Plugins

### vestibule-whitelisted-email (workspace only)

Whitelisted email plugin that allows sending emails only to pre-approved recipients.

**Tools** (namespaced as `whitelisted_email.<tool>`):
- `whitelisted_email.send_email(recipient_name, subject, body, cc_recipient_name)` - Send an email
- `whitelisted_email.list_whitelist()` - List all whitelisted recipients

**Hard-gate model:** the whitelist is the hard authorization boundary. The AI addresses recipients by friendly name only; Vestibule maps names to addresses via `EMAIL_WHITELIST`, and any recipient not in the whitelist is blocked even after `send_email` is approved. The whitelist is operator-curated and read-only for the AI (no runtime mutation). See `packages/vestibule_whitelisted_email/README.md` for setup.

**Install:** `pip install vestibule-whitelisted-email` (published to PyPI). Also included as a workspace package for testing.

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
    vestibule_whitelisted_email/         # Whitelisted email plugin
      vestibule_whitelisted_email/
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
uv run pytest --cov=vestibule --cov=packages/vestibule_whitelisted_email

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
