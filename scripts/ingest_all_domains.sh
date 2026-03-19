#!/bin/bash
# Bash equivalent of ingest_all_domains.ps1
# Ingests all supported domains (announcements, regulations, curriculum)
# into their respective vector/SQLite indexes.
#
# Usage: bash scripts/ingest_all_domains.sh [REPO_ROOT]
#   REPO_ROOT defaults to the parent directory of this script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${1:-$(dirname "$SCRIPT_DIR")}"

SVC="$REPO/services/ingestion-service"

# Resolve python: prefer venv, fall back to system python3
if [ -f "$REPO/.venv/bin/python" ]; then
  PY="$REPO/.venv/bin/python"
else
  PY="python3"
fi

export CPE_INDEX_ROOT="$REPO/indexes"
export PYTHONPATH="$SVC"

DOMAINS=("announcements" "regulations" "curriculum")

for DOMAIN in "${DOMAINS[@]}"; do
  INPUT="$REPO/data/$DOMAIN"

  if [ ! -d "$INPUT" ]; then
    echo "[SKIP] ${DOMAIN}: missing $INPUT"
    continue
  fi

  # Count supported files
  FILE_COUNT=$(find "$INPUT" -type f \( -iname "*.pdf" -o -iname "*.xlsx" -o -iname "*.xls" -o -iname "*.csv" -o -iname "*.tsv" \) 2>/dev/null | wc -l)
  if [ "$FILE_COUNT" -eq 0 ]; then
    echo "[SKIP] ${DOMAIN}: no supported files in $INPUT"
    continue
  fi

  echo "[RUN] Ingest domain=$DOMAIN (files=$FILE_COUNT)"
  export CPE_DOMAIN="$DOMAIN"
  "$PY" -m app.main --domain "$DOMAIN" --input "$INPUT" --output "$REPO/data/db/$DOMAIN"
done
