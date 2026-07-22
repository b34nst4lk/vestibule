# Bulwark Email Whitelisting Plugin

A plugin for the Bulwark MCP server that provides email sending capabilities with recipient whitelisting.

## Features

- **Whitelist-based sending**: Only pre-approved recipients can receive emails
- **Friendly names**: Reference recipients by name (e.g., "Alice") instead of email addresses
- **SMTP support**: Works with any SMTP server (Gmail, Outlook, corporate SMTP, etc.)
- **CC support**: Optionally CC additional whitelisted recipients

## Installation

```bash
pip install bulwark-email
```

Or for development:

```bash
cd packages/bulwark_email
uv pip install -e .
```

## Configuration

### TOML Configuration

Add to your `.bulwark/config.toml` or `~/.bulwark/config.toml`:

```toml
[tool.bulwark.plugins.email]
smtp_host = "smtp.gmail.com"
smtp_port = 587
smtp_use_tls = true
sender_email = "you@gmail.com"
sender_name = "Your Name"

# Whitelist: friendly name -> email address
[tool.bulwark.plugins.email.whitelist]
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

### `add_to_whitelist`

Add a recipient to the runtime whitelist.

**Parameters:**
- `name`: Friendly name
- `email`: Email address

**Example:**
```
add_to_whitelist(name="Charlie", email="charlie@example.com")
```

## Security Notes

- The whitelist prevents sending emails to unauthorized recipients
- Credentials are loaded from environment variables, not configuration files
- TLS is enabled by default for SMTP connections
