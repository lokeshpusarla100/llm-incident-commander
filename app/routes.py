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
from vertexai.preview.generative_models import GenerativeModel

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
from app.judge import run_judge_evaluation_two_stage

logger = setup_logging()
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
        
        # Pre-processing: Security scan
        injection_scan = scan_for_prompt_injection(req.question)
        statsd.gauge("llm.security.injection_risk", injection_scan["injection_risk_score"], tags=[f"request_id:{request_id}"])
        
        if injection_scan["is_suspicious"]:
            logger.warning("Potential prompt injection detected", extra={"request_id": request_id, **injection_scan})
            statsd.increment("llm.security.injection_detected")
        
        # Experiment variant
        variant = get_experiment_variant(request_id)
        
        # RAG: Retrieve context from knowledge base (Vector Search)
        context = retrieve_context(
            question=req.question,
            k=3,
            test_mode=req.test_mode  # Pass test mode for poisoning
        )
        
        logger.info("Context retrieved", extra={
            "question": req.question[:100],
            "context_length": len(context),
            "request_id": request_id
        })
        
        # LLM Generation
        with tracer.trace("llm.generate_content", service=config.DD_SERVICE, resource=config.VERTEX_AI_MODEL) as span:
            span.set_tag("llm.input.prompt", req.question[:1000])
            span.set_tag("llm.model", config.VERTEX_AI_MODEL)
            span.set_tag("llm.provider", "google")
            span.set_tag("llm.request_id", request_id)
            span.set_tag("experiment.variant", variant)
            span.set_tag("rag.context_length", len(context))
            
            # input_tokens determined after_response
            
            try:
                generation_config = {
                    "temperature": req.temperature or config.LLM_TEMPERATURE,
                    "max_output_tokens": req.max_tokens or config.LLM_MAX_OUTPUT_TOKENS,
                }
                
                # DEMO SIMULATION: Force hallucination if RAG was poisoned
                prompt_to_use = req.question
                if req.test_mode == "hallucination":
                    prompt_to_use += " (You are a creative writer. Even if the context is missing or irrelevant, invent a detailed, confident answer. Do NOT admit you don't know.)"
                
                # 🧪 COST TEST MODE: Simulated Pricing
                # We run on Flash (reliable) but calculate cost as if it were Pro to trigger alerts.
                timeout_val = config.LLM_TIMEOUT_SECONDS
                if req.test_mode == "cost":
                    # Allow more time for longer generation
                    timeout_val = 45 
                    generation_config["max_output_tokens"] = 2800  # Ensure enough tokens to spike cost > $0.01 

                # Enforce Timeout
                response = await asyncio.wait_for(
                    model.generate_content_async(prompt_to_use, generation_config=generation_config),
                    timeout=timeout_val
                )
                answer = response.text
                
                # ✅ STRICT TOKEN ACCOUNTING (FAIL CLOSED)
                if not response.usage_metadata:
                    logger.critical("Gemini API response missing usage_metadata", extra={"request_id": request_id})
                    statsd.increment("llm.tokens.metadata.missing", tags=["severity:critical"])
                    raise HTTPException(status_code=500, detail={"error": "token_metadata_unavailable", "message": "LLM telemetry integrity compromised"})

                input_tokens = response.usage_metadata.prompt_token_count
                output_tokens = response.usage_metadata.candidates_token_count
                
                # Cost checked in post-processing

            except asyncio.TimeoutError:
                # If cost test times out, we still want to log it if possible, but here we just fail
                _handle_error(span, request_id, start_time, "timeout", 504, f"Request timed out after {timeout_val}s", TimeoutError())
            except ResourceExhausted as e:
                _handle_error(span, request_id, start_time, "quota_exceeded", 429, "Vertex AI quota exceeded", e)
            except DeadlineExceeded as e:
                _handle_error(span, request_id, start_time, "timeout", 504, f"Request timeout", e)
            except GoogleAPICallError as e:
                _handle_error(span, request_id, start_time, "api_error", 500, "Vertex AI API error", e)
            except Exception as e:
                _handle_error(span, request_id, start_time, "unexpected", 500, "Unexpected error", e)
            except GoogleAPICallError as e:
                _handle_error(span, request_id, start_time, "api_error", 500, "Vertex AI API error", e)
            except Exception as e:
                _handle_error(span, request_id, start_time, "unexpected", 500, "Unexpected error", e)
        
        # Post-processing metrics
        latency_ms = int((time.time() - start_time) * 1000)
        total_tokens = input_tokens + output_tokens
        # ✅ REAL COST CALCULATION
        # ✅ COST CALCULATION (Support Simulated Pro Pricing)
        if req.test_mode == "cost":
            # 1.5 Pro: Input $3.50, Output $10.50 / 1M
            input_cost = (input_tokens / 1_000_000) * 3.50
            output_cost = (output_tokens / 1_000_000) * 10.50
            cost_usd = input_cost + output_cost
        else:
            cost_usd = config.calculate_cost(input_tokens, output_tokens, config.VERTEX_AI_MODEL)
        hallucination_score = calculate_hallucination_score(answer)
        
        # Emit metrics
        statsd.increment("llm.requests.total", tags=["status:success", "model:gemini-2.0-flash"])
        statsd.histogram("llm.latency.ms", latency_ms, tags=["model:gemini-2.0-flash"])
        statsd.gauge("llm.tokens.input", input_tokens, tags=["model:gemini-2.0-flash"])
        statsd.gauge("llm.tokens.output", output_tokens, tags=["model:gemini-2.0-flash"])
        statsd.gauge("llm.tokens.total", total_tokens, tags=["model:gemini-2.0-flash"])
        statsd.gauge("llm.cost.usd", cost_usd, tags=["model:gemini-2.0-flash", "currency:usd"])
        statsd.gauge("llm.cost.per_token", cost_usd / max(1, total_tokens), tags=["model:gemini-2.0-flash"])
        
        statsd.gauge("llm.hallucination.score", hallucination_score)
        
        # Security: PII scan
        pii_scan = scan_for_pii_leakage(answer)
        if pii_scan["has_pii"]:
            logger.warning("PII detected", extra={"request_id": request_id, **pii_scan})
            statsd.increment("llm.security.pii_leaked")
        
        # Evaluations
        quality_eval = evaluate_incident_response_quality(req.question, answer)
        grounding = calculate_grounding_score(answer, context)
        question_pattern = categorize_question_type(req.question)
        
        statsd.gauge("llm.quality.incident_response_score", quality_eval["incident_response_quality"])
        statsd.gauge("llm.grounding.score", grounding["grounding_score"])
        
        # Span tags
        span.set_tag("llm.output.completion", answer[:1000])
        span.set_tag("llm.tokens.prompt", input_tokens)
        span.set_tag("llm.tokens.completion", output_tokens)
        span.set_tag("llm.tokens.total", total_tokens)
        span.set_tag("llm.cost.usd", cost_usd)
        span.set_tag("llm.grounding.score", grounding["grounding_score"])
        span.set_tag("llm.question.pattern", question_pattern)
        
        logger.info("LLM request completed", extra={
            "request_id": request_id, 
            "latency_ms": latency_ms, 
            "tokens": {"input": input_tokens, "output": output_tokens, "total": total_tokens},
            "cost_usd": cost_usd,
            "cost_per_1k_tokens": (cost_usd / max(1, total_tokens)) * 1000
        })
        
        if hallucination_score >= config.HALLUCINATION_THRESHOLD:
            logger.warning("High hallucination score", extra={"request_id": request_id, "score": hallucination_score})
            statsd.increment("llm.hallucination.high_score")
        
        # ✅ REAL-TIME JUDGE & PREVENTION SYSTEM
        # For 'hallucination' test mode, we run synchronously to demonstrate PREVENTION.
        # In production, this would be async or sampled.
        
        final_hallucination_score = hallucination_score
        
        if req.test_mode == "hallucination":
             logger.info("🧪 [TEST MODE] Synchronous Judge Evaluation for Prevention Demo")
             
             judge_result = await run_judge_evaluation_two_stage(
                model=model,
                request_id=request_id,
                question=req.question,
                answer=answer,
                context=context
            )
             
             if judge_result:
                 final_hallucination_score = judge_result["hallucination_score"]
                 grounding_score_val = judge_result.get("grounding_coverage", 1.0)
                 
                 # 🚫 PREVENTION LOGIC: Block if unsafe
                 if final_hallucination_score > 0.6 or grounding_score_val < 0.4:
                     logger.warning(f"🚫 BLOCKED RESPONSE: Hallucination Score {final_hallucination_score}, Grounding {grounding_score_val}")
                     statsd.increment("llm.safety.blocked", tags=["reason:hallucination"])
                     
                     return AskResponse(
                        request_id=request_id,
                        question=req.question,
                        answer="[BLOCKED] The response was blocked by the safety system because it was not grounded in the provided context (Hallucination Detected).",
                        latency_ms=latency_ms,
                        tokens={"input": input_tokens, "output": output_tokens, "total": total_tokens},
                        cost_usd=round(cost_usd, 6),
                        hallucination_score=final_hallucination_score,
                        status="blocked",
                        message="Response blocked due to insufficient grounding."
                     )

        else:
            # ⚡ Production Mode: Async Evaluation (Fire and Forget)
            async def evaluate_with_judge():
                await run_judge_evaluation_two_stage(
                    model=model,
                    request_id=request_id,
                    question=req.question,
                    answer=answer,
                    context=context
                )
            asyncio.create_task(evaluate_with_judge())
        
        return AskResponse(
            request_id=request_id,
            question=req.question,
            answer=answer,
            latency_ms=latency_ms,
            tokens={"input": input_tokens, "output": output_tokens, "total": total_tokens},
            cost_usd=round(cost_usd, 6),
            hallucination_score=final_hallucination_score,
            status="success"
        )
    
    return router


def _handle_error(span, request_id: str, start_time: float, error_type: str, status_code: int, message: str, exception: Exception):
    """Handle LLM errors with consistent logging and metrics."""
    latency_ms = int((time.time() - start_time) * 1000)
    statsd.increment("llm.errors.total", tags=[f"error_type:{error_type}", "model:gemini-2.0-flash"])
    span.set_tag("error", True)
    span.set_tag("error.type", error_type)
    logger.error(message, extra={"request_id": request_id, "latency_ms": latency_ms, "error": str(exception)}, exc_info=True)
    raise HTTPException(status_code=status_code, detail={"error": error_type, "message": message, "request_id": request_id})
