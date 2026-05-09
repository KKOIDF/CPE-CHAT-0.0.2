#!/bin/bash
#SBATCH --job-name=cpe-ingest-all
#SBATCH --output=slurm-ingest-%j.log
#SBATCH --partition=gpu3060
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00

set -euo pipefail

echo "=== Host ==="
hostname
date

echo "=== GPU Info ==="
nvidia-smi || true

# Slurm may execute a staged copy of this script under /var/spool/slurmd.
# Prefer submit directory, with explicit override support.
REPO_ROOT="${CPE_REPO_ROOT:-${SLURM_SUBMIT_DIR:-$PWD}}"
REPO_ROOT="$(cd "$REPO_ROOT" && pwd)"

echo "=== Repo Root ==="
echo "$REPO_ROOT"

cd "$REPO_ROOT"

if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  source "$REPO_ROOT/.venv/bin/activate"
elif [[ -f "$REPO_ROOT/venv/bin/activate" ]]; then
  source "$REPO_ROOT/venv/bin/activate"
else
  echo "[INFO] Remote virtual environment not found. Bootstrapping at $REPO_ROOT/.venv..."
  python3 -m venv "$REPO_ROOT/.venv"
  source "$REPO_ROOT/.venv/bin/activate"
  pip install --upgrade pip
  pip install -r "$REPO_ROOT/services/ingestion-service/requirements.txt" || true
fi

echo "=== Python ==="
which python3 || true
python3 -V || true

echo "=== Run Ingest All Domains ==="
bash "$REPO_ROOT/scripts/ingest_all_domains.sh" --root "$REPO_ROOT"
