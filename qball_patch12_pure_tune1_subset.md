# Regression Eval Summary

Generated: 2026-04-02T13:19:28.585803
Input: data/eval_new_not_found_subset.json
Base URL: http://127.0.0.1:8011

## Headline

- total cases: 26
- overall pass rate: 0.3077

### Retrieval Metrics
- top-1 hit rate: 0.2308
- top-3 hit rate: 0.3077
- top-5 hit rate: 0.3846
- top-K hit rate: 0.3846
- mean reciprocal rank (mrr): 0.2756

### Answer Quality Metrics
- answer keyword hit rate: 0.6923
- average quality score (1-5): 0.0000
- % correct answers: 0.6923
- % hallucination: 0.0000
- % answerable handled correctly: 0.6923
- citation validity (groundedness): 1.0000
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 1994.09
- median total latency ms: 1252.72
- p95 total latency ms: 6364.77
- avg retrieval latency ms: 1364.44
- median retrieval latency ms: 1296.73
- p95 retrieval latency ms: 2305.29
- avg generation latency ms: 2182.33
- median generation latency ms: 1310.57
- p95 generation latency ms: 6440.83

## Coverage

- total questions: 26
- questions by domain: announcements=20, curriculum=1, regulations=5
- questions by difficulty: easy=4, hard=5, medium=17
- questions by question type: ambiguous=2, factual=3, multi-hop=3, noisy=1, policy_conflict=1, procedural=10, verification=6

## Retrieval By Domain

- announcements: total=20, top1=0.3000, top3=0.3000, top5=0.4000, mrr=0.3250
- curriculum: total=1, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- regulations: total=5, top1=0.0000, top3=0.4000, top5=0.4000, mrr=0.1333

## By Category

- uncategorized: total=26, overall=0.3077, answer=0.6923, retrieval=0.3846, top1=0.2308, top3=0.3077, top5=0.3846, citation=1.0000

## Error Tag Counts

- retrieve_not_found: 16
- pass_or_unclassified: 8
- retrieve_found_but_answer_incomplete: 2

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

- announcement_procedure: cases=19, attempted=19, success=19, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=3.4211, avg_missing_after=0.0000
- course_factual: cases=1, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- none: cases=6, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- qb_256 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1343.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_137 (uncategorized): coverage=0.25, retrieval=False, citation=True, must_not=True, latency_ms=717.3, tags=retrieve_not_found, error=none
- qb_009 (uncategorized): coverage=0.25, retrieval=False, citation=True, must_not=True, latency_ms=1349.8, tags=retrieve_not_found, error=none
- qb_004 (uncategorized): coverage=0.25, retrieval=False, citation=True, must_not=True, latency_ms=1352.5, tags=retrieve_not_found, error=none
- qb_116 (uncategorized): coverage=0.33, retrieval=True, citation=True, must_not=True, latency_ms=820.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_054 (uncategorized): coverage=0.33, retrieval=False, citation=True, must_not=True, latency_ms=998.0, tags=retrieve_not_found, error=none
- qb_032 (uncategorized): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=1322.9, tags=retrieve_not_found, error=none
- qb_255 (uncategorized): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=10307.1, tags=retrieve_not_found, error=none
- qb_033 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=426.8, tags=retrieve_not_found, error=none
- qb_176 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=437.5, tags=retrieve_not_found, error=none
- qb_122 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=463.9, tags=retrieve_not_found, error=none
- qb_257 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=701.1, tags=retrieve_not_found, error=none
- qb_323 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=767.6, tags=retrieve_not_found, error=none
- qb_080 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=857.3, tags=retrieve_not_found, error=none
- qb_070 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=864.3, tags=retrieve_not_found, error=none
- qb_265 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1186.2, tags=retrieve_not_found, error=none
- qb_139 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=2976.7, tags=retrieve_not_found, error=none
- qb_326 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=5325.0, tags=retrieve_not_found, error=none
