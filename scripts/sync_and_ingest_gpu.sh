#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${1:-}" ]]; then
  echo "Usage: $0 <user@gpu-cluster-host>"
  echo "Example: $0 student@gpu.university.edu"
  exit 1
fi

REMOTE_HOST="$1"
REMOTE_DIR="~/cpe-chat-ingest-sync"
RUN_TS="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="./reports/ingest_timings"
mkdir -p "$REPORT_DIR"
LOCAL_TIMING_JSON="$REPORT_DIR/gpu_host_transfer_${RUN_TS}.json"
LOCAL_TIMING_MD="$REPORT_DIR/gpu_host_transfer_${RUN_TS}.md"

now_ms() {
  python3 - <<'PY'
import time
print(time.time() * 1000.0)
PY
}

echo "=== 1. Syncing local repository to $REMOTE_HOST:$REMOTE_DIR ==="
sync_started="$(now_ms)"
# Notice we exclude venvs/builds because binaries are platform-dependent
rsync -avz --exclude '.git' --exclude 'venv' --exclude '.venv' \
  --exclude '__pycache__' --exclude 'indexes' --exclude 'data/db' \
  ./ "$REMOTE_HOST:$REMOTE_DIR/"
sync_finished="$(now_ms)"

echo "=== 2. Submitting SLURM job on Remote GPU ==="
remote_started="$(now_ms)"
ssh "$REMOTE_HOST" "cd $REMOTE_DIR && INGEST_RUN_MODE=gpu_host sbatch --wait ingest_all_domains.sbatch"
remote_finished="$(now_ms)"

echo "=== 3. Pulling generated indexes and databases back ==="
pull_started="$(now_ms)"
mkdir -p ./indexes ./data/db
rsync -avz "$REMOTE_HOST:$REMOTE_DIR/indexes/" ./indexes/
rsync -avz "$REMOTE_HOST:$REMOTE_DIR/data/db/" ./data/db/
rsync -avz "$REMOTE_HOST:$REMOTE_DIR/reports/ingest_timings/" "$REPORT_DIR/" || true
pull_finished="$(now_ms)"

echo "=== Done! GPU Ingestion synchronized successfully. ==="

python3 - <<'PY' "$LOCAL_TIMING_JSON" "$LOCAL_TIMING_MD" "$REMOTE_HOST" "$sync_started" "$sync_finished" "$remote_started" "$remote_finished" "$pull_started" "$pull_finished"
import json
import sys
from pathlib import Path

json_out = Path(sys.argv[1])
md_out = Path(sys.argv[2])
remote_host = sys.argv[3]
sync_started = float(sys.argv[4]); sync_finished = float(sys.argv[5])
remote_started = float(sys.argv[6]); remote_finished = float(sys.argv[7])
pull_started = float(sys.argv[8]); pull_finished = float(sys.argv[9])

payload = {
    'mode': 'gpu_host_transfer',
    'remote_host': remote_host,
    'phase_ms': {
        'sync_to_remote_ms': round(sync_finished - sync_started, 3),
        'remote_job_wait_ms': round(remote_finished - remote_started, 3),
        'pull_back_ms': round(pull_finished - pull_started, 3),
        'total_ms': round(pull_finished - sync_started, 3),
    }
}
json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
md_out.write_text(
    "# GPU Host Transfer Timing Summary\n\n"
    "| Phase | Time (ms) |\n|---|---:|\n"
    f"| sync_to_remote | {payload['phase_ms']['sync_to_remote_ms']:.2f} |\n"
    f"| remote_job_wait | {payload['phase_ms']['remote_job_wait_ms']:.2f} |\n"
    f"| pull_back | {payload['phase_ms']['pull_back_ms']:.2f} |\n"
    f"| total | {payload['phase_ms']['total_ms']:.2f} |\n",
    encoding='utf-8',
)
print(f"Wrote {json_out}")
print(f"Wrote {md_out}")
PY
