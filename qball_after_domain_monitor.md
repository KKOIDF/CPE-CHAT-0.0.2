# Regression Eval Summary

Generated: 2026-04-13T14:05:35.175174
Input: eval_cases.json
Base URL: http://localhost:8001

## Headline

- total cases: 40
- overall pass rate: 0.5250

### Retrieval Metrics
- top-1 hit rate: 0.7250
- top-3 hit rate: 0.7500
- top-5 hit rate: 0.7500
- top-K hit rate: 0.8250
- mean reciprocal rank (mrr): 0.7333

### Answer Quality Metrics
- answer keyword hit rate: 0.6250
- average quality score (1-5): 0.0000
- % correct answers: 0.6250
- % hallucination: 0.2000
- % answerable handled correctly: 0.0000
- citation validity (groundedness): 0.9750
- must-not contain pass rate: 0.8000
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 552.18
- median total latency ms: 283.41
- p95 total latency ms: 1154.22
- avg retrieval latency ms: 1365.79
- median retrieval latency ms: 1023.47
- p95 retrieval latency ms: 3115.80
- avg generation latency ms: 1013.28
- median generation latency ms: 102.65
- p95 generation latency ms: 4615.69

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

- announcements: total=8, overall=0.8750, answer=1.0000, retrieval=0.8750, citation=1.0000, avg_latency_ms=917.73, p95_latency_ms=1157.73
- curriculum: total=19, overall=0.4737, answer=0.6316, retrieval=0.8421, citation=1.0000, avg_latency_ms=144.69, p95_latency_ms=246.57
- multi: total=3, overall=0.0000, answer=0.0000, retrieval=0.6667, citation=0.6667, avg_latency_ms=406.30, p95_latency_ms=742.09
- regulations: total=10, overall=0.5000, answer=0.5000, retrieval=0.8000, citation=1.0000, avg_latency_ms=1077.74, p95_latency_ms=5260.65

## By Category

- announcements_schedule: total=6, overall=0.8333, answer=1.0000, retrieval=0.8333, top1=0.6667, top3=0.8333, top5=0.8333, citation=1.0000
- curriculum_fact_lookup: total=10, overall=0.6000, answer=0.8000, retrieval=1.0000, top1=1.0000, top3=1.0000, top5=1.0000, citation=1.0000
- multi_intent_multi_doc: total=6, overall=0.5000, answer=0.5000, retrieval=0.8333, top1=0.5000, top3=0.5000, top5=0.5000, citation=0.8333
- prerequisite_course_code: total=8, overall=0.3750, answer=0.5000, retrieval=0.6250, top1=0.6250, top3=0.6250, top5=0.6250, citation=1.0000
- regulations: total=8, overall=0.3750, answer=0.3750, retrieval=0.7500, top1=0.6250, top3=0.6250, top5=0.6250, citation=1.0000
- typo_noisy_query: total=2, overall=0.5000, answer=0.5000, retrieval=1.0000, top1=1.0000, top3=1.0000, top5=1.0000, citation=1.0000

## Error Tag Counts

- pass_or_unclassified: 21
- retrieve_found_but_answer_incomplete: 10
- hallucination: 8
- retrieve_not_found: 7
- context_conflict: 1

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

- multi_003 (multi_intent_multi_doc): coverage=0.00, retrieval=False, citation=False, must_not=False, latency_ms=113.4, tags=retrieve_not_found,context_conflict,hallucination, error=none
- regulations_001 (regulations): coverage=0.33, retrieval=True, citation=True, must_not=True, latency_ms=482.5, tags=retrieve_found_but_answer_incomplete, error=none
- prereq_003 (prerequisite_course_code): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=93.5, tags=retrieve_not_found, error=none
- curriculum_007 (curriculum_fact_lookup): coverage=0.50, retrieval=True, citation=True, must_not=False, latency_ms=229.3, tags=retrieve_found_but_answer_incomplete,hallucination, error=none
- prereq_008 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=True, must_not=False, latency_ms=232.7, tags=retrieve_found_but_answer_incomplete,hallucination, error=none
- prereq_007 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=True, must_not=False, latency_ms=233.6, tags=retrieve_found_but_answer_incomplete,hallucination, error=none
- typo_001 (typo_noisy_query): coverage=0.50, retrieval=True, citation=True, must_not=False, latency_ms=246.6, tags=retrieve_found_but_answer_incomplete,hallucination, error=none
- prereq_001 (prerequisite_course_code): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=253.7, tags=retrieve_not_found, error=none
- regulations_008 (regulations): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=313.1, tags=retrieve_not_found, error=none
- curriculum_009 (curriculum_fact_lookup): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=86.1, tags=retrieve_found_but_answer_incomplete, error=none
- regulations_007 (regulations): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=327.5, tags=retrieve_found_but_answer_incomplete, error=none
- regulations_004 (regulations): coverage=0.67, retrieval=False, citation=True, must_not=True, latency_ms=610.1, tags=retrieve_not_found, error=none
- regulations_003 (regulations): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=5260.6, tags=retrieve_found_but_answer_incomplete, error=none
- multi_002 (multi_intent_multi_doc): coverage=0.75, retrieval=True, citation=True, must_not=True, latency_ms=363.4, tags=retrieve_found_but_answer_incomplete, error=none
- multi_001 (multi_intent_multi_doc): coverage=0.75, retrieval=True, citation=True, must_not=False, latency_ms=742.1, tags=retrieve_found_but_answer_incomplete,hallucination, error=none
- prereq_002 (prerequisite_course_code): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=96.4, tags=retrieve_not_found, error=none
- curriculum_008 (curriculum_fact_lookup): coverage=1.00, retrieval=True, citation=True, must_not=False, latency_ms=245.4, tags=hallucination, error=none
- curriculum_010 (curriculum_fact_lookup): coverage=1.00, retrieval=True, citation=True, must_not=False, latency_ms=246.3, tags=hallucination, error=none
- announcement_001 (announcements_schedule): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=979.1, tags=retrieve_not_found, error=none
