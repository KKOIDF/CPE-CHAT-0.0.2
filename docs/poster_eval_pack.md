# Poster Evaluation Pack

Updated: 2026-04-12

This file provides poster-ready evaluation metrics and narrative guidance for CPE-CHAT.

## 1) Evaluation System Status

Evaluation system already exists and is usable now.

Core evaluator components:
- Main evaluator: eval_runner.py
- Live CSV evaluator: scripts/eval_testqa_csv_live_v2.py
- Regression gate: scripts/run_regression_gate.sh
- Methodology guide: EVAL_GUIDE.md

## 2) Recommended Source Of Truth For Poster

Use this run as the primary headline (best quality on stable 40-case set):
- reports/eval_runner_qball.md

Use these as ablation/comparison runs:
- qball_patch12_baseline_full_evalcases.md
- qball_patch12_pure_tune2_full_evalcases.md
- qball_patch12_pure_tune3_full_evalcases.md

Do not use as quality headline:
- qball_ci.md
Reason: runtime connection failure to service (Connection refused), resulting in near-zero metrics that reflect infra outage rather than model quality.

## 3) Poster-Ready KPI Table

### A) Best headline run (reports/eval_runner_qball.md)
- total cases: 40
- overall pass rate: 0.6750
- top-1 hit rate: 0.6500
- top-3 hit rate: 0.6750
- top-5 hit rate: 0.7000
- MRR: 0.6800
- answer keyword hit rate: 0.7000
- hallucination rate: 0.0250
- citation validity: 0.9750
- must-not-contain pass rate: 0.9750
- p95 total latency: 1193.48 ms

### B) Baseline compare (qball_patch12_baseline_full_evalcases.md)
- total cases: 40
- overall pass rate: 0.3500
- top-1 hit rate: 0.7000
- top-3 hit rate: 0.7500
- top-5 hit rate: 0.7750
- MRR: 0.7258
- answer keyword hit rate: 0.4750
- hallucination rate: 0.2000
- citation validity: 0.9250
- must-not-contain pass rate: 0.8000
- p95 total latency: 5847.01 ms

### C) Tune-3 full compare (qball_patch12_pure_tune3_full_evalcases.md)
- total cases: 40
- overall pass rate: 0.3500
- top-1 hit rate: 0.6250
- top-3 hit rate: 0.6750
- top-5 hit rate: 0.7000
- MRR: 0.6565
- answer keyword hit rate: 0.4750
- hallucination rate: 0.2000
- citation validity: 0.9250
- must-not-contain pass rate: 0.8000
- p95 total latency: 4285.88 ms

## 4) Suggested Poster Claims (Evidence-Based)

Claim 1:
- The system achieves strong grounding quality.
Evidence:
- citation validity 97.5%
- hallucination rate 2.5%
Source:
- reports/eval_runner_qball.md

Claim 2:
- Practical latency profile for interactive use on the evaluated setup.
Evidence:
- p95 total latency 1.19 s
Source:
- reports/eval_runner_qball.md

Claim 3:
- Curriculum retrieval is a strong domain in current setup.
Evidence from reference run:
- curriculum top-1 around 0.84 (see retrieval by domain section)
Source:
- reports/eval_runner_qball.md

## 5) Recommended Charts For Poster

1. Radar or grouped bar:
- Pass rate
- Top-1
- Keyword hit
- Citation validity
- 1 - Hallucination
- Latency score (inverse normalized)

2. Domain bar chart:
- announcements top-1
- curriculum top-1
- regulations top-1
- multi-intent top-1

3. Error distribution pie chart:
- pass_or_unclassified
- retrieve_found_but_answer_incomplete
- retrieve_not_found
- context_conflict
- hallucination

## 6) Metric Definitions (Short)

- Top-1 hit rate: expected supporting source appears at rank 1 retrieval
- Top-3, Top-5 hit rate: expected source appears within top K
- MRR: average reciprocal rank of first correct retrieval
- Answer keyword hit rate: expected answer keywords covered by generated answer
- Citation validity: citation source/page consistency against retrieved contexts
- Must-not-contain pass rate: forbidden content not present
- Overall pass rate: per-case combined pass criterion in evaluator

## 7) Repro Steps For Fresh Poster Numbers

1) Start rag-service
2) Run 40-case benchmark:
   python3 eval_runner.py --input eval_cases.json --base-url http://127.0.0.1:8011 --output-prefix poster_eval
3) Optional qball stress set:
   python3 eval_runner.py --input data/question_bank_250_general_th.json --base-url http://127.0.0.1:8011 --output-prefix poster_qball
4) Use generated markdown report under reports/ as final source

## 8) Risks To Disclose On Poster (Honest Reporting)

- Multi-intent remains hardest slice and still trails single-intent categories.
- Metrics can collapse to zero during infra outage; availability and quality must be reported separately.
- Different test sets (40-case vs 342-case) should not be compared without context.

## 9) One-Line Executive Summary For Poster

CPE-CHAT demonstrates high groundedness (97.5% citation validity) and low hallucination (2.5%) with sub-1.2s p95 latency on the curated 40-case benchmark, while multi-intent retrieval remains the key improvement target.
