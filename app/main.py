"""
LLM Incident Commander - FastAPI Application Entry Point
"""
import time
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import vertexai
from vertexai.preview.generative_models import GenerativeModel

from app.config import config
from app.logging_config import setup_logging
from app.handlers import http_exception_handler
from app.routes import init_routes

# Initialize
logger = setup_logging()
vertexai.init(project=config.GCP_PROJECT_ID, location=config.GCP_LOCATION)
model = GenerativeModel(config.VERTEX_AI_MODEL)

logger.info("Application initialized", extra={"project_id": config.GCP_PROJECT_ID, "model": config.VERTEX_AI_MODEL})

BASE_DIR = Path(__file__).resolve().parent.parent
app_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management"""
    logger.info("Starting LLM Incident Commander")
    yield
    logger.info("Shutting down LLM Incident Commander")


# Create FastAPI app
app = FastAPI(title=config.APP_NAME, version=config.DD_VERSION, lifespan=lifespan)

# Static files & templates
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Register routes
router = init_routes(templates, model, app_start_time)
app.include_router(router)

# Register exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to all requests"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response