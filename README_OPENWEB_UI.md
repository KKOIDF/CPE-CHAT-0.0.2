# CPE-CHAT with OpenWeb-UI on Typhoon LLM

Deploy your RAG system with Typhoon LLM integration using OpenWeb-UI - a modern web interface for LLM interactions.

## 🎯 Quick Start (30 seconds)

### Prerequisites
- Docker & Docker Compose installed
- Typhoon API key
- Indexed data (run `ingest_all_domains` first)

### Start Services

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

**Windows (PowerShell):**
```powershell
./start.ps1
```

Then open **http://localhost:3000** in your browser!

---

## 📋 What's New

### ✨ OpenAI API-Compatible Endpoint

The RAG service now exposes `/v1/chat/completions` endpoint, making it compatible with:
- **OpenWeb-UI** (web interface for chat)
- **LM Studio** (desktop app)
- **Any OpenAI-compatible client**

### 🏗 What Happens

```
You (Browser)
     ↓
OpenWeb-UI (Port 3000)
     ↓
RAG Service (Port 8001)
     ├→ Vector Search (Chroma DB)
     ├→ Keyword Search (SQLite FTS)
     └→ Send to Typhoon LLM
          ↓
     Typhoon API
     (Generates answers with your context)
     ↓
Display Answer in OpenWeb-UI
```

---

## 🚀 Deployment Options

### Option 1: Docker Compose (Recommended)

Easiest way to deploy on VM:

```bash
# 1. Configuration
cp .env.example .env
# Edit .env and add your TYPHOON_API_KEY

# 2. Start
docker-compose up -d

# 3. Access
# - Web: http://your-vm-ip:3000
# - API: http://your-vm-ip:8001
```

**Check status:**
```bash
docker-compose ps
docker-compose logs -f rag-service
```

### Option 2: Kubernetes (For Large-Scale)

Create ConfigMap for environment variables, then deploy using Helm charts.

### Option 3: Direct Python (Development)

```bash
cd services/rag-service
python -m pip install -r requirements.txt
export TYPHOON_API_KEY=your_key
export RAG_HOST=0.0.0.0
python run_server.py
```

---

## 🔌 Configuration

### Environment Variables (.env)

```ini
# Typhoon LLM
TYPHOON_API_KEY=your-api-key
TYPHOON_BASE_URL=https://api.opentyphoon.ai/v1

# (Recommended) Enable LangChain orchestration path
RAG_USE_LANGCHAIN=1

# Quality toggles (optional)
RAG_LC_MULTIQUERY=1
RAG_LC_RERANK=1
RAG_LC_COMPRESS=1

# RAG Service
RAG_HOST=0.0.0.0
RAG_PORT=8001

# OpenWeb-UI
OPENWEB_UI_PORT=3000

# Data paths
CPE_INDEX_ROOT=./indexes
```

### LangChain Mode (Recommended)

This repo includes an optional LangChain orchestration pipeline used by both `/rag/query` and `/rag/answer` when `RAG_USE_LANGCHAIN=1`.

What you get:
- Multi-query retrieval (improves recall for Thai phrasing variance)
- Optional embedding rerank (reduces noisy chunks)
- Optional context compression (fits more relevant lines into token budget)

Tuning knobs (all optional):
- `RAG_LC_MULTIQUERY=1` and `RAG_LC_MULTIQUERY_N=3`
- `RAG_LC_PARALLEL=1` to retrieve variants in parallel
- `RAG_LC_RERANK=1` and `RAG_LC_RERANK_TOPN=24`
- `RAG_LC_COMPRESS=1` and `RAG_LC_COMPRESS_MAX_CHARS=700`

### OpenWeb-UI Settings

1. Open http://localhost:3000
2. Go to **Settings → Models**
3. Add new model:
   - Name: `typhoon-rag`
   - URL: `http://localhost:8001/v1` (local) or `http://vm-ip:8001/v1` (remote)
   - Tag: Leave default
4. Select it from dropdown and start chatting!

---

## 🧪 Testing

### Test RAG Service

```bash
# Health check
curl http://localhost:8001/health

# RAG query
curl -X POST http://localhost:8001/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question":"หลักสูตรกี่หน่วยกิต","domain":"curriculum"}'

# OpenAI-compatible endpoint
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model":"typhoon-rag",
    "messages":[{"role":"user","content":"เรียนต้องกี่หน่วยกิต"}]
  }'
```

### Test OpenWeb-UI

1. Visit http://localhost:3000
2. Try a Thai question: "หลักสูตรต้องเรียนกี่หน่วยกิต"
3. Should see RAG-enhanced answer from Typhoon LLM

