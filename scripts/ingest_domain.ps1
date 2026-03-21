param(
  [Parameter(Mandatory=$true)][ValidateSet('announcements','regulations','curriculum')]$Domain,
  [Parameter(Mandatory=$true)][string]$InputPath,
  [string]$Output = "data/db/$Domain",
  # Embedding device: 'cuda' (use NVIDIA GPU), 'cpu' (force CPU), or 'auto'
  [ValidateSet('cuda','cpu','auto')][string]$EmbedDevice = 'cuda'
)

$repo = Split-Path -Parent $PSScriptRoot
$svc = Join-Path $repo "services\ingestion-service"

$py = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  $py = "python"
}

$env:CPE_DOMAIN = $Domain
$env:CPE_INDEX_ROOT = (Join-Path $repo "indexes")
$env:PYTHONPATH = $svc

# Embeddings on GPU (requires CUDA-enabled torch in the selected Python env)
$env:EMBED_DEVICE = $EmbedDevice

# Avoid UnicodeEncodeError on Windows terminals when scripts print Thai/emoji
$env:PYTHONUTF8 = '1'

Write-Host "[PY] Using: $py"
& $py -c "import sys; print('[PY] sys.executable=', sys.executable)"
& $py -c "
try:
  import torch
  print('[PY] torch=', torch.__version__)
  print('[PY] cuda_available=', torch.cuda.is_available())
  if torch.cuda.is_available():
    print('[PY] gpu=', torch.cuda.get_device_name(0))
except Exception as e:
  print('[PY] torch check skipped:', e)
"

& $py -m app.main --domain $Domain --input $InputPath --output $Output
