"""
Resilient Datadog telemetry with retry, circuit breaker, fallback.
This is production-grade failure handling (Requirement #7).
"""
import time
from functools import wraps
from datadog import statsd
from app.logging_config import setup_logging

logger = setup_logging()

class CircuitBreaker:
    """Simple circuit breaker for Datadog API calls"""
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func):
        """Execute function with circuit breaker logic"""
        # If circuit is OPEN and timeout expired, try HALF_OPEN
        if self.state == "OPEN":
            if self.last_failure_time and (time.time() - self.last_failure_time > self.timeout):
                self.state = "HALF_OPEN"
            else:
                # Fail fast
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func()
            
            # Success - reset on HALF_OPEN
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            
            return result
        
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.error(f"Circuit breaker OPENED after {self.failure_count} failures")
            
            raise

# Global circuit breaker for Datadog API
dd_circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=300)

def retry_with_backoff(max_retries=3, initial_delay=0.1, backoff_factor=2):
    """Decorator for retrying failed operations with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return dd_circuit_breaker.call(lambda: func(*args, **kwargs))
                except Exception as e:
                    last_exception = e
                    
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Datadog call failed (attempt {attempt+1}/{max_retries}). "
                            f"Retrying in {delay}s",
                            extra={"error": str(e), "delay_seconds": delay}
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
            
            # All retries exhausted - fallback to logging
            logger.error(
                "FALLBACK: Emitting to logs instead of Datadog metrics",
                extra={"original_error": str(last_exception)}
            )
            
            # Emit fallback metric via logs (not triggering recursion)
            logger.info("metric:datadog.api.failures type:count value:1 tags:fallback:true")
            
            return None
        
        return wrapper
    return decorator

@retry_with_backoff(max_retries=3)
def emit_metric_safe(metric_type: str, name: str, value, tags: list = None):
    """
    Safely emit a metric with resilience.
    
    Args:
        metric_type: 'gauge', 'increment', 'histogram'
        name: Metric name
        value: Metric value
        tags: List of tags
    """
    if metric_type == 'gauge':
        statsd.gauge(name, value, tags=tags)
    elif metric_type == 'increment':
        statsd.increment(name, value=value, tags=tags)
    elif metric_type == 'histogram':
        statsd.histogram(name, value, tags=tags)
    else:
        raise ValueError(f"Unknown metric type: {metric_type}")
