"""
API Routes for LLM Incident Commander.
Cost-Safe Architecture: Vector search is the default response path.
LLM generation only when explicitly needed.
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
from app.rag import retrieve_context, RagResult
from app.judge import run_judge_evaluation_two_stage
from app.rate_limiter import get_rate_limiter

logger = setup_logging()
router = APIRouter()


def init_routes(templates: Jinja2Templates, model, app_start_time: float):
    """Initialize routes with dependencies."""
    
    # Initialize rate limiter for LLM calls
    rate_limiter = get_rate_limiter(config.LLM_RATE_LIMIT_PER_HOUR)
    
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
        """
        Cost-Safe LLM Query Endpoint.
        
        DEFAULT: Returns vector search results directly (no LLM cost).
        LLM invoked ONLY when:
          - Similarity score < threshold, AND
          - ENABLE_LLM_GENERATION=true, AND
          - Rate limit not exceeded, AND
          - Not at panic threshold (90%)
        OR when:
          - needs_reasoning=true explicitly requested
          - test_mode is set for demo purposes
        """
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        start_time = time.time()
        
        logger.info("Request received", extra={
            "request_id": request_id, 
            "question_length": len(req.question),
            "llm_enabled": config.ENABLE_LLM_GENERATION,
            "needs_reasoning": req.needs_reasoning
        })
        
        # Pre-processing: Security scan
        injection_scan = scan_for_prompt_injection(req.question)
        statsd.gauge("llm.security.injection_risk", injection_scan["injection_risk_score"], tags=[f"request_id:{request_id}"])
        
        if injection_scan["is_suspicious"]:
            logger.warning("Potential prompt injection detected", extra={"request_id": request_id, **injection_scan})
            statsd.increment("llm.security.injection_detected")
        
        # Experiment variant
        variant = get_experiment_variant(request_id)
        
        # =========================================================================
        # STEP 1: RAG Retrieval (Always runs - this is the cost-safe default)
        # =========================================================================
        rag_result: RagResult = await retrieve_context(
            question=req.question,
            k=3,
            test_mode=req.test_mode
        )
        
        logger.info("RAG retrieval complete", extra={
            "request_id": request_id,
            "best_score": round(rag_result.best_score, 3),
            "docs_retrieved": rag_result.docs_retrieved,
            "method": rag_result.method
        })
        
        # =========================================================================
        # STEP 1.5: Handle RAG Disabled State (SAFE_MODE / No Infrastructure)
        # =========================================================================
        if rag_result.is_disabled:
            # Check if we should proceed to LLM anyway ("Gemini-Only" mode)
            # This allows running without Vector Search infra but still using Gemini
            if config.ENABLE_LLM_GENERATION and not config.SAFE_MODE:
                logger.info("RAG disabled but LLM enabled - proceeding to generation without context", extra={
                    "request_id": request_id, 
                    "reason": rag_result.disabled_reason
                })
                # Do NOT return here - fall through to Step 2
            else:
                # Default safety: Block if RAG is disabled and LLM is not explicitly forced
                latency_ms = int((time.time() - start_time) * 1000)
                
                logger.info("RAG disabled - returning safe mode response", extra={
                    "request_id": request_id,
                    "reason": rag_result.disabled_reason,
                    "latency_ms": latency_ms
                })
                
                statsd.increment("llm.rag.response", tags=["source:disabled"])
                
                return AskResponse(
                    request_id=request_id,
                    question=req.question,
                    answer=f"Vector Search is currently disabled.\n\n{rag_result.disabled_reason}\n\nTo enable on-demand Vector Search infrastructure, see the README.",
                    latency_ms=latency_ms,
                    tokens={"input": 0, "output": 0, "total": 0},
                    cost_usd=0.0,
                    hallucination_score=0.0,
                    status="rag_disabled",
                    message="Vector Search disabled. No LLM costs incurred.",
                    source="disabled",
                    llm_invocation_reason=None
                )
        
        # =========================================================================
        # STEP 2: Determine if LLM generation is needed
        # =========================================================================
        should_invoke_llm = False
        llm_invocation_reason = None
        llm_skip_reason = None
        
        # Check explicit reasoning request
        if req.needs_reasoning:
            should_invoke_llm = True
            llm_invocation_reason = "explicit_request"
        
        # Check test modes (hallucination/cost demos)
        elif req.test_mode in ["hallucination", "cost"]:
            should_invoke_llm = True
            llm_invocation_reason = f"test_mode:{req.test_mode}"
        
        # Check similarity threshold
        elif rag_result.best_score < config.LLM_SIMILARITY_THRESHOLD:
            should_invoke_llm = True
            llm_invocation_reason = f"low_similarity:{rag_result.best_score:.3f}"
        
        else:
            # High confidence RAG match - skip LLM
            llm_skip_reason = f"high_similarity:{rag_result.best_score:.3f}"
        
        # Apply guardrails if LLM would be invoked
        if should_invoke_llm:
            # Check if LLM generation is enabled
            if not config.ENABLE_LLM_GENERATION:
                should_invoke_llm = False
                llm_skip_reason = "llm_disabled"
                statsd.increment("llm.generation.skipped", tags=["reason:disabled"])
            
            # Check panic threshold (90% rate limit)
            elif rate_limiter.is_panic_threshold(config.LLM_PANIC_THRESHOLD):
                should_invoke_llm = False
                llm_skip_reason = "panic_threshold"
                statsd.increment("llm.generation.skipped", tags=["reason:panic_threshold"])
                logger.warning("🚨 LLM skipped due to panic threshold", extra={
                    "request_id": request_id,
                    "rate_limit_usage": rate_limiter.usage_percentage()
                })
            
            # Check rate limit
            elif not rate_limiter.is_allowed():
                should_invoke_llm = False
                llm_skip_reason = "rate_limited"
                statsd.increment("llm.generation.skipped", tags=["reason:rate_limited"])
                logger.warning("Rate limit exceeded for LLM generation", extra={
                    "request_id": request_id,
                    "rate_limit_usage": rate_limiter.usage_percentage()
                })
        
        # Emit rate limiter metrics
        rate_limiter.emit_metrics()
        
        # =========================================================================
        # STEP 3A: Vector-Search-Only Response (Cost-Safe Default)
        # =========================================================================
        if not should_invoke_llm:
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Format RAG context as the answer
            if rag_result.context:
                answer = f"Based on our knowledge base (confidence: {rag_result.best_score:.0%}):\n\n{rag_result.context}"
            else:
                answer = "No relevant information found in the knowledge base. Please refine your question or request LLM reasoning with needs_reasoning=true."
            
            # Emit metrics for vector-only response
            statsd.increment("llm.rag.response", tags=["source:vector_search"])
            if llm_skip_reason:
                statsd.increment("llm.generation.skipped", tags=[f"reason:{llm_skip_reason}"])
            
            logger.info("Returning vector-search-only response", extra={
                "request_id": request_id,
                "latency_ms": latency_ms,
                "skip_reason": llm_skip_reason,
                "best_score": rag_result.best_score
            })
            
            return AskResponse(
                request_id=request_id,
                question=req.question,
                answer=answer,
                latency_ms=latency_ms,
                tokens={"input": 0, "output": 0, "total": 0},
                cost_usd=0.0,
                hallucination_score=0.0,  # RAG responses are grounded by definition
                status="vector_only",
                message=f"Response from vector search. LLM skipped: {llm_skip_reason}" if llm_skip_reason else "High confidence match from knowledge base.",
                source="vector_search",
                llm_invocation_reason=None
            )
        
        # =========================================================================
        # STEP 3B: LLM Generation (Only when necessary)
        # =========================================================================
        logger.info("🔥 Invoking LLM generation", extra={
            "request_id": request_id,
            "reason": llm_invocation_reason,
            "rate_limit_usage": f"{rate_limiter.usage_percentage():.1%}"
        })
        
        # Emit LLM invocation metric with reason
        statsd.increment("llm.generation.invoked", tags=[f"reason:{llm_invocation_reason}"])
        statsd.increment("llm.rag.response", tags=["source:llm"])
        
        with tracer.trace("llm.generate_content", service=config.DD_SERVICE, resource=config.VERTEX_AI_MODEL) as span:
            span.set_tag("llm.input.prompt", req.question[:1000])
            span.set_tag("llm.model", config.VERTEX_AI_MODEL)
            span.set_tag("llm.provider", "google")
            span.set_tag("llm.request_id", request_id)
            span.set_tag("llm.invocation_reason", llm_invocation_reason)
            span.set_tag("experiment.variant", variant)
            span.set_tag("rag.context_length", len(rag_result.context))
            span.set_tag("rag.best_score", rag_result.best_score)
            
            try:
                # Apply hard token cap
                requested_tokens = req.max_tokens or config.LLM_MAX_OUTPUT_TOKENS
                max_tokens = min(requested_tokens, config.LLM_MAX_OUTPUT_TOKENS_CAP)
                
                generation_config = {
                    "temperature": req.temperature or config.LLM_TEMPERATURE,
                    "max_output_tokens": max_tokens,
                }
                
                # Build prompt with context
                prompt_to_use = f"""Context from knowledge base:
{rag_result.context}

