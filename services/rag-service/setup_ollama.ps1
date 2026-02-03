# PowerShell script to set up and run RAG service with Ollama + Typhoon 2.5

Write-Host "🚀 Setting up Ollama + Typhoon 2.5 for RAG Service" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Ollama is installed
$ollamaInstalled = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaInstalled) {
    Write-Host "❌ Ollama is not installed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Ollama first:"
    Write-Host "  Download from https://ollama.com/download"
    Write-Host ""
    exit 1
}

Write-Host "✅ Ollama is installed" -ForegroundColor Green
Write-Host ""

# Check if Ollama server is running
try {
    $response = Invoke-WebRequest -Uri "http://localhost:11434" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    Write-Host "✅ Ollama server is running" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Ollama server is not running" -ForegroundColor Yellow
    Write-Host "Please start Ollama manually in another terminal:"
    Write-Host "  ollama serve"
    Write-Host ""
    Write-Host "Or it may start automatically in the background."
    Start-Sleep -Seconds 2
}

Write-Host ""

# Check if model is available
$MODEL = "scb10x/typhoon2.5-qwen3-30b-a3b"
$modelList = ollama list
if ($modelList -notmatch $MODEL) {
    Write-Host "📥 Model '$MODEL' not found" -ForegroundColor Yellow
    Write-Host "Pulling model... (this may take a while)"
    ollama pull $MODEL
} else {
    Write-Host "✅ Model '$MODEL' is available" -ForegroundColor Green
}

Write-Host ""
Write-Host "🔧 Installing Python dependencies..." -ForegroundColor Cyan
pip install -q ollama

Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Environment variables:" -ForegroundColor Cyan
Write-Host "  LLM_ENABLE=1"
Write-Host "  LLM_PROVIDER=ollama"
Write-Host "  LLM_MODEL=$MODEL"
Write-Host "  OLLAMA_BASE_URL=http://localhost:11434"
Write-Host ""
Write-Host "To start the RAG service:" -ForegroundColor Cyan
Write-Host "  `$env:LLM_ENABLE=`"1`""
Write-Host "  `$env:LLM_PROVIDER=`"ollama`""
Write-Host "  `$env:LLM_MODEL=`"$MODEL`""
Write-Host "  python run_server.py"
Write-Host ""
Write-Host "To test the integration:" -ForegroundColor Cyan
Write-Host "  `$env:LLM_ENABLE=`"1`"; `$env:LLM_PROVIDER=`"ollama`"; `$env:LLM_MODEL=`"$MODEL`"; python test_ollama_typhoon.py"
Write-Host ""
