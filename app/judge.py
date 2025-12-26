"""
LLM-as-a-Judge module for LLM Incident Commander.
Handles async semantic evaluation of LLM responses.
"""
import json
import asyncio
from datadog import statsd
from ddtrace import tracer

from app.config import config
from app.logging_config import setup_logging
from app.evaluators import categorize_question_type

logger = setup_logging()

# LLM-as-a-Judge prompt for semantic hallucination detection
JUDGE_PROMPT = """You are an AI Quality Assurance Judge evaluating response accuracy.

Categorize hallucinations into distinct types:
1. **CONTRADICTION**: Response directly contradicts known facts or context
   Example: Known fact says "System is UP" → Response claims "System is DOWN"

2. **UNSUPPORTED**: Response makes claims with no evidence or basis
   Example: Claiming specific numbers or dates without any source

3. **UNCERTAINTY**: Response uses excessive hedging indicating guessing

USER QUESTION: "{question}"
AI RESPONSE: "{response}"

Evaluate the response and respond with ONLY this JSON structure:
{{
  "hallucination_score": <float 0.0-1.0, where 1.0 is complete fabrication>,
  "hallucination_type": "none" | "contradiction" | "unsupported" | "uncertainty",
  "has_uncertainty_phrases": <boolean>,
  "has_contradictions": <boolean>,
  "is_evasive": <boolean>,
  "reasoning": "<one sentence explanation>"
}}
"""


async def run_judge_evaluation(model, request_id: str, question: str, response: str):
    """
    Runs an async evaluation using a separate LLM call.
    Emits llm.judge.* metrics to Datadog.
    
    Args:
        model: The GenerativeModel instance
        request_id: Unique request identifier
        question: Original user question
        response: LLM-generated response to evaluate
    """
    try:
        logger.info(f"Starting judge evaluation for request {request_id}")
        
        # Format and estimate tokens
        judge_input_text = JUDGE_PROMPT.format(question=question, response=response)
        input_tokens = config.estimate_tokens(judge_input_text)
        
        judge_response = await model.generate_content_async(
            judge_input_text,
            generation_config={"temperature": 0.0, "response_mime_type": "application/json"}
        )
        
        # Parse JSON
        try:
            eval_data = json.loads(judge_response.text)
            
            # Extract metrics (enhanced with hallucination_type)
            score = float(eval_data.get("hallucination_score", 0.0))
            hallucination_type = eval_data.get("hallucination_type", "none")
            has_uncertainty = eval_data.get("has_uncertainty_phrases", False)
            has_contradictions = eval_data.get("has_contradictions", False)
            is_evasive = eval_data.get("is_evasive", False)
            reasoning = eval_data.get("reasoning", "No reasoning provided")
            
            # Calculate faithfulness score (inverse of hallucination)
            faithfulness_score = 1.0 - score
            
            # Categorize question for pattern analysis
            question_pattern = categorize_question_type(question)
            
            # Estimate token usage and calculate cost
            output_tokens = config.estimate_tokens(judge_response.text)
            total_tokens = input_tokens + output_tokens
            judge_cost = config.calculate_cost(input_tokens, output_tokens)
            
            # Emit metrics to Datadog
            statsd.gauge(
                "llm.judge.hallucination_score", 
                score, 
                tags=[
                    f"request_id:{request_id}", 
                    f"hallucination_type:{hallucination_type}",
                    "model:gemini-2.0-flash", 
                    "role:judge"
                ]
            )
            
            # Faithfulness metric (positive framing)
            statsd.gauge(
                "llm.faithfulness_score",
                faithfulness_score,
                tags=[f"request_id:{request_id}", f"pattern:{question_pattern}"]
            )
            
            # Pattern analysis: Track hallucinations by question type
            statsd.increment(
                "llm.hallucination.by_pattern",
                tags=[
                    f"pattern:{question_pattern}", 
                    f"hallucination_type:{hallucination_type}",
                    f"score_bucket:{'high' if score >= 0.7 else 'medium' if score >= 0.4 else 'low'}"
                ]
            )
            
            statsd.gauge(
                "llm.judge.cost.usd",
                judge_cost,
                tags=["model:gemini-2.0-flash", "role:judge"]
            )
            
            statsd.gauge(
                "llm.judge.tokens.total",
                total_tokens,
                tags=["model:gemini-2.0-flash", "role:judge"]
            )
            
            # Track high risk with type attribution
            if score >= 0.7:
                logger.warning(
                    "High hallucination risk detected by judge",
                    extra={
                        "request_id": request_id,
                        "judge_score": score,
                        "hallucination_type": hallucination_type,
                        "reasoning": reasoning,
                        "user_question": question[:200],
                        "llm_response": response[:200]
                    }
                )
                statsd.increment(
                    "llm.judge.high_risk_detected", 
                    tags=[
                        "model:gemini-2.0-flash", 
                        "severity:high",
                        f"hallucination_type:{hallucination_type}"
                    ]
                )
            
            logger.info(
                "Judge evaluation completed", 
                extra={
                    "request_id": request_id,
                    "judge_score": score,
                    "hallucination_type": hallucination_type,
                    "has_uncertainty": has_uncertainty,
                    "has_contradictions": has_contradictions,
                    "is_evasive": is_evasive,
                    "reasoning": reasoning,
                    "judge_cost_usd": judge_cost,
                    "judge_tokens": total_tokens
                }
            )
            
        except json.JSONDecodeError:
            logger.error(f"Judge returned invalid JSON for request {request_id}: {judge_response.text}")
            statsd.increment("llm.judge.errors", tags=["error_type:json_parse", "model:gemini-2.0-flash"])

    except Exception as e:
        logger.error(f"Judge evaluation failed for request {request_id}: {e}")
        statsd.increment("llm.judge.errors", tags=["error_type:unknown", "model:gemini-2.0-flash"])
