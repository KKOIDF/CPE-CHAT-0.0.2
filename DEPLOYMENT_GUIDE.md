# CPE-CHAT on OpenWeb-UI - VM Deployment Guide

## Overview
This guide explains how to deploy the RAG system with Typhoon LLM integration using OpenWeb-UI on a VM.

## Architecture
```
┌─────────────────────────────────────────────────────────┐
│  OpenWeb-UI (Port 3000)                                 │
│  - Web interface for chat interactions                  │
│  - Connects to RAG Service via OpenAI API endpoints    │
└──────────────────────┬──────────────────────────────────┘
                       │
                       │ HTTP Requests to /v1/chat/completions
                       │
┌──────────────────────▼──────────────────────────────────┐
│  RAG Service (Port 8001)                                │
│  - FastAPI backend                                      │
│  - RAG query engine (vector + keyword search)          │
│  - Typhoon LLM integration (API-based)                 │
│  - OpenAI API-compatible endpoints                      │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ├─→ Chroma DB (Vector embeddings)
                       ├─→ SQLite FTS (Full-text search)
                       └─→ Typhoon API (LLM generation)
```

## Prerequisites

### 1. Environment Variables
Create a `.env` file in the project root:

```bash
# Typhoon LLM Configuration
TYPHOON_API_KEY=your_typhoon_api_key_here
TYPHOON_BASE_URL=https://api.opentyphoon.ai/v1

# Optional: Ports configuration
RAG_PORT=8001
OPENWEB_UI_PORT=3000

# Optional: OpenWeb-UI tag
OPENWEB_UI_TAG=latest

# Optional: Custom OpenWeb-UI URL (for CORS)
OPENWEB_UI_URL=http://your-vm-ip:3000
```

### 2. Required Data
Ensure these directories exist and contain indexed data:
```
indexes/
├── announcements/
│   └── vector/
│       ├── chroma/
│       └── sqlite/
├── regulations/
│   └── vector/
│       ├── chroma/
│       └── sqlite/
└── curriculum/
    ├── vector/
    │ ├── chroma/
    │ └── sqlite/
    └── graph/
```

If you don't have the indexes yet, run the ingestion service:
```bash
# On Windows (PowerShell)
./scripts/ingest_all_domains.ps1

# On Linux/Mac
# (Python-based ingestion equivalent)
```

## Deployment

### Option 1: Docker Compose (Recommended for VM)

1. **Start the services:**
```bash
docker-compose up -d
```

2. **Check status:**
```bash
docker-compose ps
docker-compose logs rag-service
docker-compose logs openweb-ui
```

3. **Access OpenWeb-UI:**
- Open browser: `http://your-vm-ip:3000`

4. **Stop services:**
```bash
docker-compose down
```

### Option 2: Manual Docker Build (Development)

1. **Build RAG service:**
```bash
cd services/rag-service
docker build -t cpe-chat-rag:latest .
```

2. **Run RAG service:**
```bash
docker run -d \
  --name cpe-chat-rag \
  -p 8001:8001 \
  -e TYPHOON_API_KEY="your_key" \
  -e RAG_HOST="0.0.0.0" \
  -e RAG_PORT="8001" \
  -v /path/to/indexes:/app/indexes \
  cpe-chat-rag:latest
```

3. **Run OpenWeb-UI:**
```bash
docker run -d \
  --name cpe-chat-openweb-ui \
  -p 3000:8080 \
  -e OPENAI_API_BASE_URL="http://cpe-chat-rag:8001" \
  --link cpe-chat-rag \
  ghcr.io/open-webui/open-webui:latest
```

### Option 3: Direct Python (Development/Testing)

1. **Install dependencies:**
```bash
cd services/rag-service
pip install -r requirements.txt
```

2. **Run RAG service:**
```bash
export PYTHONPATH=app
export RAG_HOST=0.0.0.0
export RAG_PORT=8001
export TYPHOON_API_KEY=your_key
python run_server.py
```

