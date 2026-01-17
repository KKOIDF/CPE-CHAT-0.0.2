param(
  [string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$repo = $Root
$domains = @('announcements','regulations','curriculum')

foreach ($d in $domains) {
  $input = Join-Path $repo ("data\" + $d)
  if (-not (Test-Path $input)) {
    Write-Host "[SKIP] $d: missing $input"
    continue
  }

  $files = Get-ChildItem -Path $input -Recurse -File -Include *.pdf,*.xlsx,*.xls,*.csv,*.tsv -ErrorAction SilentlyContinue
  if (-not $files -or $files.Count -eq 0) {
    Write-Host "[SKIP] $d: no supported files in $input"
    continue
  }

  Write-Host "[RUN] Ingest domain=$d (files=$($files.Count))"
  & (Join-Path $PSScriptRoot "ingest_domain.ps1") -Domain $d -Input $input -Output ("data/db/" + $d)
}
