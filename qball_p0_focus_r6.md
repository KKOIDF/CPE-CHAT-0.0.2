# Regression Eval Summary

Generated: 2026-04-16T18:29:39.555883
Input: eval_cases_p0_focus.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 5
- overall pass rate: 0.6000

### Retrieval Metrics
- top-1 hit rate: 0.0000
- top-3 hit rate: 0.6000
- top-5 hit rate: 0.6000
- top-K hit rate: 1.0000
- mean reciprocal rank (mrr): 0.2784

### Answer Quality Metrics
- answer keyword hit rate: 0.6000
- average quality score (1-5): 0.0000
- % correct answers: 0.6000
- % hallucination: 0.0000
- % answerable handled correctly: 0.0000
- citation validity (groundedness): 1.0000
- citation precision: 0.0000
- citation recall: 0.0000
- citation micro precision: 0.0000
- citation micro recall: 0.0000
- must-not contain pass rate: 1.0000
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 398.25
- median total latency ms: 300.40
- p95 total latency ms: 785.76
- avg retrieval latency ms: 1746.54
- median retrieval latency ms: 1574.99
- p95 retrieval latency ms: 2762.84
- avg generation latency ms: 0.00
- median generation latency ms: 0.00
- p95 generation latency ms: 0.00

## Coverage

- total questions: 5
- questions by domain: curriculum=3, multi=1, regulations=1
- questions by difficulty: unspecified=5
- questions by question type: unspecified=5

## Retrieval By Domain

- curriculum: total=3, top1=0.0000, top3=1.0000, top5=1.0000, mrr=0.4444
- multi: total=1, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- regulations: total=1, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0588

## Domain Monitor

- curriculum: total=3, overall=0.6667, answer=0.6667, retrieval=1.0000, citation=1.0000, avg_latency_ms=177.60, p95_latency_ms=300.40
- multi: total=1, overall=0.0000, answer=0.0000, retrieval=1.0000, citation=1.0000, avg_latency_ms=785.76, p95_latency_ms=785.76
- regulations: total=1, overall=1.0000, answer=1.0000, retrieval=1.0000, citation=1.0000, avg_latency_ms=672.71, p95_latency_ms=672.71

## By Category

- multi_intent_multi_doc: total=1, overall=0.0000, answer=0.0000, retrieval=1.0000, top1=0.0000, top3=0.0000, top5=0.0000, citation=1.0000
- prerequisite_course_code: total=3, overall=0.6667, answer=0.6667, retrieval=1.0000, top1=0.0000, top3=1.0000, top5=1.0000, citation=1.0000
- regulations: total=1, overall=1.0000, answer=1.0000, retrieval=1.0000, top1=0.0000, top3=0.0000, top5=0.0000, citation=1.0000

## Error Tag Counts

- pass_or_unclassified: 3
- retrieve_found_but_answer_incomplete: 2

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

- prereq_001 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=300.4, tags=retrieve_found_but_answer_incomplete, error=none
- multi_003 (multi_intent_multi_doc): coverage=0.75, retrieval=True, citation=True, must_not=True, latency_ms=785.8, tags=retrieve_found_but_answer_incomplete, error=none
