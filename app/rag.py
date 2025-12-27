"""
Retrieval-Augmented Generation (RAG) using Vertex AI Vector Search.
Provides semantic search over incident knowledge base.
"""
import os
import time
from typing import Optional
from langchain_google_vertexai import VertexAIEmbeddings
from langchain_google_vertexai import VectorSearchVectorStore
from google.cloud import aiplatform
from app.logging_config import setup_logging
from datadog import statsd

logger = setup_logging()

# Initialize Vertex AI
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
REGION = os.environ.get("GCP_REGION", "us-central1")

# Vector Search configuration (from setup)
VS_INDEX_ID = os.environ.get("VS_INDEX_ID")
VS_ENDPOINT_ID = os.environ.get("VS_ENDPOINT_ID")
VS_BUCKET_NAME = os.environ.get("VS_BUCKET_NAME")

# Global vector store (lazy loaded)
_vector_store = None

def get_vector_store():
    """Lazy load vector store"""
    global _vector_store
    
    if _vector_store is None:
        try:
            logger.info("Initializing Vertex AI Vector Search")
            
            if not PROJECT_ID:
                logger.warning("GCP_PROJECT_ID not set, skipping Vector Search initialization")
                return None

            # Initialize Vertex AI
            aiplatform.init(project=PROJECT_ID, location=REGION)
            
            # Initialize embeddings model
            embeddings = VertexAIEmbeddings(
                model_name="text-embedding-004",
                project=PROJECT_ID
            )
            
            # Check if vector search env vars are present
            if not all([VS_INDEX_ID, VS_ENDPOINT_ID, VS_BUCKET_NAME]):
                logger.warning("Vector Search environment variables missing. Using fallback/empty context.")
                return None

            # Load vector store from existing index
            _vector_store = VectorSearchVectorStore.from_components(
                project_id=PROJECT_ID,
                region=REGION,
                gcs_bucket_name=VS_BUCKET_NAME,
                index_id=VS_INDEX_ID,
                endpoint_id=VS_ENDPOINT_ID,
                embedding=embeddings,
                stream_update=False  # Read-only for RAG
            )
            
            logger.info("✓ Vector Search loaded successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Vector Search: {e}")
            return None
    
    return _vector_store

def retrieve_context(question: str, k: int = 3, test_mode: str = None) -> str:
    """
    Retrieve relevant context from Vector Search using semantic similarity.
    
    Args:
        question: User question
        k: Number of documents to retrieve
        test_mode: "hallucination" triggers RAG poisoning
        
    Returns:
        Combined context from top-k similar documents
    """
    start_time = time.time()
    
    # 🧪 RAG POISONING (Failure Injection)
    # If in hallucination test mode, we intentionally return irrelevant context.
    # This simulates a retrieval failure or "poisoned" knowledge base.
    if test_mode == "hallucination":
        logger.info(f"🧪 [TEST MODE] Injecting RAG Poison for question: {question[:50]}...")
        return "Context: This document describes how to bake a chocolate cake. 1. Mix flour and sugar. 2. Add eggs. 3. Bake at 350F. (Irrelevant context injected for testing)"

    try:
        vector_store = get_vector_store()
        
        if not vector_store:
             # Fallback to local KB if vector store not available (for dev/test without full setup)
             logger.info("Vector store not available, using fallback keyword search")
             return _retrieve_context_fallback(question)

        # Semantic search using vector similarity
        logger.debug(f"Retrieving context for: {question[:100]}")
        
        docs = vector_store.similarity_search(question, k=k)
        
        # Extract and combine context
        context_parts = []
        for i, doc in enumerate(docs, 1):
            context_parts.append(f"[Source {i}]\n{doc.page_content}")
            
            # Log metadata for debugging
            if doc.metadata:
                logger.debug(f"Retrieved doc {i}: {doc.metadata}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        retrieval_latency = (time.time() - start_time) * 1000
        
        # Emit metrics to Datadog
        statsd.histogram("llm.retrieval.latency.ms", retrieval_latency, tags=["method:vector_search"])
        statsd.gauge("llm.retrieval.docs_retrieved", len(docs), tags=["method:vector_search"])
        statsd.gauge("llm.retrieval.context_length", len(context), tags=["method:vector_search"])
        
        logger.info(
            "Context retrieved successfully",
            extra={
                "docs_retrieved": len(docs),
                "context_length": len(context),
                "retrieval_latency_ms": retrieval_latency
            }
        )
        
        return context
    
    except Exception as e:
        logger.error(
            "Vector Search retrieval failed",
            extra={"error": str(e)},
            exc_info=True
        )
        statsd.increment("llm.retrieval.errors", tags=["method:vector_search"])
        
        # Fallback
        return _retrieve_context_fallback(question)

def _retrieve_context_fallback(question: str) -> str:
    """Fallback using local simple keyword matching"""
    logger.warning("⚠️ RUNNING IN RAG FALLBACK MODE - VECTOR SEARCH DISABLED ⚠️")
    
    # Incident knowledge base from previous step for fallback
    INCIDENT_KB = {
        "incident": """Incident is a detected service disruption affecting users...""",
        "latency": """Database latency is response time...""",
        "quota": """API Quota limits control resource consumption...""",
        "hallucination": """Hallucination occurs when LLM generates false info...""",
        "observability": """Observability enables understanding system state...""",
        "token": """Token is atomic unit LLM processes...""",
    }
    question_lower = question.lower()
    relevant_docs = []
    for keyword, doc in INCIDENT_KB.items():
        if keyword.lower() in question_lower:
            relevant_docs.append(doc.strip())
    return "\n---\n".join(relevant_docs) if relevant_docs else ""

def test_vector_search():
    """Test that vector search is working"""
    try:
        vector_store = get_vector_store()
        if not vector_store:
            return False
            
        # Test query
        test_query = "What is database latency?"
        docs = vector_store.similarity_search(test_query, k=1)
        
        if docs:
            logger.info(f"✓ Vector Search working. Retrieved: {docs[0].page_content[:100]}...")
            return True
        else:
            logger.warning("Vector Search returned no results")
            return False
    except Exception as e:
        logger.error(f"Vector Search test failed: {e}")
        return False
