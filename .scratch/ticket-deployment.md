---
title: Define deployment and installation approach
status: closed
labels: []
parent: .scratch/plugin-mcp-server-map.md
resolved: PyPI for users, source for dev; `portcullis` CLI with subcommands; uv workspace for dev; public release
---

## Question

How is the server and plugins installed and run?

## Resolution

### Decision Summary

| Aspect | Decision |
|--------|----------|
| **Installation method** | PyPI for users (`pip install portcullis`), source for development |
| **CLI entry point** | `portcullis` CLI with subcommands (`serve`, `healthcheck`, `plugins`) |
| **Plugin installation** | Separate PyPI packages (`pip install portcullis-email`) |
| **Distribution scope** | Public release — design for other users from the start |
| **Development workflow** | uv workspace — develop server + plugins together, publish separately |

### Project Structure

```
portcullis/
  pyproject.toml          # Root workspace config
  packages/
    portcullis/              # Core server (published to PyPI)
    portcullis-email/        # Email plugin (published separately)
    portcullis-calendar/     # Calendar plugin (published separately)
```

### CLI Usage

```bash
# Install server
pip install portcullis

# Install plugins
pip install portcullis-email portcullis-calendar

# Run server
portcullis serve

# Check configuration
portcullis healthcheck

# List loaded plugins
portcullis plugins list
```

### Development

```bash
# In repo root
uv sync  # installs workspace members

# Run server with local plugins
uv run portcullis serve
```

### Implementation

Created `portcullis/cli.py` with typer-based CLI with the following commands:

| Command | Description |
|---------|-------------|
| `portcullis version` | Show [Pp]ortcullis version |
| `portcullis serve [--transport stdio\|http-sse] [--host] [--port]` | Start MCP server with plugins |
| `portcullis healthcheck [-v]` | Validate plugin secrets |
| `portcullis plugins [-v]` | List discovered/loaded plugins |

Entry point configured in `pyproject.toml`:
```toml
[project.scripts]
portcullis = "portcullis.cli:main"
```

6 CLI tests in `tests/test_cli.py` - all passing.
