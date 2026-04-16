# Regression Eval Summary

Generated: 2026-04-16T18:42:42.618102
Input: eval_cases.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 40
- overall pass rate: 0.9500

### Retrieval Metrics
- top-1 hit rate: 0.7250
- top-3 hit rate: 0.8250
- top-5 hit rate: 0.8250
- top-K hit rate: 1.0000
- mean reciprocal rank (mrr): 0.7704

### Answer Quality Metrics
- answer keyword hit rate: 0.9500
- average quality score (1-5): 0.0000
- % correct answers: 0.9500
- % hallucination: 0.0000
- % answerable handled correctly: 0.0000
- citation validity (groundedness): 1.0000
- citation precision: 0.2500
- citation recall: 0.1875
- citation micro precision: 0.2500
- citation micro recall: 0.1571
- must-not contain pass rate: 1.0000
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 469.09
- median total latency ms: 347.72
- p95 total latency ms: 1131.35
- avg retrieval latency ms: 1258.05
- median retrieval latency ms: 1084.70
- p95 retrieval latency ms: 2155.60
- avg generation latency ms: 140.18
- median generation latency ms: 139.96
- p95 generation latency ms: 307.04

## Coverage

- total questions: 40
- questions by domain: announcements=8, curriculum=19, multi=3, regulations=10
- questions by difficulty: unspecified=40
- questions by question type: unspecified=40

## Retrieval By Domain

- announcements: total=8, top1=0.7500, top3=0.8750, top5=0.8750, mrr=0.7917
- curriculum: total=19, top1=0.8421, top3=1.0000, top5=1.0000, mrr=0.9123
- multi: total=3, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- regulations: total=10, top1=0.7000, top3=0.7000, top5=0.7000, mrr=0.7150

## Domain Monitor

- announcements: total=8, overall=1.0000, answer=1.0000, retrieval=1.0000, citation=1.0000, avg_latency_ms=997.71, p95_latency_ms=1509.64
- curriculum: total=19, overall=0.9474, answer=0.9474, retrieval=1.0000, citation=1.0000, avg_latency_ms=168.37, p95_latency_ms=305.45
- multi: total=3, overall=1.0000, answer=1.0000, retrieval=1.0000, citation=1.0000, avg_latency_ms=643.53, p95_latency_ms=793.44
- regulations: total=10, overall=0.9000, answer=0.9000, retrieval=1.0000, citation=1.0000, avg_latency_ms=565.23, p95_latency_ms=1131.35

## By Category

- announcements_schedule: total=6, overall=1.0000, answer=1.0000, retrieval=1.0000, top1=0.6667, top3=0.8333, top5=0.8333, citation=1.0000
- curriculum_fact_lookup: total=10, overall=0.9000, answer=0.9000, retrieval=1.0000, top1=1.0000, top3=1.0000, top5=1.0000, citation=1.0000
- multi_intent_multi_doc: total=6, overall=1.0000, answer=1.0000, retrieval=1.0000, top1=0.5000, top3=0.5000, top5=0.5000, citation=1.0000
- prerequisite_course_code: total=8, overall=1.0000, answer=1.0000, retrieval=1.0000, top1=0.6250, top3=1.0000, top5=1.0000, citation=1.0000
- regulations: total=8, overall=1.0000, answer=1.0000, retrieval=1.0000, top1=0.6250, top3=0.6250, top5=0.6250, citation=1.0000
- typo_noisy_query: total=2, overall=0.5000, answer=0.5000, retrieval=1.0000, top1=1.0000, top3=1.0000, top5=1.0000, citation=1.0000

## Error Tag Counts

- pass_or_unclassified: 38
- retrieve_found_but_answer_incomplete: 2

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.2750
- retrieval_adaptive_retry_succeeded: 0.1000
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.3250
- structured_rescue_succeeded: 0.3250
- curriculum_bypass_vector_triggered: 0.3250
- low_confidence_detected: 0.3250
- initial_retrieval_doc_count: 2.3500
- retry_retrieval_doc_count: 1.2000
- initial_top_score: 0.4887
- retry_top_score: 0.0780

## Answer Schema Metrics By Task

- announcement_temporal: cases=6, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- none: cases=34, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- curriculum_009 (curriculum_fact_lookup): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=108.0, tags=retrieve_found_but_answer_incomplete, error=none
- typo_002 (typo_noisy_query): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=487.9, tags=retrieve_found_but_answer_incomplete, error=none
