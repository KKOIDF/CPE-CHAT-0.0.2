# Regression Eval Summary

Generated: 2026-04-16T17:50:14.030868
Input: eval_cases_p0_focus.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 5
- overall pass rate: 0.0000

### Retrieval Metrics
- top-1 hit rate: 0.0000
- top-3 hit rate: 0.0000
- top-5 hit rate: 0.0000
- top-K hit rate: 0.0000
- mean reciprocal rank (mrr): 0.0000

### Answer Quality Metrics
- answer keyword hit rate: 0.4000
- average quality score (1-5): 0.0000
- % correct answers: 0.4000
- % hallucination: 0.2000
- % answerable handled correctly: 0.0000
- citation validity (groundedness): 0.8000
- citation precision: 0.0000
- citation recall: 0.0000
- citation micro precision: 0.0000
- citation micro recall: 0.0000
- must-not contain pass rate: 0.8000
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 269.69
- median total latency ms: 171.56
- p95 total latency ms: 705.72
- avg retrieval latency ms: 1887.78
- median retrieval latency ms: 1577.22
- p95 retrieval latency ms: 3092.26
- avg generation latency ms: 0.00
- median generation latency ms: 0.00
- p95 generation latency ms: 0.00

## Coverage

- total questions: 5
- questions by domain: curriculum=3, multi=1, regulations=1
- questions by difficulty: unspecified=5
- questions by question type: unspecified=5

## Retrieval By Domain

- curriculum: total=3, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- multi: total=1, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- regulations: total=1, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000

## Domain Monitor

- curriculum: total=3, overall=0.0000, answer=0.3333, retrieval=0.0000, citation=1.0000, avg_latency_ms=157.05, p95_latency_ms=286.13
- multi: total=1, overall=0.0000, answer=0.0000, retrieval=0.0000, citation=0.0000, avg_latency_ms=171.56, p95_latency_ms=171.56
- regulations: total=1, overall=0.0000, answer=1.0000, retrieval=0.0000, citation=1.0000, avg_latency_ms=705.72, p95_latency_ms=705.72

## By Category

- multi_intent_multi_doc: total=1, overall=0.0000, answer=0.0000, retrieval=0.0000, top1=0.0000, top3=0.0000, top5=0.0000, citation=0.0000
- prerequisite_course_code: total=3, overall=0.0000, answer=0.3333, retrieval=0.0000, top1=0.0000, top3=0.0000, top5=0.0000, citation=1.0000
- regulations: total=1, overall=0.0000, answer=1.0000, retrieval=0.0000, top1=0.0000, top3=0.0000, top5=0.0000, citation=1.0000

## Error Tag Counts

- retrieve_not_found: 5
- context_conflict: 1
- hallucination: 1

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.0000
- retrieval_adaptive_retry_succeeded: 0.0000
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.0000
- low_confidence_detected: 0.2000
- initial_retrieval_doc_count: 1.0000
- retry_retrieval_doc_count: 0.0000
- initial_top_score: 0.0033
- retry_top_score: 0.0000

## Answer Schema Metrics By Task

- none: cases=5, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- multi_003 (multi_intent_multi_doc): coverage=0.00, retrieval=False, citation=False, must_not=False, latency_ms=171.6, tags=retrieve_not_found,context_conflict,hallucination, error=none
- prereq_003 (prerequisite_course_code): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=91.5, tags=retrieve_not_found, error=none
- prereq_001 (prerequisite_course_code): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=286.1, tags=retrieve_not_found, error=none
- prereq_002 (prerequisite_course_code): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=93.5, tags=retrieve_not_found, error=none
- regulations_004 (regulations): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=705.7, tags=retrieve_not_found, error=none
