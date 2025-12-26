"""
Centralized configuration for LLM Incident Commander
"""
import os
from typing import Optional

class Config:
    """Application configuration"""
    
    # Google Cloud / Vertex AI
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "forms-e5771")
    GCP_LOCATION: str = os.getenv("GCP_LOCATION", "us-central1")
    VERTEX_AI_MODEL: str = os.getenv("VERTEX_AI_MODEL", "gemini-2.0-flash")
    
    # Datadog Configuration
    DD_SERVICE: str = os.getenv("DD_SERVICE", "llm-incident-commander")
    DD_ENV: str = os.getenv("DD_ENV", "production")
    DD_VERSION: str = os.getenv("DD_VERSION", "1.0.0")
    DD_LOGS_INJECTION: str = os.getenv("DD_LOGS_INJECTION", "true")
    
    # Application Settings
    APP_NAME: str = "LLM Incident Commander"
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    
    # LLM Generation Config
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_OUTPUT_TOKENS: int = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "512"))
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    
    # Pricing (Gemini 2.0 Flash pricing as of Dec 2024)
    # Per 1M tokens - https://cloud.google.com/vertex-ai/generative-ai/pricing
    PRICE_PER_1M_INPUT_TOKENS: float = 0.075  # $0.075 per 1M input tokens
    PRICE_PER_1M_OUTPUT_TOKENS: float = 0.30  # $0.30 per 1M output tokens
    
    # SLO Targets (for reference in metrics)
    SLO_LATENCY_TARGET_MS: int = 2000  # 2 seconds
    SLO_AVAILABILITY_TARGET: float = 0.99  # 99%
    SLO_ERROR_RATE_TARGET: float = 0.01  # 1%
    
    # Hallucination Detection
    HALLUCINATION_THRESHOLD: float = 0.7  # Alert if score exceeds this
    HALLUCINATION_RED_FLAGS: list = [
        "I think", "maybe", "might be wrong", "not sure",
        "I'm not certain", "possibly", "could be", "I guess"
    ]
    
    # Retry Configuration (for production resilience)
    MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    RETRY_DELAY_SECONDS: float = float(os.getenv("LLM_RETRY_DELAY", "1.0"))
    RETRY_BACKOFF_MULTIPLIER: float = float(os.getenv("LLM_RETRY_BACKOFF", "2.0"))
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimate token count for text.
        Approximation: ~4 characters per token for English text.
        This is a rough estimate - actual tokenization may vary.
        """
        return max(1, len(text) // 4)
    
    @staticmethod
    def calculate_cost(input_tokens: int, output_tokens: int) -> float:
        """
        Calculate estimated cost in USD for LLM request.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        input_cost = (input_tokens / 1_000_000) * Config.PRICE_PER_1M_INPUT_TOKENS
        output_cost = (output_tokens / 1_000_000) * Config.PRICE_PER_1M_OUTPUT_TOKENS
        return input_cost + output_cost


config = Config()
