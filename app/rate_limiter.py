"""
Sliding Window Rate Limiter for LLM Invocation Cost Protection.
Simple in-memory implementation - sufficient for single-instance deployments.
"""
import time
from threading import Lock
from collections import deque
from datadog import statsd
from app.logging_config import setup_logging

logger = setup_logging()


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter for protecting LLM generation costs.
    Thread-safe implementation using a deque of timestamps.
    """
    
    def __init__(self, max_calls: int, window_seconds: int = 3600):
        """
        Initialize rate limiter.
        
        Args:
            max_calls: Maximum allowed calls within the window
            window_seconds: Window size in seconds (default: 1 hour)
        """
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._timestamps: deque = deque()
        self._lock = Lock()
    
    def _cleanup_old_timestamps(self):
        """Remove timestamps outside the current window."""
        cutoff = time.time() - self.window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
    
    def is_allowed(self) -> bool:
        """
        Check if a new call is allowed and record it if so.
        
        Returns:
            True if call is allowed, False if rate limited
        """
        with self._lock:
            self._cleanup_old_timestamps()
            
            if len(self._timestamps) >= self.max_calls:
                logger.warning(f"Rate limit exceeded: {len(self._timestamps)}/{self.max_calls} calls in window")
                statsd.increment("llm.rate_limit.exceeded")
                return False
            
            self._timestamps.append(time.time())
            return True
    
    def current_count(self) -> int:
        """Get current number of calls in the window."""
        with self._lock:
            self._cleanup_old_timestamps()
            return len(self._timestamps)
    
    def usage_percentage(self) -> float:
        """Get current usage as a percentage of max."""
        return self.current_count() / self.max_calls if self.max_calls > 0 else 0.0
    
    def is_panic_threshold(self, panic_threshold: float = 0.9) -> bool:
        """
        Check if we're at or above the panic threshold.
        
        Args:
            panic_threshold: Percentage threshold (default 0.9 = 90%)
            
        Returns:
            True if usage >= panic_threshold
        """
        usage = self.usage_percentage()
        if usage >= panic_threshold:
            logger.warning(f"🚨 LLM rate limit at panic threshold: {usage:.1%} usage")
            statsd.gauge("llm.cost.risk_signal", 1)
            return True
        return False
    
    def emit_metrics(self):
        """Emit current rate limiter metrics to Datadog."""
        count = self.current_count()
        usage = self.usage_percentage()
        statsd.gauge("llm.rate_limit.current_count", count)
        statsd.gauge("llm.rate_limit.usage_percentage", usage * 100)
        
        # Emit risk signal based on usage
        if usage >= 0.9:
            statsd.gauge("llm.cost.risk_signal", 1)
        elif usage >= 0.5:
            statsd.gauge("llm.cost.risk_signal", 0.5)
        else:
            statsd.gauge("llm.cost.risk_signal", 0)


# Global rate limiter instance - initialized lazily in routes.py
_llm_rate_limiter = None


def get_rate_limiter(max_calls: int, window_seconds: int = 3600) -> SlidingWindowRateLimiter:
    """Get or create the global rate limiter instance."""
    global _llm_rate_limiter
    if _llm_rate_limiter is None:
        _llm_rate_limiter = SlidingWindowRateLimiter(max_calls, window_seconds)
        logger.info(f"Initialized LLM rate limiter: {max_calls} calls/{window_seconds}s")
    return _llm_rate_limiter
