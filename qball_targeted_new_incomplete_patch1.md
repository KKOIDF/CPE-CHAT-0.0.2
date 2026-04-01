# Regression Eval Summary

Generated: 2026-04-01T20:58:57.383480
Input: data/eval_new_incomplete_subset.json
Base URL: http://127.0.0.1:8011

## Headline

- total cases: 21
- overall pass rate: 0.1905

### Retrieval Metrics
- top-1 hit rate: 0.1429
- top-3 hit rate: 0.1905
- top-5 hit rate: 0.1905
- top-K hit rate: 0.1905
- mean reciprocal rank (mrr): 0.1667

### Answer Quality Metrics
- answer keyword hit rate: 0.7143
- average quality score (1-5): 0.0000
- % correct answers: 0.7143
- % hallucination: 0.0000
- % answerable handled correctly: 0.7143
- citation validity (groundedness): 1.0000
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 2193.65
- median total latency ms: 1006.75
- p95 total latency ms: 6172.05
- avg retrieval latency ms: 1291.25
- median retrieval latency ms: 918.35
- p95 retrieval latency ms: 4582.92
- avg generation latency ms: 1564.15
- median generation latency ms: 164.75
- p95 generation latency ms: 5223.82

## Coverage

- total questions: 21
- questions by domain: announcements=19, curriculum=1, regulations=1
- questions by difficulty: easy=3, hard=4, medium=14
- questions by question type: ambiguous=1, factual=5, multi-hop=3, noisy=1, policy_conflict=1, procedural=7, verification=3

## Retrieval By Domain

- announcements: total=19, top1=0.1053, top3=0.1053, top5=0.1053, mrr=0.1053
- curriculum: total=1, top1=0.0000, top3=1.0000, top5=1.0000, mrr=0.5000
- regulations: total=1, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000

## By Category

- uncategorized: total=21, overall=0.1905, answer=0.7143, retrieval=0.1905, top1=0.1429, top3=0.1905, top5=0.1905, citation=1.0000

## Error Tag Counts

- retrieve_not_found: 17
- pass_or_unclassified: 4

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.0000
- retrieval_adaptive_retry_succeeded: 0.0000
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.0000
- low_confidence_detected: 0.0000
- initial_retrieval_doc_count: 0.0000
- retry_retrieval_doc_count: 0.0000
- initial_top_score: 0.0000
- retry_top_score: 0.0000

## Answer Schema Metrics By Task

- announcement_procedure: cases=16, attempted=16, success=16, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=3.6250, avg_missing_after=0.0000
- course_factual: cases=1, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- none: cases=2, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- regulation_procedure: cases=2, attempted=2, success=2, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=3.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- qb_256 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=817.6, tags=retrieve_not_found, error=none
- qb_137 (uncategorized): coverage=0.25, retrieval=False, citation=True, must_not=True, latency_ms=839.5, tags=retrieve_not_found, error=none
- qb_004 (uncategorized): coverage=0.25, retrieval=False, citation=True, must_not=True, latency_ms=1019.4, tags=retrieve_not_found, error=none
- qb_116 (uncategorized): coverage=0.33, retrieval=False, citation=True, must_not=True, latency_ms=1154.2, tags=retrieve_not_found, error=none
- qb_054 (uncategorized): coverage=0.33, retrieval=False, citation=True, must_not=True, latency_ms=1268.4, tags=retrieve_not_found, error=none
- qb_032 (uncategorized): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=995.9, tags=retrieve_not_found, error=none
- qb_159 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=765.9, tags=retrieve_not_found, error=none
- qb_100 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=868.4, tags=retrieve_not_found, error=none
- qb_265 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=887.1, tags=retrieve_not_found, error=none
- qb_154 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=937.0, tags=retrieve_not_found, error=none
- qb_001 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=954.6, tags=retrieve_not_found, error=none
- qb_080 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=998.2, tags=retrieve_not_found, error=none
- qb_121 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1006.2, tags=retrieve_not_found, error=none
- qb_170 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1006.8, tags=retrieve_not_found, error=none
- qb_139 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1018.5, tags=retrieve_not_found, error=none
- qb_070 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1022.9, tags=retrieve_not_found, error=none
- qb_326 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1026.0, tags=retrieve_not_found, error=none
