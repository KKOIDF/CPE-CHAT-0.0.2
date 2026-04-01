# Regression Eval Summary

Generated: 2026-04-01T22:37:32.830036
Input: data/eval_new_not_found_subset.json
Base URL: http://127.0.0.1:8001

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
- answer keyword hit rate: 0.7308
- average quality score (1-5): 0.0000
- % correct answers: 0.7308
- % hallucination: 0.0000
- % answerable handled correctly: 0.7308
- citation validity (groundedness): 1.0000
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 2035.79
- median total latency ms: 1157.39
- p95 total latency ms: 5212.77
- avg retrieval latency ms: 1265.99
- median retrieval latency ms: 1138.93
- p95 retrieval latency ms: 2760.66
- avg generation latency ms: 1903.43
- median generation latency ms: 2010.85
- p95 generation latency ms: 4079.43

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

- uncategorized: total=26, overall=0.0000, answer=0.7308, retrieval=0.0000, top1=0.0000, top3=0.0000, top5=0.0000, citation=1.0000

## Error Tag Counts

- retrieve_not_found: 26
- answer_out_of_domain: 1

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

- announcement_procedure: cases=19, attempted=19, success=19, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=3.5263, avg_missing_after=0.0000
- course_factual: cases=1, attempted=1, success=0, attempt_rate=1.0000, success_rate_of_attempts=0.0000, avg_missing_before=1.0000, avg_missing_after=1.0000
- none: cases=6, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- qb_137 (uncategorized): coverage=0.25, retrieval=False, citation=True, must_not=True, latency_ms=1111.4, tags=retrieve_not_found, error=none
- qb_009 (uncategorized): coverage=0.25, retrieval=False, citation=True, must_not=True, latency_ms=1250.2, tags=retrieve_not_found, error=none
- qb_004 (uncategorized): coverage=0.25, retrieval=False, citation=True, must_not=True, latency_ms=1403.5, tags=retrieve_not_found, error=none
- qb_116 (uncategorized): coverage=0.33, retrieval=False, citation=True, must_not=True, latency_ms=926.7, tags=retrieve_not_found, error=none
- qb_054 (uncategorized): coverage=0.33, retrieval=False, citation=True, must_not=True, latency_ms=1081.4, tags=retrieve_not_found, error=none
- qb_032 (uncategorized): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=1188.0, tags=retrieve_not_found, error=none
- qb_256 (uncategorized): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=4273.2, tags=retrieve_not_found, error=none
- qb_033 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=517.7, tags=retrieve_not_found, error=none
- qb_122 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=520.4, tags=retrieve_not_found, error=none
- qb_176 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=535.3, tags=retrieve_not_found, error=none
- qb_323 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=859.0, tags=retrieve_not_found, error=none
- qb_100 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=881.1, tags=retrieve_not_found, error=none
- qb_159 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=936.2, tags=retrieve_not_found, error=none
- qb_121 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1009.1, tags=retrieve_not_found, error=none
- qb_080 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1049.9, tags=retrieve_not_found, error=none
- qb_265 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1112.2, tags=retrieve_not_found, error=none
- qb_257 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1139.6, tags=retrieve_not_found, error=none
- qb_070 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1175.1, tags=retrieve_not_found, error=none
- qb_154 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1503.2, tags=retrieve_not_found, error=none
- qb_001 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1616.1, tags=retrieve_not_found, error=none
