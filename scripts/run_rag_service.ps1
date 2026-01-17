param(
  [int]$Port = 8001
)

$repo = Split-Path -Parent $PSScriptRoot
$svc = Join-Path $repo "services\rag-service"

Push-Location $svc
try {
  $env:PYTHONPATH = "app"
  python -c "import uvicorn; uvicorn.run('app.main:app', host='127.0.0.1', port=$Port, timeout_keep_alive=60)"
} finally {
  Pop-Location
}
