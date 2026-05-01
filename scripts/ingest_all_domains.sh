#!/usr/bin/env bash
set -euo pipefail

ROOT=""
MODE="${INGEST_RUN_MODE:-local}"

usage() {
  cat <<'EOF'
Usage:
  ingest_all_domains.sh [--root <repo_root>]

Defaults:
  --root is the parent directory of this script.

What it does:
  - For each domain in: announcements, regulations, curriculum
  - Looks for supported files under <root>/data/<domain>
  - If found, runs scripts/ingest_domain.sh
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="${2:-}"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$ROOT"
if [[ -z "$REPO_ROOT" ]]; then
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

DOMAINS=("announcements" "regulations" "curriculum")
RUN_TS="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="$REPO_ROOT/reports/ingest_timings"
mkdir -p "$REPORT_DIR"
RUN_SUMMARY_JSON="$REPORT_DIR/${MODE}_all_domains_${RUN_TS}.json"
RUN_SUMMARY_MD="$REPORT_DIR/${MODE}_all_domains_${RUN_TS}.md"

summary_items=()
total_started="$(python3 - <<'PY'
import time
print(time.time())
PY
)"

for d in "${DOMAINS[@]}"; do
  input="$REPO_ROOT/data/raw/$d"
  if [[ ! -d "$input" ]]; then
    echo "[SKIP] $d: missing $input"
    continue
  fi

  # Supported file types: pdf, txt, xlsx, xls, csv, tsv
  count="$(find "$input" -type f \( \
      -iname '*.pdf' -o -iname '*.txt' -o \
      -iname '*.xlsx' -o -iname '*.xls' -o \
      -iname '*.csv' -o -iname '*.tsv' \
    \) 2>/dev/null | wc -l | tr -d '[:space:]')"

  if [[ "${count:-0}" == "0" ]]; then
    echo "[SKIP] $d: no supported files in $input"
    continue
  fi

  echo "[RUN] Ingest domain=$d (files=$count)"
  timing_json="$REPORT_DIR/${MODE}_${d}_${RUN_TS}.json"
  "$SCRIPT_DIR/ingest_domain.sh" --domain "$d" --input "$input" --output "$REPO_ROOT/data/db/$d" --timing-out "$timing_json" --timing-label "${MODE}:${d}"
  summary_items+=("$timing_json")

  # Generate manifest
  mkdir -p "$REPO_ROOT/indexes"
  find "$input" -type f -exec sha256sum {} + | sort > "$REPO_ROOT/indexes/${d}_manifest.txt"
  echo "[DONE] Generated manifest: indexes/${d}_manifest.txt"
done

python3 - <<'PY' "$RUN_SUMMARY_JSON" "$RUN_SUMMARY_MD" "$MODE" "${summary_items[@]}"
import json
import sys
from pathlib import Path

json_out = Path(sys.argv[1])
md_out = Path(sys.argv[2])
mode = sys.argv[3]
paths = [Path(p) for p in sys.argv[4:]]

rows = []
totals = {
    'files': 0,
    'records': 0,
    'chunks': 0,
    'flagged_chunks': 0,
    'embedded_chunks': 0,
    'extract_total_ms': 0.0,
    'chunking_ms': 0.0,
    'db_store_ms': 0.0,
    'structured_artifacts_ms': 0.0,
    'embedding_ms': 0.0,
    'neo4j_ms': 0.0,
    'total_ms': 0.0,
}
for path in paths:
    data = json.loads(path.read_text(encoding='utf-8'))
    rows.append(data)
    counts = data.get('counts', {})
    phase = data.get('phase_ms', {})
    for key in ('files', 'records', 'chunks', 'flagged_chunks', 'embedded_chunks'):
        totals[key] += int(counts.get(key, 0))
    for key in ('extract_total_ms', 'chunking_ms', 'db_store_ms', 'structured_artifacts_ms', 'embedding_ms', 'neo4j_ms'):
        totals[key] += float(phase.get(key, 0.0))
    totals['total_ms'] += float(data.get('total_ms', 0.0))

payload = {
    'mode': mode,
    'generated_at': rows[0].get('generated_at') if rows else '',
    'domains': rows,
    'totals': totals,
}
json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

lines = []
lines.append(f"# Ingestion Timing Summary ({mode})")
lines.append("")
lines.append("| Domain | Files | Records | Chunks | Embedded | Extract ms | Chunking ms | DB ms | Embedding ms | Total ms |")
lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for row in rows:
    counts = row.get('counts', {})
    phase = row.get('phase_ms', {})
    lines.append(
        f"| `{row.get('domain','')}` | {int(counts.get('files',0))} | {int(counts.get('records',0))} | "
        f"{int(counts.get('chunks',0))} | {int(counts.get('embedded_chunks',0))} | "
        f"{float(phase.get('extract_total_ms',0.0)):.2f} | {float(phase.get('chunking_ms',0.0)):.2f} | "
        f"{float(phase.get('db_store_ms',0.0)):.2f} | {float(phase.get('embedding_ms',0.0)):.2f} | "
        f"{float(row.get('total_ms',0.0)):.2f} |"
    )
lines.append("")
lines.append("## Totals")
lines.append("")
lines.append("| Metric | Value |")
lines.append("|---|---:|")
for key in ('files','records','chunks','flagged_chunks','embedded_chunks','extract_total_ms','chunking_ms','db_store_ms','structured_artifacts_ms','embedding_ms','neo4j_ms','total_ms'):
    val = totals[key]
    if isinstance(val, float):
        lines.append(f"| `{key}` | {val:.2f} |")
    else:
        lines.append(f"| `{key}` | {val} |")
md_out.write_text("\n".join(lines) + "\n", encoding='utf-8')
print(f"Wrote {json_out}")
print(f"Wrote {md_out}")
PY
