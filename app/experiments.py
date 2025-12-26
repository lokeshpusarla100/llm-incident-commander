"""
Experiments module for LLM Incident Commander.
Handles A/B testing and experiment variant assignment.
"""
import hashlib


# Experiment variants for A/B testing
EXPERIMENT_VARIANTS = {
    "control": {"temperature": 0.7, "system_prompt": ""},
    "variant_a": {"temperature": 0.3, "system_prompt": "Be concise and actionable."},
    "variant_b": {"temperature": 0.9, "system_prompt": "Be creative in troubleshooting."}
}


def get_experiment_variant(request_id: str) -> str:
    """Assign user to experiment variant based on request ID hash."""
    hash_val = int(hashlib.md5(request_id.encode()).hexdigest(), 16)
    bucket = hash_val % 100
    
    if bucket < 20:
        return "control"
    elif bucket < 60:
        return "variant_a"
    else:
        return "variant_b"