3. **In another terminal, run OpenWeb-UI:**
```bash
# Install OpenWeb-UI from: https://github.com/open-webui/open-webui
# Or use Docker
```

## Configuration in OpenWeb-UI

### 1. Add Custom Model/Provider

1. Navigate to **Settings → Models**
2. Click **Add New Model**
3. Fill in the form:
   - **Model Name:** `typhoon-rag`
   - **API URL:** `http://your-vm-ip:8001/v1`  (if using external VM)
     or `http://rag-service:8001/v1` (if using Docker)
   - **API Key:** Leave empty or put dummy value
   - **Request Method:** Auto-detect

### 2. Alternative: Set RAG as Default LLM

If your OpenWeb-UI setup allows direct OWASP API configuration:
1. Go to **Settings → API Keys**
2. Add OpenAI-compatible API:
   - Base URL: `http://your-vm-ip:8001/v1`
   - API Key: (any value)

## Testing the Setup

### Test RAG Service Directly

```bash
# Check health
curl http://your-vm-ip:8001/health

# Test RAG query endpoint
curl -X POST http://your-vm-ip:8001/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "หลักสูตรต้องมีหน่วยกิตกี่หน่วย",
    "domain": "curriculum"
  }'

# Test OpenAI-compatible endpoint
curl -X POST http://your-vm-ip:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "typhoon-rag",
    "messages": [
      {"role": "user", "content": "หลักสูตรต้องมีหน่วยกิตกี่หน่วย"}
    ]
  }'
```

### Test from OpenWeb-UI

1. Access OpenWeb-UI at `http://your-vm-ip:3000`
2. Select the `typhoon-rag` model from dropdown
3. Try a query in Thai (e.g., "หลักสูตรต้องมีหน่วยกิตกี่หน่วย")
4. Verify the response comes from RAG + Typhoon LLM

## Troubleshooting

### RAG Service won't start
```bash
# Check logs
docker-compose logs rag-service

# Common issues:
# 1. TYPHOON_API_KEY not set
# 2. Indexes or data directories not found
# 3. Port 8001 already in use
```

### OpenWeb-UI can't connect to RAG
```bash
# Check Docker networking
docker-compose exec openweb-ui ping rag-service

# Verify RAG service is running
docker-compose exec rag-service curl http://localhost:8001/health
```

### Network issues on VM
```bash
# Instead of 'rag-service:8001', use the VM's IP
# Update CORS_ORIGINS in docker-compose.yml:
CORS_ORIGINS: "http://vm-ip:3000,http://localhost:3000"

# Or use VM hostname
CORS_ORIGINS: "http://your-vm-hostname:3000"
```

## Performance Notes

- **First load:** May take time to download BAAI/bge-m3 embedding model (~2GB)
- **Chroma DB:** Loads vector index into memory (500 MB - 2 GB depending on data)
- **SQLite FTS:** Fast keyword search on top of data
- **Typhoon API:** Requires valid API key and internet connection

## Next Steps

1. **Monitor logs:** `docker-compose logs -f rag-service`
2. **Scale:** Increase RAG_MAX_TOKENS or adjust LLM_TEMPERATURE
3. **Custom domains:** Add new domains by running ingestion scripts
4. **Graph expansion:** For curriculum, configure Neo4j connection
5. **Authentication:** Add OpenWeb-UI auth token via environment variable

## API Endpoints

Your RAG service now exposes:

| Endpoint | Method | Purpose | Format |
|----------|--------|---------|--------|
| `/health` | GET | Health check | JSON |
| `/rag/query` | POST | RAG query retrieval | JSON |
| `/rag/answer` | POST | RAG + LLM answer | JSON |
| `/v1/chat/completions` | POST | OpenAI-compatible chat | OpenAI API |

The `/v1/chat/completions` endpoint is what OpenWeb-UI uses!

## Support

For issues with:
- **Typhoon LLM:** Check API key and tier limits
- **OpenWeb-UI:** See https://github.com/open-webui/open-webui
- **RAG logic:** Check `services/rag-service/app/rag_logic.py`
