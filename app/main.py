"""
LLM Incident Commander - FastAPI application with Vertex AI and Datadog observability
"""
import time
import uuid
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
    
    # Normalize score: 3+ red flags = maximum score
    score = min(1.0, hits / 3.0)
    return round(score, 3)


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
            test_response = model.generate_content(
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
    
    # Create custom span for the entire LLM operation
    with tracer.trace(
        "llm.generate_content",
        service=config.DD_SERVICE,
        resource=config.VERTEX_AI_MODEL
    ) as span:
        span.set_tag("request_id", request_id)
        span.set_tag("question_length", len(req.question))
        span.set_tag("model", config.VERTEX_AI_MODEL)
        
        # Estimate input tokens
        input_tokens = config.estimate_tokens(req.question)
        span.set_tag("input_tokens_estimated", input_tokens)
        
        try:
            # Generate content with timeout handling
            generation_config = {
                "temperature": req.temperature or config.LLM_TEMPERATURE,
                "max_output_tokens": req.max_tokens or config.LLM_MAX_OUTPUT_TOKENS,
            }
            
            with tracer.trace("llm.vertex_api_call", service=config.DD_SERVICE) as api_span:
                api_span.set_tag("temperature", generation_config["temperature"])
                api_span.set_tag("max_tokens", generation_config["max_output_tokens"])
                
                response = model.generate_content(
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
    
    # Add tags to span
    span.set_tag("latency_ms", latency_ms)
    span.set_tag("output_tokens_estimated", output_tokens)
    span.set_tag("total_tokens", total_tokens)
    span.set_tag("cost_usd", cost_usd)
    span.set_tag("hallucination_score", hallucination_score)
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