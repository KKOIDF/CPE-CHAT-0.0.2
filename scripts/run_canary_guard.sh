#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
INPUT="${INPUT:-eval_cases.json}"
TIMEOUT="${TIMEOUT:-120}"
LIMIT="${LIMIT:-40}"
OUTPUT_PREFIX="${OUTPUT_PREFIX:-qball_canary_guard}"
BASELINE="${BASELINE:-reports/baseline_canary_10pct.json}"

# Keep these conservative for canary hold/continue automation.
GATE_OVERALL_DROP_PCT="${GATE_OVERALL_DROP_PCT:-0}"
GATE_CITATION_DROP_PCT="${GATE_CITATION_DROP_PCT:-0}"
GATE_P95_INCREASE_PCT="${GATE_P95_INCREASE_PCT:-15}"
GATE_PROTECTED_CATEGORIES="${GATE_PROTECTED_CATEGORIES:-announcements_schedule,multi_intent_multi_doc,regulations}"

# Canary-specific production guardrails.
PROD_MIN_ANSWER_HIT_RATE="${PROD_MIN_ANSWER_HIT_RATE:-0.80}"
PROD_MIN_RETRIEVAL_HIT_RATE="${PROD_MIN_RETRIEVAL_HIT_RATE:-0.85}"
PROD_MIN_CITATION_VALIDITY_RATE="${PROD_MIN_CITATION_VALIDITY_RATE:-0.95}"
PROD_MIN_CITATION_PRECISION="${PROD_MIN_CITATION_PRECISION:-0.90}"
PROD_MIN_CITATION_RECALL="${PROD_MIN_CITATION_RECALL:-0.80}"
PROD_MAX_HALLUCINATION_RATE="${PROD_MAX_HALLUCINATION_RATE:-0.05}"
PROD_MIN_MUST_NOT_CONTAIN_PASS_RATE="${PROD_MIN_MUST_NOT_CONTAIN_PASS_RATE:-0.95}"
PROD_MAX_P95_LATENCY_MS="${PROD_MAX_P95_LATENCY_MS:-1400}"
PROD_DOMAIN_MAX_P95_LATENCY_MS="${PROD_DOMAIN_MAX_P95_LATENCY_MS:-announcements=1400,regulations=2500,curriculum=2000,multi=2200}"

echo "[canary-guard] base_url=${BASE_URL} baseline=${BASELINE}"
set +e
python3 eval_runner.py \
  --input "${INPUT}" \
  --base-url "${BASE_URL}" \
  --timeout "${TIMEOUT}" \
  --limit "${LIMIT}" \
  --preflight-health \
  --output-prefix "${OUTPUT_PREFIX}" \
  --compare-baseline "${BASELINE}" \
  --gate-overall-drop-pct "${GATE_OVERALL_DROP_PCT}" \
  --gate-citation-drop-pct "${GATE_CITATION_DROP_PCT}" \
  --gate-p95-increase-pct "${GATE_P95_INCREASE_PCT}" \
  --gate-protected-categories "${GATE_PROTECTED_CATEGORIES}" \
  --production-gate \
  --prod-min-overall-pass-rate 0 \
  --prod-min-answer-hit-rate "${PROD_MIN_ANSWER_HIT_RATE}" \
  --prod-min-retrieval-hit-rate "${PROD_MIN_RETRIEVAL_HIT_RATE}" \
  --prod-min-citation-validity-rate "${PROD_MIN_CITATION_VALIDITY_RATE}" \
  --prod-min-citation-precision "${PROD_MIN_CITATION_PRECISION}" \
  --prod-min-citation-recall "${PROD_MIN_CITATION_RECALL}" \
  --prod-max-hallucination-rate "${PROD_MAX_HALLUCINATION_RATE}" \
  --prod-min-must-not-contain-pass-rate "${PROD_MIN_MUST_NOT_CONTAIN_PASS_RATE}" \
  --prod-max-p95-latency-ms "${PROD_MAX_P95_LATENCY_MS}" \
  --prod-max-p95-retrieval-latency-ms 5000 \
  --prod-category-min-overall-pass-rate "" \
  --prod-domain-min-overall-pass-rate "" \
  --prod-domain-max-p95-latency-ms "${PROD_DOMAIN_MAX_P95_LATENCY_MS}"
eval_status=$?
set -e

# Single-line CI decision output for direct rollout gating.
if [[ "${eval_status}" -eq 0 ]]; then
  echo "CI_ROLLOUT_DECISION=continue"
elif [[ "${eval_status}" -eq 1 ]]; then
  echo "CI_ROLLOUT_DECISION=hold"
else
  echo "CI_ROLLOUT_DECISION=hold"
fi

exit "${eval_status}"
