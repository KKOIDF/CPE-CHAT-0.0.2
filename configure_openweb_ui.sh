#!/bin/bash
# Configure OpenWeb-UI to use local RAG service

docker stop open-webui 2>/dev/null

docker run -d \
  --name open-webui \
  -p 3000:8080 \
  -v open-webui:/app/backend/data \
  -e OPENAI_API_BASE_URL="http://host.docker.internal:8001/v1" \
  -e OPENAI_API_KEY="not-required" \
  --add-host=host.docker.internal:host-gateway \
  --restart unless-stopped \
  ghcr.io/open-webui/open-webui:latest

echo ""
echo "✅ OpenWeb-UI configured to use RAG Service"
echo "   - OpenWeb-UI: http://localhost:3000"
echo "   - RAG API: http://localhost:8001"
echo ""
echo "In OpenWeb-UI, select model: typhoon-v2.5-30b-a3b-instruct"
