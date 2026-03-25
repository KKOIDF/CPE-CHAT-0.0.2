# Regression Eval Summary

Generated: 2026-03-24T21:29:45.087763
Input: eval_cases.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 40
- overall pass rate: 0.0750

### Retrieval Metrics
- top-1 hit rate: 0.3000
- top-K hit rate: 0.6500
- mean reciprocal rank (mrr): 0.4642

### Answer Quality Metrics
- answer keyword hit rate: 0.4000
- citation validity (groundedness): 0.2500
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 1300.93
- p95 total latency ms: 6275.29
- avg retrieval latency ms: 2330.37
- p95 retrieval latency ms: 4955.62

## By Category

- announcements_schedule: total=6, overall=0.0000, answer=0.3333, retrieval=0.5000, citation=0.0000
- curriculum_fact_lookup: total=10, overall=0.0000, answer=0.8000, retrieval=0.9000, citation=0.0000
- multi_intent_multi_doc: total=6, overall=0.0000, answer=0.0000, retrieval=0.0000, citation=0.5000
- prerequisite_course_code: total=8, overall=0.0000, answer=0.3750, retrieval=1.0000, citation=0.0000
- regulations: total=8, overall=0.3750, answer=0.3750, retrieval=0.5000, citation=0.7500
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

- prereq_004 (prerequisite_course_code): coverage=0.00, retrieval=True, citation=False, must_not=True, latency_ms=85.1, error=none
- announcement_004 (announcements_schedule): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=3920.5, error=none
- announcement_002 (announcements_schedule): coverage=0.00, retrieval=True, citation=False, must_not=True, latency_ms=7579.8, error=none
- regulations_004 (regulations): coverage=0.33, retrieval=False, citation=False, must_not=True, latency_ms=1134.4, error=none
- announcement_001 (announcements_schedule): coverage=0.33, retrieval=False, citation=False, must_not=True, latency_ms=3922.9, error=none
- regulations_008 (regulations): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=94.4, error=none
- prereq_008 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=False, must_not=True, latency_ms=84.5, error=none
- regulations_005 (regulations): coverage=0.50, retrieval=False, citation=False, must_not=True, latency_ms=86.5, error=none
- prereq_007 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=False, must_not=True, latency_ms=89.8, error=none
- prereq_001 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=False, must_not=True, latency_ms=90.9, error=none
