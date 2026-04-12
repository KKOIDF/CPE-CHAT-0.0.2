# Regression Eval Summary

Generated: 2026-04-02T20:17:04.573426
Input: eval_cases.json
Base URL: http://127.0.0.1:8011

## Headline

- total cases: 40
- overall pass rate: 0.3500

### Retrieval Metrics
- top-1 hit rate: 0.6250
- top-3 hit rate: 0.6750
- top-5 hit rate: 0.7000
- top-K hit rate: 0.8250
- mean reciprocal rank (mrr): 0.6565

### Answer Quality Metrics
- answer keyword hit rate: 0.4750
- average quality score (1-5): 0.0000
- % correct answers: 0.4750
- % hallucination: 0.2000
- % answerable handled correctly: 0.0000
- citation validity (groundedness): 0.9250
- must-not contain pass rate: 0.8000

### Latency Metrics
- avg total latency ms: 830.05
- median total latency ms: 291.70
- p95 total latency ms: 4285.88
- avg retrieval latency ms: 2092.93
- median retrieval latency ms: 1415.49
- p95 retrieval latency ms: 4078.87
- avg generation latency ms: 2215.53
- median generation latency ms: 2486.82
- p95 generation latency ms: 4515.74

## Coverage

- total questions: 40
- questions by domain: announcements=8, curriculum=19, multi=3, regulations=10
- questions by difficulty: unspecified=40
- questions by question type: unspecified=40

## Retrieval By Domain

- announcements: total=8, top1=0.3750, top3=0.5000, top5=0.6250, mrr=0.4625
- curriculum: total=19, top1=0.8421, top3=0.8421, top5=0.8421, mrr=0.8421
- multi: total=3, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- regulations: total=10, top1=0.6000, top3=0.7000, top5=0.7000, mrr=0.6559

## By Category

- announcements_schedule: total=6, overall=0.0000, answer=0.0000, retrieval=0.5000, top1=0.1667, top3=0.3333, top5=0.5000, citation=1.0000
- curriculum_fact_lookup: total=10, overall=0.6000, answer=0.8000, retrieval=1.0000, top1=1.0000, top3=1.0000, top5=1.0000, citation=1.0000
- multi_intent_multi_doc: total=6, overall=0.1667, answer=0.5000, retrieval=0.8333, top1=0.5000, top3=0.5000, top5=0.5000, citation=0.5000
- prerequisite_course_code: total=8, overall=0.3750, answer=0.5000, retrieval=0.6250, top1=0.6250, top3=0.6250, top5=0.6250, citation=1.0000
- regulations: total=8, overall=0.3750, answer=0.3750, retrieval=1.0000, top1=0.5000, top3=0.6250, top5=0.6250, citation=1.0000
- typo_noisy_query: total=2, overall=0.5000, answer=0.5000, retrieval=1.0000, top1=1.0000, top3=1.0000, top5=1.0000, citation=1.0000

## Error Tag Counts

- retrieve_found_but_answer_incomplete: 15
- pass_or_unclassified: 14
- hallucination: 8
- retrieve_not_found: 7
- context_conflict: 3

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.0250
- retrieval_adaptive_retry_succeeded: 0.0250
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.0000
- low_confidence_detected: 0.0750
- initial_retrieval_doc_count: 1.0000
- retry_retrieval_doc_count: 0.1250
- initial_top_score: 0.0920
- retry_top_score: 0.0239

## Answer Schema Metrics By Task

- announcement_procedure: cases=1, attempted=1, success=1, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=4.0000, avg_missing_after=0.0000
- none: cases=34, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- regulation_procedure: cases=5, attempted=5, success=5, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=4.0000, avg_missing_after=1.6000

## Failed Cases Top 20

- regulations_003 (regulations): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1516.2, tags=retrieve_found_but_answer_incomplete, error=none
- announcement_003 (announcements_schedule): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=3129.1, tags=retrieve_not_found, error=none
- announcement_001 (announcements_schedule): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=4115.9, tags=retrieve_not_found, error=none
- announcement_006 (announcements_schedule): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=4285.9, tags=retrieve_found_but_answer_incomplete, error=none
- announcement_002 (announcements_schedule): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=4855.0, tags=retrieve_found_but_answer_incomplete, error=none
- announcement_005 (announcements_schedule): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=5311.4, tags=retrieve_found_but_answer_incomplete, error=none
- multi_003 (multi_intent_multi_doc): coverage=0.00, retrieval=False, citation=False, must_not=False, latency_ms=108.3, tags=retrieve_not_found,context_conflict,hallucination, error=none
- announcement_004 (announcements_schedule): coverage=0.20, retrieval=False, citation=True, must_not=True, latency_ms=912.4, tags=retrieve_not_found, error=none
- regulations_001 (regulations): coverage=0.33, retrieval=True, citation=True, must_not=True, latency_ms=416.1, tags=retrieve_found_but_answer_incomplete, error=none
- prereq_003 (prerequisite_course_code): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=94.5, tags=retrieve_not_found, error=none
- typo_001 (typo_noisy_query): coverage=0.50, retrieval=True, citation=True, must_not=False, latency_ms=193.3, tags=retrieve_found_but_answer_incomplete,hallucination, error=none
- prereq_001 (prerequisite_course_code): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=193.9, tags=retrieve_not_found, error=none
- prereq_008 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=True, must_not=False, latency_ms=197.1, tags=retrieve_found_but_answer_incomplete,hallucination, error=none
- prereq_007 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=True, must_not=False, latency_ms=203.7, tags=retrieve_found_but_answer_incomplete,hallucination, error=none
- curriculum_007 (curriculum_fact_lookup): coverage=0.50, retrieval=True, citation=True, must_not=False, latency_ms=210.6, tags=retrieve_found_but_answer_incomplete,hallucination, error=none
- regulations_008 (regulations): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=385.2, tags=retrieve_found_but_answer_incomplete, error=none
- curriculum_009 (curriculum_fact_lookup): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=2.7, tags=retrieve_found_but_answer_incomplete, error=none
- regulations_004 (regulations): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=389.5, tags=retrieve_found_but_answer_incomplete, error=none
- regulations_007 (regulations): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=442.4, tags=retrieve_found_but_answer_incomplete, error=none
- multi_002 (multi_intent_multi_doc): coverage=0.75, retrieval=True, citation=True, must_not=True, latency_ms=474.0, tags=retrieve_found_but_answer_incomplete, error=none
