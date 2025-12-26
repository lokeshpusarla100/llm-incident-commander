"""
Evaluators module for LLM Incident Commander.
Handles hallucination scoring, quality evaluation, and grounding analysis.
"""
from app.config import config


def calculate_hallucination_score(text: str) -> float:
    """
    Calculate hallucination score based on uncertainty indicators.
    Score ranges from 0.0 (confident) to 1.0 (highly uncertain).
    """
    text_lower = text.lower()
    hits = sum(1 for flag in config.HALLUCINATION_RED_FLAGS if flag.lower() in text_lower)
    
    score = min(1.0, hits / 3.0)
    return round(score, 3)


def calculate_grounding_score(response: str, context: str) -> dict:
    """
    Calculate how much of the response is grounded in context.
    Uses simple substring matching for MVP (semantic similarity for production).
    """
    if not context or not response:
        return {"grounding_score": 0.0, "grounded_claims": 0, "total_claims": 0}
    
    # Break response into sentences
    response_sentences = [s.strip() for s in response.split('.') if s.strip()]
    grounded_sentences = 0
    
    for sentence in response_sentences:
        # Check if sentence has grounded words (>3 chars) in context
        sentence_words = [w.lower() for w in sentence.split() if len(w) > 3]
        if any(word in context.lower() for word in sentence_words):
            grounded_sentences += 1
    
    total = len(response_sentences) if response_sentences else 1
    grounding_ratio = grounded_sentences / total
    
    return {
        "grounding_score": round(grounding_ratio, 2),
        "grounded_claims": grounded_sentences,
        "total_claims": len(response_sentences)
    }


def evaluate_incident_response_quality(question: str, response: str) -> dict:
    """
    Custom evaluation for incident response quality.
    Checks if response contains key incident metadata.
    """
    score = 0.0
    reasons = []
    
    # Check 1: Response mentions incident ID
    if any(word in response.lower() for word in ["incident", "issue", "#"]):
        score += 0.33
    else:
        reasons.append("No incident reference")
    
    # Check 2: Response provides actionable steps
    action_words = ["restart", "check", "verify", "review", "analyze", "investigate", "monitor", "debug"]
    if any(word in response.lower() for word in action_words):
        score += 0.33
    else:
        reasons.append("No actionable steps")
    
    # Check 3: Response has sufficient detail (>50 words)
    word_count = len(response.split())
    if word_count >= 50:
        score += 0.34
    else:
        reasons.append(f"Too brief ({word_count} words)")
    
    return {
        "incident_response_quality": round(score, 2),
        "word_count": word_count,
        "has_incident_ref": score >= 0.33,
        "has_action_items": score >= 0.66,
        "reasons": reasons
    }


def categorize_question_type(question: str) -> str:
    """Categorize questions for pattern analysis of hallucination trends."""
    q_lower = question.lower()
    
    if any(word in q_lower for word in ["troubleshoot", "fix", "resolve", "debug"]):
        return "troubleshooting"
    elif any(word in q_lower for word in ["why", "explain", "reason"]):
        return "explanation"
    elif any(word in q_lower for word in ["how", "steps", "process"]):
        return "procedural"
    elif any(word in q_lower for word in ["what", "which", "who", "where"]):
        return "factual"
    elif any(word in q_lower for word in ["status", "check", "is it"]):
        return "status_check"
    else:
        return "general"
