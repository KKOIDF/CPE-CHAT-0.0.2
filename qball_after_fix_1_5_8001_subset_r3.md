# Regression Eval Summary

Generated: 2026-04-12T17:12:03.761374
Input: data/eval_new_incomplete_subset.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 21
- overall pass rate: 0.4286

### Retrieval Metrics
- top-1 hit rate: 0.6190
- top-3 hit rate: 0.8095
- top-5 hit rate: 0.8095
- top-K hit rate: 0.8095
- mean reciprocal rank (mrr): 0.6825

### Answer Quality Metrics
- answer keyword hit rate: 0.5238
- average quality score (1-5): 0.0000
- % correct answers: 0.5238
- % hallucination: 0.0000
- % answerable handled correctly: 0.5238
- citation validity (groundedness): 0.9524
- must-not contain pass rate: 1.0000
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 3508.59
- median total latency ms: 1710.12
- p95 total latency ms: 8854.09
- avg retrieval latency ms: 1932.78
- median retrieval latency ms: 1412.72
- p95 retrieval latency ms: 2654.23
- avg generation latency ms: 2322.00
- median generation latency ms: 79.48
- p95 generation latency ms: 6758.30

## Coverage

- total questions: 21
- questions by domain: announcements=19, curriculum=1, regulations=1
- questions by difficulty: easy=3, hard=4, medium=14
- questions by question type: ambiguous=1, factual=5, multi-hop=3, noisy=1, policy_conflict=1, procedural=7, verification=3

## Retrieval By Domain

- announcements: total=19, top1=0.6316, top3=0.8421, top5=0.8421, mrr=0.7018
- curriculum: total=1, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- regulations: total=1, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000

## By Category

- uncategorized: total=21, overall=0.4286, answer=0.5238, retrieval=0.8095, top1=0.6190, top3=0.8095, top5=0.8095, citation=0.9524

## Error Tag Counts

- pass_or_unclassified: 9
- retrieve_found_but_answer_incomplete: 8
- retrieve_not_found: 4
- context_conflict: 1

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.6190
- retrieval_adaptive_retry_succeeded: 0.6190
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.0000
- low_confidence_detected: 0.6190
- initial_retrieval_doc_count: 3.8095
- retry_retrieval_doc_count: 3.0952
- initial_top_score: 0.0338
- retry_top_score: 0.1607

## Answer Schema Metrics By Task

- announcement_procedure: cases=16, attempted=16, success=16, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=3.7500, avg_missing_after=0.0000
- course_factual: cases=1, attempted=1, success=0, attempt_rate=1.0000, success_rate_of_attempts=0.0000, avg_missing_before=3.0000, avg_missing_after=3.0000
- none: cases=2, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- regulation_procedure: cases=2, attempted=2, success=2, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=4.0000, avg_missing_after=2.0000

## Failed Cases Top 20

- qb_256 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=2204.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_310 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=8019.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_295 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=8854.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_260 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=21799.7, tags=retrieve_not_found, error=none
- qb_319 (uncategorized): coverage=0.00, retrieval=True, citation=False, must_not=True, latency_ms=7418.5, tags=retrieve_found_but_answer_incomplete,context_conflict, error=none
- qb_137 (uncategorized): coverage=0.25, retrieval=True, citation=True, must_not=True, latency_ms=1250.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_004 (uncategorized): coverage=0.25, retrieval=True, citation=True, must_not=True, latency_ms=1925.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_054 (uncategorized): coverage=0.33, retrieval=False, citation=True, must_not=True, latency_ms=1292.5, tags=retrieve_not_found, error=none
- qb_116 (uncategorized): coverage=0.33, retrieval=True, citation=True, must_not=True, latency_ms=1740.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_032 (uncategorized): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=1304.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_070 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1228.8, tags=retrieve_not_found, error=none
- qb_080 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1232.2, tags=retrieve_not_found, error=none
