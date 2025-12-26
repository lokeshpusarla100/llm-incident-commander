#!/bin/bash

# Deploy Vector Search Setup

echo "🚀 VERTEX AI VECTOR SEARCH DEPLOYMENT"
echo "========================================"

# Step 1: Install dependencies
echo "📦 Installing Python dependencies..."
pip install langchain-google-vertexai google-cloud-aiplatform google-cloud-storage

# Step 2: Authenticate with Google Cloud
echo "🔐 Authenticating with Google Cloud..."
gcloud auth application-default login

# Step 3: Run setup script
echo "⚙️ Setting up Vector Search Index..."
python setup_vector_search.py

# Step 4: Load environment variables
echo "📝 Loading configuration..."
if [ -f .env ]; then
    source .env
    export VS_INDEX_ID
    export VS_ENDPOINT_ID
    export VS_BUCKET_NAME
else
    echo "Warning: .env file not found. Vector Search might not work if env vars are not set."
fi

# Step 5: Test connection
echo "✅ Testing Vector Search..."
python -c "
from app.rag import test_vector_search
if test_vector_search():
    print('✓ Vector Search is ready!')
else:
    print('✗ Vector Search test failed (or skipped if env vars missing)')
    # Don't exit with error to allow fallback
"

echo ""
echo "✅ DEPLOYMENT COMPLETE!"
echo "You can now run the app."
