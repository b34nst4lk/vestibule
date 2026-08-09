"""
Human-in-the-loop approval workflow for Vestibule MCP server.

Gates tool calls behind an approval check. Approval policy is declared by
plugins (per-tool), enabled globally, and overridable per-tool by the
operator:

    [tool.vestibule.approval]
    enabled = true

    [tool.vestibule.approval.overrides]
    send_email = "never"   # operator override

Plugins declare their default per-tool policy via the
``vestibule_approval_policy`` hook. The effective mode for a tool is:

1. operator override (if present)
2. plugin-declared policy (if present)
3. not gated (allowed)

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


class ApprovalMode(StrEnum):
    """Supported approval modes."""

    ALWAYS = "always"
    FIRST_ONLY = "first_only"
    NEVER = "never"


# Name of the built-in MCP tool clients call to grant approval. Kept in one
# place so the exception message and the CLI registration stay in sync.
APPROVE_TOOL_NAME = "approve_tool"


class ApprovalRequired(Exception):
    """Raised when a tool call requires human approval."""

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(
            f"Approval required for tool '{tool_name}'. "
            f"Call the '{APPROVE_TOOL_NAME}' tool to approve it, then retry."
        )


class ApprovalTracker:
    """Thread-safe tracker for tool approval state.

    Policies and overrides are expected to be pre-normalized to
    ``dict[str, ApprovalMode]`` (see :func:`normalize_approval_modes`).
    """

    def __init__(
        self,
        enabled: bool = True,
        policies: dict[str, ApprovalMode] | None = None,
        overrides: dict[str, ApprovalMode] | None = None,
    ):
        self._enabled = enabled
        # Plugin-declared per-tool policies (the defaults).
        self._policies: dict[str, ApprovalMode] = dict(policies or {})
        # Operator per-tool overrides (win over plugin policies).
        self._overrides: dict[str, ApprovalMode] = dict(overrides or {})
        # Sticky approvals (first_only): once approved, stays approved.
        self._approved: set[str] = set()
        # One-time approvals (always): consumed by the next call.
        self._pending: set[str] = set()
        self._lock = threading.Lock()

    def configure(
        self,
        enabled: bool = True,
        policies: dict[str, ApprovalMode] | None = None,
        overrides: dict[str, ApprovalMode] | None = None,
    ) -> None:
        """(Re)configure the tracker, resetting all approval state."""
        with self._lock:
            self._enabled = enabled
            self._policies = dict(policies or {})
            self._overrides = dict(overrides or {})
            self._approved.clear()
            self._pending.clear()

    def _mode_for(self, tool_name: str) -> ApprovalMode | None:
        """Return the effective approval mode for a tool, or None if not gated.

        Caller must hold ``_lock``.
        """
        if not self._enabled:
            return None
        if tool_name in self._overrides:
            return self._overrides[tool_name]
        if tool_name in self._policies:
            return self._policies[tool_name]
        return None

    def is_gated(self, tool_name: str) -> bool:
        """Return True if the tool has any approval policy applied."""
        with self._lock:
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
# the loaded Config and plugin-declared policies. This keeps approval state
# consistent across stdio and HTTP/SSE without threading a Config object
# through every handler.
_tracker = ApprovalTracker()


def normalize_approval_modes(
    modes: dict[str, ApprovalMode | str] | None,
) -> dict[str, ApprovalMode]:
    """Normalize a mapping of tool name -> mode to ``ApprovalMode`` values.

    Accepts either ``ApprovalMode`` members or their string values. Raises
    ``ValueError`` if a value is not a supported mode, so misconfigurations
    surface at load time rather than failing later at runtime.
    """
    if not modes:
        return {}
    normalized: dict[str, ApprovalMode] = {}
    for name, mode in modes.items():
        if isinstance(mode, ApprovalMode):
            normalized[name] = mode
        else:
            try:
                normalized[name] = ApprovalMode(mode)
            except ValueError:
                supported = ", ".join(m.value for m in ApprovalMode)
                raise ValueError(
                    f"Invalid approval mode '{mode}' for tool '{name}'. "
                    f"Supported modes: {supported}."
                ) from None
    return normalized


def configure_approval(
    enabled: bool = True,
    policies: dict[str, ApprovalMode | str] | None = None,
    overrides: dict[str, ApprovalMode | str] | None = None,
) -> None:
    """Configure the shared approval tracker (called at server startup)."""
    _tracker.configure(
        enabled,
        normalize_approval_modes(policies),
        normalize_approval_modes(overrides),
    )


def check_approval(tool_name: str) -> None:
    """Check the shared approval tracker for a tool call."""
    _tracker.check(tool_name)


def grant_approval(tool_name: str) -> None:
    """Grant approval for a tool on the shared tracker."""
    _tracker.approve(tool_name)


def get_approval_tracker() -> ApprovalTracker:
    """Return the shared approval tracker instance (for testing)."""
    return _tracker
