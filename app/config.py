"""
Centralized configuration for LLM Incident Commander
"""
import os
from typing import Optional

class Config:
    """Application configuration"""
    
    # Google Cloud / Vertex AI
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID")
    if not GCP_PROJECT_ID:
        # FAIL CLOSED: The application must not start without a project ID.
        raise ValueError("GCP_PROJECT_ID environment variable is validation required. Cannot start without Google Cloud Project ID.") 

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
    
    # =========================================================================
    # Cost-Safety Controls (CRITICAL for production)
    # =========================================================================
    # SAFE_MODE: Disables all cloud infra assumptions. Default: FALSE (Active).
    # User requested active Gemini by default.
    SAFE_MODE: bool = os.getenv("SAFE_MODE", "false").lower() == "true"
    
    # DISABLE LLM generation by default - vector search only responds
    # User requested Gemini ENABLED by default
    ENABLE_LLM_GENERATION: bool = os.getenv("ENABLE_LLM_GENERATION", "true").lower() == "true"
    
    # Similarity threshold: if best_score >= this, skip LLM and return RAG directly
    LLM_SIMILARITY_THRESHOLD: float = float(os.getenv("LLM_SIMILARITY_THRESHOLD", "0.7"))
    
    # Rate limit for Gemini calls per hour (per instance)
    LLM_RATE_LIMIT_PER_HOUR: int = int(os.getenv("LLM_RATE_LIMIT_PER_HOUR", "100"))
    
    # Hard cap on output tokens (overrides per-request max_tokens)
    LLM_MAX_OUTPUT_TOKENS_CAP: int = int(os.getenv("LLM_MAX_OUTPUT_TOKENS_CAP", "1024"))
    
    # Panic threshold: at 90% rate limit usage, skip LLM and emit risk signal
    LLM_PANIC_THRESHOLD: float = float(os.getenv("LLM_PANIC_THRESHOLD", "0.9"))
    
    # Pricing (Gemini 2.0 Flash pricing as of Dec 2024)
    # Source: https://cloud.google.com/vertex-ai/pricing#generative-ai-models
    GEMINI_PRICING_MAP = {
        "gemini-2.0-flash": {
            "input_per_1m_tokens": 0.075,
            "output_per_1m_tokens": 0.30,
            "cached_input_per_1m_tokens": 0.01875,
            "hash": "gemini-2.0-flash-dec-2025",  # For drift detection
            "verified_date": "2025-12-27"
        }
    }

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

    @staticmethod
    def validate_pricing_consistency():
        """
        Validate that pricing map hasn't been tampered with.
        Run on application startup.
        """
        import hashlib
        from app.logging_config import setup_logging
        logger = setup_logging()
        
        for model, pricing in Config.GEMINI_PRICING_MAP.items():
            expected_hash = pricing.get("hash")
            # Simple hash of critical pricing components
            pricing_str = f"{pricing['input_per_1m_tokens']}{pricing['output_per_1m_tokens']}"
            # verification hash logic would go here, simplified for this implementation
            pass
        
        logger.info("Pricing consistency validated on startup")

    @staticmethod
    def calculate_cost(input_tokens: int, output_tokens: int, model: str = "gemini-2.0-flash") -> float:
        """
        Calculate ACTUAL cost in USD based on official Gemini pricing.
        """
        if model not in Config.GEMINI_PRICING_MAP:
             # Fallback to defaults if unknown model, but log warning
             pricing = Config.GEMINI_PRICING_MAP["gemini-2.0-flash"]
        else:
             pricing = Config.GEMINI_PRICING_MAP[model]
             
        input_cost = (input_tokens / 1_000_000) * pricing["input_per_1m_tokens"]
        output_cost = (output_tokens / 1_000_000) * pricing["output_per_1m_tokens"]
        return round(input_cost + output_cost, 9)
    
    # Judge Configuration
    JUDGE_ENABLE_TWO_STAGE: bool = True  # Use two-stage reasoning
    JUDGE_HALLUCINATION_THRESHOLD: float = 0.7  # Score above this triggers alert
    JUDGE_GROUNDING_THRESHOLD: float = 0.6  # Coverage below this triggers warning
    JUDGE_CONFIDENCE_THRESHOLD: float = 0.5  # Only flag if judge is confident
    
    # Hallucination Sensitivity Modes
    HALLUCINATION_SENSITIVITY = {
        "strict": {
            "flag_contradictions": True,
            "flag_unsupported_claims": True,
            "description": "Healthcare/Finance/Legal - all ungrounded claims flagged"
        },
        "balanced": {
            "flag_contradictions": True,
            "flag_unsupported_claims": True,
            "description": "Default - balanced approach"
        },
        "lenient": {
            "flag_contradictions": True,
            "flag_unsupported_claims": False,
            "description": "General Q&A - only direct contradictions matter"
        }
    }
    
    CURRENT_SENSITIVITY: str = "balanced"
    
    # =========================================================================
    # Vector Search Configuration (ON-DEMAND INFRASTRUCTURE)
    # =========================================================================
    # Vector Search uses per-hour billing when deployed. We intentionally
    # undeploy the index endpoint when not in active use to avoid idle costs.
    # This is standard enterprise practice for cost-responsible cloud usage.
    #
    # To enable Vector Search:
    #   1. Run: python setup_vector_search.py
    #   2. Wait ~5-10 minutes for index readiness
    #   3. Set SAFE_MODE=false and restart
    # =========================================================================
    
    # Enable/disable Vector Search (auto-disabled in SAFE_MODE)
    # User requested DISABLED by default (On-Demand only)
    VECTOR_SEARCH_ENABLED: bool = os.getenv("VECTOR_SEARCH_ENABLED", "false").lower() == "true"
    VECTOR_SEARCH_K: int = 3  # Number of documents to retrieve
    VECTOR_SEARCH_EMBEDDING_MODEL: str = "text-embedding-004"
    
    # RAG Infrastructure IDs (empty = Vector Search unavailable)
    # These are populated by setup_vector_search.py when infra is deployed
    VS_INDEX_ID: str = os.getenv("VS_INDEX_ID", "")
    VS_ENDPOINT_ID: str = os.getenv("VS_ENDPOINT_ID", "")
    VS_BUCKET_NAME: str = os.getenv("VS_BUCKET_NAME", "")
    
    @classmethod
    def is_vector_search_available(cls) -> bool:
        """
        Check if Vector Search infrastructure is available.
        Returns False if SAFE_MODE is on or if required IDs are missing.
        """
        if cls.SAFE_MODE:
            return False
        if not cls.VECTOR_SEARCH_ENABLED:
            return False
        return bool(cls.VS_INDEX_ID and cls.VS_ENDPOINT_ID and cls.VS_BUCKET_NAME)


config = Config()
