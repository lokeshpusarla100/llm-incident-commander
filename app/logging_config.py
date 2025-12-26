"""
Structured logging configuration for Datadog integration
"""
import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict
from ddtrace import tracer

class DatadogJSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for Datadog logs.
    Automatically injects trace and span IDs for correlation.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with Datadog fields"""
        
        # Get trace context from ddtrace
        span = tracer.current_span()
        
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "llm-incident-commander",
        }
        
        # Add trace correlation if available
        if span:
            log_data["dd.trace_id"] = str(span.trace_id)
            log_data["dd.span_id"] = str(span.span_id)
        
        # Add extra fields from record
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        if hasattr(record, "latency_ms"):
            log_data["latency_ms"] = record.latency_ms
            
        if hasattr(record, "tokens"):
            log_data["tokens"] = record.tokens
            
        if hasattr(record, "cost_usd"):
            log_data["cost_usd"] = record.cost_usd
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def setup_logging() -> logging.Logger:
    """
    Configure structured JSON logging for the application.
    Logs will be automatically forwarded to Datadog when using ddtrace.
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("llm-incident-commander")
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(DatadogJSONFormatter())
    
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger
