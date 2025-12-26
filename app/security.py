"""
Security module for LLM Incident Commander.
Handles prompt injection detection and PII leakage scanning.
"""
import re


def scan_for_prompt_injection(question: str) -> dict:
    """
    Detect potential prompt injection attacks.
    Returns risk score and detected patterns.
    """
    risk_score = 0.0
    patterns_detected = []
    
    # Pattern 1: Instruction override attempts
    override_patterns = [
        r"ignore (previous|all) instructions",
        r"disregard (the|your) (system|above) prompt",
        r"new instructions?:",
        r"you are now",
        r"forget (what|everything) (you|i) (told|said)"
    ]
    for pattern in override_patterns:
        if re.search(pattern, question.lower()):
            risk_score += 0.4
            patterns_detected.append(f"override_attempt: {pattern}")
    
    # Pattern 2: Role manipulation
    role_patterns = [
        r"you are (a|an) (hacker|attacker|villain)",
        r"act as (if )?you (are|were)",
        r"pretend (to be|you are)"
    ]
    for pattern in role_patterns:
        if re.search(pattern, question.lower()):
            risk_score += 0.3
            patterns_detected.append(f"role_manipulation: {pattern}")
    
    # Pattern 3: Excessive length (potential token stuffing)
    if len(question) > 2000:
        risk_score += 0.3
        patterns_detected.append(f"excessive_length: {len(question)} chars")
    
    return {
        "injection_risk_score": min(1.0, risk_score),
        "patterns_detected": patterns_detected,
        "is_suspicious": risk_score >= 0.5
    }


def scan_for_pii_leakage(response: str) -> dict:
    """Detect PII in LLM responses."""
    pii_found = []
    
    # Email addresses
    if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', response):
        pii_found.append("email")
    
    # Phone numbers (US format)
    if re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', response):
        pii_found.append("phone")
    
    # SSN pattern
    if re.search(r'\b\d{3}-\d{2}-\d{4}\b', response):
        pii_found.append("ssn")
    
    # Credit card (simple check)
    if re.search(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', response):
        pii_found.append("credit_card")
    
    return {
        "pii_types_found": pii_found,
        "has_pii": len(pii_found) > 0,
        "pii_count": len(pii_found)
    }
