"""
LLM Incident Commander - FastAPI application with Vertex AI and Datadog observability
"""
import time
import uuid
import asyncio
import json
import re
import hashlib
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from datadog import statsd
from ddtrace import tracer

import vertexai
from vertexai.preview.generative_models import GenerativeModel
from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted, DeadlineExceeded

from app.config import config
from app.logging_config import setup_logging

# Initialize structured logging
logger = setup_logging()

# Initialize Vertex AI
vertexai.init(project=config.GCP_PROJECT_ID, location=config.GCP_LOCATION)
model = GenerativeModel(config.VERTEX_AI_MODEL)

logger.info(
    "Application initialized",
    extra={
        "project_id": config.GCP_PROJECT_ID,
        "model": config.VERTEX_AI_MODEL,
        "location": config.GCP_LOCATION
    }
)

# Get base directory for static files and templates
BASE_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for the application"""
    logger.info("Starting LLM Incident Commander")
    yield
    logger.info("Shutting down LLM Incident Commander")


app = FastAPI(
    title=config.APP_NAME,
    version=config.DD_VERSION,
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Setup templates
templates = Jinja2Templates(directory=BASE_DIR / "templates")


class AskRequest(BaseModel):
    """Request model for LLM queries"""
    question: str = Field(..., min_length=1, max_length=5000, description="Question to ask the LLM")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Override default temperature")
    max_tokens: Optional[int] = Field(None, ge=1, le=8192, description="Override max output tokens")


class AskResponse(BaseModel):
    """Response model for LLM queries"""
    request_id: str
    question: str
    answer: str
    latency_ms: int
    tokens: dict
    cost_usd: float
    hallucination_score: float


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    version: str
    vertex_ai: str
    uptime_seconds: Optional[int] = None


# Track application start time for uptime
app_start_time = time.time()


# ============================================================================
# SECURITY SCANNING FUNCTIONS
# ============================================================================

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
    """Detect PII in LLM responses"""
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


# ============================================================================
# CUSTOM EVALUATION FUNCTIONS
# ============================================================================

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


# ============================================================================
# RAG PIPELINE PLACEHOLDER (Future-proofing)
# ============================================================================

def retrieve_context(question: str) -> str:
    """
    Placeholder for future RAG implementation.
    When implemented, this will retrieve relevant docs from vector DB.
    """
    with tracer.trace("llm.retrieval", service=config.DD_SERVICE) as span:
        span.set_tag("retrieval.query", question[:100])
        span.set_tag("retrieval.source", "none")  # Will be "pinecone" or "weaviate" later
        span.set_tag("retrieval.chunks", 0)
        return ""  # No context for now


# ============================================================================
# EXPERIMENT TRACKING
# ============================================================================

EXPERIMENT_VARIANTS = {
    "control": {"temperature": 0.7, "system_prompt": ""},
    "variant_a": {"temperature": 0.3, "system_prompt": "Be concise and actionable."},
    "variant_b": {"temperature": 0.9, "system_prompt": "Be creative in troubleshooting."}
}


def get_experiment_variant(request_id: str) -> str:
    """Assign user to experiment variant based on request ID hash"""
    hash_val = int(hashlib.md5(request_id.encode()).hexdigest(), 16)
    bucket = hash_val % 100
    
    if bucket < 20:
        return "control"
    elif bucket < 60:
        return "variant_a"
    else:
        return "variant_b"


# ============================================================================
# HALLUCINATION DETECTION (Legacy keyword-based)
# ============================================================================

def calculate_hallucination_score(text: str) -> float:
    """
    Calculate hallucination score based on uncertainty indicators.
    Score ranges from 0.0 (confident) to 1.0 (highly uncertain).
    
    Args:
        text: LLM response text
        
    Returns:
        Hallucination score (0.0 - 1.0)
    """
    text_lower = text.lower()
    hits = sum(1 for flag in config.HALLUCINATION_RED_FLAGS if flag.lower() in text_lower)
    
    score = min(1.0, hits / 3.0)
    return round(score, 3)


# LLM-as-a-Judge prompt for semantic hallucination detection
JUDGE_PROMPT = """You are an AI Quality Assurance Judge evaluating response accuracy.

USER QUESTION: "{question}"
AI RESPONSE: "{response}"

Evaluate the response for these issues:
1. **Hallucination**: Makes unfounded claims, cites non-existent facts, or provides information without basis
2. **Uncertainty**: Uses excessive hedging language indicating the model is guessing
3. **Evasiveness**: Avoids directly answering the question or gives overly generic responses
4. **Contradictions**: Contains logically inconsistent or self-contradicting statements

