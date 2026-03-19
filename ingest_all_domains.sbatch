#!/bin/bash
#SBATCH --job-name=cpe-ingest
#SBATCH --output=slurm-%j.log
#SBATCH --partition=GPU03
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00

set -euo pipefail

echo "=== Host ==="
hostname
date

echo "=== GPU Info ==="
nvidia-smi

# Repository root: override REPO_ROOT env var if needed, or default to the
# directory that contains this .sbatch file.
REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "$0")" && pwd)}"

# Activate virtual environment
source "$REPO_ROOT/.venv/bin/activate"

echo "=== Python ==="
which python3
python3 -V

echo "=== Run Ingest All Domains ==="
bash "$REPO_ROOT/scripts/ingest_all_domains.sh" "$REPO_ROOT"
