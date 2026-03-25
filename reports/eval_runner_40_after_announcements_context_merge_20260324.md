# Regression Eval Summary

Generated: 2026-03-24T23:11:19.481498
Input: eval_cases.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 40
- overall pass rate: 0.4250

### Retrieval Metrics
- top-1 hit rate: 0.4500
- top-K hit rate: 0.8000
- mean reciprocal rank (mrr): 0.5567

### Answer Quality Metrics
- answer keyword hit rate: 0.5000
- citation validity (groundedness): 1.0000
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 919.34
- p95 total latency ms: 4288.25
- avg retrieval latency ms: 2404.99
- p95 retrieval latency ms: 4862.59

## By Category

- announcements_schedule: total=6, overall=0.1667, answer=0.5000, retrieval=0.5000, citation=1.0000
- curriculum_fact_lookup: total=10, overall=0.7000, answer=0.8000, retrieval=0.9000, citation=1.0000
- multi_intent_multi_doc: total=6, overall=0.3333, answer=0.3333, retrieval=0.5000, citation=1.0000
- prerequisite_course_code: total=8, overall=0.5000, answer=0.5000, retrieval=1.0000, citation=1.0000
- regulations: total=8, overall=0.3750, answer=0.3750, retrieval=0.8750, citation=1.0000
- typo_noisy_query: total=2, overall=0.0000, answer=0.0000, retrieval=1.0000, citation=1.0000

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.1750
- retrieval_adaptive_retry_succeeded: 0.1500
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.4750
- low_confidence_detected: 0.1750
- initial_retrieval_doc_count: 2.8750
- retry_retrieval_doc_count: 0.7000
- initial_top_score: 0.3277
- retry_top_score: 0.1202

## Failed Cases Top 10

- multi_005 (multi_intent_multi_doc): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=646.7, error=none
- regulations_004 (regulations): coverage=0.33, retrieval=False, citation=True, must_not=True, latency_ms=1100.3, error=none
- prereq_001 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=92.5, error=none
- prereq_007 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=117.0, error=none
- prereq_008 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=118.7, error=none
- curriculum_007 (curriculum_fact_lookup): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=128.6, error=none
- typo_001 (typo_noisy_query): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=164.0, error=none
- prereq_003 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=237.5, error=none
- regulations_008 (regulations): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=310.9, error=none
- regulations_005 (regulations): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=671.6, error=none
