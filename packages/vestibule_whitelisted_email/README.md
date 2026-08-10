# Vestibule Whitelisted Email

Send emails from the AI to a pre-approved list of recipients. The whitelist is the hard gate — only recipients you define can receive email, and the AI cannot change it at runtime.

## What it does

- **Whitelist-gated sending** — only pre-approved recipients can receive email.
- **Friendly names** — the AI addresses recipients by name (`"Alice"`); Vestibule maps the name to an address.
- **Hard gate** — the whitelist is read-only for the AI. There is no tool to add or remove recipients at runtime; edit `EMAIL_WHITELIST` and restart to change it.
- **SMTP + TLS** — works with any SMTP server; TLS on by default.
- **Optional CC** — CC any other whitelisted recipient.

## Tools

- `send_email(recipient_name, subject, body, cc_recipient_name?)` — send to a whitelisted recipient.
- `list_whitelist()` — list the whitelisted recipients.

## Setup

The plugin is configured entirely through environment variables. Vestibule loads a `.env` file at startup, so put them there:

```bash
# SMTP
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USE_TLS=true
EMAIL_SMTP_PASSWORD=your_app_password
EMAIL_SMTP_USER=you@gmail.com

# Sender
EMAIL_SENDER_EMAIL=you@gmail.com
EMAIL_SENDER_NAME=Your Name

# Whitelist: JSON mapping friendly names to addresses
EMAIL_WHITELIST={"alice":"alice@example.com","bob":"bob@example.com"}
```

Only `EMAIL_SMTP_PASSWORD` is required; the rest have sensible defaults (`smtp.gmail.com`, port 587, TLS on).

### Gmail

Use an [App Password](https://support.google.com/accounts/answer/185833) (requires 2-Step Verification) as `EMAIL_SMTP_PASSWORD`.

## Security

- Only whitelisted recipients can receive email. The whitelist is the hard boundary, read-only for the AI.
- Credentials live in the server environment and are never returned in tool results.
