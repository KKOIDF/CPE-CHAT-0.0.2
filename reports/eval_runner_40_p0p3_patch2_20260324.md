# Regression Eval Summary

Generated: 2026-03-25T00:05:43.233647
Input: eval_cases.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 40
- overall pass rate: 0.6500

### Retrieval Metrics
- top-1 hit rate: 0.5000
- top-K hit rate: 0.8750
- mean reciprocal rank (mrr): 0.6076

### Answer Quality Metrics
- answer keyword hit rate: 0.7500
- citation validity (groundedness): 1.0000
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 515.47
- p95 total latency ms: 1057.26
- avg retrieval latency ms: 2262.62
- p95 retrieval latency ms: 4947.14

## By Category

- announcements_schedule: total=6, overall=1.0000, answer=1.0000, retrieval=1.0000, citation=1.0000
- curriculum_fact_lookup: total=10, overall=0.7000, answer=0.8000, retrieval=0.9000, citation=1.0000
- multi_intent_multi_doc: total=6, overall=0.3333, answer=0.6667, retrieval=0.5000, citation=1.0000
- prerequisite_course_code: total=8, overall=0.5000, answer=0.5000, retrieval=1.0000, citation=1.0000
- regulations: total=8, overall=0.8750, answer=1.0000, retrieval=0.8750, citation=1.0000
- typo_noisy_query: total=2, overall=0.0000, answer=0.0000, retrieval=1.0000, citation=1.0000

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.1750
- retrieval_adaptive_retry_succeeded: 0.1750
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.4750
- low_confidence_detected: 0.1750
- initial_retrieval_doc_count: 2.8750
- retry_retrieval_doc_count: 0.7250
- initial_top_score: 0.3273
- retry_top_score: 0.1445

## Failed Cases Top 10

- prereq_001 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=105.3, error=none
- prereq_008 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=117.3, error=none
- prereq_007 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=121.5, error=none
- curriculum_007 (curriculum_fact_lookup): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=169.9, error=none
- typo_001 (typo_noisy_query): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=190.2, error=none
- prereq_003 (prerequisite_course_code): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=223.1, error=none
- curriculum_009 (curriculum_fact_lookup): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=218.9, error=none
- typo_002 (typo_noisy_query): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=459.6, error=none
- multi_006 (multi_intent_multi_doc): coverage=0.75, retrieval=True, citation=True, must_not=True, latency_ms=81.7, error=none
- multi_003 (multi_intent_multi_doc): coverage=0.75, retrieval=False, citation=True, must_not=True, latency_ms=1245.4, error=none
