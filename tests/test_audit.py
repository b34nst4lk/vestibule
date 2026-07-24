"""
Tests for the audit logging module.
"""

import json
import logging
from io import StringIO

import pytest

from portcullis.audit import log_tool_call, mask_sensitive_data


@pytest.fixture
def capture_audit_logs():
    """Capture audit logs to a string buffer for testing."""
    import portcullis.audit as audit_module

    # Create a string handler
    string_buffer = StringIO()
    handler = logging.StreamHandler(string_buffer)
    handler.setLevel(logging.INFO)

    # Get the audit logger and add our handler
    logger = audit_module._audit_logger
    logger.addHandler(handler)

    yield string_buffer

    # Cleanup
    logger.removeHandler(handler)


class TestMaskSensitiveData:
    """Tests for the mask_sensitive_data function."""

    def test_mask_secretstr(self):
        """Test that SecretStr values are masked."""
        from pydantic import SecretStr

        secret = SecretStr("my-secret-password")
        assert mask_sensitive_data(secret) == "***"

    def test_mask_dict_with_secrets(self):
        """Test masking sensitive values in a dictionary."""
        from pydantic import SecretStr

        data = {
            "username": "alice",
            "password": SecretStr("secret123"),
            "email": "alice@example.com",
        }
        result = mask_sensitive_data(data)
        assert result["username"] == "alice"
        assert result["password"] == "***"
        assert result["email"] == "alice@example.com"

    def test_mask_nested_dict(self):
        """Test masking in nested dictionaries."""
        from pydantic import SecretStr

        data = {
            "user": {"name": "alice", "token": SecretStr("abc123")},
            "settings": {"theme": "dark"},
        }
        result = mask_sensitive_data(data)
        assert result["user"]["name"] == "alice"
        assert result["user"]["token"] == "***"
        assert result["settings"]["theme"] == "dark"

    def test_mask_list(self):
        """Test masking in lists."""
        from pydantic import SecretStr

        data = ["value1", SecretStr("secret"), "value3"]
        result = mask_sensitive_data(data)
        assert result[0] == "value1"
        assert result[1] == "***"
        assert result[2] == "value3"

    def test_empty_values_unchanged(self):
        """Test that empty values are not masked."""
        assert mask_sensitive_data("") == ""
        assert mask_sensitive_data({}) == {}
        assert mask_sensitive_data([]) == []
        assert mask_sensitive_data(None) is None

    def test_primitives_unchanged(self):
        """Test that primitive values pass through unchanged."""
        assert mask_sensitive_data(42) == 42
        assert mask_sensitive_data(3.14) == 3.14
        assert mask_sensitive_data(True) is True
        assert mask_sensitive_data("hello") == "hello"


class TestLogToolCall:
    """Tests for the log_tool_call function."""

    def test_log_successful_tool_call(self, capture_audit_logs):
        """Test logging a successful tool call."""
        log_tool_call(
            tool_name="send_email",
            arguments={"recipient": "alice@example.com", "body": "Hello"},
            success=True,
            result="Email sent successfully",
            session_id="test-session-123",
        )

        log_output = capture_audit_logs.getvalue()
        assert log_output  # Should have output

        # Parse the JSON log
        log_entry = json.loads(log_output.strip())
        assert log_entry["event_type"] == "tool_call"
        assert log_entry["tool_name"] == "send_email"
        assert log_entry["success"] is True
        assert log_entry["session_id"] == "test-session-123"
        assert "timestamp" in log_entry

    def test_log_failed_tool_call(self, capture_audit_logs):
        """Test logging a failed tool call."""
        log_tool_call(
            tool_name="send_email",
            arguments={"recipient": "alice@example.com"},
            success=False,
            error="SMTP connection failed",
            session_id="test-session-456",
        )

        log_output = capture_audit_logs.getvalue()
        log_entry = json.loads(log_output.strip())

        assert log_entry["success"] is False
        assert log_entry["error"] == "SMTP connection failed"
        assert "result_preview" not in log_entry  # No result on failure

    def test_log_masks_sensitive_arguments(self, capture_audit_logs):
        """Test that sensitive arguments are masked in logs."""
        from pydantic import SecretStr

        log_tool_call(
            tool_name="api_call",
            arguments={
                "endpoint": "/users",
                "api_key": SecretStr("sk-1234567890"),
            },
            success=True,
            result="OK",
        )

        log_output = capture_audit_logs.getvalue()
        log_entry = json.loads(log_output.strip())

        assert log_entry["arguments"]["api_key"] == "***"
        assert log_entry["arguments"]["endpoint"] == "/users"

    def test_log_truncates_long_results(self, capture_audit_logs):
        """Test that long results are truncated."""
        long_result = "x" * 1000  # 1000 characters

        log_tool_call(
            tool_name="get_data",
            arguments={},
            success=True,
            result=long_result,
        )

        log_output = capture_audit_logs.getvalue()
        log_entry = json.loads(log_output.strip())

        preview = log_entry["result_preview"]
        assert len(preview) < 600  # Should be truncated
        assert "... (truncated)" in preview
