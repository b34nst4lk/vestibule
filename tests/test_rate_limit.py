"""
Tests for the per-tool rate limiting module.
"""

import pytest

from portcullis.rate_limit import (
    DEFAULT_RATE_LIMIT,
    RateLimiter,
    RateLimitExceeded,
    TokenBucket,
)


class TestTokenBucket:
    """Tests for the token bucket primitive."""

    def test_full_bucket_allows_consumption(self):
        """A full bucket allows consuming tokens."""
        bucket = TokenBucket(capacity=10, refill_per_second=1.0)
        assert bucket.try_consume() is True

    def test_empty_bucket_rejects(self):
        """An empty bucket rejects consumption."""
        bucket = TokenBucket(capacity=1, refill_per_second=0.0)
        assert bucket.try_consume() is True
        assert bucket.try_consume() is False

    def test_retry_after_when_empty(self):
        """retry_after reports seconds until a token is available."""
        bucket = TokenBucket(capacity=1, refill_per_second=1.0)
        bucket.try_consume()
        assert bucket.retry_after() > 0

    def test_retry_after_zero_when_available(self):
        """retry_after is 0 when a token is available."""
        bucket = TokenBucket(capacity=5, refill_per_second=1.0)
        assert bucket.retry_after() == 0.0


class TestRateLimiter:
    """Tests for the per-tool rate limiter."""

    def test_default_limit_applied(self):
        """Tools without an explicit limit use the default."""
        limiter = RateLimiter(limits={}, default=2)
        limiter.check("some_tool")
        limiter.check("some_tool")
        with pytest.raises(RateLimitExceeded):
            limiter.check("some_tool")

    def test_per_tool_limit(self):
        """Each tool has its own independent bucket."""
        limiter = RateLimiter(limits={"a": 1, "b": 3}, default=10)
        limiter.check("a")
        with pytest.raises(RateLimitExceeded):
            limiter.check("a")
        # b is unaffected
        limiter.check("b")
        limiter.check("b")
        limiter.check("b")

    def test_configure_replaces_limits(self):
        """configure() replaces existing buckets."""
        limiter = RateLimiter(limits={"a": 1}, default=10)
        limiter.check("a")
        with pytest.raises(RateLimitExceeded):
            limiter.check("a")
        limiter.configure({"a": 5})
        limiter.check("a")  # bucket reset to 5

    def test_error_message_contains_tool_name(self):
        """The exception message names the tool and retry window."""
        limiter = RateLimiter(limits={"a": 1}, default=10)
        limiter.check("a")
        with pytest.raises(RateLimitExceeded) as excinfo:
            limiter.check("a")
        assert "a" in str(excinfo.value)
        assert "Try again" in str(excinfo.value)

    def test_default_constant(self):
        """The default limit constant is 60/min."""
        assert DEFAULT_RATE_LIMIT == 60
