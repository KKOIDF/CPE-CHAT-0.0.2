#!/bin/bash
# Start RAG Service without Docker

cd ~/CPE-CHAT-0.0.2

# Activate virtual environment
source venv/bin/activate

# Set essential environment variables
export RAG_HOST=0.0.0.0
export RAG_PORT=8001
export LLM_ENABLE=1
export LLM_PROVIDER=typhoon
export LLM_MODEL=typhoon-instruct
export TYPHOON_API_KEY="${TYPHOON_API_KEY:-$(grep TYPHOON_API_KEY .env | grep -E '^(TY_OCR_API_KEY|TYPHOON_API_KEY)' | head -1 | cut -d= -f2)}"
export CPE_INDEX_ROOT=~/CPE-CHAT-0.0.2/indexes
export EMBEDDING_MODEL=BAAI/bge-m3
export TOKEN_BUDGET=1200
export MAX_CONTEXTS=8
export LLM_MAX_TOKENS=512
export LLM_TEMPERATURE=0.4

echo "Starting RAG Service..."
echo "- Host: $RAG_HOST:$RAG_PORT"
echo "- LLM Provider: $LLM_PROVIDER"
echo "- Embedding Model: $EMBEDDING_MODEL"
echo "- Index Root: $CPE_INDEX_ROOT"
echo ""

# Start the service
cd services/rag-service
python run_server.py
