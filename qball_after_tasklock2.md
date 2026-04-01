# Regression Eval Summary

Generated: 2026-03-31T20:33:56.448757
Input: /tmp/eval_cases_qball_342.json
Base URL: http://127.0.0.1:8011

## Headline

- total cases: 342
- overall pass rate: 0.2690

### Retrieval Metrics
- top-1 hit rate: 0.5029
- top-3 hit rate: 0.7135
- top-5 hit rate: 0.7690
- top-K hit rate: 0.8304
- mean reciprocal rank (mrr): 0.6160

### Answer Quality Metrics
- answer keyword hit rate: 0.2895
- average quality score (1-5): 0.0000
- % correct answers: 0.2895
- % hallucination: 0.0000
- % answerable handled correctly: 0.3070
- citation validity (groundedness): 0.9737
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 2456.05
- median total latency ms: 891.36
- p95 total latency ms: 8878.20
- avg retrieval latency ms: 1719.33
- median retrieval latency ms: 926.05
- p95 retrieval latency ms: 4537.01
- avg generation latency ms: 2450.92
- median generation latency ms: 2157.47
- p95 generation latency ms: 6918.76

## Coverage

- total questions: 342
- questions by domain: announcements=157, curriculum=101, regulations=81, unknown=3
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=157, top1=0.3567, top3=0.5796, top5=0.6815, mrr=0.4930
- curriculum: total=101, top1=0.6535, top3=0.9505, top5=0.9604, mrr=0.7908
- regulations: total=81, top1=0.5802, top3=0.6667, top5=0.6914, mrr=0.6223
- unknown: total=3, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000

## By Category

- uncategorized: total=342, overall=0.2690, answer=0.2895, retrieval=0.8304, top1=0.5029, top3=0.7135, top5=0.7690, citation=0.9737

## Error Tag Counts

- retrieve_found_but_answer_incomplete: 192
- pass_or_unclassified: 92
- retrieve_not_found: 58
- context_conflict: 9
- answer_out_of_domain: 7

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.0175
- retrieval_adaptive_retry_succeeded: 0.0175
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.0000
- low_confidence_detected: 0.0380
- initial_retrieval_doc_count: 1.2632
- retry_retrieval_doc_count: 0.1404
- initial_top_score: 0.0463
- retry_top_score: 0.0158

## Answer Schema Metrics By Task

- announcement_procedure: cases=52, attempted=23, success=21, attempt_rate=0.4423, success_rate_of_attempts=0.9130, avg_missing_before=3.5577, avg_missing_after=3.0192
- course_factual: cases=36, attempted=7, success=0, attempt_rate=0.1944, success_rate_of_attempts=0.0000, avg_missing_before=0.5833, avg_missing_after=0.5833
- course_study_plan: cases=20, attempted=19, success=18, attempt_rate=0.9500, success_rate_of_attempts=0.9474, avg_missing_before=1.6000, avg_missing_after=0.1500
- none: cases=182, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- regulation_procedure: cases=52, attempted=42, success=37, attempt_rate=0.8077, success_rate_of_attempts=0.8810, avg_missing_before=2.1346, avg_missing_after=0.8846

## Failed Cases Top 20

- qb_177 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=238.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_179 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=256.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_167 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=283.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_301 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=302.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_099 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=324.4, tags=retrieve_not_found, error=none
- qb_184 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=337.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_292 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=404.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_236 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=475.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_256 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=529.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_321 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=530.9, tags=retrieve_not_found, error=none
- qb_320 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=533.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_319 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=571.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_341 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=571.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_137 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=581.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_101 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=585.3, tags=retrieve_not_found, error=none
- qb_014 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=593.0, tags=retrieve_not_found,answer_out_of_domain, error=none
- qb_157 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=594.7, tags=retrieve_not_found, error=none
- qb_161 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=602.7, tags=retrieve_not_found, error=none
- qb_261 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=606.7, tags=retrieve_not_found, error=none
- qb_227 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=616.9, tags=retrieve_not_found, error=none
