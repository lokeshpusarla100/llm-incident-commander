"""
Setup Vertex AI Vector Search Index.
This creates the vector search index that stores incident KB embeddings.
Run once: python setup_vector_search.py
"""
import os
import time
from pathlib import Path
from collections import defaultdict
from google.cloud import aiplatform
from google.cloud import storage
from langchain_google_vertexai import VectorSearchVectorStore, VertexAIEmbeddings

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
REGION = "us-central1"
BUCKET_NAME = f"{PROJECT_ID}-llm-incident-vector-search"
INDEX_NAME = "llm-incident-commander-kb"
ENDPOINT_NAME = "llm-incident-commander-endpoint"

# NOTE: If you change these, you must also update app/rag.py
RAG_DATA_DIR = Path("rag_data")

# Metadata mapping for richer RAG signals
METADATA_MAPPING = {
    "incident_definition.md": {"type": "definition", "domain": "incident_management", "severity": "medium"},
    "latency_playbook.md": {"type": "playbook", "domain": "database", "severity": "high"},
    "quota_playbook.md": {"type": "playbook", "domain": "api_quota", "severity": "high"},
    "hallucination_policy.md": {"type": "policy", "domain": "llm_quality", "severity": "critical"},
    "observability_principles.md": {"type": "principle", "domain": "observability", "severity": "medium"},
    "token_costs.md": {"type": "reference", "domain": "cost_management", "severity": "low"},
}

def create_bucket():
    """Create GCS bucket if it doesn't exist"""
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

def get_or_create_index():
    """Get existing index or create a new one"""
    aiplatform.init(project=PROJECT_ID, location=REGION)
    
    # Check if index exists
    indexes = aiplatform.MatchingEngineIndex.list(filter=f'display_name="{INDEX_NAME}"')
    if indexes:
        print(f"✓ Found existing Index: {indexes[0].resource_name}")
        return indexes[0]
        
    print(f"Creating new Index {INDEX_NAME} (Brute Force / Streaming)...")
    # Brute Force is faster to create and better for small datasets (<1M)
    index = aiplatform.MatchingEngineIndex.create_brute_force_index(
        display_name=INDEX_NAME,
        dimensions=768, # text-embedding-004 dimensions
        distance_measure_type="DOT_PRODUCT_DISTANCE",
        index_update_method="STREAM_UPDATE"  # Enable real-time updates
    )
    print(f"✓ Index created: {index.resource_name}")
    return index

def get_or_create_endpoint():
    """Get existing endpoint or create a new one"""
    endpoints = aiplatform.MatchingEngineIndexEndpoint.list(filter=f'display_name="{ENDPOINT_NAME}"')
    if endpoints:
        print(f"✓ Found existing Endpoint: {endpoints[0].resource_name}")
        return endpoints[0]
        
    print(f"Creating new Endpoint {ENDPOINT_NAME}...")
    endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
        display_name=ENDPOINT_NAME,
        public_endpoint_enabled=True
    )
    print(f"✓ Endpoint created: {endpoint.resource_name}")
    return endpoint

def deploy_index(index, endpoint):
    """Deploy index to endpoint if not already deployed"""
    
    # Check if deployed
    for deployed_index in endpoint.deployed_indexes:
        if deployed_index.display_name == "deployed_index_1":
             print("✓ Index already deployed to endpoint")
             return
             
    print("Deploying index to endpoint (this takes ~15-20 mins)...")
    try:
        endpoint.deploy_index(
            index=index,
            deployed_index_id="deployed_index_1"
        )
        print("✓ Index deployed successfully")
    except Exception as e:
        if "AlreadyExists" in str(e) or "already exists" in str(e):
            print("✓ Index already deployed (caught exception)")
        else:
            raise e

def main():
    print("\n🚀 VECTOR SEARCH SETUP")
    print("="*60)
    
    if not PROJECT_ID:
        print("❌ Error: GCP_PROJECT_ID environment variable not set.")
        return

    # 1. Create Bucket
    create_bucket()
    
    # 2. Get/Create Infrastructure
    try:
        # Note: We are using a simplified approach here. 
        # For a truly robust setup, we'd create the index, wait for it, etc.
        # But VectorSearchVectorStore.from_components is strictly for *existing* components.
        # Since creating an index takes 45 mins, for this challenge/demo,
        # we might want to check if the user *really* wants to wait or if there's a misunderstand.
        # However, the user is stuck.
        
        # ACTUALLY, checking LangChain docs, the `VectorSearchVectorStore` constructor
        # does NOT create the index infrastructure for you automatically in a simple synchronous way usually.
        # But `VectorSearchVectorStore` class has a `.create(...)` method (factory).
        # Let's try to use the constructor properly if we knew the signature.
        
        # HOWEVER, the error was "missing 2 required positional arguments: 'index_id' and 'endpoint_id'".
        # This confirms we are hitting the path where it expects existing resources.
        
        # Let's fix it by creating resources using SDK first (or finding them).
        
        index = get_or_create_index()
        endpoint = get_or_create_endpoint()
        deploy_index(index, endpoint)
        
        # 3. Initialize VectorStore with IDs
        embeddings = VertexAIEmbeddings(model_name="text-embedding-004")
        
        vector_store = VectorSearchVectorStore.from_components(
            project_id=PROJECT_ID,
            region=REGION,
            gcs_bucket_name=BUCKET_NAME,
            index_id=index.resource_name.split("/")[-1],
            endpoint_id=endpoint.resource_name.split("/")[-1],
            embedding=embeddings,
            stream_update=True
        )
        
        # 4. Add Documents
        print(f"\nLoading documents from {RAG_DATA_DIR}...")
        texts = []
        metadatas = []
        
        if RAG_DATA_DIR.exists():
            for file_path in RAG_DATA_DIR.glob("*.md"):
                content = file_path.read_text()
                metadata = METADATA_MAPPING.get(file_path.name, {"type": "general"})
                texts.append(content)
                metadatas.append(metadata)
                
            if texts:
                print(f"Adding {len(texts)} documents to vector store...")
                vector_store.add_texts(texts=texts, metadatas=metadatas)
                print("✓ Documents added")
        
        print("\n✅ SETUP COMPLETE")
        print("="*60)
        print(f"export VS_INDEX_ID={index.resource_name.split('/')[-1]}")
        print(f"export VS_ENDPOINT_ID={endpoint.resource_name.split('/')[-1]}")
        print(f"export VS_BUCKET_NAME={BUCKET_NAME}")
        
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        # Fallback to help debug
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
