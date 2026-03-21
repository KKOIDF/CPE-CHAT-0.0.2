# VM Deployment Checklist

ระบบ RAG เชื่อมกับ Typhoon LLM สามารถ deploy ไปยัง VM ผ่าน OpenWeb-UI ได้แล้ว!

## ✅ ขั้นตอนการ Deploy (Step-by-Step)

### 📋 Pre-deployment Checklist

- [ ] Docker installed on VM (`docker --version`)
- [ ] Docker Compose installed on VM (`docker-compose --version`)
- [ ] Copy project to VM (using git clone or scp)
- [ ] Verify indexed data exists: `ls indexes/` should show directories
- [ ] Have Typhoon API key ready

### 🔧 Step 1: Configuration

```bash
# On VM, go to project directory
cd /path/to/CPE-CHAT-0.0.2

# Create .env from template
cp .env.example .env

# Edit .env and add your Typhoon API key
nano .env  # or vi, vim, etc.
```

**Required settings in .env:**
```
TYPHOON_API_KEY=your-actual-api-key-here
TYPHOON_BASE_URL=https://api.opentyphoon.ai/v1
```

**Optional customizations:**
```
RAG_PORT=8001                    # If port conflict, change this
OPENWEB_UI_PORT=3000            # If port conflict, change this
CPE_INDEX_ROOT=/path/to/indexes  # If indexes elsewhere
```

### 🚀 Step 2: Start Services

```bash
# Start everything with one command
docker-compose up -d

# Verify all services started
docker-compose ps

# Check RAG service health
curl http://localhost:8001/health

# Wait 30 seconds for OpenWeb-UI to start
sleep 30
```

### 🌐 Step 3: Access OpenWeb-UI

**On VM (or same network):**
```
http://your-vm-ip:3000
```

**From outside network:**
- Use VM's public IP/hostname
- Update CORS_ORIGINS in docker-compose.yml
- Ensure firewall allows port 3000

### 💬 Step 4: Start Using

1. Open browser to `http://your-vm-ip:3000`
2. OpenWeb-UI should load
3. Model should auto-detect RAG service
4. Try asking in Thai: "หลักสูตรต้องเรียนกี่หน่วยกิต"
5. Wait for answer (first time ~3 seconds, then faster)

---

## 🔍 Verification

### Service Status
```bash
# Check all containers running
docker-compose ps

# Expected output:
# NAME              STATUS          PORTS
# cpe-chat-rag      Up (healthy)    0.0.0.0:8001→8001/tcp
# cpe-chat-openweb-ui  Up          0.0.0.0:3000→8080/tcp
```

### RAG Service
```bash
# Health check
curl http://localhost:8001/health
# Should return: {"status":"ok"}

# Test RAG query
curl -X POST http://localhost:8001/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question":"หลักสูตร","domain":"curriculum"}'

# Test OpenAI endpoint (what OpenWeb-UI uses)
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model":"typhoon-rag",
    "messages":[
      {"role":"user","content":"หลักสูตรหน่วยกิต"}
    ]
  }'
```

### WebUI Connection
```bash
# Check if OpenWeb-UI can reach RAG service
docker-compose exec openweb-ui curl http://rag-service:8001/health
```

---

## 📊 Architecture on VM

```
┌─────────────────────────────────────────────────┐
│            Virtual Machine (VM)                 │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │  Port 3000 - OpenWeb-UI                 │   │
│  │  Modern chat interface                  │   │
│  └────────────────┬────────────────────────┘   │
│                   │                             │
│                   │ (internal Docker network)   │
│                   ↓                             │
│  ┌─────────────────────────────────────────┐   │
│  │  Port 8001 - RAG Service API            │   │
│  │  • Vector search (Chroma)               │   │
│  │  • Keyword search (SQLite)              │   │
│  │  • OpenAI-compatible endpoints          │   │
│  │  • Typhoon LLM integration              │   │
│  └─────────────────────────────────────────┘   │
│                   │                             │
│                   └────→ Internet API           │
│                         (Typhoon)              │
└─────────────────────────────────────────────────┘
                      ↓
              External Access
          (from other machines)
```

---

## 🛠 Management Commands

### View Logs
```bash
# All services
docker-compose logs

# Specific service
docker-compose logs rag-service
docker-compose logs openweb-ui

# Follow logs in real-time
docker-compose logs -f rag-service

# Last 50 lines
docker-compose logs rag-service --tail=50
```

### Control Services
```bash
# Stop all
docker-compose stop

# Start all
docker-compose start

# Restart specific service
docker-compose restart rag-service

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# View status
docker-compose ps

# Remove containers (keep data)
docker-compose down

# Remove everything including data
docker-compose down -v
```

### Container Access
```bash
# Shell into container
docker-compose exec rag-service bash

# Run command in container
docker-compose exec rag-service curl http://localhost:8001/health

# Check container resources
docker stats
```

---

## 🔧 Troubleshooting

### Problem: Services won't start

```bash
# Check logs
docker-compose logs rag-service | head -50

# Common issues:
# ❌ TYPHOON_API_KEY not set
#    ✅ Make sure .env has valid API key

# ❌ Port already in use
#    ✅ Change RAG_PORT or OPENWEB_UI_PORT in .env

# ❌ Indexes not found
#    ✅ Verify: ls -la indexes/announcements/vector/
```

### Problem: Can't connect from another machine

