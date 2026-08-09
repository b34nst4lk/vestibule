"""
Tests for the human-in-the-loop approval workflow module.
"""

import pytest

from vestibule.approval import (
    ApprovalMode,
    ApprovalRequired,
    ApprovalTracker,
)


class TestApprovalMode:
    """Tests for the approval mode enum."""

    def test_values(self):
        """The enum exposes the three documented modes."""
        assert ApprovalMode.ALWAYS == "always"
        assert ApprovalMode.FIRST_ONLY == "first_only"
        assert ApprovalMode.NEVER == "never"


class TestApprovalTracker:
    """Tests for the approval state tracker."""

    def test_never_policy_allows_all(self):
        """A tool with a never policy requires no approval."""
        tracker = ApprovalTracker(policies={"send_email": ApprovalMode.NEVER})
        tracker.check("send_email")  # should not raise

    def test_non_gated_tool_passes(self):
        """Tools with no declared policy never require approval."""
        tracker = ApprovalTracker(policies={"send_email": ApprovalMode.ALWAYS})
        tracker.check("list_whitelist")  # not gated, should not raise

    def test_first_only_requires_first_call(self):
        """In first_only mode, the first call requires approval."""
        tracker = ApprovalTracker(policies={"send_email": ApprovalMode.FIRST_ONLY})
        with pytest.raises(ApprovalRequired):
            tracker.check("send_email")

    def test_first_only_is_sticky_after_approval(self):
        """Once approved, subsequent first_only calls skip approval."""
        tracker = ApprovalTracker(policies={"send_email": ApprovalMode.FIRST_ONLY})
        tracker.approve("send_email")
        tracker.check("send_email")  # should not raise
        tracker.check("send_email")  # still approved

    def test_always_requires_approval_each_call(self):
        """In always mode, every call requires approval."""
        tracker = ApprovalTracker(policies={"send_email": ApprovalMode.ALWAYS})
        with pytest.raises(ApprovalRequired):
            tracker.check("send_email")
        tracker.approve("send_email")
        tracker.check("send_email")  # one-time approval consumed
        with pytest.raises(ApprovalRequired):
            tracker.check("send_email")  # needs approval again

    def test_approval_required_message_names_tool(self):
        """The exception message names the tool and the approve_tool tool."""
        tracker = ApprovalTracker(policies={"send_email": ApprovalMode.FIRST_ONLY})
        with pytest.raises(ApprovalRequired) as excinfo:
            tracker.check("send_email")
        assert "send_email" in str(excinfo.value)
        assert "approve_tool" in str(excinfo.value)

    def test_configure_resets_state(self):
        """configure() replaces policies and clears approval state."""
        tracker = ApprovalTracker(policies={"send_email": ApprovalMode.FIRST_ONLY})
        tracker.approve("send_email")
        tracker.configure(policies={"other_tool": ApprovalMode.NEVER})
        assert tracker.is_gated("other_tool")
        assert not tracker.is_gated("send_email")
        tracker.check("other_tool")  # never mode, no approval needed

    def test_reset_clears_approvals(self):
        """reset() clears approval state but keeps policies."""
        tracker = ApprovalTracker(policies={"send_email": ApprovalMode.FIRST_ONLY})
        tracker.approve("send_email")
        tracker.reset()
        with pytest.raises(ApprovalRequired):
            tracker.check("send_email")

    def test_is_gated(self):
        """is_gated reflects the declared policies."""
        tracker = ApprovalTracker(policies={"send_email": ApprovalMode.FIRST_ONLY})
        assert tracker.is_gated("send_email")
        assert not tracker.is_gated("list_whitelist")

    def test_disabled_tracker_never_gates(self):
        """When enabled=False, no tool requires approval."""
        tracker = ApprovalTracker(
            enabled=False,
            policies={"send_email": ApprovalMode.ALWAYS},
        )
        tracker.check("send_email")  # should not raise

    def test_override_never_allows_tool(self):
        """An operator override to never wins over a plugin policy."""
        tracker = ApprovalTracker(
            policies={"send_email": ApprovalMode.ALWAYS},
            overrides={"send_email": ApprovalMode.NEVER},
        )
        tracker.check("send_email")  # should not raise

    def test_override_always_requires_each_call(self):
        """An operator override to always wins over a looser plugin policy."""
        tracker = ApprovalTracker(
            policies={"send_email": ApprovalMode.NEVER},
            overrides={"send_email": ApprovalMode.ALWAYS},
        )
        with pytest.raises(ApprovalRequired):
            tracker.check("send_email")
        tracker.approve("send_email")
        tracker.check("send_email")  # one-time approval consumed
        with pytest.raises(ApprovalRequired):
            tracker.check("send_email")

    def test_override_applies_to_tool_without_policy(self):
        """An override gates a tool even if the plugin declared no policy."""
        tracker = ApprovalTracker(
            policies={"send_email": ApprovalMode.FIRST_ONLY},
            overrides={"other_tool": ApprovalMode.ALWAYS},
        )
        with pytest.raises(ApprovalRequired):
            tracker.check("other_tool")

    def test_mixed_policies(self):
        """Different tools can have different policies simultaneously."""
        tracker = ApprovalTracker(
            policies={"send_email": ApprovalMode.FIRST_ONLY},
            overrides={
                "send_whitelisted_emails": ApprovalMode.NEVER,
                "other_plugin_tool": ApprovalMode.ALWAYS,
            },
        )
        # always allowed
        tracker.check("send_whitelisted_emails")
        # always requires approval
        with pytest.raises(ApprovalRequired):
            tracker.check("other_plugin_tool")
        # plugin policy first_only
        with pytest.raises(ApprovalRequired):
            tracker.check("send_email")
        # not gated at all
        tracker.check("list_whitelist")


class TestApprovalGate:
    """Tests for the approval gate in the shared tool-call handler."""

    def _make_server(self):
        """Build a minimal mock FastMCP server that records calls."""
        calls = []

        class _Result:
            content = [type("C", (), {"text": "ok"})()]
            isError = False

        class _Server:
            async def call_tool(self, name, arguments):
                calls.append((name, arguments))
                return _Result()

        return _Server(), calls

    async def test_gated_tool_returns_approval_required(self):
        """A gated tool call returns an approval-required response and is not executed."""
        from vestibule.approval import configure_approval
        from vestibule.transports.common import handle_tools_call

        configure_approval(policies={"send_email": "first_only"})
        server, calls = self._make_server()

        result = await handle_tools_call(server, "send_email", {"to": "a@b.c"})

        assert calls == []  # tool was not executed
        assert result["isError"] is False
        assert result["structuredContent"]["approval_required"] is True
        assert result["structuredContent"]["tool"] == "send_email"
        assert "approve_tool" in result["content"][0]["text"]

    async def test_approved_tool_executes(self):
        """After approval, the tool call executes normally."""
        from vestibule.approval import configure_approval, grant_approval
        from vestibule.transports.common import handle_tools_call

        configure_approval(policies={"send_email": "first_only"})
        grant_approval("send_email")
        server, calls = self._make_server()

        result = await handle_tools_call(server, "send_email", {"to": "a@b.c"})

        assert calls == [("send_email", {"to": "a@b.c"})]
        assert result["isError"] is False

    async def test_non_gated_tool_executes(self):
        """A non-gated tool executes without approval."""
        from vestibule.approval import configure_approval
        from vestibule.transports.common import handle_tools_call

        configure_approval(policies={"send_email": "first_only"})
        server, calls = self._make_server()

        result = await handle_tools_call(server, "list_whitelist", {})

        assert calls == [("list_whitelist", {})]
        assert result["isError"] is False
