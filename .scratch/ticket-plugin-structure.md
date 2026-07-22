---
title: Define plugin package structure and entry point
status: closed
labels: []
parent: .scratch/plugin-mcp-server-map.md
blocked_by:
  - .scratch/ticket-hook-specs.md
resolved: Entry point group `portcullis.plugins`; package named `portcullis-<name>`; hooks in `__init__.py`; all hooks optional
---

## Question

What does a plugin package look like and how is it discovered?

## Resolution

### Decision Summary

| Aspect | Decision |
|--------|----------|
| **Entry point group** | `portcullis.plugins` |
| **Package naming** | `portcullis-<name>` (e.g., `portcullis-email`) |
| **Module structure** | Hook implementations in `__init__.py` |
| **Entry point target** | The package itself (e.g., `email = "portcullis_email"`) |
| **Required hooks** | All hooks optional — plugin implements any subset |

### Example Plugin Package

```
portcullis-email/
  pyproject.toml
  portcullis_email/
    __init__.py
```

```toml
# portcullis-email/pyproject.toml
[project]
name = "portcullis-email"
version = "1.0.0"

[project.entry-points."portcullis.plugins"]
email = "portcullis_email"
```

```python
# portcullis-email/portcullis_email/__init__.py
from portcullis import hooks
from pydantic import BaseModel

class EmailPluginConfig(BaseModel):
    smtp_host: str
    default_recipient: str = ""

@hooks.hookimpl
def portcullis_register_plugin_info():
    return {"name": "email", "version": "1.0.0"}

@hooks.hookimpl
def portcullis_config_schema():
    return EmailPluginConfig

@hooks.hookimpl
def portcullis_register_tools(tool_registry):
    tool_registry.add_tool(
        name="send_email",
        description="Send an email to a whitelisted recipient",
        input_schema=EmailPluginConfig.model_json_schema(),
        handler=send_email_handler,
    )
```

### Plugin Dependencies

Plugins handle their own dependencies via `pyproject.toml`. The server does not manage plugin dependencies.
