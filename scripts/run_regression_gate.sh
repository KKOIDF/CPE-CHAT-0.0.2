#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
INPUT="${INPUT:-scripts/regression_gate_50.csv}"
TIMEOUT="${TIMEOUT:-120}"
SIM_THRESHOLD="${SIM_THRESHOLD:-0.45}"
GATE_MIN_EXACTNESS="${GATE_MIN_EXACTNESS:-0.70}"
GATE_MIN_CITATION_VALIDITY="${GATE_MIN_CITATION_VALIDITY:-0.90}"
GATE_MAX_LATENCY_P95="${GATE_MAX_LATENCY_P95:-12000}"
GATE_REQUIRED_GROUPS="${GATE_REQUIRED_GROUPS:-curriculum_fact_lookup,prerequisite_course_code,regulations_clause_query,multi_doc_multi_intent,announcement_schedule}"
GATE_MIN_CASES_PER_GROUP="${GATE_MIN_CASES_PER_GROUP:-8}"

echo "[regression-gate] Running eval against ${BASE_URL}"
python3 scripts/eval_testqa_csv_live_v2.py \
  --input "${INPUT}" \
  --base-url "${BASE_URL}" \
  --timeout "${TIMEOUT}" \
  --sim-threshold "${SIM_THRESHOLD}" \
  --require-citations \
  --gate-min-exactness "${GATE_MIN_EXACTNESS}" \
  --gate-min-citation-validity "${GATE_MIN_CITATION_VALIDITY}" \
  --gate-max-latency-p95 "${GATE_MAX_LATENCY_P95}" \
  --gate-required-groups "${GATE_REQUIRED_GROUPS}" \
  --gate-min-cases-per-group "${GATE_MIN_CASES_PER_GROUP}"