```bash
# Check if service listening on all interfaces
docker-compose logs rag-service | grep "Uvicorn running"
# Should show: 0.0.0.0:8001

# Check firewall on VM
sudo ufw status  # Ubuntu/Debian
# If enabled, add: sudo ufw allow 8001 && sudo ufw allow 3000

# Test from another machine
curl http://vm-ip:8001/health
```

### Problem: OpenWeb-UI shows no models

```bash
# Restart OpenWeb-UI container
docker-compose restart openweb-ui

# Wait 30 seconds
sleep 30

# Check RAG service is healthy
curl http://localhost:8001/health
# Should return {"status":"ok"}

# Check OpenWeb-UI logs
docker-compose logs openweb-ui | tail -50
```

### Problem: Slow responses

```bash
# Check Typhoon API status (in Typhoon dashboard)

# Monitor container resources
docker stats

# Reduce context size
# Edit docker-compose.yml:
TOKEN_BUDGET=1000  # from 1200

# Or reduce response length
LLM_MAX_TOKENS=256  # from 512

# Restart
docker-compose restart rag-service
```

---

## 📈 Performance Optimization

### For VM with Limited Resources

Edit `docker-compose.yml`:

```yaml
services:
  rag-service:
    environment:
      # Reduce memory usage
      TOKEN_BUDGET: "800"      # Smaller context
      MAX_CONTEXTS: "5"        # Fewer documents
      LLM_MAX_TOKENS: "256"    # Shorter response
      EMBED_BATCH: "16"        # Slower but uses less RAM
      LLM_TEMPERATURE: "0.3"   # More deterministic
```

### For Fast Responses

Edit `docker-compose.yml`:

```yaml
services:
  rag-service:
    environment:
      # Increase for better quality
      TOKEN_BUDGET: "2000"     # Larger context
      MAX_CONTEXTS: "15"       # More documents
      LLM_MAX_TOKENS: "1024"   # Longer response
      EMBED_BATCH: "64"        # Faster embedding
      LLM_TEMPERATURE: "0.5"   # More creative
```

---

## 🔐 Security for VM Deployment

### Access Control

```bash
# Only allow local access (most secure)
# Edit docker-compose.yml:
#   ports:
#     - "127.0.0.1:3000:8080"  # Only localhost

# Allow specific IPs
# Use firewall rules:
sudo ufw allow from 192.168.1.100 to any port 3000
sudo ufw allow from 192.168.1.100 to any port 8001

# Allow range
sudo ufw allow from 192.168.1.0/24 to any port 3000
```

### Monitor Access

```bash
# Check connections
netstat -tulpn | grep LISTEN

# Monitor logs for suspicious activity
docker-compose logs rag-service | grep -i error
```

---

## 📋 Post-Deployment Checklist

- [ ] `.env` configured with TYPHOON_API_KEY
- [ ] `docker-compose up -d` completed successfully
- [ ] `docker-compose ps` shows both services running
- [ ] `curl http://localhost:8001/health` returns `{"status":"ok"}`
- [ ] OpenWeb-UI accessible at `http://vm-ip:3000`
- [ ] Can ask a question and get response
- [ ] Tested from external machine (if needed)
- [ ] Logs checked for errors: `docker-compose logs`
- [ ] Firewall rules configured (if needed)
- [ ] Monitoring/alerting set up (optional)

---

## 🚨 Emergency Commands

### If everything breaks
```bash
# Stop everything
docker-compose down

# Remove containers
docker rm cpe-chat-rag cpe-chat-openweb-ui

# Remove images
docker rmi cpe-chat-rag:latest ghcr.io/open-webui/open-webui

# Rebuild and restart
docker-compose up -d --build

# Check logs
docker-compose logs
```

### If out of disk space
```bash
# Check disk usage
df -h

# Clean up Docker
docker system prune -a

# Remove old images
docker image prune -a
```

---

## 📞 Support Information

### Quick Diagnosis

```bash
#!/bin/bash
echo "=== System Info ==="
uname -a
docker --version
docker-compose --version

echo "=== Service Status ==="
docker-compose ps

echo "=== RAG Service Health ==="
curl http://localhost:8001/health

echo "=== Recent Logs ==="
docker-compose logs --tail=20
```

### Debug Mode

Enable debug logging in docker-compose.yml:
```yaml
environment:
  OPENAI_DEBUG: "1"
  TYPHOON_DEBUG: "1"
```

Then check logs:
```bash
docker-compose logs -f rag-service | grep -i typhoon
```

---

## 🎯 Success Indicators

✅ **Everything is working if:**
- Web UI loads at `http://vm-ip:3000`
- RAG service responds: `curl http://vm-ip:8001/health`
- Can type questions and get answers
- First response takes ~3 seconds
- Subsequent responses faster due to caching
- No errors in `docker-compose logs`

---

## 📚 Related Documentation

- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Detailed setup guide
- [README_OPENWEB_UI.md](README_OPENWEB_UI.md) - OpenWeb-UI features
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Technical changes
- [README_DOMAINS.md](README_DOMAINS.md) - Domain-specific queries

---

## 🎉 Ready to Deploy!

```bash
# One-command deployment
./start.sh  # on Linux/Mac
# or
./start.ps1  # on Windows

# Then visit: http://your-vm-ip:3000
```

**Questions? Check the documentation files above or examine the docker-compose.yml for more details.**
