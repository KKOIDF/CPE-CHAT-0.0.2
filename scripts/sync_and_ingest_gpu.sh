#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${1:-}" ]]; then
  echo "Usage: $0 <user@gpu-cluster-host>"
  echo "Example: $0 student@gpu.university.edu"
  exit 1
fi

REMOTE_HOST="$1"
REMOTE_DIR="~/cpe-chat-ingest-sync"

echo "=== 1. Syncing local repository to $REMOTE_HOST:$REMOTE_DIR ==="
# Notice we exclude venvs/builds because binaries are platform-dependent
rsync -avz --exclude '.git' --exclude 'venv' --exclude '.venv' \
  --exclude '__pycache__' --exclude 'indexes' --exclude 'data/db' \
  ./ "$REMOTE_HOST:$REMOTE_DIR/"

echo "=== 2. Submitting SLURM job on Remote GPU ==="
ssh "$REMOTE_HOST" "cd $REMOTE_DIR && sbatch --wait ingest_all_domains.sbatch"

echo "=== 3. Pulling generated indexes and databases back ==="
mkdir -p ./indexes ./data/db
rsync -avz "$REMOTE_HOST:$REMOTE_DIR/indexes/" ./indexes/
rsync -avz "$REMOTE_HOST:$REMOTE_DIR/data/db/" ./data/db/

echo "=== Done! GPU Ingestion synchronized successfully. ==="
