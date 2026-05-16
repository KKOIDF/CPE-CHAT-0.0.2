#!/bin/bash
# Start RAG Service without Docker

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"


cd "$REPO_DIR"

# Activate virtual environment
if [ -f "$REPO_DIR/venv/bin/activate" ]; then
	# shellcheck disable=SC1091
	source "$REPO_DIR/venv/bin/activate"
else
	echo "[WARN] venv not found at $REPO_DIR/venv; continuing with system Python." >&2
fi

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
	PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
	PYTHON_BIN="python"
else
	echo "[ERROR] Neither python3 nor python was found in PATH." >&2
	exit 127
fi

# Set essential environment variables
export RAG_HOST=0.0.0.0
export RAG_PORT=8001
export LLM_ENABLE=1
export LLM_PROVIDER=typhoon
export LLM_MODEL="${LLM_MODEL:-}"

# Best-effort load LLM_MODEL from repo-level .env if not already set
if [ -z "${LLM_MODEL:-}" ] && [ -f "$REPO_DIR/.env" ]; then
	LLM_MODEL="$(grep -E '^LLM_MODEL=' "$REPO_DIR/.env" | tail -n 1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
	export LLM_MODEL
fi

# Safe default if still unset
export LLM_MODEL="${LLM_MODEL:-typhoon-v2.5-30b-a3b-instruct}"

# Best-effort load TYPHOON_API_KEY from repo-level .env if not already set
if [ -z "${TYPHOON_API_KEY:-}" ] && [ -f "$REPO_DIR/.env" ]; then
	TYPHOON_API_KEY="$(grep -E '^TYPHOON_API_KEY=' "$REPO_DIR/.env" | tail -n 1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
	export TYPHOON_API_KEY
fi

export TYPHOON_BASE_URL="${TYPHOON_BASE_URL:-https://api.opentyphoon.ai/v1}"
export CPE_INDEX_ROOT="$REPO_DIR/indexes"
export EMBEDDING_MODEL=BAAI/bge-m3
export EMBEDDING_DIM=${EMBEDDING_DIM:-1024}
export TOKEN_BUDGET=1200
export MAX_CONTEXTS=8
export LLM_MAX_TOKENS=512
export LLM_TEMPERATURE=0.4

# MLflow observability (optional)
export MLFLOW_TRACKING_URI="${MLFLOW_TRACKING_URI:-http://localhost:5000}"
export MLFLOW_OBSERVABILITY_ENABLE="${MLFLOW_OBSERVABILITY_ENABLE:-1}"
export MLFLOW_OBSERVABILITY_EXPERIMENT="${MLFLOW_OBSERVABILITY_EXPERIMENT:-cpe-chat-local-observability}"
export MLFLOW_OBS_FLUSH_S="${MLFLOW_OBS_FLUSH_S:-10}"
export MLFLOW_OBS_WINDOW_N="${MLFLOW_OBS_WINDOW_N:-500}"

# Per-request logging (log every incoming question as JSONL artifact)
export MLFLOW_OBS_REQUEST_LOG_ENABLE="${MLFLOW_OBS_REQUEST_LOG_ENABLE:-1}"
# Store question + answer + ctx_sources by default
export MLFLOW_OBS_REQUEST_LOG_CONTENT="${MLFLOW_OBS_REQUEST_LOG_CONTENT:-1}"
export MLFLOW_OBS_REQUEST_LOG_MAX_CHARS="${MLFLOW_OBS_REQUEST_LOG_MAX_CHARS:-2000}"
export MLFLOW_OBS_REQUEST_LOG_DIR="${MLFLOW_OBS_REQUEST_LOG_DIR:-requests}"

# Tracing (capture every request)
export MLFLOW_TRACING_ENABLE="${MLFLOW_TRACING_ENABLE:-1}"
export MLFLOW_TRACE_SAMPLE_RATE="${MLFLOW_TRACE_SAMPLE_RATE:-1}"
export MLFLOW_TRACE_CONTENT="${MLFLOW_TRACE_CONTENT:-1}"
export MLFLOW_TRACE_MAX_CHARS="${MLFLOW_TRACE_MAX_CHARS:-1200}"

echo "Starting RAG Service..."
echo "- Host: $RAG_HOST:$RAG_PORT"
echo "- LLM Provider: $LLM_PROVIDER"
echo "- Embedding Model: $EMBEDDING_MODEL"
echo "- Index Root: $CPE_INDEX_ROOT"
echo ""

# Start the service
cd "$REPO_DIR/services/rag-service"
"$PYTHON_BIN" run_server.py
