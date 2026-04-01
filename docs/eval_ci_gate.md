# Eval CI Gate (QBall)

This document defines a deterministic evaluation flow for the 342-case qball set and a simple regression gate.

## Dataset and Baseline

- Dataset: `data/question_bank_250_general_th.json`
- Baseline report: `reports/eval_runner_qball_20260331_155326.json`

## 1) Run Full Eval

```bash
python3 eval_runner.py \
  --input data/question_bank_250_general_th.json \
  --base-url http://127.0.0.1:8011 \
  --timeout 120 \
  --output-prefix qball_ci
```

## 2) Regression Gate Against Baseline

```bash
python3 eval_runner.py \
  --input data/question_bank_250_general_th.json \
  --base-url http://127.0.0.1:8011 \
  --timeout 120 \
  --output-prefix qball_ci_gate \
  --compare-baseline reports/eval_runner_qball_20260331_155326.json \
  --gate-overall-drop-pct 3 \
  --gate-citation-drop-pct 0 \
  --gate-p95-increase-pct 25 \
  --gate-protected-categories curriculum_fact_lookup,regulations
```

## 3) Compare Candidate Report Quickly

```bash
python3 scripts/eval_compare.py \
  --baseline reports/eval_runner_qball_20260331_155326.json \
  --candidate qball_phase3_schema_enforced.json \
  --top-n 20 \
  --out reports/qball_phase3_compare.json
```

## Suggested Operational Checks

- No new `runtime_error` cases.
- `retrieve_found_but_answer_incomplete` should not regress.
- `retrieve_not_found` should not regress.
- Citation validity should stay stable.

## Rollback Criteria

Rollback immediately if any of the following occur:

- New `runtime_error` cases appear in qball.
- `retrieve_found_but_answer_incomplete` increases by more than 3 cases.
- `retrieve_not_found` increases by more than 3 cases.
- Overall pass rate drops by more than 0.01 absolute.
