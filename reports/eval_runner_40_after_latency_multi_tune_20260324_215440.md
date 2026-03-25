# Regression Eval Summary

Generated: 2026-03-24T21:57:05.898000
Input: eval_cases.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 40
- overall pass rate: 0.1000

### Retrieval Metrics
- top-1 hit rate: 0.2500
- top-K hit rate: 0.6750
- mean reciprocal rank (mrr): 0.4163

### Answer Quality Metrics
- answer keyword hit rate: 0.4500
- citation validity (groundedness): 0.2750
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 1272.83
- p95 total latency ms: 6696.39
- avg retrieval latency ms: 2353.73
- p95 retrieval latency ms: 5336.63

## By Category

- announcements_schedule: total=6, overall=0.0000, answer=0.3333, retrieval=0.5000, citation=0.0000
- curriculum_fact_lookup: total=10, overall=0.0000, answer=0.8000, retrieval=0.8000, citation=0.0000
- multi_intent_multi_doc: total=6, overall=0.1667, answer=0.3333, retrieval=0.3333, citation=0.5000
- prerequisite_course_code: total=8, overall=0.0000, answer=0.3750, retrieval=1.0000, citation=0.0000
- regulations: total=8, overall=0.3750, answer=0.3750, retrieval=0.5000, citation=0.8750
- typo_noisy_query: total=2, overall=0.0000, answer=0.0000, retrieval=1.0000, citation=0.5000

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.0250
- retrieval_adaptive_retry_succeeded: 0.0250
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.0000
- low_confidence_detected: 0.0250
- initial_retrieval_doc_count: 0.1250
- retry_retrieval_doc_count: 0.1250
- initial_top_score: 0.0004
- retry_top_score: 0.0219

## Failed Cases Top 10

- prereq_004 (prerequisite_course_code): coverage=0.00, retrieval=True, citation=False, must_not=True, latency_ms=88.5, error=none
- announcement_004 (announcements_schedule): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=1550.9, error=none
- announcement_002 (announcements_schedule): coverage=0.00, retrieval=True, citation=False, must_not=True, latency_ms=6696.4, error=none
- regulations_004 (regulations): coverage=0.33, retrieval=False, citation=True, must_not=True, latency_ms=1342.8, error=none
- announcement_001 (announcements_schedule): coverage=0.33, retrieval=False, citation=False, must_not=True, latency_ms=3115.2, error=none
- regulations_008 (regulations): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=85.4, error=none
- prereq_001 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=False, must_not=True, latency_ms=82.0, error=none
- regulations_005 (regulations): coverage=0.50, retrieval=False, citation=False, must_not=True, latency_ms=85.9, error=none
- prereq_008 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=False, must_not=True, latency_ms=88.4, error=none
- typo_001 (typo_noisy_query): coverage=0.50, retrieval=True, citation=False, must_not=True, latency_ms=89.4, error=none
