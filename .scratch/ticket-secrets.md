---
title: Define secrets management approach
status: closed
labels: []
parent: .scratch/plugin-mcp-server-map.md
resolved: Plugin-declared env_prefix with collision detection; plugins read via os.getenv(); healthcheck command for validation
---

## Question

How are secrets managed and accessed by plugins?

## Resolution

### Decision Summary

| Aspect | Decision |
|--------|----------|
| **Naming** | Plugins document their own secret names, but must declare an `env_prefix` to avoid clashes |
| **Access** | Plugins read via `os.getenv()` — server is agnostic, user is responsible for managing `.env` |
| **Validation** | Fail-fast via `portcullis healthcheck` command — shows missing vars and their descriptions |
| **Isolation** | Server detects prefix collisions at startup |

### Plugin Metadata Hook

Plugins declare their secrets requirements:

```python
@hooks.hookimpl
def portcullis_plugin_metadata():
    return {
        "name": "email",
        "env_prefix": "EMAIL_",
        "required_env_vars": [
            {"name": "SMTP_HOST", "description": "SMTP server hostname"},
            {"name": "SMTP_USER", "description": "SMTP username"},
            {"name": "SMTP_PASSWORD", "description": "SMTP password or app-specific password"},
        ],
    }
```

### Example `.env` File

```bash
# Email plugin
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_USER=me@gmail.com
EMAIL_SMTP_PASSWORD=abcd1234

# Calendar plugin
CALENDAR_API_KEY=xyz789
CALENDAR_CLIENT_ID=client123
CALENDAR_CLIENT_SECRET=secret456
```

### Example `portcullis healthcheck` Output

```
$ portcullis healthcheck
Loading plugins...

Email plugin (portcullis-email):
  ✓ EMAIL_SMTP_HOST is set
  ✗ EMAIL_SMTP_USER is MISSING (SMTP username)
  ✗ EMAIL_PASSWORD is MISSING (SMTP password)

Calendar plugin (portcullis-calendar):
  ✓ CALENDAR_API_KEY is set

Summary: 2 missing, 4 configured.
```

### New Command

- `portcullis healthcheck` — Check env var configuration for all plugins
- `portcullis serve` — May optionally run healthcheck first
