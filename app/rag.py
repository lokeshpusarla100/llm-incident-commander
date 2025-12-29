import os
import time
import asyncio
from typing import Optional
from dataclasses import dataclass
from langchain_google_vertexai import VertexAIEmbeddings
from langchain_google_vertexai import VectorSearchVectorStore
from google.cloud import aiplatform
from app.logging_config import setup_logging
from app.config import config
from datadog import statsd

logger = setup_logging()


@dataclass
class RagResult:
    """
    Result from RAG retrieval with similarity scores for cost-safe gating.
    
    method values:
      - "vector_search": Retrieved from Vertex AI Vector Search
      - "fallback": Local keyword matching (Vector Search unavailable)
      - "disabled": RAG is explicitly disabled (SAFE_MODE or no infra)
      - "test_mode": Test/demo mode
    """
    context: str  # Formatted context for LLM prompt or direct response
    best_score: float  # Highest similarity score (used for LLM gating)
    avg_score: float  # Average similarity score
    docs_retrieved: int  # Number of documents retrieved
    method: str  # "vector_search" | "fallback" | "disabled" | "test_mode"
    disabled_reason: str = ""  # Why RAG is disabled (if method="disabled")
    
    def is_high_confidence(self, threshold: float = 0.7) -> bool:
        """Check if best_score meets threshold for direct response (no LLM needed)."""
        return self.best_score >= threshold
    
    @property
    def is_disabled(self) -> bool:
        """Check if RAG retrieval is disabled."""
        return self.method == "disabled"


# Global vector store (lazy loaded)
_vector_store = None

def get_vector_store():
    """Lazy load vector store"""
    global _vector_store
    
    if _vector_store is not None:
        return _vector_store

    if not config.VECTOR_SEARCH_ENABLED:
        logger.warning("Vector Search disabled via config")
        return None

    try:
        logger.info("Initializing Vertex AI Vector Search (once)")
        
        if not config.GCP_PROJECT_ID:
            logger.warning("GCP_PROJECT_ID not set, skipping Vector Search initialization")
            return None

        # Initialize Vertex AI
        aiplatform.init(project=config.GCP_PROJECT_ID, location=config.GCP_LOCATION)
        
        # Initialize embeddings model
        embeddings = VertexAIEmbeddings(
            model_name="text-embedding-004",
            project=config.GCP_PROJECT_ID
        )
        
        # Check if vector search env vars are present
        if not all([config.VS_INDEX_ID, config.VS_ENDPOINT_ID, config.VS_BUCKET_NAME]):
            logger.warning("Vector Search environment variables missing. Using fallback/empty context.")
            return None

        # Load vector store from existing index
        # This call can block, so we might want to be careful, but lazy loading helps.
        _vector_store = VectorSearchVectorStore.from_components(
            project_id=config.GCP_PROJECT_ID,
            region=config.GCP_LOCATION,
            gcs_bucket_name=config.VS_BUCKET_NAME,
            index_id=config.VS_INDEX_ID,
            endpoint_id=config.VS_ENDPOINT_ID,
            embedding=embeddings,
            stream_update=True,  # Must match Index configuration
            private_service_connect_ip_address=None,  # Use public endpoint for local dev
        )
        
        logger.info("✓ Vector Search loaded successfully")
        return _vector_store
        
    except Exception as e:
        logger.error(f"Failed to initialize Vector Search: {e}")
        return None

