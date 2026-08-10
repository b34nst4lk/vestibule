# Vestibule Whitelisted Email Plugin

A plugin for the Vestibule MCP server that provides email sending capabilities with recipient whitelisting.

## Features

- **Whitelist-based sending**: Only pre-approved recipients can receive emails
- **Friendly names**: Reference recipients by name (e.g., "Alice") instead of email addresses
- **SMTP support**: Works with any SMTP server (Gmail, Outlook, corporate SMTP, etc.)
- **CC support**: Optionally CC additional whitelisted recipients

## Hard-Gate Model

The whitelist is the **hard authorization boundary** — the AI cannot bypass it.

- The AI assistant addresses recipients by **friendly name only** (e.g. `"alice"`); it never provides a raw email address.
- Vestibule maps the friendly name to an email address via the whitelist (`EMAIL_WHITELIST`). If the name is **not** in the whitelist, the send is **blocked** — even if `send_email` has already been approved.
- The whitelist is **operator-curated and read-only for the AI**. There is no tool to add or remove recipients at runtime (`add_to_whitelist` was removed). The only way to change the whitelist is to edit `EMAIL_WHITELIST` and restart.
- SMTP credentials live in the server environment and are **never exposed** in tool results or audit logs.

This means the **approval gate** (`first_only` on `send_email`) and the **whitelist gate** are **independent**: approving `send_email` unlocks the tool, but the whitelist still blocks any recipient not in `EMAIL_WHITELIST`.

## Installation

```bash
pip install vestibule-whitelisted-email
```

Or for development:

```bash
cd packages/vestibule_whitelisted_email
uv pip install -e .
```

## Configuration

### TOML Configuration

Add to your `.vestibule/config.toml` or `~/.vestibule/config.toml`:

```toml
[tool.vestibule.plugins.whitelisted_email]
smtp_host = "smtp.gmail.com"
smtp_port = 587
smtp_use_tls = true
sender_email = "you@gmail.com"
sender_name = "Your Name"

# Whitelist: friendly name -> email address
[tool.vestibule.plugins.whitelisted_email.whitelist]
alice = "alice@example.com"
bob = "bob@example.com"
team = "team@company.com"
```

### Environment Variables

Set these environment variables for secrets and runtime config:

```bash
# Required
EMAIL_SMTP_PASSWORD=your_app_password
EMAIL_SENDER_EMAIL=you@gmail.com

# Optional
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USE_TLS=true
EMAIL_SMTP_USER=you@gmail.com
EMAIL_SENDER_NAME=Your Name
EMAIL_WHITELIST={"alice": "alice@example.com", "bob": "bob@example.com"}
EMAIL_DEFAULT_RECIPIENT=alice
```

### Gmail App Password

If using Gmail, you'll need to create an [App Password](https://support.google.com/accounts/answer/185833):

1. Enable 2-Step Verification on your Google Account
2. Go to Security > App passwords
3. Generate a new app password for "Mail"
4. Use this password as `EMAIL_SMTP_PASSWORD`

## Available Tools

### `send_email`

Send an email to a whitelisted recipient.

**Parameters:**
- `recipient_name` (required): Friendly name from whitelist
- `subject` (required): Email subject
- `body` (required): Email body text
- `cc_recipient_name` (optional): Friendly name for CC recipient

**Example:**
```
send_email(
    recipient_name="Alice",
    subject="Meeting Tomorrow",
    body="Hi Alice, just reminding you about our meeting tomorrow at 2pm."
)
```

### `list_whitelist`

List all whitelisted recipients.

**Example:**
```
list_whitelist()
```

## Security Notes

- The whitelist is the **hard authorization boundary**: only operator-curated recipients (from `EMAIL_WHITELIST`) can receive emails. There is no tool to add recipients at runtime — the AI cannot escalate the whitelist.
- The whitelist is loaded from `EMAIL_WHITELIST` at startup and is read-only for the AI.
- Credentials are loaded from environment variables, not configuration files, and are never exposed in tool results.
- TLS is enabled by default for SMTP connections.

## Authoring a Stricter Variant

This plugin ships a pragmatic default: `send_email` is gated `first_only` (ask once per session), and the whitelist is the hard gate. If your threat model needs more, author a stricter variant:

- **Per-recipient approval** — gate `send_email` with `always` instead of `first_only`, so every send (even to a whitelisted recipient) requires human approval.
- **Per-recipient allowlist** — maintain a separate per-recipient approval list in addition to the whitelist.
- **No CC** — drop the `cc_recipient_name` parameter to remove the CC path entirely.
- **Sender allowlist** — restrict which sender addresses can be used.

The plugin architecture supports this: copy the plugin, adjust the `vestibule_approval_policy` hook and the tool signatures, and register it under a new namespace.
