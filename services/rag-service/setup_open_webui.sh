#!/bin/bash

# Script to set up Open WebUI with Ollama
# For CPE-CHAT project with Typhoon 2.5 model

echo "🚀 Open WebUI + Ollama Setup Script"
echo "===================================="
echo ""

# Check if Ollama is running
if ! curl -s http://localhost:11434 > /dev/null; then
    echo "❌ Ollama is not running!"
    echo ""
    echo "Please start Ollama first:"
    echo "  ollama serve"
    echo ""
    exit 1
fi

echo "✅ Ollama is running"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "⚠️  Docker is not installed"
    echo ""
    read -p "Do you want to install Docker? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
        echo ""
        echo "✅ Docker installed successfully"
        echo ""
        echo "⚠️  You need to log out and log back in for group changes to take effect"
        echo "   Or run: newgrp docker"
        echo ""
        read -p "Press Enter to continue..."
    else
        echo "Please install Docker manually and run this script again."
        exit 1
    fi
fi

echo "✅ Docker is installed"
echo ""

# Check if open-webui container already exists
if docker ps -a | grep -q open-webui; then
    echo "⚠️  open-webui container already exists"
    echo ""
    read -p "Do you want to remove and recreate it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing existing container..."
        docker stop open-webui 2>/dev/null
        docker rm open-webui 2>/dev/null
        echo "✅ Old container removed"
    else
        echo "Keeping existing container. Starting it if stopped..."
        docker start open-webui
        echo ""
        echo "✅ Container started"
        echo ""
        echo "Access Open WebUI at: http://localhost:3000"
        exit 0
    fi
fi

echo ""
echo "📥 Pulling Open WebUI Docker image..."
docker pull ghcr.io/open-webui/open-webui:main

echo ""
echo "🔧 Starting Open WebUI container..."
docker run -d \
  --name open-webui \
    --network host \
    -e OLLAMA_BASE_URL=http://127.0.0.1:11434 \
    -e PORT=3000 \
  -v open-webui:/app/backend/data \
  --restart always \
  ghcr.io/open-webui/open-webui:main

echo ""
echo "⏳ Waiting for Open WebUI to start..."
sleep 5

# Check if container is running
if docker ps | grep -q open-webui; then
    echo "✅ Open WebUI is running!"
    echo ""
    echo "=" * 60
    echo "🎉 Setup Complete!"
    echo "=" * 60
    echo ""
    echo "Access Open WebUI at:"
    echo "  http://localhost:3000"
    echo ""
    echo "Or from another device:"
    echo "  http://$(hostname -I | awk '{print $1}'):3000"
    echo ""
    echo "Next steps:"
    echo "  1. Open the URL in your browser"
    echo "  2. Create your first account (will be admin)"
    echo "  3. Go to Settings → Connections"
    echo "  4. Set Ollama URL to: http://127.0.0.1:11434"
    echo "  5. Verify connection"
    echo "  6. Start chatting with Typhoon 2.5!"
    echo ""
    echo "Available models:"
    ollama list | tail -n +2
    echo ""
    echo "To view logs: docker logs -f open-webui"
    echo "To stop: docker stop open-webui"
    echo "To restart: docker restart open-webui"
    echo ""
else
    echo "❌ Failed to start Open WebUI"
    echo ""
    echo "Check logs with: docker logs open-webui"
    exit 1
fi
