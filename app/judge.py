"""
LLM-as-a-Judge for Semantic Hallucination Detection.
Implements Datadog's rubric-based approach with contradiction vs unsupported classification.
"""
import asyncio
import json
from app.config import config
from app.logging_config import setup_logging
from datadog import statsd

logger = setup_logging()

# Simplified rubric-based judge prompt (single stage for reliability)
JUDGE_PROMPT = """You are an AI Quality Assurance Judge evaluating if a response is grounded in context.

CONTEXT (Retrieved from Vertex AI Vector Search):
{context}

USER QUESTION: {question}
AI RESPONSE: {response}

Evaluate the response and classify any issues:
1. **CONTRADICTION**: Response directly contradicts the context
2. **UNSUPPORTED**: Response makes claims not covered by context
3. **AGREEMENT**: Response is grounded in context

Respond with ONLY this JSON structure:
{{
  "hallucination_score": <0.0-1.0, where 1.0 is complete fabrication>,
  "grounding_coverage": <0.0-1.0, percentage of claims backed by context>,
  "hallucination_type": "none" | "contradiction" | "unsupported" | "mixed",
  "contradictions": <count of contradictions>,
  "unsupported_claims": <count of unsupported claims>,
  "is_faithful": <true if hallucination_score < 0.3>,
  "reasoning": "<one paragraph summary>"
}}"""


async def run_judge_evaluation_two_stage(
    model,
    request_id: str,
    question: str,
    answer: str,
    context: str = ""
):
    """
    LLM-as-a-Judge with Datadog's rubric-based approach.
    Uses single-stage for reliability with JSON mime type enforcement.
    """
    try:
        # Use default context if empty
        if not context or context.strip() == "":
            context = "No specific context provided. Evaluate based on factual accuracy."
        
        prompt = JUDGE_PROMPT.format(
            context=context[:2000],
            response=answer[:2000],
            question=question[:500]
        )
        
        
        
        # Use native async call for better performance and style
        judge_response = await model.generate_content_async(
            prompt,
            generation_config={
                "temperature": 0.0,
                "response_mime_type": "application/json",
                "max_output_tokens": 512
            }
        )
        
        # ✅ REAL TOKEN ACCOUNTING FOR JUDGE
        if not hasattr(judge_response, 'usage_metadata') or not judge_response.usage_metadata:
             logger.error("Judge API response missing usage_metadata", extra={"request_id": request_id})
             statsd.increment("llm.judge.tokens.metadata.missing")
             return None
             
        input_tokens = judge_response.usage_metadata.prompt_token_count
        output_tokens = judge_response.usage_metadata.candidates_token_count
        
        # Parse JSON response
        try:
            eval_data = json.loads(judge_response.text)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            text = judge_response.text
            if "{" in text and "}" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                eval_data = json.loads(text[start:end])
            else:
                raise
        
        # Extract metrics
        hallucination_score = float(eval_data.get("hallucination_score", 0.0))
        grounding_coverage = float(eval_data.get("grounding_coverage", 1.0))
        hallucination_type = eval_data.get("hallucination_type", "none")
        is_faithful = eval_data.get("is_faithful", True)
        contradictions = int(eval_data.get("contradictions", 0))
        unsupported = int(eval_data.get("unsupported_claims", 0))
        reasoning = eval_data.get("reasoning", "")
        
        # Calculate cost
        total_tokens = input_tokens + output_tokens
        judge_cost = config.calculate_cost(input_tokens, output_tokens)
        
        # Emit Datadog metrics
        statsd.gauge("llm.judge.hallucination_score", hallucination_score,
            tags=[f"request_id:{request_id}", "model:gemini-2.0-flash", "role:judge", f"is_faithful:{is_faithful}"])
        
        statsd.gauge("llm.judge.grounding_coverage", grounding_coverage,
            tags=[f"request_id:{request_id}", "model:gemini-2.0-flash"])
        
        statsd.gauge("llm.judge.contradictions", contradictions, tags=[f"request_id:{request_id}"])
        statsd.gauge("llm.judge.unsupported_claims", unsupported, tags=[f"request_id:{request_id}"])
        statsd.gauge("llm.judge.cost.usd", judge_cost, tags=["model:gemini-2.0-flash", "role:judge"])
        statsd.gauge("llm.judge.tokens.total", total_tokens, tags=["model:gemini-2.0-flash"])
        
        # Calculate faithfulness score (inverse)
        faithfulness_score = 1.0 - hallucination_score
        statsd.gauge("llm.faithfulness_score", faithfulness_score, tags=[f"request_id:{request_id}"])
        
        # Log results
        logger.info("Judge evaluation completed (rubric-based)", extra={
            "request_id": request_id,
            "hallucination_score": hallucination_score,
            "grounding_coverage": grounding_coverage,
            "hallucination_type": hallucination_type,
            "is_faithful": is_faithful,
            "contradictions": contradictions,
            "unsupported_claims": unsupported,
            "judge_cost_usd": round(judge_cost, 6),
            "reasoning": reasoning[:200]
        })
        
        # High risk detection
        if hallucination_score >= 0.7:
            logger.warning("High hallucination risk detected", extra={
                "request_id": request_id,
                "hallucination_score": hallucination_score,
                "hallucination_type": hallucination_type,
                "reasoning": reasoning
            })
            statsd.increment("llm.judge.high_risk_detected", tags=["model:gemini-2.0-flash", "severity:high"])
        
        # Low grounding warning
        if grounding_coverage < 0.6:
            logger.warning("Low grounding coverage detected", extra={
                "request_id": request_id,
                "grounding_coverage": grounding_coverage
            })
            statsd.increment("llm.judge.low_grounding", tags=["model:gemini-2.0-flash"])
        
        return {
            "hallucination_score": hallucination_score,
            "grounding_coverage": grounding_coverage,
            "hallucination_type": hallucination_type,
            "is_faithful": is_faithful,
            "contradictions": contradictions,
            "unsupported_claims": unsupported,
            "cost_usd": judge_cost,
            "tokens": total_tokens
        }
    
    except json.JSONDecodeError as e:
        logger.error("Judge returned invalid JSON", extra={"request_id": request_id, "error": str(e)})
        statsd.increment("llm.judge.errors", tags=["error_type:json_parse", "model:gemini-2.0-flash"])
        return None
    
    except Exception as e:
        logger.error("Judge evaluation failed", extra={"request_id": request_id, "error": str(e)}, exc_info=True)
        statsd.increment("llm.judge.errors", tags=["error_type:unknown", "model:gemini-2.0-flash"])
        return None
