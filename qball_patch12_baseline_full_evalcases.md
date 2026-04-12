# Regression Eval Summary

Generated: 2026-04-02T13:14:09.849132
Input: eval_cases.json
Base URL: http://127.0.0.1:8011

## Headline

- total cases: 40
- overall pass rate: 0.3500

### Retrieval Metrics
- top-1 hit rate: 0.7000
- top-3 hit rate: 0.7500
- top-5 hit rate: 0.7750
- top-K hit rate: 0.8750
- mean reciprocal rank (mrr): 0.7258

### Answer Quality Metrics
- answer keyword hit rate: 0.4750
- average quality score (1-5): 0.0000
- % correct answers: 0.4750
- % hallucination: 0.2000
- % answerable handled correctly: 0.0000
- citation validity (groundedness): 0.9250
- must-not contain pass rate: 0.8000

### Latency Metrics
- avg total latency ms: 1076.24
- median total latency ms: 292.78
- p95 total latency ms: 5847.01
- avg retrieval latency ms: 2753.84
- median retrieval latency ms: 2101.15
- p95 retrieval latency ms: 5489.29
- avg generation latency ms: 3057.32
- median generation latency ms: 2471.85
- p95 generation latency ms: 6531.21

## Coverage

- total questions: 40
- questions by domain: announcements=8, curriculum=19, multi=3, regulations=10
- questions by difficulty: unspecified=40
- questions by question type: unspecified=40

## Retrieval By Domain

- announcements: total=8, top1=0.7500, top3=0.8750, top5=0.8750, mrr=0.7917
- curriculum: total=19, top1=0.8421, top3=0.8421, top5=0.8421, mrr=0.8421
- multi: total=3, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- regulations: total=10, top1=0.6000, top3=0.7000, top5=0.8000, mrr=0.6700

## By Category

- announcements_schedule: total=6, overall=0.0000, answer=0.0000, retrieval=0.8333, top1=0.6667, top3=0.8333, top5=0.8333, citation=1.0000
- curriculum_fact_lookup: total=10, overall=0.6000, answer=0.8000, retrieval=1.0000, top1=1.0000, top3=1.0000, top5=1.0000, citation=1.0000
- multi_intent_multi_doc: total=6, overall=0.1667, answer=0.5000, retrieval=0.8333, top1=0.5000, top3=0.5000, top5=0.5000, citation=0.5000
- prerequisite_course_code: total=8, overall=0.3750, answer=0.5000, retrieval=0.6250, top1=0.6250, top3=0.6250, top5=0.6250, citation=1.0000
- regulations: total=8, overall=0.3750, answer=0.3750, retrieval=1.0000, top1=0.5000, top3=0.6250, top5=0.7500, citation=1.0000
- typo_noisy_query: total=2, overall=0.5000, answer=0.5000, retrieval=1.0000, top1=1.0000, top3=1.0000, top5=1.0000, citation=1.0000

## Error Tag Counts

- retrieve_found_but_answer_incomplete: 17
- pass_or_unclassified: 14
- hallucination: 8
- retrieve_not_found: 5
- context_conflict: 3

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.2500
- retrieval_adaptive_retry_succeeded: 0.1000
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.2000
- structured_rescue_succeeded: 0.2000
- curriculum_bypass_vector_triggered: 0.2000
- low_confidence_detected: 0.3250
- initial_retrieval_doc_count: 2.3750
- retry_retrieval_doc_count: 0.9500
- initial_top_score: 0.3564
- retry_top_score: 0.1181

## Answer Schema Metrics By Task

- announcement_procedure: cases=1, attempted=1, success=1, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=4.0000, avg_missing_after=0.0000
- none: cases=34, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- regulation_procedure: cases=5, attempted=5, success=5, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=4.0000, avg_missing_after=2.0000

## Failed Cases Top 20

- regulations_003 (regulations): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1929.4, tags=retrieve_found_but_answer_incomplete, error=none
- announcement_003 (announcements_schedule): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=4006.9, tags=retrieve_found_but_answer_incomplete, error=none
- announcement_002 (announcements_schedule): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=5847.0, tags=retrieve_found_but_answer_incomplete, error=none
- announcement_005 (announcements_schedule): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=6406.3, tags=retrieve_found_but_answer_incomplete, error=none
- announcement_006 (announcements_schedule): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=8211.4, tags=retrieve_found_but_answer_incomplete, error=none
- multi_003 (multi_intent_multi_doc): coverage=0.00, retrieval=False, citation=False, must_not=False, latency_ms=53.4, tags=retrieve_not_found,context_conflict,hallucination, error=none
- announcement_004 (announcements_schedule): coverage=0.20, retrieval=True, citation=True, must_not=True, latency_ms=2159.8, tags=retrieve_found_but_answer_incomplete, error=none
- regulations_001 (regulations): coverage=0.33, retrieval=True, citation=True, must_not=True, latency_ms=426.4, tags=retrieve_found_but_answer_incomplete, error=none
- announcement_001 (announcements_schedule): coverage=0.33, retrieval=False, citation=True, must_not=True, latency_ms=5038.2, tags=retrieve_not_found, error=none
- prereq_003 (prerequisite_course_code): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=64.1, tags=retrieve_not_found, error=none
- curriculum_007 (curriculum_fact_lookup): coverage=0.50, retrieval=True, citation=True, must_not=False, latency_ms=197.4, tags=retrieve_found_but_answer_incomplete,hallucination, error=none
- prereq_008 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=True, must_not=False, latency_ms=203.7, tags=retrieve_found_but_answer_incomplete,hallucination, error=none
- typo_001 (typo_noisy_query): coverage=0.50, retrieval=True, citation=True, must_not=False, latency_ms=205.4, tags=retrieve_found_but_answer_incomplete,hallucination, error=none
- prereq_001 (prerequisite_course_code): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=211.3, tags=retrieve_not_found, error=none
- prereq_007 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=True, must_not=False, latency_ms=271.8, tags=retrieve_found_but_answer_incomplete,hallucination, error=none
- regulations_008 (regulations): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=273.2, tags=retrieve_found_but_answer_incomplete, error=none
- curriculum_009 (curriculum_fact_lookup): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=6.8, tags=retrieve_found_but_answer_incomplete, error=none
- regulations_007 (regulations): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=484.1, tags=retrieve_found_but_answer_incomplete, error=none
- regulations_004 (regulations): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=677.6, tags=retrieve_found_but_answer_incomplete, error=none
- multi_002 (multi_intent_multi_doc): coverage=0.75, retrieval=True, citation=True, must_not=True, latency_ms=385.2, tags=retrieve_found_but_answer_incomplete, error=none
