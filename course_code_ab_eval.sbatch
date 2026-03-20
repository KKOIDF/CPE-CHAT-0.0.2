#!/bin/bash
#SBATCH --job-name=cpe-course-ab
#SBATCH --output=slurm-course-ab-%j.log
#SBATCH --partition=gpu4090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:30:00

set -euo pipefail

echo "=== Host ==="
hostname
date

echo "=== GPU Info ==="
nvidia-smi || true

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
  echo "[ERROR] Virtual environment not found at $REPO_ROOT/.venv or $REPO_ROOT/venv" >&2
  exit 1
fi

echo "=== Python ==="
which python3 || true
python3 -V || true

# Runtime config for deterministic A/B eval.
export CPE_INDEX_ROOT="${CPE_INDEX_ROOT:-$REPO_ROOT/indexes}"
export LLM_ENABLE=0

# Optional: reduce tokenizer parallelism noise in batch logs.
export TOKENIZERS_PARALLELISM=false

echo "=== Run Course-Code A/B Evaluation ==="
python3 "$REPO_ROOT/scripts/course_code_ab_eval.py"

echo "=== Done ==="
date
