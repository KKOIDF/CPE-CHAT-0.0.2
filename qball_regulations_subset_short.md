# Regression Eval Summary

Generated: 2026-04-13T16:46:13.925449
Input: eval_cases_regulations_subset.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 8
- overall pass rate: 0.5000

### Retrieval Metrics
- top-1 hit rate: 0.6250
- top-3 hit rate: 0.6250
- top-5 hit rate: 0.6250
- top-K hit rate: 0.7500
- mean reciprocal rank (mrr): 0.6250

### Answer Quality Metrics
- answer keyword hit rate: 0.5000
- average quality score (1-5): 0.0000
- % correct answers: 0.5000
- % hallucination: 0.0000
- % answerable handled correctly: 0.0000
- citation validity (groundedness): 1.0000
- citation precision: 0.7500
- citation recall: 0.3750
- citation micro precision: 0.7500
- citation micro recall: 0.3750
- must-not contain pass rate: 1.0000
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 430.44
- median total latency ms: 455.17
- p95 total latency ms: 665.09
- avg retrieval latency ms: 1156.07
- median retrieval latency ms: 1116.96
- p95 retrieval latency ms: 1830.99
- avg generation latency ms: 0.00
- median generation latency ms: 0.00
- p95 generation latency ms: 0.00

## Coverage

- total questions: 8
- questions by domain: regulations=8
- questions by difficulty: unspecified=8
- questions by question type: unspecified=8

## Retrieval By Domain

- regulations: total=8, top1=0.6250, top3=0.6250, top5=0.6250, mrr=0.6250

## Domain Monitor

- regulations: total=8, overall=0.5000, answer=0.5000, retrieval=0.7500, citation=1.0000, avg_latency_ms=430.44, p95_latency_ms=665.09

## By Category

- regulations: total=8, overall=0.5000, answer=0.5000, retrieval=0.7500, top1=0.6250, top3=0.6250, top5=0.6250, citation=1.0000

## Error Tag Counts

- pass_or_unclassified: 4
- retrieve_found_but_answer_incomplete: 2
- retrieve_not_found: 2

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.1250
- retrieval_adaptive_retry_succeeded: 0.1250
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.0000
- low_confidence_detected: 0.3750
- initial_retrieval_doc_count: 5.0000
- retry_retrieval_doc_count: 0.6250
- initial_top_score: 0.5031
- retry_top_score: 0.1195

## Answer Schema Metrics By Task

- none: cases=8, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- regulations_001 (regulations): coverage=0.33, retrieval=True, citation=True, must_not=True, latency_ms=507.9, tags=retrieve_found_but_answer_incomplete, error=none
- regulations_008 (regulations): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=308.0, tags=retrieve_not_found, error=none
- regulations_007 (regulations): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=323.5, tags=retrieve_found_but_answer_incomplete, error=none
- regulations_004 (regulations): coverage=0.67, retrieval=False, citation=True, must_not=True, latency_ms=453.6, tags=retrieve_not_found, error=none
