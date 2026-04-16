#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
INPUT="${INPUT:-eval_cases.json}"
TIMEOUT="${TIMEOUT:-120}"
LIMIT="${LIMIT:-40}"
BASELINE_PATH="${BASELINE_PATH:-reports/baseline_canary_10pct.json}"

SMOKE_A_PREFIX="${SMOKE_A_PREFIX:-qball_week2_smoke_a}"
SMOKE_B_PREFIX="${SMOKE_B_PREFIX:-qball_week2_smoke_b}"
REFRESH_PREFIX="${REFRESH_PREFIX:-qball_week2_baseline_refresh}"

echo "[week2] smoke run A"
BASE_URL="${BASE_URL}" INPUT="${INPUT}" TIMEOUT="${TIMEOUT}" LIMIT="${LIMIT}" OUTPUT_PREFIX="${SMOKE_A_PREFIX}" BASELINE="${BASELINE_PATH}" \
  bash scripts/run_canary_guard.sh

echo "[week2] smoke run B"
BASE_URL="${BASE_URL}" INPUT="${INPUT}" TIMEOUT="${TIMEOUT}" LIMIT="${LIMIT}" OUTPUT_PREFIX="${SMOKE_B_PREFIX}" BASELINE="${BASELINE_PATH}" \
  bash scripts/run_canary_guard.sh

echo "[week2] ranking robustness check"
python3 scripts/check_ranking_robustness.py --report-json "${SMOKE_B_PREFIX}.json"

GIT_SHA="${BASELINE_COMMIT:-$(git rev-parse --short HEAD 2>/dev/null || echo week2)}"
echo "[week2] refresh baseline from commit=${GIT_SHA}"
python3 eval_runner.py \
  --input "${INPUT}" \
  --base-url "${BASE_URL}" \
  --timeout "${TIMEOUT}" \
  --limit "${LIMIT}" \
  --preflight-health \
  --output-prefix "${REFRESH_PREFIX}" \
  --baseline-commit "${GIT_SHA}" \
  --production-gate \
  --prod-min-overall-pass-rate 0 \
  --prod-min-answer-hit-rate 0.80 \
  --prod-min-retrieval-hit-rate 0.85 \
  --prod-min-citation-validity-rate 0.95 \
  --prod-min-citation-precision 0.90 \
  --prod-min-citation-recall 0.80 \
  --prod-max-hallucination-rate 0.05 \
  --prod-min-must-not-contain-pass-rate 0.95 \
  --prod-max-p95-latency-ms 1400 \
  --prod-max-p95-retrieval-latency-ms 5000 \
  --prod-category-min-overall-pass-rate "" \
  --prod-domain-min-overall-pass-rate "" \
  --prod-domain-max-p95-latency-ms "announcements=1400,regulations=2500,curriculum=2000,multi=2200"

BASE_SHORT="$(printf '%s' "${GIT_SHA}" | cut -c1-7)"
SRC_JSON="reports/baseline_${BASE_SHORT}.json"
SRC_MD="reports/baseline_${BASE_SHORT}.md"
if [[ -f "${SRC_JSON}" ]]; then
  cp "${SRC_JSON}" "${BASELINE_PATH}"
  echo "[week2] updated baseline json: ${BASELINE_PATH}"
fi
if [[ -f "${SRC_MD}" ]]; then
  cp "${SRC_MD}" "reports/baseline_canary_10pct.md"
  echo "[week2] updated baseline md: reports/baseline_canary_10pct.md"
fi

echo "[week2] completed"
