import os
import time
import asyncio
from typing import Optional
from langchain_google_vertexai import VertexAIEmbeddings
from langchain_google_vertexai import VectorSearchVectorStore
from google.cloud import aiplatform
from app.logging_config import setup_logging
from app.config import config
from datadog import statsd

logger = setup_logging()

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

async def retrieve_context(question: str, k: int = 3, test_mode: str = None) -> str:
    """
    Retrieve relevant context from Vector Search using semantic similarity.
    Async wrapper with timeout to prevent hanging.
    """
    start_time = time.time()
    
    # RAG Poisoning Test Mode
    if test_mode == "hallucination":
        logger.info(f"🧪 [TEST MODE] Injecting RAG Poison...")
        return "Context: This document describes how to bake a chocolate cake. (Irrelevant context)"

    try:
        vector_store = get_vector_store()
        
        if not vector_store:
            logger.info("Vector store not available, using fallback")
            statsd.increment("llm.rag.fallback", tags=["reason:unavailable"])
            return _retrieve_context_fallback(question)

        # Async retrieval with timeout
        # We run the blocking similarity_search in a thread
        try:
            docs = await asyncio.wait_for(
                asyncio.to_thread(vector_store.similarity_search, question, k=k),
                timeout=5.0  # 5 second timeout for cold-start
            )
        except asyncio.TimeoutError:
            logger.warning("⏱️ Vector Search timeout (5s) - falling back")
            statsd.increment("llm.rag.fallback", tags=["reason:timeout"])
            return _retrieve_context_fallback(question)
        
        # Process results
        context_parts = [f"[Source {i+1}]\n{doc.page_content}" for i, doc in enumerate(docs)]
        context = "\n\n---\n\n".join(context_parts)
        
        retrieval_latency = (time.time() - start_time) * 1000
        
        # Metrics
        statsd.increment("llm.rag.success", tags=["method:vector_search"])
        statsd.histogram("llm.retrieval.latency.ms", retrieval_latency, tags=["method:vector_search"])
        statsd.gauge("llm.retrieval.docs_retrieved", len(docs), tags=["method:vector_search"])
        
        logger.debug(f"Retrieved {len(docs)} documents in {retrieval_latency:.2f}ms")
        
        return context
    
    except Exception as e:
        logger.error(f"Vector Search error: {e}")
        statsd.increment("llm.rag.fallback", tags=["reason:error"])
        return _retrieve_context_fallback(question)

def _retrieve_context_fallback(question: str) -> str:
    """Fallback using local simple keyword matching"""
    # ... existing fallback code ...
    INCIDENT_KB = {
        "incident": """Incident is a detected service disruption...""",
        "latency": """Database latency is response time...""",
        # ... (keep existing KB)
    }
    # ... match logic ...
    question_lower = question.lower()
    relevant_docs = []
    for keyword, doc in INCIDENT_KB.items():
        if keyword.lower() in question_lower:
            relevant_docs.append(doc.strip())
    return "\n---\n".join(relevant_docs) if relevant_docs else ""
