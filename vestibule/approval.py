"""
Human-in-the-loop approval workflow for Vestibule MCP server.

Gates tool calls behind an approval check. Approval mode is configured
globally with an optional per-tool list:

    [tool.vestibule.approval]
    mode = "first_only"   # always | first_only | never
    tools = ["send_email"]

Modes:
- ``never``:      no approval required.
- ``first_only``: the first call to a gated tool requires approval; once
                  approved, subsequent calls skip (approval is sticky).
- ``always``:     every call to a gated tool requires approval; approval is
                  granted per-call via the built-in ``approve_tool`` tool.

Approval state is held in memory only (runtime, not persistent).
"""

import threading
from enum import StrEnum

# Default mode applied when no approval configuration is provided.
DEFAULT_APPROVAL_MODE = "first_only"


class ApprovalMode(StrEnum):
    """Supported approval modes."""

    ALWAYS = "always"
    FIRST_ONLY = "first_only"
    NEVER = "never"


class ApprovalRequired(Exception):
    """Raised when a tool call requires human approval."""

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(
            f"Approval required for tool '{tool_name}'. "
            f"Call the 'approve_tool' tool to approve it, then retry."
        )


class ApprovalTracker:
    """Thread-safe tracker for tool approval state."""

    def __init__(
        self,
        mode: ApprovalMode | str = DEFAULT_APPROVAL_MODE,
        tools: list[str] | None = None,
        overrides: dict[str, ApprovalMode | str] | None = None,
    ):
        self._default_mode = ApprovalMode(mode)
        self._gated: set[str] = set(tools or [])
        # Per-tool mode overrides: tool name -> its own approval mode.
        self._overrides: dict[str, ApprovalMode] = {
            name: ApprovalMode(m) for name, m in (overrides or {}).items()
        }
        # Sticky approvals (first_only): once approved, stays approved.
        self._approved: set[str] = set()
        # One-time approvals (always): consumed by the next call.
        self._pending: set[str] = set()
        self._lock = threading.Lock()

    def configure(
        self,
        mode: ApprovalMode | str,
        tools: list[str] | None = None,
        overrides: dict[str, ApprovalMode | str] | None = None,
    ) -> None:
        """(Re)configure the tracker, resetting all approval state."""
        with self._lock:
            self._default_mode = ApprovalMode(mode)
            self._gated = set(tools or [])
            self._overrides = {name: ApprovalMode(m) for name, m in (overrides or {}).items()}
            self._approved.clear()
            self._pending.clear()

    def _mode_for(self, tool_name: str) -> ApprovalMode | None:
        """Return the effective approval mode for a tool, or None if not gated."""
        if tool_name in self._overrides:
            return self._overrides[tool_name]
        if tool_name in self._gated:
            return self._default_mode
        return None

    def is_gated(self, tool_name: str) -> bool:
        """Return True if the tool has any approval policy applied."""
        return self._mode_for(tool_name) is not None

    def check(self, tool_name: str) -> None:
        """
        Check whether a tool call is allowed, raising ApprovalRequired if not.

        Args:
            tool_name: The name of the tool being called.

        Raises:
            ApprovalRequired: If the tool call requires human approval.
        """
        with self._lock:
            mode = self._mode_for(tool_name)
            if mode is None or mode == ApprovalMode.NEVER:
                return
            # A one-time approval (always mode) is consumed by this call.
            if tool_name in self._pending:
                self._pending.discard(tool_name)
                return
            if mode == ApprovalMode.FIRST_ONLY and tool_name in self._approved:
                return
            raise ApprovalRequired(tool_name)

    def approve(self, tool_name: str) -> None:
        """
        Grant approval for a tool.

        In ``always`` mode the approval is one-time (consumed by the next
        call); in ``first_only`` mode it is sticky.
        """
        with self._lock:
            if self._mode_for(tool_name) == ApprovalMode.ALWAYS:
                self._pending.add(tool_name)
            else:
                self._approved.add(tool_name)

    def reset(self) -> None:
        """Clear all approval state."""
        with self._lock:
            self._approved.clear()
            self._pending.clear()


# -----------------------------------------------------------------------------
# Module-level default tracker
# -----------------------------------------------------------------------------
# The transports share a single tracker instance, configured at startup from
# the loaded Config. This keeps approval state consistent across stdio and
# HTTP/SSE without threading a Config object through every handler.
_tracker = ApprovalTracker()


def configure_approval(
    mode: ApprovalMode | str,
    tools: list[str] | None = None,
    overrides: dict[str, ApprovalMode | str] | None = None,
) -> None:
    """Configure the shared approval tracker (called at server startup)."""
    _tracker.configure(mode, tools, overrides)


def check_approval(tool_name: str) -> None:
    """Check the shared approval tracker for a tool call."""
    _tracker.check(tool_name)


def grant_approval(tool_name: str) -> None:
    """Grant approval for a tool on the shared tracker."""
    _tracker.approve(tool_name)


def get_approval_tracker() -> ApprovalTracker:
    """Return the shared approval tracker instance (for testing)."""
    return _tracker
