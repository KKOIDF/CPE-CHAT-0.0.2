param(
  [Parameter(Mandatory=$true)][ValidateSet('announcements','regulations','curriculum')]$Domain,
  [Parameter(Mandatory=$true)][string]$Input,
  [string]$Output = "data/db/$Domain"
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

& $py -m app.main --domain $Domain --input $Input --output $Output
