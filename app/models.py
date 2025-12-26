"""
Pydantic models for LLM Incident Commander API.
"""
from typing import Optional
from pydantic import BaseModel, Field


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
