# Regression Eval Summary

Generated: 2026-04-13T15:42:15.900309
Input: eval_cases.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 40
- overall pass rate: 0.7000

### Retrieval Metrics
- top-1 hit rate: 0.7250
- top-3 hit rate: 0.7500
- top-5 hit rate: 0.7500
- top-K hit rate: 0.8250
- mean reciprocal rank (mrr): 0.7333

### Answer Quality Metrics
- answer keyword hit rate: 0.7500
- average quality score (1-5): 0.0000
- % correct answers: 0.7500
- % hallucination: 0.0250
- % answerable handled correctly: 0.0000
- citation validity (groundedness): 0.9750
- citation precision: 0.2692
- citation recall: 0.2000
- citation micro precision: 0.2857
- citation micro recall: 0.1714
- must-not contain pass rate: 0.9750
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 647.85
- median total latency ms: 325.63
- p95 total latency ms: 1794.96
- avg retrieval latency ms: 1838.99
- median retrieval latency ms: 1039.06
- p95 retrieval latency ms: 7361.09
- avg generation latency ms: 1270.93
- median generation latency ms: 195.48
- p95 generation latency ms: 6607.52

## Coverage

- total questions: 40
- questions by domain: announcements=8, curriculum=19, multi=3, regulations=10
- questions by difficulty: unspecified=40
- questions by question type: unspecified=40

## Retrieval By Domain

- announcements: total=8, top1=0.7500, top3=0.8750, top5=0.8750, mrr=0.7917
- curriculum: total=19, top1=0.8421, top3=0.8421, top5=0.8421, mrr=0.8421
- multi: total=3, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- regulations: total=10, top1=0.7000, top3=0.7000, top5=0.7000, mrr=0.7000

## Domain Monitor

- announcements: total=8, overall=0.8750, answer=1.0000, retrieval=0.8750, citation=1.0000, avg_latency_ms=1144.28, p95_latency_ms=1815.32
- curriculum: total=19, overall=0.7895, answer=0.8421, retrieval=0.8421, citation=1.0000, avg_latency_ms=149.43, p95_latency_ms=251.94
- multi: total=3, overall=0.3333, answer=0.3333, retrieval=0.6667, citation=0.6667, avg_latency_ms=428.73, p95_latency_ms=739.03
- regulations: total=10, overall=0.5000, answer=0.5000, retrieval=0.8000, citation=1.0000, avg_latency_ms=1263.45, p95_latency_ms=7435.65

## By Category

- announcements_schedule: total=6, overall=0.8333, answer=1.0000, retrieval=0.8333, top1=0.6667, top3=0.8333, top5=0.8333, citation=1.0000
- curriculum_fact_lookup: total=10, overall=0.9000, answer=0.9000, retrieval=1.0000, top1=1.0000, top3=1.0000, top5=1.0000, citation=1.0000
- multi_intent_multi_doc: total=6, overall=0.6667, answer=0.6667, retrieval=0.8333, top1=0.5000, top3=0.5000, top5=0.5000, citation=0.8333
- prerequisite_course_code: total=8, overall=0.6250, answer=0.7500, retrieval=0.6250, top1=0.6250, top3=0.6250, top5=0.6250, citation=1.0000
- regulations: total=8, overall=0.3750, answer=0.3750, retrieval=0.7500, top1=0.6250, top3=0.6250, top5=0.6250, citation=1.0000
- typo_noisy_query: total=2, overall=1.0000, answer=1.0000, retrieval=1.0000, top1=1.0000, top3=1.0000, top5=1.0000, citation=1.0000

## Error Tag Counts

- pass_or_unclassified: 28
- retrieve_not_found: 7
- retrieve_found_but_answer_incomplete: 5
- context_conflict: 1
- hallucination: 1

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.2750
- retrieval_adaptive_retry_succeeded: 0.1000
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.3250
- structured_rescue_succeeded: 0.3250
- curriculum_bypass_vector_triggered: 0.3250
- low_confidence_detected: 0.3250
- initial_retrieval_doc_count: 2.2250
- retry_retrieval_doc_count: 1.2000
- initial_top_score: 0.4722
- retry_top_score: 0.0780

## Answer Schema Metrics By Task

- announcement_temporal: cases=6, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- none: cases=34, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- multi_003 (multi_intent_multi_doc): coverage=0.00, retrieval=False, citation=False, must_not=False, latency_ms=153.3, tags=retrieve_not_found,context_conflict,hallucination, error=none
- regulations_001 (regulations): coverage=0.33, retrieval=True, citation=True, must_not=True, latency_ms=707.7, tags=retrieve_found_but_answer_incomplete, error=none
- prereq_003 (prerequisite_course_code): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=95.5, tags=retrieve_not_found, error=none
- prereq_001 (prerequisite_course_code): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=229.6, tags=retrieve_not_found, error=none
- regulations_008 (regulations): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=344.5, tags=retrieve_not_found, error=none
- curriculum_009 (curriculum_fact_lookup): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=85.2, tags=retrieve_found_but_answer_incomplete, error=none
- regulations_007 (regulations): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=382.0, tags=retrieve_found_but_answer_incomplete, error=none
- regulations_004 (regulations): coverage=0.67, retrieval=False, citation=True, must_not=True, latency_ms=497.1, tags=retrieve_not_found, error=none
- regulations_003 (regulations): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=7435.7, tags=retrieve_found_but_answer_incomplete, error=none
- multi_002 (multi_intent_multi_doc): coverage=0.75, retrieval=True, citation=True, must_not=True, latency_ms=393.9, tags=retrieve_found_but_answer_incomplete, error=none
- prereq_002 (prerequisite_course_code): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=106.1, tags=retrieve_not_found, error=none
- announcement_001 (announcements_schedule): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=1022.0, tags=retrieve_not_found, error=none
