# Regression Eval Summary

Generated: 2026-04-01T22:24:49.105437
Input: data/eval_new_not_found_subset.json
Base URL: http://127.0.0.1:8011

## Headline

- total cases: 26
- overall pass rate: 0.0000

### Retrieval Metrics
- top-1 hit rate: 0.0000
- top-3 hit rate: 0.0000
- top-5 hit rate: 0.0000
- top-K hit rate: 0.0000
- mean reciprocal rank (mrr): 0.0000

### Answer Quality Metrics
- answer keyword hit rate: 0.6923
- average quality score (1-5): 0.0000
- % correct answers: 0.6923
- % hallucination: 0.0000
- % answerable handled correctly: 0.6923
- citation validity (groundedness): 1.0000
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 1940.94
- median total latency ms: 1003.69
- p95 total latency ms: 10256.76
- avg retrieval latency ms: 1202.42
- median retrieval latency ms: 1033.34
- p95 retrieval latency ms: 2691.37
- avg generation latency ms: 2037.24
- median generation latency ms: 232.09
- p95 generation latency ms: 6086.01

## Coverage

- total questions: 26
- questions by domain: announcements=20, curriculum=1, regulations=5
- questions by difficulty: easy=4, hard=5, medium=17
- questions by question type: ambiguous=2, factual=3, multi-hop=3, noisy=1, policy_conflict=1, procedural=10, verification=6

## Retrieval By Domain

- announcements: total=20, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- curriculum: total=1, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- regulations: total=5, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000

## By Category

- uncategorized: total=26, overall=0.0000, answer=0.6923, retrieval=0.0000, top1=0.0000, top3=0.0000, top5=0.0000, citation=1.0000

## Error Tag Counts

- retrieve_not_found: 26

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.0000
- retrieval_adaptive_retry_succeeded: 0.0000
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.0000
- low_confidence_detected: 0.0769
- initial_retrieval_doc_count: 0.5769
- retry_retrieval_doc_count: 0.0000
- initial_top_score: 0.0056
- retry_top_score: 0.0000

## Answer Schema Metrics By Task

- announcement_procedure: cases=19, attempted=19, success=19, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=3.6842, avg_missing_after=0.0000
- course_factual: cases=1, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- none: cases=6, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- qb_256 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=583.8, tags=retrieve_not_found, error=none
- qb_137 (uncategorized): coverage=0.25, retrieval=False, citation=True, must_not=True, latency_ms=907.5, tags=retrieve_not_found, error=none
- qb_009 (uncategorized): coverage=0.25, retrieval=False, citation=True, must_not=True, latency_ms=925.1, tags=retrieve_not_found, error=none
- qb_004 (uncategorized): coverage=0.25, retrieval=False, citation=True, must_not=True, latency_ms=935.3, tags=retrieve_not_found, error=none
- qb_116 (uncategorized): coverage=0.33, retrieval=False, citation=True, must_not=True, latency_ms=1027.5, tags=retrieve_not_found, error=none
- qb_054 (uncategorized): coverage=0.33, retrieval=False, citation=True, must_not=True, latency_ms=1212.3, tags=retrieve_not_found, error=none
- qb_032 (uncategorized): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=989.0, tags=retrieve_not_found, error=none
- qb_255 (uncategorized): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=10256.8, tags=retrieve_not_found, error=none
- qb_122 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=643.0, tags=retrieve_not_found, error=none
- qb_176 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=654.9, tags=retrieve_not_found, error=none
- qb_257 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=712.6, tags=retrieve_not_found, error=none
- qb_033 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=741.1, tags=retrieve_not_found, error=none
- qb_139 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=758.2, tags=retrieve_not_found, error=none
- qb_159 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=860.2, tags=retrieve_not_found, error=none
- qb_154 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=937.1, tags=retrieve_not_found, error=none
- qb_170 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=964.8, tags=retrieve_not_found, error=none
- qb_080 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1018.4, tags=retrieve_not_found, error=none
- qb_326 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1031.0, tags=retrieve_not_found, error=none
- qb_323 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1032.7, tags=retrieve_not_found, error=none
- qb_100 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1064.9, tags=retrieve_not_found, error=none
