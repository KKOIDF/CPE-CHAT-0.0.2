#!/bin/bash

# Script to set up and run RAG service with Ollama + Typhoon 2.5

echo "🚀 Setting up Ollama + Typhoon 2.5 for RAG Service"
echo "=================================================="
echo ""

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama is not installed!"
    echo ""
    echo "Please install Ollama first:"
    echo "  Linux: curl -fsSL https://ollama.com/install.sh | sh"
    echo "  macOS: brew install ollama"
    echo "  Windows: Download from https://ollama.com/download"
    exit 1
fi

echo "✅ Ollama is installed"
echo ""

# Check if Ollama server is running
if ! curl -s http://localhost:11434 > /dev/null; then
    echo "⚠️  Ollama server is not running"
    echo "Starting Ollama server in background..."
    ollama serve &
    sleep 3
fi

echo "✅ Ollama server is running"
echo ""

# Check if model is available
MODEL="scb10x/typhoon2.5-qwen3-30b-a3b"
if ! ollama list | grep -q "$MODEL"; then
    echo "📥 Model '$MODEL' not found"
    echo "Pulling model... (this may take a while)"
    ollama pull "$MODEL"
else
    echo "✅ Model '$MODEL' is available"
fi

echo ""
echo "🔧 Installing Python dependencies..."
pip install -q ollama

echo ""
echo "✅ Setup complete!"
echo ""
echo "Environment variables:"
echo "  LLM_ENABLE=1"
echo "  LLM_PROVIDER=ollama"
echo "  LLM_MODEL=$MODEL"
echo "  OLLAMA_BASE_URL=http://localhost:11434"
echo ""
echo "To start the RAG service:"
echo "  export LLM_ENABLE=1"
echo "  export LLM_PROVIDER=ollama"
echo "  export LLM_MODEL=$MODEL"
echo "  python run_server.py"
echo ""
echo "To test the integration:"
echo "  python test_ollama_typhoon.py"
echo ""
