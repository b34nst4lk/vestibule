---
title: Build example email whitelisting plugin
status: closed
labels: []
parent: .scratch/plugin-mcp-server-map.md
blocked_by:
  - .scratch/ticket-hook-specs.md
  - .scratch/ticket-plugin-structure.md
  - .scratch/ticket-secrets.md
resolved: Created bulwark-email plugin with 3 tools (send_email, list_whitelist, add_to_whitelist), env-based secrets, TOML config support, and 20 passing tests
---

## Question

Build the minimal example plugin that demonstrates the system.

Requirements:
- Implements the email whitelisting use case
- Takes a recipient name (e.g., "Alice") and resolves to actual email from a whitelist
- Exposes an MCP tool for sending emails/invites
- Uses secrets for SMTP/API credentials

Output: Working example plugin + documentation.

## Resolution

### Created Files

```
packages/bulwark_email/
  pyproject.toml              # Package config with entry point
  bulwark_email/
    __init__.py               # Hook implementations + tools
  tests/
    conftest.py               # Pytest fixtures
    test_email_plugin.py      # 20 tests
  README.md                   # User documentation
```

### Implemented Features

| Feature | Implementation |
|---------|----------------|
| **Whitelist** | Dict mapping friendly names → emails via `EMAIL_WHITELIST` env var |
| **Tools** | `send_email`, `list_whitelist`, `add_to_whitelist` |
| **Secrets** | `EMAIL_SMTP_PASSWORD`, `EMAIL_SMTP_USER` (optional) |
| **Config** | Pydantic model with SMTP settings, sender info |
| **Validation** | `bulwark_validate_secrets` hook checks for required password |

### Example Configuration

**Environment (.env):**
```bash
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PASSWORD=app_password
EMAIL_SENDER_EMAIL=you@gmail.com
EMAIL_WHITELIST={"alice": "alice@example.com", "bob": "bob@example.com"}
```

**TOML (.bulwark/config.toml):**
```toml
[tool.bulwark.plugins.email]
smtp_host = "smtp.gmail.com"
sender_email = "you@gmail.com"

[tool.bulwark.plugins.email.whitelist]
alice = "alice@example.com"
bob = "bob@example.com"
```

### Tests

20 tests covering:
- Plugin metadata registration
- Config schema validation
- Secrets validation
- Tool registration
- Recipient lookup (case-insensitive)
- Whitelist management
