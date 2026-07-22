"""
Pytest fixtures for the email plugin tests.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from portcullis import hooks


@pytest.fixture
def mock_smtp():
    """Mock SMTP connection for testing email sending."""
    with patch("smtplib.SMTP") as mock:
        mock_server = MagicMock()
        mock.return_value = mock_server
        yield mock_server


@pytest.fixture
def sample_whitelist():
    """Sample whitelist for testing."""
    return {
        "alice": "alice@example.com",
        "bob": "bob@example.com",
        "charlie": "charlie@company.com",
    }


@pytest.fixture
def env_config(sample_whitelist):
    """Set up environment variables for testing."""
    import json

    env_vars = {
        "EMAIL_SMTP_HOST": "smtp.example.com",
        "EMAIL_SMTP_PORT": "587",
        "EMAIL_SMTP_USE_TLS": "true",
        "EMAIL_SENDER_EMAIL": "sender@example.com",
        "EMAIL_SENDER_NAME": "Test Sender",
        "EMAIL_SMTP_PASSWORD": "test_password",
        "EMAIL_SMTP_USER": "test_user",
        "EMAIL_WHITELIST": json.dumps(sample_whitelist),
        "EMAIL_DEFAULT_RECIPIENT": "alice",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        yield env_vars


@pytest.fixture
def minimal_env_config():
    """Minimal environment variables required for testing."""
    import json

    env_vars = {
        "EMAIL_SMTP_HOST": "smtp.example.com",
        "EMAIL_SENDER_EMAIL": "sender@example.com",
        "EMAIL_SMTP_PASSWORD": "test_password",
        "EMAIL_WHITELIST": json.dumps({"alice": "alice@example.com"}),
    }

    with patch.dict(os.environ, env_vars, clear=True):
        yield env_vars
