"""
API Routes for LLM Incident Commander.
"""
import time
import uuid
import asyncio

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datadog import statsd
from ddtrace import tracer
from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted, DeadlineExceeded

from app.config import config
from app.logging_config import setup_logging
from app.models import AskRequest, AskResponse, HealthResponse
from app.security import scan_for_prompt_injection, scan_for_pii_leakage
from app.evaluators import (
    calculate_hallucination_score,
    calculate_grounding_score,
    evaluate_incident_response_quality,
    categorize_question_type
)
from app.experiments import get_experiment_variant, EXPERIMENT_VARIANTS
from app.rag import retrieve_context
from app.judge import run_judge_evaluation

logger = setup_logging()

# Create router
router = APIRouter()


def init_routes(templates: Jinja2Templates, model, app_start_time: float):
    """Initialize routes with dependencies."""
    
    @router.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        """Serve the main web UI."""
        return templates.TemplateResponse("index.html", {"request": request})

    @router.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check with Vertex AI connectivity test."""
        uptime = int(time.time() - app_start_time)
        vertex_status = "unknown"
        
        try:
            with tracer.trace("health_check.vertex_ai_test", service=config.DD_SERVICE):
                test_response = await model.generate_content_async("ping", generation_config={"max_output_tokens": 5})
                if test_response.text:
                    vertex_status = "connected"
                    statsd.increment("app.health.vertex_ai.success")
        except Exception as e:
            vertex_status = f"error: {str(e)[:50]}"
            statsd.increment("app.health.vertex_ai.error")
            logger.warning(f"Vertex AI health check failed: {e}")
        
        statsd.gauge("app.uptime.seconds", uptime)
        statsd.increment("app.health.checks.total")
        
        return HealthResponse(
            status="healthy" if vertex_status == "connected" else "degraded",
            service=config.DD_SERVICE,
            version=config.DD_VERSION,
            vertex_ai=vertex_status,
            uptime_seconds=uptime
        )

    @router.post("/ask", response_model=AskResponse)
    async def ask(req: AskRequest, request: Request):
        """Send a question to the LLM with comprehensive telemetry."""
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        start_time = time.time()
        
        logger.info("LLM request received", extra={"request_id": request_id, "question_length": len(req.question)})
        
        # Pre-processing
        injection_scan = scan_for_prompt_injection(req.question)
        statsd.gauge("llm.security.injection_risk", injection_scan["injection_risk_score"], tags=[f"request_id:{request_id}"])
        
        if injection_scan["is_suspicious"]:
            logger.warning("Potential prompt injection detected", extra={"request_id": request_id, **injection_scan})
            statsd.increment("llm.security.injection_detected")
        
        variant = get_experiment_variant(request_id)
        context = retrieve_context(req.question)
        
        # LLM Generation
        with tracer.trace("llm.generate_content", service=config.DD_SERVICE, resource=config.VERTEX_AI_MODEL) as span:
            span.set_tag("llm.input.prompt", req.question[:1000])
            span.set_tag("llm.model", config.VERTEX_AI_MODEL)
            span.set_tag("llm.provider", "google")
            span.set_tag("llm.request_id", request_id)
            span.set_tag("experiment.variant", variant)
            
            input_tokens = config.estimate_tokens(req.question)
            
            try:
                generation_config = {
                    "temperature": req.temperature or config.LLM_TEMPERATURE,
                    "max_output_tokens": req.max_tokens or config.LLM_MAX_OUTPUT_TOKENS,
                }
                
                response = await model.generate_content_async(req.question, generation_config=generation_config)
                answer = response.text
                
            except ResourceExhausted as e:
                _handle_error(span, request_id, start_time, "quota_exceeded", 429, "Vertex AI quota exceeded", e)
            except DeadlineExceeded as e:
                _handle_error(span, request_id, start_time, "timeout", 504, f"Request exceeded {config.LLM_TIMEOUT_SECONDS}s timeout", e)
            except GoogleAPICallError as e:
                _handle_error(span, request_id, start_time, "api_error", 500, "Failed to communicate with Vertex AI", e)
            except Exception as e:
                _handle_error(span, request_id, start_time, "unexpected", 500, "An unexpected error occurred", e)
        
        # Post-processing
        latency_ms = int((time.time() - start_time) * 1000)
        output_tokens = config.estimate_tokens(answer)
        total_tokens = input_tokens + output_tokens
        cost_usd = config.calculate_cost(input_tokens, output_tokens)
        hallucination_score = calculate_hallucination_score(answer)
        
        # Emit metrics
        statsd.increment("llm.requests.total", tags=["status:success", "model:gemini-2.0-flash"])
        statsd.histogram("llm.latency.ms", latency_ms, tags=["model:gemini-2.0-flash"])
        statsd.gauge("llm.tokens.input", input_tokens)
        statsd.gauge("llm.tokens.output", output_tokens)
        statsd.gauge("llm.cost.usd", cost_usd)
        statsd.gauge("llm.hallucination.score", hallucination_score)
        
        # Evaluations
        pii_scan = scan_for_pii_leakage(answer)
        if pii_scan["has_pii"]:
            logger.warning("PII detected", extra={"request_id": request_id, **pii_scan})
            statsd.increment("llm.security.pii_leaked")
        
        quality_eval = evaluate_incident_response_quality(req.question, answer)
        grounding = calculate_grounding_score(answer, context)
        question_pattern = categorize_question_type(req.question)
        
        statsd.gauge("llm.quality.incident_response_score", quality_eval["incident_response_quality"])
        statsd.gauge("llm.grounding.score", grounding["grounding_score"])
        
        # Span tags
        span.set_tag("llm.output.completion", answer[:1000])
        span.set_tag("llm.tokens.total", total_tokens)
        span.set_tag("llm.cost.usd", cost_usd)
        span.set_tag("llm.grounding.score", grounding["grounding_score"])
        span.set_tag("llm.question.pattern", question_pattern)
        
        logger.info("LLM request completed", extra={"request_id": request_id, "latency_ms": latency_ms, "cost_usd": cost_usd})
        
        if hallucination_score >= config.HALLUCINATION_THRESHOLD:
            logger.warning("High hallucination score", extra={"request_id": request_id, "score": hallucination_score})
            statsd.increment("llm.hallucination.high_score")
        
        # Fire and forget: Judge evaluation
        asyncio.create_task(run_judge_evaluation(model, request_id, req.question, answer))
        
        return AskResponse(
            request_id=request_id,
            question=req.question,
            answer=answer,
            latency_ms=latency_ms,
            tokens={"input": input_tokens, "output": output_tokens, "total": total_tokens},
            cost_usd=round(cost_usd, 6),
            hallucination_score=hallucination_score
        )
    
    return router


def _handle_error(span, request_id: str, start_time: float, error_type: str, status_code: int, message: str, exception: Exception):
    """Handle LLM errors with consistent logging and metrics."""
    latency_ms = int((time.time() - start_time) * 1000)
    statsd.increment("llm.errors.total", tags=[f"error_type:{error_type}", "model:gemini-2.0-flash"])
    span.set_tag("error", True)
    span.set_tag("error.type", error_type)
    logger.error(message, extra={"request_id": request_id, "latency_ms": latency_ms, "error": str(exception)})
    raise HTTPException(status_code=status_code, detail={"error": error_type, "message": message, "request_id": request_id})
