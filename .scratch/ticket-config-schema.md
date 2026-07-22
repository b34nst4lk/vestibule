---
title: Define TOML configuration schema
status: closed
labels: []
parent: .scratch/plugin-mcp-server-map.md
resolved: Multi-level config (CLI > project > user > defaults); [tool.portcullis] + [tool.portcullis.plugins.<name>]; plugin-declared Pydantic models; fail-fast validation
---

## Question

What is the TOML schema for plugin configuration?

## Resolution

### Decision Summary

| Aspect | Decision |
|--------|----------|
| **File locations** | Multi-level merge: CLI `--config=` > `.portcullis/config.toml` > `~/.portcullis/config.toml` > built-in defaults |
| **Namespace** | `[tool.portcullis]` for server settings, `[tool.portcullis.plugins.<name>]` for plugin config |
| **Plugin config** | Plugin declares Pydantic model via `portcullis_config_schema()` hook; server validates and passes typed config |
| **Validation** | Fail-fast at startup if required fields missing or validation fails |

### TOML Structure

```toml
# .portcullis/config.toml

# Server settings
[tool.portcullis]
host = "localhost"
port = 8080
transport = "stdio"  # or "http-sse"
log-level = "info"

# Plugin configs
[tool.portcullis.plugins.email]
smtp_host = "smtp.gmail.com"
default_recipient = "admin@example.com"
max_retries = 3

[tool.portcullis.plugins.calendar]
timezone = "UTC"
default_duration_minutes = 30
```

### Plugin Config Pattern

```python
from pydantic import BaseModel

class EmailPluginConfig(BaseModel):
    smtp_host: str
    default_recipient: str = ""
    max_retries: int = 3

@hooks.hookimpl
def portcullis_config_schema():
    return EmailPluginConfig

@hooks.hookimpl
def portcullis_init(config: EmailPluginConfig):
    # config is fully typed and validated
    ...
```

### Example Config File

See `.scratch/example-config.toml` for a complete example.

### Research

See `.scratch/research-toml-config-patterns.md` for pytest, mypy, black, and modern CLI tool patterns.
