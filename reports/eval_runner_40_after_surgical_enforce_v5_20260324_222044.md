# Regression Eval Summary

Generated: 2026-03-24T22:22:43.753482
Input: eval_cases.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 40
- overall pass rate: 0.1000

### Retrieval Metrics
- top-1 hit rate: 0.1750
- top-K hit rate: 0.2500
- mean reciprocal rank (mrr): 0.2421

### Answer Quality Metrics
- answer keyword hit rate: 0.3750
- citation validity (groundedness): 0.9750
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 714.92
- p95 total latency ms: 2839.46
- avg retrieval latency ms: 2273.61
- p95 retrieval latency ms: 4308.26

## By Category

- announcements_schedule: total=6, overall=0.0000, answer=0.0000, retrieval=0.5000, citation=1.0000
- curriculum_fact_lookup: total=10, overall=0.0000, answer=0.8000, retrieval=0.0000, citation=1.0000
- multi_intent_multi_doc: total=6, overall=0.1667, answer=0.1667, retrieval=0.3333, citation=1.0000
- prerequisite_course_code: total=8, overall=0.0000, answer=0.3750, retrieval=0.0000, citation=1.0000
- regulations: total=8, overall=0.3750, answer=0.3750, retrieval=0.5000, citation=0.8750
- typo_noisy_query: total=2, overall=0.0000, answer=0.0000, retrieval=0.5000, citation=1.0000

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.1250
- retrieval_adaptive_retry_succeeded: 0.1000
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.4750
- low_confidence_detected: 0.1250
- initial_retrieval_doc_count: 1.8750
- retry_retrieval_doc_count: 0.4500
- initial_top_score: 0.2201
- retry_top_score: 0.0705

## Failed Cases Top 10

- prereq_004 (prerequisite_course_code): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=135.4, error=none
- multi_005 (multi_intent_multi_doc): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=648.7, error=none
- announcement_002 (announcements_schedule): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=844.9, error=none
- announcement_005 (announcements_schedule): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=857.7, error=none
- announcement_003 (announcements_schedule): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=905.1, error=none
- announcement_004 (announcements_schedule): coverage=0.20, retrieval=False, citation=True, must_not=True, latency_ms=995.5, error=none
- announcement_006 (announcements_schedule): coverage=0.25, retrieval=True, citation=True, must_not=True, latency_ms=1020.0, error=none
- announcement_001 (announcements_schedule): coverage=0.33, retrieval=False, citation=True, must_not=True, latency_ms=1091.9, error=none
- regulations_004 (regulations): coverage=0.33, retrieval=False, citation=True, must_not=True, latency_ms=1204.6, error=none
- regulations_008 (regulations): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=92.1, error=none
