#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
INPUT="${INPUT:-eval_cases.json}"
TIMEOUT="${TIMEOUT:-120}"
BASELINE="${BASELINE:-reports/baseline_92f33ef.json}"
OVERALL_DROP_PCT="${GATE_OVERALL_DROP_PCT:-3}"
CITATION_DROP_PCT="${GATE_CITATION_DROP_PCT:-0}"
P95_INCREASE_PCT="${GATE_P95_INCREASE_PCT:-25}"
PROTECTED="${GATE_PROTECTED_CATEGORIES:-curriculum_fact_lookup,regulations}"

python3 eval_runner.py \
  --input "${INPUT}" \
  --base-url "${BASE_URL}" \
  --timeout "${TIMEOUT}" \
  --compare-baseline "${BASELINE}" \
  --gate-overall-drop-pct "${OVERALL_DROP_PCT}" \
  --gate-citation-drop-pct "${CITATION_DROP_PCT}" \
  --gate-p95-increase-pct "${P95_INCREASE_PCT}" \
  --gate-protected-categories "${PROTECTED}"
