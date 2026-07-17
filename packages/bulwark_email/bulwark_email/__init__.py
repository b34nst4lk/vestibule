"""
Bulwark Email Whitelisting Plugin

This plugin provides email sending capabilities with recipient whitelisting.
Only pre-approved recipients can receive emails, ensuring sensitive information
is only sent to trusted addresses.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any

import pluggy
from pydantic import BaseModel, Field

from bulwark import hooks

# -----------------------------------------------------------------------------
# Configuration Schema
# -----------------------------------------------------------------------------


class WhitelistEntry(BaseModel):
    """A single whitelist entry mapping a friendly name to an email address."""

    name: str
    email: str


class EmailPluginConfig(BaseModel):
    """Configuration schema for the email plugin."""

    # SMTP settings
    smtp_host: str = Field(..., description="SMTP server hostname")
    smtp_port: int = Field(default=587, description="SMTP port (default: 587)")
    smtp_use_tls: bool = Field(default=True, description="Use TLS for SMTP")

    # Sender settings
    sender_email: str = Field(..., description="Sender email address")
    sender_name: str = Field(default="", description="Optional sender name")

    # Recipient whitelist - maps friendly names to actual emails
    whitelist: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of friendly names to email addresses, e.g., {'alice': 'alice@example.com'}"
    )

    # Optional settings
    default_recipient: str = Field(
        default="",
        description="Default recipient friendly name if not specified"
    )


# -----------------------------------------------------------------------------
# Plugin Metadata
# -----------------------------------------------------------------------------


@hooks.hookimpl
def bulwark_register_plugin_info() -> tuple[str, hooks.PluginMetadata]:
    """Return plugin metadata."""
    meta = hooks.PluginMetadata(
        name="email",
        version="0.1.0",
        description="Email whitelisting plugin - send emails only to pre-approved recipients",
    )
    return "email", meta


# -----------------------------------------------------------------------------
# Configuration Schema Hook
# -----------------------------------------------------------------------------


@hooks.hookimpl
def bulwark_config_schema() -> type[BaseModel]:
    """Return the Pydantic config schema for this plugin."""
    return EmailPluginConfig


# -----------------------------------------------------------------------------
# Secrets Validation Hook
# -----------------------------------------------------------------------------


@hooks.hookimpl
def bulwark_validate_secrets() -> tuple[str, bool, str]:
    """
    Validate that required secrets are available.

    Required env vars (with EMAIL_ prefix):
    - EMAIL_SMTP_PASSWORD: SMTP password or app-specific password
    - EMAIL_SMTP_USER: SMTP username (optional if sender_email is sufficient)
    """
    smtp_password = os.getenv("EMAIL_SMTP_PASSWORD")
    smtp_user = os.getenv("EMAIL_SMTP_USER")

    if not smtp_password:
        return (
            "email",
            False,
            "EMAIL_SMTP_PASSWORD is required (SMTP password or app-specific password)"
        )

    # smtp_user is optional - some SMTP servers only need the password
    return "email", True, ""


# -----------------------------------------------------------------------------
# Tool Registration Hook
# -----------------------------------------------------------------------------


@hooks.hookimpl
def bulwark_register_tools(mcp_server: Any) -> None:
    """Register MCP tools with the server."""

    @mcp_server.tool()
    def send_email(
        recipient_name: str,
        subject: str,
        body: str,
        cc_recipient_name: str | None = None,
    ) -> str:
        """
        Send an email to a whitelisted recipient.

        Args:
            recipient_name: The friendly name of the recipient (must be in whitelist)
            subject: Email subject line
            body: Email body text
            cc_recipient_name: Optional friendly name of a CC recipient (must also be in whitelist)

        Returns:
            str: Success message or error description

        Example:
            send_email(
                recipient_name="Alice",
                subject="Meeting Tomorrow",
                body="Hi Alice, just reminding you about our meeting tomorrow at 2pm."
            )
        """
        # Get configuration from environment or use defaults
        config = _get_config_from_env()

        # Resolve recipient from whitelist
        recipient_email = _resolve_recipient(recipient_name, config.whitelist)
        if not recipient_email:
            return (
                f"Error: Recipient '{recipient_name}' is not in the whitelist. "
                f"Available recipients: {', '.join(config.whitelist.keys()) or 'none'}"
            )

        # Resolve CC recipient if provided
        cc_email = None
        if cc_recipient_name:
            cc_email = _resolve_recipient(cc_recipient_name, config.whitelist)
            if not cc_email:
                return (
                    f"Error: CC recipient '{cc_recipient_name}' is not in the whitelist. "
                    f"Available recipients: {', '.join(config.whitelist.keys()) or 'none'}"
                )

        # Get SMTP credentials from environment
        smtp_password = os.getenv("EMAIL_SMTP_PASSWORD")
        smtp_user = os.getenv("EMAIL_SMTP_USER", config.sender_email)

        if not smtp_password:
            return "Error: SMTP password not configured. Set EMAIL_SMTP_PASSWORD environment variable."

        try:
            # Create the email message
            msg = MIMEMultipart()
            msg["From"] = (
                f"{config.sender_name} <{config.sender_email}>"
                if config.sender_name
                else config.sender_email
            )
            msg["To"] = recipient_email
            msg["Subject"] = subject

            if cc_email:
                msg["Cc"] = cc_email

            msg.attach(MIMEText(body, "plain"))

            # Determine all recipients for sending
            all_recipients = [recipient_email]
            if cc_email:
                all_recipients.append(cc_email)

            # Send the email
            if config.smtp_use_tls:
                server = smtplib.SMTP(config.smtp_host, config.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(config.smtp_host, config.smtp_port)

            server.login(smtp_user, smtp_password)
            server.sendmail(config.sender_email, all_recipients, msg.as_string())
            server.quit()

            cc_msg = f" (CC: {cc_recipient_name})" if cc_recipient_name else ""
            return f"Email sent successfully to {recipient_name}{cc_msg} at {recipient_email}"

        except smtplib.SMTPAuthenticationError:
            return "Error: SMTP authentication failed. Check your credentials (EMAIL_SMTP_USER/EMAIL_SMTP_PASSWORD)."
        except smtplib.SMTPConnectError:
            return f"Error: Could not connect to SMTP server at {config.smtp_host}:{config.smtp_port}."
        except Exception as e:
            return f"Error sending email: {str(e)}"

    @mcp_server.tool()
    def list_whitelist() -> str:
        """
        List all whitelisted recipients.

        Returns:
            str: Formatted list of friendly names and their email addresses
        """
        config = _get_config_from_env()

        if not config.whitelist:
            return "No recipients in the whitelist."

        lines = ["Whitelisted recipients:"]
        for name, email in sorted(config.whitelist.items()):
            lines.append(f"  - {name}: {email}")
        return "\n".join(lines)

    @mcp_server.tool()
    def add_to_whitelist(name: str, email: str) -> str:
        """
        Add a recipient to the whitelist.

        Note: This only adds to the runtime whitelist. For permanent additions,
        update the configuration file.

        Args:
            name: Friendly name for the recipient
            email: Actual email address

        Returns:
            str: Confirmation message
        """
        # Validate email format
        if "@" not in email or "." not in email.split("@")[-1]:
            return f"Error: Invalid email address format: {email}"

        # Add to runtime whitelist
        config = _get_config_from_env()
        config.whitelist[name.lower()] = email

        return f"Added '{name}' ({email}) to the whitelist."


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def _get_config_from_env() -> EmailPluginConfig:
    """
    Build config from environment variables.

    Environment variables (all prefixed with EMAIL_):
    - EMAIL_SMTP_HOST: SMTP server hostname (required)
    - EMAIL_SMTP_PORT: SMTP port (default: 587)
    - EMAIL_SMTP_USE_TLS: Use TLS (default: true)
    - EMAIL_SENDER_EMAIL: Sender email address (required)
    - EMAIL_SENDER_NAME: Optional sender name
    - EMAIL_WHITELIST: JSON string of whitelist dict, e.g., '{"alice": "alice@example.com"}'
    - EMAIL_DEFAULT_RECIPIENT: Default recipient friendly name
    """
    import json

    whitelist_json = os.getenv("EMAIL_WHITELIST", "{}")
    try:
        whitelist = json.loads(whitelist_json)
    except json.JSONDecodeError:
        whitelist = {}

    return EmailPluginConfig(
        smtp_host=os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.getenv("EMAIL_SMTP_PORT", "587")),
        smtp_use_tls=os.getenv("EMAIL_SMTP_USE_TLS", "true").lower() == "true",
        sender_email=os.getenv("EMAIL_SENDER_EMAIL", ""),
        sender_name=os.getenv("EMAIL_SENDER_NAME", ""),
        whitelist=whitelist,
        default_recipient=os.getenv("EMAIL_DEFAULT_RECIPIENT", ""),
    )


def _resolve_recipient(
    name: str, whitelist: dict[str, str]
) -> str | None:
    """
    Resolve a friendly name to an actual email address.

    Args:
        name: Friendly name to look up
        whitelist: Dictionary mapping names to emails

    Returns:
        str | None: Email address if found, None otherwise
    """
    # Case-insensitive lookup
    name_lower = name.lower()
    return whitelist.get(name_lower)
