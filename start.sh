#!/bin/bash

# ==============================================================
# CPE-CHAT with OpenWeb-UI - Quick Start Script
# ==============================================================
# This script automates the setup and deployment process

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}========================================${NC}"
}

print_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 is not installed"
        return 1
    fi
}

print_header "CPE-CHAT OpenWeb-UI Quick Start"

# Check prerequisites
print_info "Checking prerequisites..."

if ! check_command docker; then
    print_error "Docker is required but not installed"
    echo "Install from: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! check_command docker-compose; then
    print_error "Docker Compose is required but not installed"
    echo "Install from: https://docs.docker.com/compose/install/"
    exit 1
fi

print_info "Docker and Docker Compose are installed ✓"

# Check .env file
print_info "Checking environment configuration..."

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        print_info "Creating .env from .env.example..."
        cp .env.example .env
        print_info "Created .env - Please update TYPHOON_API_KEY!"
    else
        print_error ".env file not found and .env.example not available"
        exit 1
    fi
fi

# Verify TYPHOON_API_KEY is set
if ! grep -q "^TYPHOON_API_KEY=" .env || grep "^TYPHOON_API_KEY=your_typhoon_api_key_here" .env; then
    print_error "TYPHOON_API_KEY is not configured in .env"
    echo "Please update .env with your Typhoon API key"
    exit 1
fi

print_info ".env configuration found ✓"

# Check data directories
print_info "Checking indexed data directories..."
if [ ! -d "indexes" ] || [ -z "$(find indexes -type f -name '*.db' 2>/dev/null)" ]; then
    print_error "No indexed data found in ./indexes/"
    echo ""
    echo "Please run the ingestion process first:"
    echo "  - On Windows (PowerShell): ./scripts/ingest_all_domains.ps1"
    echo "  - On Linux: python services/ingestion-service/scripts/[ingest_script].py"
    echo ""
    exit 1
fi

print_info "Indexed data found ✓"

# Build and start services
print_header "Starting Docker Services"

print_info "Building and starting RAG service and OpenWeb-UI..."
docker-compose up -d

# Wait for services to be ready
print_info "Waiting for services to start..."
sleep 5

# Check RAG service health
print_info "Checking RAG service health..."
if docker-compose exec -T rag-service curl -f http://localhost:8001/health > /dev/null 2>&1; then
    print_info "RAG service is healthy ✓"
else
    print_error "RAG service is not responding"
    echo "Check logs with: docker-compose logs rag-service"
    exit 1
fi

print_info "Waiting for OpenWeb-UI to start (30 seconds)..."
sleep 30

# Get port information
RAG_PORT=$(grep "RAG_PORT" .env | cut -d '=' -f 2)
OPENWEB_PORT=$(grep "OPENWEB_UI_PORT" .env | cut -d '=' -f 2)

RAG_PORT=${RAG_PORT:-8001}
OPENWEB_PORT=${OPENWEB_PORT:-3000}

print_header "✓ Services Started Successfully!"

echo ""
echo "Access your services:"
echo ""
echo -e "${GREEN}OpenWeb-UI:${NC}     http://localhost:${OPENWEB_PORT}"
echo -e "${GREEN}RAG API:${NC}        http://localhost:${RAG_PORT}"
echo -e "${GREEN}Health Check:${NC}   http://localhost:${RAG_PORT}/health"
echo ""

echo "Next steps:"
echo "1. Open http://localhost:${OPENWEB_PORT} in your browser"
echo "2. Configure model settings (should auto-detect RAG service)"
echo "3. Try asking a question in Thai"
echo ""

echo "Useful commands:"
echo "  - View logs:     docker-compose logs -f"
echo "  - Stop services: docker-compose down"
echo "  - Restart:       docker-compose restart"
echo "  - RAG service logs: docker-compose logs -f rag-service"
echo "  - OpenWeb-UI logs:  docker-compose logs -f openweb-ui"
echo ""

# Optional: Open browser
if command -v xdg-open &> /dev/null; then
    read -p "Open OpenWeb-UI in browser now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        xdg-open "http://localhost:${OPENWEB_PORT}" &
    fi
fi

print_header "Setup Complete! Happy Chatting! 🚀"