User Question: {req.question}

Please provide a helpful response based on the context above."""
                
                # DEMO SIMULATION: Force hallucination if RAG was poisoned
                if req.test_mode == "hallucination":
                    prompt_to_use = req.question + " (You are a creative writer. Even if the context is missing or irrelevant, invent a detailed, confident answer. Do NOT admit you don't know.)"
                
                # 🧪 COST TEST MODE: Simulated Pricing
                timeout_val = config.LLM_TIMEOUT_SECONDS
                if req.test_mode == "cost":
                    timeout_val = 45
                    generation_config["max_output_tokens"] = min(2800, config.LLM_MAX_OUTPUT_TOKENS_CAP)

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

            except asyncio.TimeoutError:
                _handle_error(span, request_id, start_time, "timeout", 504, f"Request timed out after {timeout_val}s", TimeoutError())
            except ResourceExhausted as e:
                _handle_error(span, request_id, start_time, "quota_exceeded", 429, "Vertex AI quota exceeded", e)
            except DeadlineExceeded as e:
                _handle_error(span, request_id, start_time, "timeout", 504, f"Request timeout", e)
            except GoogleAPICallError as e:
                _handle_error(span, request_id, start_time, "api_error", 500, "Vertex AI API error", e)
            except Exception as e:
                _handle_error(span, request_id, start_time, "unexpected", 500, "Unexpected error", e)
        
        # Post-processing metrics
        latency_ms = int((time.time() - start_time) * 1000)
        total_tokens = input_tokens + output_tokens
        
        # Cost calculation
        if req.test_mode == "cost":
            input_cost = (input_tokens / 1_000_000) * 3.50
            output_cost = (output_tokens / 1_000_000) * 10.50
            cost_usd = input_cost + output_cost
        else:
            cost_usd = config.calculate_cost(input_tokens, output_tokens, config.VERTEX_AI_MODEL)
        
        hallucination_score = calculate_hallucination_score(answer)
        
        # Emit metrics
        latency_bucket = "under_2s" if latency_ms < 2000 else "over_2s"
        statsd.increment("llm.requests.total", tags=["status:success", "model:gemini-2.0-flash", f"latency_bucket:{latency_bucket}"])
        statsd.histogram("llm.latency.ms", latency_ms, tags=["model:gemini-2.0-flash", f"latency_bucket:{latency_bucket}"])
        statsd.gauge("llm.tokens.input", input_tokens, tags=["model:gemini-2.0-flash"])
        statsd.gauge("llm.tokens.output", output_tokens, tags=["model:gemini-2.0-flash"])
        statsd.gauge("llm.tokens.total", total_tokens, tags=["model:gemini-2.0-flash"])
        statsd.gauge("llm.cost.usd", cost_usd, tags=["model:gemini-2.0-flash", "currency:usd"])
        statsd.gauge("llm.cost.per_token", cost_usd / max(1, total_tokens), tags=["model:gemini-2.0-flash"])
        
        # Security: PII scan
        pii_scan = scan_for_pii_leakage(answer)
        if pii_scan["has_pii"]:
            logger.warning("PII detected", extra={"request_id": request_id, **pii_scan})
            statsd.increment("llm.security.pii_leaked")
        
        # Evaluations
        quality_eval = evaluate_incident_response_quality(req.question, answer)
        grounding = calculate_grounding_score(answer, rag_result.context)
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
            "invocation_reason": llm_invocation_reason
        })
        
        if hallucination_score >= config.HALLUCINATION_THRESHOLD:
            logger.warning("High hallucination score (heuristic)", extra={"request_id": request_id, "score": hallucination_score})
        
        # ✅ REAL-TIME JUDGE & PREVENTION SYSTEM
        final_hallucination_score = hallucination_score
        
        if req.test_mode == "hallucination":
            logger.info("🧪 [TEST MODE] Synchronous Judge Evaluation for Prevention Demo")
            
            judge_result = await run_judge_evaluation_two_stage(
                model=model,
                request_id=request_id,
                question=req.question,
                answer=answer,
                context=rag_result.context
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
                        message="Response blocked due to insufficient grounding.",
                        source="llm_generation",
                        llm_invocation_reason=llm_invocation_reason
                    )
        else:
            # ⚡ Production Mode: Async Evaluation (Fire and Forget)
            async def evaluate_with_judge():
                await run_judge_evaluation_two_stage(
                    model=model,
                    request_id=request_id,
                    question=req.question,
                    answer=answer,
                    context=rag_result.context
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
            status="success",
            source="llm_generation",
            llm_invocation_reason=llm_invocation_reason
        )
    
    return router


def _handle_error(span, request_id: str, start_time: float, error_type: str, status_code: int, message: str, exception: Exception):
    """Handle LLM errors with consistent logging and metrics."""
    latency_ms = int((time.time() - start_time) * 1000)
    latency_bucket = "under_2s" if latency_ms < 2000 else "over_2s"
    # ✅ ERROR-RATE SLO: Count errors as requests for correct SLO math
    statsd.increment("llm.requests.total", tags=["status:error", f"error_type:{error_type}", "model:gemini-2.0-flash", f"latency_bucket:{latency_bucket}"])
    statsd.increment("llm.errors.total", tags=[f"error_type:{error_type}", "model:gemini-2.0-flash"])
    span.set_tag("error", True)
    span.set_tag("error.type", error_type)
    logger.error(message, extra={"request_id": request_id, "latency_ms": latency_ms, "error": str(exception)}, exc_info=True)
    raise HTTPException(status_code=status_code, detail={"error": error_type, "message": message, "request_id": request_id})