async def retrieve_context(question: str, k: int = 3, test_mode: str = None) -> RagResult:
    """
    Retrieve relevant context from Vector Search using semantic similarity.
    Returns RagResult with similarity scores for cost-safe LLM gating.
    
    SAFE_MODE behavior:
      - If SAFE_MODE=true or Vector Search is not deployed, returns a "disabled" result
      - The caller should check rag_result.is_disabled and respond accordingly
      - NO automatic LLM fallback - cost safety is explicit
    
    The caller should use rag_result.is_high_confidence(threshold) to decide
    whether to return the RAG context directly or invoke the LLM.
    """
    start_time = time.time()
    
    # =========================================================================
    # SAFE_MODE CHECK: Explicit disabled state when infra is not available
    # =========================================================================
    if config.SAFE_MODE:
        logger.info("SAFE_MODE enabled - Vector Search disabled to prevent costs")
        statsd.increment("llm.rag.disabled", tags=["reason:safe_mode"])
        return RagResult(
            context="",
            best_score=0.0,
            avg_score=0.0,
            docs_retrieved=0,
            method="disabled",
            disabled_reason="SAFE_MODE is enabled. Vector Search infrastructure is not deployed to prevent costs. See README for on-demand setup."
        )
    
    # Check if Vector Search infrastructure is available
    if not config.is_vector_search_available():
        logger.warning("Vector Search infrastructure not available (endpoint undeployed)")
        statsd.increment("llm.rag.disabled", tags=["reason:infra_unavailable"])
        return RagResult(
            context="",
            best_score=0.0,
            avg_score=0.0,
            docs_retrieved=0,
            method="disabled",
            disabled_reason="Vector Search index/endpoint not deployed. Run setup_vector_search.py to provision on-demand infrastructure."
        )
    
    # RAG Poisoning Test Mode - return low confidence to trigger LLM
    if test_mode == "hallucination":
        logger.info(f"🧪 [TEST MODE] Injecting RAG Poison...")
        return RagResult(
            context="Context: This document describes how to bake a chocolate cake. (Irrelevant context)",
            best_score=0.0,  # Force LLM invocation for demo
            avg_score=0.0,
            docs_retrieved=1,
            method="test_mode"
        )

    try:
        vector_store = get_vector_store()
        
        if not vector_store:
            logger.info("Vector store not available, using fallback")
            statsd.increment("llm.rag.fallback", tags=["reason:unavailable"])
            return _retrieve_context_fallback(question)

        # Async retrieval with timeout - use similarity_search_with_score for scoring
        try:
            # similarity_search_with_score returns List[Tuple[Document, float]]
            docs_with_scores = await asyncio.wait_for(
                asyncio.to_thread(vector_store.similarity_search_with_score, question, k=k),
                timeout=10.0  # 10 second timeout for cold-start
            )
        except asyncio.TimeoutError:
            logger.warning("⏱️ Vector Search timeout (10s) - falling back")
            statsd.increment("llm.rag.fallback", tags=["reason:timeout"])
            return _retrieve_context_fallback(question)
        
        if not docs_with_scores:
            logger.info("No documents retrieved from vector search")
            statsd.increment("llm.rag.fallback", tags=["reason:no_results"])
            return _retrieve_context_fallback(question)
        
        # Extract scores - Note: Vertex AI returns distance (lower is better)
        # We convert to similarity (higher is better) by using 1 / (1 + distance)
        scores = []
        docs = []
        for doc, distance in docs_with_scores:
            # Convert distance to similarity score (0-1 range)
            similarity = 1.0 / (1.0 + distance) if distance >= 0 else 0.0
            scores.append(similarity)
            docs.append(doc)
        
        best_score = max(scores) if scores else 0.0
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        # Process results with scores for transparency
        context_parts = []
        for i, (doc, score) in enumerate(zip(docs, scores)):
            context_parts.append(f"[Source {i+1}] (confidence: {score:.2f})\n{doc.page_content}")
        context = "\n\n---\n\n".join(context_parts)
        
        retrieval_latency = (time.time() - start_time) * 1000
        
        # Metrics - include score information
        statsd.increment("llm.rag.success", tags=["method:vector_search"])
        statsd.histogram("llm.retrieval.latency.ms", retrieval_latency, tags=["method:vector_search"])
        statsd.gauge("llm.retrieval.docs_retrieved", len(docs), tags=["method:vector_search"])
        statsd.gauge("llm.rag.best_score", best_score, tags=["method:vector_search"])
        statsd.gauge("llm.rag.avg_score", avg_score, tags=["method:vector_search"])
        
        # Log score details for debugging
        logger.info(f"RAG retrieval complete", extra={
            "docs_retrieved": len(docs),
            "best_score": round(best_score, 3),
            "avg_score": round(avg_score, 3),
            "latency_ms": round(retrieval_latency, 2),
            "threshold": config.LLM_SIMILARITY_THRESHOLD
        })
        
        return RagResult(
            context=context,
            best_score=best_score,
            avg_score=avg_score,
            docs_retrieved=len(docs),
            method="vector_search"
        )
    
    except Exception as e:
        logger.error(f"Vector Search error: {e}")
        statsd.increment("llm.rag.fallback", tags=["reason:error"])
        return _retrieve_context_fallback(question)


def _retrieve_context_fallback(question: str) -> RagResult:
    """
    Fallback using local simple keyword matching.
    Returns RagResult with low confidence to potentially trigger LLM.
    """
    INCIDENT_KB = {
        "incident": """Incident is a detected service disruption requiring immediate attention. 
        Key actions: Assess severity, notify stakeholders, begin root cause analysis.""",
        "latency": """Database latency is response time for database operations.
        High latency (>2s) triggers alerts. Common causes: connection pool exhaustion, slow queries, lock contention.""",
        "error": """Error handling follows fail-fast principles. 
        5xx errors trigger immediate alerting. 4xx errors logged for analysis.""",
        "cost": """Cost management for LLM operations uses token-based billing.
        Monitor input/output tokens. Set rate limits to prevent runaway costs.""",
        "hallucination": """Hallucination in LLM outputs means generating content not grounded in provided context.
        Use Judge LLM evaluation to detect. Block responses with hallucination score > 0.6.""",
    }
    
    question_lower = question.lower()
    relevant_docs = []
    
    for keyword, doc in INCIDENT_KB.items():
        if keyword.lower() in question_lower:
            relevant_docs.append(doc.strip())
    
    if relevant_docs:
        context = "\n---\n".join(relevant_docs)
        # Fallback matches have moderate confidence
        return RagResult(
            context=context,
            best_score=0.5,  # Moderate - may or may not need LLM
            avg_score=0.5,
            docs_retrieved=len(relevant_docs),
            method="fallback"
        )
    else:
        # No match - low confidence, will likely need LLM if enabled
        return RagResult(
            context="",
            best_score=0.0,
            avg_score=0.0,
            docs_retrieved=0,
            method="fallback"
        )

