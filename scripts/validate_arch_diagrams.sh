#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DOCS_DIR="$ROOT_DIR/docs"
RENDER_DIR="$DOCS_DIR/rendered"

RENDER=0
if [[ "${1:-}" == "--render" ]]; then
  RENDER=1
fi

mapfile -t PUML_FILES < <(find "$DOCS_DIR" -maxdepth 1 -type f -name "*.puml" | sort)
mapfile -t DIAGRAM_FILES < <(
  for f in "${PUML_FILES[@]}"; do
    if grep -qi "@startuml" "$f"; then
      echo "$f"
    fi
  done
)
if [[ ${#DIAGRAM_FILES[@]} -eq 0 ]]; then
  echo "No .puml files found under $DOCS_DIR"
  exit 1
fi

echo "Found ${#DIAGRAM_FILES[@]} diagram PUML files"

run_plantuml() {
  local args=("$@")
  if command -v plantuml >/dev/null 2>&1; then
    plantuml "${args[@]}"
  else
    docker run --rm \
      -v "$ROOT_DIR:/workspace" \
      -w /workspace \
      plantuml/plantuml:latest \
      "${args[@]}"
  fi
}

echo "[1/2] Syntax check (.puml)"
run_plantuml -checkonly "${DIAGRAM_FILES[@]#$ROOT_DIR/}"

echo "Syntax check passed"

if [[ $RENDER -eq 1 ]]; then
  echo "[2/2] Render SVG diagrams"
  mkdir -p "$RENDER_DIR"
  # -o path is relative to each input file directory.
  run_plantuml -tsvg -o rendered "${DIAGRAM_FILES[@]#$ROOT_DIR/}"
  echo "Rendered SVG files to $RENDER_DIR"
fi
