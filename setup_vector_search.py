"""
Setup Vertex AI Vector Search Index.
This creates the vector search index that stores incident KB embeddings.
Run once: python setup_vector_search.py
"""
import os
from google.cloud import aiplatform
from google.cloud import storage
from langchain_google_vertexai import VertexAIEmbeddings
from langchain_google_vertexai import VectorSearchVectorStore
import uuid

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
REGION = "us-central1"
BUCKET_NAME = f"{PROJECT_ID}-llm-incident-vector-search"
INDEX_NAME = "llm-incident-commander-kb"
ENDPOINT_NAME = "llm-incident-commander-endpoint"
DEPLOYED_INDEX_ID = "incident-kb-index"

# Initialize Vertex AI
try:
    aiplatform.init(project=PROJECT_ID, location=REGION)
except Exception as e:
    print(f"Warning: Failed to initialize aiplatform. Ensure GCP_PROJECT_ID is set. Error: {e}")

# Create GCS bucket for storing vectors
def create_bucket():
    """Create GCS bucket if it doesn't exist"""
    if not PROJECT_ID:
        print("Error: GCP_PROJECT_ID environment variable not set.")
        return None
        
    storage_client = storage.Client(project=PROJECT_ID)
    try:
        bucket = storage_client.get_bucket(BUCKET_NAME)
        print(f"✓ Bucket {BUCKET_NAME} already exists")
    except:
        try:
            bucket = storage_client.create_bucket(BUCKET_NAME, location=REGION)
            print(f"✓ Created bucket {BUCKET_NAME}")
        except Exception as e:
             print(f"Error creating bucket: {e}")
             return None
    return bucket

# Step 1: Create Embeddings Model
def create_vector_search_index():
    """Create Vector Search Index"""
    if not PROJECT_ID:
        return None

    print("\n" + "="*60)
    print("STEP 1: Creating Vector Search Index")
    print("="*60)
    
    # Use Vertex AI embeddings (text-embedding-004)
    embeddings_model = VertexAIEmbeddings(
        model_name="text-embedding-004",
        project=PROJECT_ID
    )
    
    # Define knowledge base documents
    documents = [
        {
            "content": """Incident is a detected service disruption affecting users.
                        Severity levels: SEV-1 (critical), SEV-2 (high), SEV-3 (medium), SEV-4 (low).
                        Key metrics: MTTD (mean time to detection), MTTR (mean time to resolution).
                        Response workflow: Detection → Investigation → Mitigation → Resolution → Post-mortem.""",
            "metadata": {"category": "incident_definition", "id": "incident_001"}
        },
        {
            "content": """Database latency is response time for query execution.
                        P50: median latency, P95: 95th percentile, P99: tail latency.
                        Typical LLM latency: 500-2000ms.
                        Causes: Missing indexes, slow queries, connection pool exhaustion, high IO wait.
                        Monitoring: Track query time, execution plans, slow query logs.""",
            "metadata": {"category": "database", "id": "latency_001"}
        },
        {
            "content": """API Quota limits control resource consumption.
                        Types: Requests Per Minute (RPM), Tokens Per Minute (TPM).
                        When exceeded: HTTP 429 Too Many Requests.
                        Reset: Hourly, daily, or monthly depending on plan.
                        Mitigation: Rate limiting, request queuing, exponential backoff.""",
            "metadata": {"category": "quota", "id": "quota_001"}
        },
        {
            "content": """Hallucination occurs when LLM generates false information confidently.
                        Types: Contradictions (against facts), Unsupported claims (not in context).
                        Detection: Semantic analysis, contradiction checking, entailment.
                        Mitigation: RAG (retrieval-augmented generation), fact-checking, prompting.""",
            "metadata": {"category": "llm_quality", "id": "hallucination_001"}
        },
        {
            "content": """Observability enables understanding system state from outputs.
                        Three pillars: Metrics (quantitative), Logs (events), Traces (request flow).
                        LLM observability: Token usage, cost, latency, output quality, hallucinations.
                        Tools: Datadog APM, custom metrics, structured logs.""",
            "metadata": {"category": "observability", "id": "observability_001"}
        },
        {
            "content": """Token is atomic unit LLM processes. 1 token ≈ 4 characters.
                        Input tokens: tokens in prompt. Output tokens: tokens generated.
                        Pricing: Different rates for input vs output.
                        Gemini 2.0 Flash: $0.075/1M input, $0.30/1M output.
                        Cost optimization: Prompt caching, batching, cheaper models.""",
            "metadata": {"category": "tokens", "id": "tokens_001"}
        },
    ]
    
    # Extract texts
    texts = [doc["content"] for doc in documents]
    metadatas = [doc["metadata"] for doc in documents]
    
    print(f"Embedding {len(texts)} documents...")
    
    try:
        # Create Vector Store (automatically creates index)
        # Note: This operation can take a significant amount of time (20+ mins) for new index creation
        vector_store = VectorSearchVectorStore.from_components(
            project_id=PROJECT_ID,
            region=REGION,
            gcs_bucket_name=BUCKET_NAME,
            index_display_name=INDEX_NAME,
            endpoint_display_name=ENDPOINT_NAME,
            embedding=embeddings_model,
            stream_update=True
        )
        
        print(f"Adding texts to vector store...")
        vector_store.add_texts(
            texts=texts,
            metadatas=metadatas,
            is_complete_overwrite=True
        )
        
        print(f"✓ Vector Store created successfully")
        
        # Get index and endpoint IDs for later use
        index_id = vector_store._index_obj.resource_name.split("/")[-1]
        endpoint_id = vector_store._endpoint_obj.resource_name.split("/")[-1]
        
        print(f"\nVECTOR SEARCH CONFIGURATION (save this!):")
        print(f"  INDEX_ID: {index_id}")
        print(f"  ENDPOINT_ID: {endpoint_id}")
        print(f"  BUCKET_NAME: {BUCKET_NAME}")
        
        # Save to .env for later use
        with open(".env", "a") as f:
            f.write(f"\nVS_INDEX_ID={index_id}\n")
            f.write(f"VS_ENDPOINT_ID={endpoint_id}\n")
            f.write(f"VS_BUCKET_NAME={BUCKET_NAME}\n")
        
        return vector_store
    except Exception as e:
        print(f"Error creating vector search index: {e}")
        return None

if __name__ == "__main__":
    print("\n🚀 VECTOR SEARCH SETUP")
    print("="*60)
    
    if not PROJECT_ID:
        print("Please set GCP_PROJECT_ID environment variable.")
        exit(1)

    # Create bucket
    create_bucket()
    
    # Create vector search index and add documents
    vector_store = create_vector_search_index()
    
    if vector_store:
        print("\n✅ SETUP COMPLETE!")
        print("Next: Run 'source .env' and deploy the app")
    else:
        print("\n❌ SETUP FAILED")
