"""
Per-tool rate limiting for Portcullis MCP server.

Implements a token-bucket rate limiter keyed by tool name. Limits are
configured as requests-per-minute and can be set per tool via TOML:

    [tool.portcullis.rate_limits]
    send_email = 10
    list_whitelist = 120

Tools without an explicit limit fall back to the default (60/min).
"""

import threading
import time

# Default limit applied to tools without an explicit configuration.
DEFAULT_RATE_LIMIT = 60  # requests per minute


class RateLimitExceeded(Exception):
    """Raised when a tool call exceeds its configured rate limit."""

    def __init__(self, tool_name: str, retry_after: float):
        self.tool_name = tool_name
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded for tool '{tool_name}'. Try again in {retry_after:.1f} seconds."
        )


class TokenBucket:
    """A simple thread-safe token bucket."""

    def __init__(self, capacity: float, refill_per_second: float):
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def try_consume(self, tokens: float = 1.0) -> bool:
        """
        Attempt to consume tokens from the bucket.

        Returns:
            True if the tokens were consumed, False if the bucket is empty.
        """
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                self.capacity,
                self._tokens + elapsed * self.refill_per_second,
            )
            self._last_refill = now

            if self._tokens < tokens:
                return False

            self._tokens -= tokens
            return True

    def retry_after(self) -> float:
        """Seconds until at least one token is available."""
        with self._lock:
            if self._tokens >= 1.0:
                return 0.0
            if self.refill_per_second <= 0:
                return float("inf")
            return (1.0 - self._tokens) / self.refill_per_second


class RateLimiter:
    """Per-tool token-bucket rate limiter."""

    def __init__(self, limits: dict[str, int] | None = None, default: int = DEFAULT_RATE_LIMIT):
        self._default = default
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()
        if limits:
            self.configure(limits)

    def configure(self, limits: dict[str, int], default: int | None = None) -> None:
        """
        (Re)configure the limiter with per-tool limits.

        Args:
            limits: Mapping of tool name to requests-per-minute limit.
            default: Optional new default limit (requests per minute).
        """
        if default is not None:
            self._default = default
        with self._lock:
            self._buckets = {name: self._make_bucket(limit) for name, limit in limits.items()}

    def _make_bucket(self, limit: int) -> TokenBucket:
        """Build a token bucket from a requests-per-minute limit."""
        limit = max(1, int(limit))
        return TokenBucket(capacity=float(limit), refill_per_second=limit / 60.0)

    def _bucket_for(self, tool_name: str) -> TokenBucket:
        with self._lock:
            bucket = self._buckets.get(tool_name)
            if bucket is None:
                bucket = self._make_bucket(self._default)
                self._buckets[tool_name] = bucket
            return bucket

    def check(self, tool_name: str) -> None:
        """
        Check whether a tool call is allowed, raising RateLimitExceeded if not.

        Args:
            tool_name: The name of the tool being called.

        Raises:
            RateLimitExceeded: If the tool has exceeded its rate limit.
        """
        bucket = self._bucket_for(tool_name)
        if not bucket.try_consume():
            raise RateLimitExceeded(tool_name, bucket.retry_after())


# -----------------------------------------------------------------------------
# Module-level default limiter
# -----------------------------------------------------------------------------
# The transports share a single limiter instance, configured at startup from
# the loaded Config. This keeps rate limiting consistent across stdio and
# HTTP/SSE without threading a Config object through every handler.
_limiter = RateLimiter()


def configure_rate_limits(limits: dict[str, int], default: int | None = None) -> None:
    """Configure the shared rate limiter (called at server startup)."""
    _limiter.configure(limits, default=default)


def check_rate_limit(tool_name: str) -> None:
    """Check the shared rate limiter for a tool call."""
    _limiter.check(tool_name)


def get_limiter() -> RateLimiter:
    """Return the shared rate limiter instance (for testing)."""
    return _limiter
