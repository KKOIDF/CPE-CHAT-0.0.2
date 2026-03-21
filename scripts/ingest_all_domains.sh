#!/usr/bin/env bash
set -euo pipefail

ROOT=""

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

for d in "${DOMAINS[@]}"; do
  input="$REPO_ROOT/data/$d"
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
  "$SCRIPT_DIR/ingest_domain.sh" --domain "$d" --input "$input" --output "$REPO_ROOT/data/db/$d"
done
