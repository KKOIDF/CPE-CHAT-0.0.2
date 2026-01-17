param(
  [Parameter(Mandatory=$true)][ValidateSet('announcements','regulations','curriculum')]$Domain,
  [Parameter(Mandatory=$true)][string]$Input,
  [string]$Output = "data/db/$Domain"
)

$repo = Split-Path -Parent $PSScriptRoot
$svc = Join-Path $repo "services\ingestion-service"

$env:CPE_DOMAIN = $Domain
$env:CPE_INDEX_ROOT = (Join-Path $repo "indexes")
$env:PYTHONPATH = $svc

python -m app.main --domain $Domain --input $Input --output $Output
