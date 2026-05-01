#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ingest_domain.sh --domain <announcements|regulations|curriculum> --input <path> [--output <path>]

Environment:
  - CPE_INDEX_ROOT will be set to <repo>/indexes
  - PYTHONPATH will include <repo>/services/ingestion-service
EOF
}

DOMAIN=""
INPUT_PATH=""
OUTPUT=""
TIMING_OUT=""
TIMING_LABEL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--domain)
      DOMAIN="${2:-}"; shift 2 ;;
    -i|--input|--input-path)
      INPUT_PATH="${2:-}"; shift 2 ;;
    -o|--output)
      OUTPUT="${2:-}"; shift 2 ;;
    --timing-out)
      TIMING_OUT="${2:-}"; shift 2 ;;
    --timing-label)
      TIMING_LABEL="${2:-}"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

DOMAIN="$(echo "${DOMAIN}" | tr '[:upper:]' '[:lower:]')"
if [[ -z "$DOMAIN" || -z "$INPUT_PATH" ]]; then
  echo "[ERROR] --domain and --input are required" >&2
  usage
  exit 2
fi

case "$DOMAIN" in
  announcements|regulations|curriculum) ;;
  *)
    echo "[ERROR] Invalid domain: $DOMAIN" >&2
    exit 2
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SVC_DIR="$REPO_ROOT/services/ingestion-service"

if [[ -z "$OUTPUT" ]]; then
  OUTPUT="$REPO_ROOT/data/db/$DOMAIN"
fi

PY="$REPO_ROOT/venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$REPO_ROOT/.venv/bin/python"
fi
if [[ ! -x "$PY" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PY="python3"
  else
    PY="python"
  fi
fi

export CPE_DOMAIN="$DOMAIN"
export CPE_INDEX_ROOT="$REPO_ROOT/indexes"
export PYTHONPATH="$SVC_DIR${PYTHONPATH:+:$PYTHONPATH}"
if [[ -z "$TIMING_OUT" ]]; then
  ts="$(date +%Y%m%d_%H%M%S)"
  TIMING_OUT="$REPO_ROOT/reports/ingest_timings/${DOMAIN}_${ts}.json"
fi
if [[ -z "$TIMING_LABEL" ]]; then
  TIMING_LABEL="local:${DOMAIN}"
fi

"$PY" -m app.main --domain "$DOMAIN" --input "$INPUT_PATH" --output "$OUTPUT" --langchain --timing-out "$TIMING_OUT" --timing-label "$TIMING_LABEL"
