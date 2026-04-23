# Regression Eval Summary

Generated: 2026-04-16T20:44:39.845665
Input: eval_cases.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 12
- overall pass rate: 1.0000

### Retrieval Metrics
- top-1 hit rate: 0.8333
- top-3 hit rate: 1.0000
- top-5 hit rate: 1.0000
- top-K hit rate: 1.0000
- mean reciprocal rank (mrr): 0.9028

### Answer Quality Metrics
- answer keyword hit rate: 1.0000
- average quality score (1-5): 0.0000
- % correct answers: 1.0000
- % hallucination: 0.0000
- % answerable handled correctly: 0.0000
- citation validity (groundedness): 1.0000
- citation precision: 0.8333
- citation recall: 0.8333
- citation micro precision: 0.8333
- citation micro recall: 0.4545
- must-not contain pass rate: 1.0000
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 151.73
- median total latency ms: 93.32
- p95 total latency ms: 243.34
- avg retrieval latency ms: 151.73
- median retrieval latency ms: 93.32
- p95 retrieval latency ms: 243.34
- avg generation latency ms: 0.00
- median generation latency ms: 0.00
- p95 generation latency ms: 0.00

## Coverage

- total questions: 12
- questions by domain: curriculum=12
- questions by difficulty: unspecified=12
- questions by question type: unspecified=12

## Retrieval By Domain

- curriculum: total=12, top1=0.8333, top3=1.0000, top5=1.0000, mrr=0.9028

## Domain Monitor

- curriculum: total=12, overall=1.0000, answer=1.0000, retrieval=1.0000, citation=1.0000, avg_latency_ms=151.73, p95_latency_ms=243.34

## By Category

- curriculum_fact_lookup: total=10, overall=1.0000, answer=1.0000, retrieval=1.0000, top1=1.0000, top3=1.0000, top5=1.0000, citation=1.0000
- prerequisite_course_code: total=2, overall=1.0000, answer=1.0000, retrieval=1.0000, top1=0.0000, top3=1.0000, top5=1.0000, citation=1.0000

## Error Tag Counts

- pass_or_unclassified: 12

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.5000
- retrieval_adaptive_retry_succeeded: 0.0000
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.8333
- structured_rescue_succeeded: 0.8333
- curriculum_bypass_vector_triggered: 0.8333
- low_confidence_detected: 0.5000
- initial_retrieval_doc_count: 1.1667
- retry_retrieval_doc_count: 2.0000
- initial_top_score: 0.8333
- retry_top_score: 0.1132

## Answer Schema Metrics By Task

- none: cases=12, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- none
