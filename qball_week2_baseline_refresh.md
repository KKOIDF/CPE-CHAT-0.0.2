# Regression Eval Summary

Generated: 2026-04-16T20:10:47.417400
Input: eval_cases.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 40
- overall pass rate: 1.0000

### Retrieval Metrics
- top-1 hit rate: 0.7750
- top-3 hit rate: 0.8500
- top-5 hit rate: 0.8500
- top-K hit rate: 1.0000
- mean reciprocal rank (mrr): 0.8121

### Answer Quality Metrics
- answer keyword hit rate: 1.0000
- average quality score (1-5): 0.0000
- % correct answers: 1.0000
- % hallucination: 0.0000
- % answerable handled correctly: 0.0000
- citation validity (groundedness): 1.0000
- citation precision: 0.9250
- citation recall: 0.9036
- citation micro precision: 0.9318
- citation micro recall: 0.2697
- must-not contain pass rate: 1.0000
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 317.90
- median total latency ms: 236.66
- p95 total latency ms: 777.21
- avg retrieval latency ms: 305.52
- median retrieval latency ms: 236.66
- p95 retrieval latency ms: 777.21
- avg generation latency ms: 495.44
- median generation latency ms: 495.44
- p95 generation latency ms: 495.44

## Coverage

- total questions: 40
- questions by domain: announcements=8, curriculum=19, multi=3, regulations=10
- questions by difficulty: unspecified=40
- questions by question type: unspecified=40

## Retrieval By Domain

- announcements: total=8, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- curriculum: total=19, top1=0.8421, top3=1.0000, top5=1.0000, mrr=0.9123
- multi: total=3, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- regulations: total=10, top1=0.7000, top3=0.7000, top5=0.7000, mrr=0.7150

## Domain Monitor

- announcements: total=8, overall=1.0000, answer=1.0000, retrieval=1.0000, citation=1.0000, avg_latency_ms=207.28, p95_latency_ms=589.84
- curriculum: total=19, overall=1.0000, answer=1.0000, retrieval=1.0000, citation=1.0000, avg_latency_ms=162.44, p95_latency_ms=266.60
- multi: total=3, overall=1.0000, answer=1.0000, retrieval=1.0000, citation=1.0000, avg_latency_ms=757.72, p95_latency_ms=1047.46
- regulations: total=10, overall=1.0000, answer=1.0000, retrieval=1.0000, citation=1.0000, avg_latency_ms=569.84, p95_latency_ms=1668.24

## By Category

- announcements_schedule: total=6, overall=1.0000, answer=1.0000, retrieval=1.0000, top1=1.0000, top3=1.0000, top5=1.0000, citation=1.0000
- curriculum_fact_lookup: total=10, overall=1.0000, answer=1.0000, retrieval=1.0000, top1=1.0000, top3=1.0000, top5=1.0000, citation=1.0000
- multi_intent_multi_doc: total=6, overall=1.0000, answer=1.0000, retrieval=1.0000, top1=0.5000, top3=0.5000, top5=0.5000, citation=1.0000
- prerequisite_course_code: total=8, overall=1.0000, answer=1.0000, retrieval=1.0000, top1=0.6250, top3=1.0000, top5=1.0000, citation=1.0000
- regulations: total=8, overall=1.0000, answer=1.0000, retrieval=1.0000, top1=0.6250, top3=0.6250, top5=0.6250, citation=1.0000
- typo_noisy_query: total=2, overall=1.0000, answer=1.0000, retrieval=1.0000, top1=1.0000, top3=1.0000, top5=1.0000, citation=1.0000

## Error Tag Counts

- pass_or_unclassified: 40

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.1750
- retrieval_adaptive_retry_succeeded: 0.0250
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.3250
- structured_rescue_succeeded: 0.3250
- curriculum_bypass_vector_triggered: 0.3250
- low_confidence_detected: 0.2250
- initial_retrieval_doc_count: 1.6250
- retry_retrieval_doc_count: 0.7250
- initial_top_score: 0.4345
- retry_top_score: 0.0579

## Answer Schema Metrics By Task

- none: cases=40, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- none