---

## 📊 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Service health |
| `/rag/query` | POST | Retrieve context only |
| `/rag/answer` | POST | RAG + LLM answer |
| `/v1/chat/completions` | POST | OpenAI-compatible chat |

### Example: Custom Domain Query

```bash
curl -X POST http://localhost:8001/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What does the curriculum cover?",
    "domain": "curriculum"
  }'
```

Query-specific domains: `announcements`, `regulations`, `curriculum`

---

## 🔍 Troubleshooting

### RAG Service won't start

**Check logs:**
```bash
docker-compose logs rag-service
```

**Common fixes:**
- ✗ `TYPHOON_API_KEY not set` → Add to .env
- ✗ `Port 8001 in use` → Change RAG_PORT in .env
- ✗ `Indexes not found` → Run ingestion: `./scripts/ingest_all_domains.ps1`

### OpenWeb-UI won't connect

**Check connectivity:**
```bash
# From container
docker-compose exec openweb-ui curl http://rag-service:8001/health

# Test from host
curl http://localhost:8001/health
```

**If using external VM:**
- Don't use `rag-service:8001` (internal DNS)
- Use `http://your-vm-ip:8001` or `http://your-vm-hostname:8001`
- Update CORS_ORIGINS in docker-compose.yml

### Models not appearing in OpenWeb-UI

1. Ensure RAG service is healthy: `curl http://localhost:8001/health`
2. In OpenWeb-UI, go to **Settings → API Keys**
3. Add/check OpenAI API configuration
4. Restart OpenWeb-UI: `docker-compose restart openweb-ui`

### Slow responses

Check these:
1. **Typhoon API rate limits:** Check your API tier
2. **Network latency:** Use VM IP instead of hostname
3. **Embedding model:** First load downloads BAAI/bge-m3 (~2GB)
4. **Chroma DB:** Large indexes take time to load

---

## 🛠 Managing Services

**View all logs:**
```bash
docker-compose logs -f
```

**Restart all services:**
```bash
docker-compose restart
```

**Restart specific service:**
```bash
docker-compose restart rag-service
docker-compose restart openweb-ui
```

**Stop services:**
```bash
docker-compose down
```

**Remove everything including volumes:**
```bash
docker-compose down -v
```

---

## 📈 Performance Tuning

### For Large Deployments

Edit `docker-compose.yml`:

```yaml
environment:
  TOKEN_BUDGET: "2000"        # Increase context window
  MAX_CONTEXTS: "15"          # More retrieved documents
  LLM_MAX_TOKENS: "1024"      # Longer responses
  EMBED_BATCH: "64"           # Faster embedding
  LLM_TEMPERATURE: "0.3"      # More deterministic
```

### GPU Acceleration

If running on GPU VM:
```yaml
services:
  rag-service:
    deploy:
      resources:
        reservations:
          devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

---

## 🔐 Security Notes

### For Production

1. **Change defaults:**
   - Don't expose port 8001 to internet (use reverse proxy)
   - Enable OpenWeb-UI auth token
   - Use HTTPS/TLS

2. **Network isolation:**
   - Run services in private network
   - Use firewall rules
   - Consider VPN access

3. **API security:**
   - Rotate TYPHOON_API_KEY regularly
   - Monitor API usage
   - Implement rate limiting

---

## 📚 Additional Resources

- **OpenWeb-UI:** https://github.com/open-webui/open-webui
- **Typhoon LLM:** https://opentyphoon.ai
- **RAG Logic:** See `services/rag-service/app/rag_logic.py`
- **Deployment Guide:** See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

---

## 🆘 Need Help?

### Check Logs
```bash
# RAG service
docker-compose logs rag-service | tail -50

# OpenWeb-UI
docker-compose logs openweb-ui | tail -50
```

### Common Issues

**Q: Can't access http://localhost:3000**
- A: Check if OpenWeb-UI container is running: `docker-compose ps`
- A: Wait 30 seconds for it to fully start

**Q: Models not showing in OpenWeb-UI**
- A: Refresh browser (Ctrl+F5 or Cmd+Shift+R)
- A: Check RAG service API: `curl http://localhost:8001/health`

**Q: Getting rate limit errors**
- A: Check Typhoon API quota
- A: Reduce LLM_TEMPERATURE to decrease API calls

---

## 🎉 Next Steps

1. ✅ Start services with `./start.sh` or `./start.ps1`
2. ✅ Open http://localhost:3000
3. ✅ Ask questions in Thai
4. ✅ Monitor with `docker-compose logs -f`
5. ✅ Scale/customize as needed

**Happy chatting! 🚀**