Scoring guidelines:
- 0.0-0.3: Confident, factual, directly answers question
- 0.4-0.6: Contains some hedging language but generally accurate
- 0.7-0.9: Significant uncertainty, evasiveness, or potential inaccuracies
- 1.0: Clear hallucination, completely fabricated information, or nonsensical response

Respond with ONLY this exact JSON structure (no markdown, no extra text):
{{
  "hallucination_score": <float between 0.0 and 1.0>,
  "has_uncertainty_phrases": <boolean>,
  "has_contradictions": <boolean>,
  "is_evasive": <boolean>,
  "reasoning": "<one sentence explanation of the score>"
}}
"""


async def run_judge_evaluation(request_id: str, question: str, response: str):
    """
    Runs an async evaluation using a separate LLM call.
    Emits the 'llm.judge.score' metric to Datadog.
    """
    try:
        # Create a new, separate generation request for the judge
        # Use a lower temperature for the judge to ensure consistency
        logger.info(f"Starting judge evaluation for request {request_id}")
        
        # Estimate input tokens for judge to track cost
        judge_input_text = JUDGE_PROMPT.format(question=question, response=response)
        input_tokens = config.estimate_tokens(judge_input_text)
        
        judge_response = await model.generate_content_async(
            judge_input_text,
            generation_config={"temperature": 0.0, "response_mime_type": "application/json"}
        )
        
        # Parse JSON
        try:
            eval_data = json.loads(judge_response.text)
            
            # Extract metrics
            score = float(eval_data.get("hallucination_score", 0.0))
            has_uncertainty = eval_data.get("has_uncertainty_phrases", False)
            has_contradictions = eval_data.get("has_contradictions", False)
            is_evasive = eval_data.get("is_evasive", False)
            reasoning = eval_data.get("reasoning", "No reasoning provided")
            
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
                    "model:gemini-2.0-flash", 
                    "role:judge"
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
            
            # Track high risk
            if score >= 0.7:
                logger.warning(
                    "High hallucination risk detected by judge",
                    extra={
                        "request_id": request_id,
                        "judge_score": score,
                        "reasoning": reasoning,
                        "user_question": question[:200],
                        "llm_response": response[:200]
                    }
                )
                statsd.increment(
                    "llm.judge.high_risk_detected", 
                    tags=["model:gemini-2.0-flash", "severity:high"]
                )
            
            logger.info(
                "Judge evaluation completed", 
                extra={
                    "request_id": request_id,
                    "judge_score": score,
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


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to all requests for tracing"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    return response


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Serve the main web UI for LLM Incident Commander.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint with Vertex AI connectivity test.
    Returns application status and dependency health.
    """
    uptime = int(time.time() - app_start_time)
    
    # Test Vertex AI connectivity with a simple request
    vertex_status = "unknown"
    try:
        # Quick test with minimal tokens
        with tracer.trace("health_check.vertex_ai_test", service=config.DD_SERVICE):
            test_response = await model.generate_content_async(
                "ping",
                generation_config={"max_output_tokens": 5}
            )
            if test_response.text:
                vertex_status = "connected"
                statsd.increment("app.health.vertex_ai.success")
    except Exception as e:
        vertex_status = f"error: {str(e)[:50]}"
        statsd.increment("app.health.vertex_ai.error")
        logger.warning(f"Vertex AI health check failed: {e}")
    
    # Send overall health metric
    statsd.gauge("app.uptime.seconds", uptime)
    statsd.increment("app.health.checks.total")
    
    return HealthResponse(
        status="healthy" if vertex_status == "connected" else "degraded",
        service=config.DD_SERVICE,
        version=config.DD_VERSION,
        vertex_ai=vertex_status,
        uptime_seconds=uptime
    )


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest, request: Request):
    """
    Send a question to the LLM and receive a response.
    Includes comprehensive telemetry for latency, tokens, cost, and quality.
    """
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    start_time = time.time()
    
    logger.info(
        "LLM request received",
        extra={
            "request_id": request_id,
            "question_length": len(req.question)
        }
    )
    
    # ========================================================================
    # PRE-PROCESSING: Security Scanning & Experiment Assignment
    # ========================================================================
    
    # Security: Scan for prompt injection attacks
    injection_scan = scan_for_prompt_injection(req.question)
    statsd.gauge(
        "llm.security.injection_risk",
        injection_scan["injection_risk_score"],
        tags=[f"request_id:{request_id}"]
    )
    
    if injection_scan["is_suspicious"]:
        logger.warning(
            "Potential prompt injection detected",
            extra={"request_id": request_id, **injection_scan}
        )
        statsd.increment("llm.security.injection_detected")
    
    # Experiment: Assign variant for A/B testing
    variant = get_experiment_variant(request_id)
    variant_config = EXPERIMENT_VARIANTS[variant]
    
    # RAG: Retrieve context (placeholder for future implementation)
    context = retrieve_context(req.question)
    
    # Create custom span for the entire LLM operation
    with tracer.trace(
        "llm.generate_content",
        service=config.DD_SERVICE,
        resource=config.VERTEX_AI_MODEL
    ) as span:
        # Enhanced prompt/response tracing (Datadog LLM Observability format)
        span.set_tag("llm.input.prompt", req.question[:1000])  # Truncate for storage
        span.set_tag("llm.input.temperature", req.temperature or config.LLM_TEMPERATURE)
        span.set_tag("llm.input.max_tokens", req.max_tokens or config.LLM_MAX_OUTPUT_TOKENS)
        span.set_tag("llm.model", config.VERTEX_AI_MODEL)
        span.set_tag("llm.provider", "google")
        span.set_tag("llm.request_id", request_id)
        span.set_tag("experiment.variant", variant)
        span.set_tag("security.injection_risk", injection_scan["injection_risk_score"])
        
        # Estimate input tokens
        input_tokens = config.estimate_tokens(req.question)
        
        try:
            # Generate content with timeout handling
            generation_config = {
                "temperature": req.temperature or config.LLM_TEMPERATURE,
                "max_output_tokens": req.max_tokens or config.LLM_MAX_OUTPUT_TOKENS,
            }
            
            with tracer.trace("llm.vertex_api_call", service=config.DD_SERVICE) as api_span:
                api_span.set_tag("temperature", generation_config["temperature"])
                api_span.set_tag("max_tokens", generation_config["max_output_tokens"])
                
                response = await model.generate_content_async(
                    req.question,
                    generation_config=generation_config
                )
                answer = response.text
                
        except ResourceExhausted as e:
            # Quota exceeded - critical error
            latency_ms = int((time.time() - start_time) * 1000)
            
            statsd.increment(
                "llm.errors.total",
                tags=["error_type:quota_exceeded", "model:gemini-2.0-flash"]
            )
            span.set_tag("error", True)
            span.set_tag("error.type", "quota_exceeded")
            
            logger.error(
                "Vertex AI quota exceeded",
                extra={
                    "request_id": request_id,
                    "latency_ms": latency_ms,
                    "error": str(e)
                }
            )
            
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "quota_exceeded",
                    "message": "Vertex AI quota exceeded. Please try again later.",
                    "request_id": request_id
                }
            )
            
        except DeadlineExceeded as e:
            # Timeout error
            latency_ms = int((time.time() - start_time) * 1000)
            
            statsd.increment(
                "llm.errors.total",
                tags=["error_type:timeout", "model:gemini-2.0-flash"]
            )
            span.set_tag("error", True)
            span.set_tag("error.type", "timeout")
            
            logger.error(
                "Vertex AI request timeout",
                extra={
                    "request_id": request_id,
                    "latency_ms": latency_ms,
                    "timeout_seconds": config.LLM_TIMEOUT_SECONDS
                }
            )
            
            raise HTTPException(
                status_code=504,
                detail={
                    "error": "timeout",
                    "message": f"Request exceeded {config.LLM_TIMEOUT_SECONDS}s timeout",
                    "request_id": request_id
                }
            )
            
        except GoogleAPICallError as e:
            # Generic API error
            latency_ms = int((time.time() - start_time) * 1000)
            
            statsd.increment(
                "llm.errors.total",
                tags=["error_type:api_error", "model:gemini-2.0-flash"]
            )
            span.set_tag("error", True)
            span.set_tag("error.type", "api_error")
            
            logger.error(
                "Vertex AI API error",
                extra={
                    "request_id": request_id,
                    "latency_ms": latency_ms,
                    "error": str(e)
                }
            )
            
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "api_error",
                    "message": "Failed to communicate with Vertex AI",
                    "request_id": request_id
                }
            )
        
        except Exception as e:
            # Unexpected error
            latency_ms = int((time.time() - start_time) * 1000)
            
            statsd.increment(
                "llm.errors.total",
                tags=["error_type:unexpected", "model:gemini-2.0-flash"]
            )
            span.set_tag("error", True)
            span.set_tag("error.type", "unexpected")
            
            logger.error(
                "Unexpected error in LLM request",
                extra={
                    "request_id": request_id,
                    "latency_ms": latency_ms,
                    "error": str(e)
                },
                exc_info=True
            )
            
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "unexpected_error",
                    "message": "An unexpected error occurred",
                    "request_id": request_id
                }
            )
    
    # Calculate metrics
    latency_ms = int((time.time() - start_time) * 1000)
    output_tokens = config.estimate_tokens(answer)
    total_tokens = input_tokens + output_tokens
    cost_usd = config.calculate_cost(input_tokens, output_tokens)
    hallucination_score = calculate_hallucination_score(answer)
    
    # Emit comprehensive metrics to Datadog
    statsd.increment("llm.requests.total", tags=["status:success", "model:gemini-2.0-flash"])
    statsd.histogram("llm.latency.ms", latency_ms, tags=["model:gemini-2.0-flash"])
    statsd.gauge("llm.tokens.input", input_tokens)
    statsd.gauge("llm.tokens.output", output_tokens)
    statsd.gauge("llm.tokens.total", total_tokens)
    statsd.gauge("llm.cost.usd", cost_usd)
    statsd.gauge("llm.hallucination.score", hallucination_score)
    
    # Advanced LLM-specific metrics
    token_efficiency = output_tokens / max(1, input_tokens)  # Output/input ratio
    statsd.gauge("llm.token_efficiency", token_efficiency)
    statsd.histogram("llm.response.length", len(answer))  # Response character count
    statsd.gauge("llm.prompt.complexity", len(req.question.split()))  # Word count
    
    # ========================================================================
    # POST-PROCESSING: Security, Quality Evaluation & Enhanced Tracing
    # ========================================================================
    
    # Security: Scan for PII leakage in response
    pii_scan = scan_for_pii_leakage(answer)
    if pii_scan["has_pii"]:
        logger.warning(
            "PII detected in LLM response",
            extra={"request_id": request_id, **pii_scan}
        )
        statsd.increment(
            "llm.security.pii_leaked",
            tags=[f"pii_type:{','.join(pii_scan['pii_types_found'])}"]
        )
    
    # Custom Evaluation: Incident response quality scoring
    quality_eval = evaluate_incident_response_quality(req.question, answer)
    statsd.gauge(
        "llm.quality.incident_response_score",
        quality_eval["incident_response_quality"],
        tags=[f"request_id:{request_id}", f"experiment_variant:{variant}"]
    )
    statsd.gauge(
        "llm.quality.word_count",
        quality_eval["word_count"],
        tags=[f"request_id:{request_id}"]
    )
    
    # Add enhanced output tags to span (Datadog LLM Observability format)
    span.set_tag("llm.output.completion", answer[:1000])  # Truncate for storage
    span.set_tag("llm.output.finish_reason", "stop")
    span.set_tag("llm.tokens.prompt", input_tokens)
    span.set_tag("llm.tokens.completion", output_tokens)
    span.set_tag("llm.tokens.total", total_tokens)
    span.set_tag("llm.cost.usd", cost_usd)
    span.set_tag("llm.latency.ms", latency_ms)
    span.set_tag("llm.quality.score", quality_eval["incident_response_quality"])
    span.set_tag("success", True)
    
    # Log successful request
    logger.info(
        "LLM request completed successfully",
        extra={
            "request_id": request_id,
            "latency_ms": latency_ms,
            "tokens": {
                "input": input_tokens,
                "output": output_tokens,
                "total": total_tokens
            },
            "cost_usd": cost_usd
        }
    )
    
    # Check if hallucination score exceeds threshold
    if hallucination_score >= config.HALLUCINATION_THRESHOLD:
        logger.warning(
            "High hallucination score detected",
            extra={
                "request_id": request_id,
                "hallucination_score": hallucination_score,
                "threshold": config.HALLUCINATION_THRESHOLD,
                "answer_preview": answer[:100]
            }
        )
        statsd.increment("llm.hallucination.high_score", tags=["model:gemini-2.0-flash"])
    
    # FIRE AND FORGET: Schedule the judge to run in the background
    # This ensures the user doesn't wait for the extra API call
    asyncio.create_task(
        run_judge_evaluation(request_id, req.question, answer)
    )
    
    return AskResponse(
        request_id=request_id,
        question=req.question,
        answer=answer,
        latency_ms=latency_ms,
        tokens={
            "input": input_tokens,
            "output": output_tokens,
            "total": total_tokens
        },
        cost_usd=round(cost_usd, 6),
        hallucination_score=hallucination_score
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom exception handler to ensure consistent error responses"""
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail if isinstance(exc.detail, dict) else {
            "error": "http_error",
            "message": str(exc.detail),
            "request_id": request_id
        }
    )