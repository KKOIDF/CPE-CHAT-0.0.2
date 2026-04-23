# ==============================================================
# CPE-CHAT with OpenWeb-UI - Quick Start Script (Windows)
# ==============================================================
# This script automates the setup and deployment process

# Check if running as admin (optional but recommended)
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

function Print-Header {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host $args[0] -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
}

function Print-Info {
    Write-Host "[INFO] $($args -join ' ')" -ForegroundColor Yellow
}

function Print-Error {
    Write-Host "[ERROR] $($args -join ' ')" -ForegroundColor Red
}

function Print-Warning {
    Write-Host "[WARNING] $($args -join ' ')" -ForegroundColor Yellow
}

function Print-Success {
    Write-Host "[SUCCESS] $($args -join ' ')" -ForegroundColor Green
}

Print-Header "CPE-CHAT OpenWeb-UI Quick Start (Windows)"

# Check prerequisites
Print-Info "Checking prerequisites..."

# Check Docker
try {
    $dockerVersion = docker --version 2>$null
    if ($LASTEXITCODE -ne 0) { throw }
    Print-Success "Docker found: $dockerVersion"
} catch {
    Print-Error "Docker is not installed or not in PATH"
    Write-Host "Install from: https://docs.docker.com/docker-for-windows/install/" 
    exit 1
}

# Check Docker Compose
try {
    $composeVersion = docker-compose --version 2>$null
    if ($LASTEXITCODE -ne 0) { throw }
    Print-Success "Docker Compose found: $composeVersion"
} catch {
    Print-Error "Docker Compose is not installed"
    Write-Host "Install from: https://docs.docker.com/compose/install/"
    exit 1
}

# Check .env file
Print-Info "Checking environment configuration..."

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Print-Info "Creating .env from .env.example..."
        Copy-Item ".env.example" ".env"
        Print-Warning ".env created - Please update your LLM provider settings!"
        notepad .env
    } else {
        Print-Error ".env file not found"
        exit 1
    }
}

$llmProviderLine = Get-Content ".env" | Select-String "^LLM_PROVIDER="
$llmProvider = if ($llmProviderLine) { $llmProviderLine.ToString().Split('=')[1].Trim() } else { "typhoon" }

if ($llmProvider -eq "typhoon") {
    $envContent = Get-Content ".env" | Select-String "^TYPHOON_API_KEY"
    if (-not $envContent -or $envContent -match "your_typhoon_api_key_here") {
        Print-Error "TYPHOON_API_KEY is not configured in .env"
        Write-Host "Please update .env with your Typhoon API key"
        exit 1
    }
} elseif ($llmProvider -eq "ollama") {
    $envContent = Get-Content ".env" | Select-String "^OLLAMA_BASE_URL="
    if (-not $envContent) {
        Print-Error "OLLAMA_BASE_URL is not configured in .env"
        Write-Host "Please update .env with your Ollama base URL"
        exit 1
    }
}

Print-Success ".env configuration found"

# Check data directories
Print-Info "Checking indexed data directories..."

if (-not (Test-Path "indexes") -or @(Get-ChildItem "indexes" -Recurse -Filter "*.db" -ErrorAction SilentlyContinue).Count -eq 0) {
    Print-Error "No indexed data found in ./indexes/"
    Write-Host ""
    Write-Host "Please run the ingestion process first:"
    Write-Host "  ./scripts/ingest_all_domains.ps1"
    Write-Host ""
    exit 1
}

Print-Success "Indexed data found"

# Start services
Print-Header "Starting Docker Services"

Print-Info "Building and starting RAG service and OpenWeb-UI..."
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Print-Error "Failed to start services"
    exit 1
}

# Wait for services
Print-Info "Waiting for services to start (10 seconds)..."
Start-Sleep -Seconds 10

# Check health
Print-Info "Checking RAG service health..."
try {
    $response = docker-compose exec -T rag-service curl -f http://localhost:8001/health 2>$null
    if ($LASTEXITCODE -eq 0) {
        Print-Success "RAG service is healthy"
    } else {
        Print-Error "RAG service is not responding"
        Write-Host "Check logs with: docker-compose logs rag-service"
        exit 1
    }
} catch {
    Print-Error "Could not verify RAG service"
}

Print-Info "Waiting for OpenWeb-UI to start (30 seconds)..."
Start-Sleep -Seconds 30

# Get ports from .env
$ragPort = 8001
$openwPort = 3000

$envLines = @(Get-Content ".env" | Select-String "^RAG_PORT" | ForEach-Object { $_.ToString() })
if ($envLines) {
    $ragPort = $envLines[0].Split('=')[1].Trim()
}

$envLines = @(Get-Content ".env" | Select-String "^OPENWEB_UI_PORT" | ForEach-Object { $_.ToString() })
if ($envLines) {
    $openwPort = $envLines[0].Split('=')[1].Trim()
}

Print-Header "✓ Services Started Successfully!"

Write-Host ""
Write-Host "Access your services:" -ForegroundColor Green
Write-Host ""
Write-Host "OpenWeb-UI:     http://localhost:$openwPort" -ForegroundColor Green
Write-Host "RAG API:        http://localhost:$ragPort" -ForegroundColor Green
Write-Host "Health Check:   http://localhost:$ragPort/health" -ForegroundColor Green
Write-Host ""

Write-Host "Next steps:" -ForegroundColor Green
Write-Host "1. Open http://localhost:$openwPort in your browser"
Write-Host "2. Confirm the loaded model in OpenWeb-UI"
Write-Host "3. Try asking a question in Thai"
Write-Host ""

Write-Host "Useful commands:" -ForegroundColor Green
Write-Host "  - View logs:       docker-compose logs -f"
Write-Host "  - Stop services:   docker-compose down"
Write-Host "  - Restart:         docker-compose restart"
Write-Host "  - RAG logs:        docker-compose logs -f rag-service"
Write-Host "  - OpenWeb-UI logs: docker-compose logs -f openweb-ui"
Write-Host ""

# Try to open browser
try {
    $response = Read-Host "Open OpenWeb-UI in browser now? (y/n)"
    if ($response -eq "y" -or $response -eq "Y") {
        Start-Process "http://localhost:$openwPort"
    }
} catch {
    # Ignore if can't read input
}

Print-Header "Setup Complete! Happy Chatting! 🚀"
