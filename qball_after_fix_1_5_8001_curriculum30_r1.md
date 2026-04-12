# Regression Eval Summary

Generated: 2026-04-12T17:29:42.034564
Input: data/eval_curriculum_targeted_30.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 30
- overall pass rate: 0.2333

### Retrieval Metrics
- top-1 hit rate: 0.9667
- top-3 hit rate: 1.0000
- top-5 hit rate: 1.0000
- top-K hit rate: 1.0000
- mean reciprocal rank (mrr): 0.9833

### Answer Quality Metrics
- answer keyword hit rate: 0.2333
- average quality score (1-5): 0.0000
- % correct answers: 0.2333
- % hallucination: 0.0000
- % answerable handled correctly: 0.2333
- citation validity (groundedness): 0.8333
- must-not contain pass rate: 1.0000
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 3897.88
- median total latency ms: 329.69
- p95 total latency ms: 22013.41
- avg retrieval latency ms: 8557.82
- median retrieval latency ms: 8464.15
- p95 retrieval latency ms: 9877.54
- avg generation latency ms: 13409.86
- median generation latency ms: 13546.34
- p95 generation latency ms: 14219.39

## Coverage

- total questions: 30
- questions by domain: curriculum=30
- questions by difficulty: easy=10, medium=20
- questions by question type: factual=16, procedural=14

## Retrieval By Domain

- curriculum: total=30, top1=0.9667, top3=1.0000, top5=1.0000, mrr=0.9833

## By Category

- uncategorized: total=30, overall=0.2333, answer=0.2333, retrieval=1.0000, top1=0.9667, top3=1.0000, top5=1.0000, citation=0.8333

## Error Tag Counts

- retrieve_found_but_answer_incomplete: 23
- pass_or_unclassified: 7
- context_conflict: 5

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.0000
- retrieval_adaptive_retry_succeeded: 0.0000
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.3667
- structured_rescue_succeeded: 0.3667
- curriculum_bypass_vector_triggered: 0.5333
- low_confidence_detected: 0.0000
- initial_retrieval_doc_count: 1.2667
- retry_retrieval_doc_count: 0.0000
- initial_top_score: 0.3944
- retry_top_score: 0.0000

## Answer Schema Metrics By Task

- course_factual: cases=5, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=2.8000, avg_missing_after=2.8000
- none: cases=25, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- qb_003 (uncategorized): coverage=0.00, retrieval=True, citation=False, must_not=True, latency_ms=21812.5, tags=retrieve_found_but_answer_incomplete,context_conflict, error=none
- qb_120 (uncategorized): coverage=0.00, retrieval=True, citation=False, must_not=True, latency_ms=21872.1, tags=retrieve_found_but_answer_incomplete,context_conflict, error=none
- qb_015 (uncategorized): coverage=0.00, retrieval=True, citation=False, must_not=True, latency_ms=21895.0, tags=retrieve_found_but_answer_incomplete,context_conflict, error=none
- qb_045 (uncategorized): coverage=0.00, retrieval=True, citation=False, must_not=True, latency_ms=22013.4, tags=retrieve_found_but_answer_incomplete,context_conflict, error=none
- qb_059 (uncategorized): coverage=0.00, retrieval=True, citation=False, must_not=True, latency_ms=22134.3, tags=retrieve_found_but_answer_incomplete,context_conflict, error=none
- qb_129 (uncategorized): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=249.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_133 (uncategorized): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=256.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_087 (uncategorized): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=281.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_091 (uncategorized): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=306.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_030 (uncategorized): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=317.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_102 (uncategorized): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=341.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_076 (uncategorized): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=341.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_068 (uncategorized): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=342.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_026 (uncategorized): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=343.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_114 (uncategorized): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=362.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_018 (uncategorized): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=363.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_024 (uncategorized): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=369.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_103 (uncategorized): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=416.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_041 (uncategorized): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=499.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_074 (uncategorized): coverage=0.60, retrieval=True, citation=True, must_not=True, latency_ms=237.5, tags=retrieve_found_but_answer_incomplete, error=none
