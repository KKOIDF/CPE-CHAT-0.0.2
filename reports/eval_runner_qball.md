# Regression Eval Summary

Generated: 2026-03-30T12:43:58.359155
Input: eval_cases.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 40
- overall pass rate: 0.6750

### Retrieval Metrics
- top-1 hit rate: 0.6500
- top-3 hit rate: 0.6750
- top-5 hit rate: 0.7000
- top-K hit rate: 0.8750
- mean reciprocal rank (mrr): 0.6800

### Answer Quality Metrics
- answer keyword hit rate: 0.7000
- average quality score (1-5): 0.0000
- % correct answers: 0.7000
- % hallucination: 0.0250
- % answerable handled correctly: 0.0000
- citation validity (groundedness): 0.9750
- must-not contain pass rate: 0.9750

### Latency Metrics
- avg total latency ms: 475.26
- median total latency ms: 336.14
- p95 total latency ms: 1193.48
- avg retrieval latency ms: 2116.47
- median retrieval latency ms: 1395.67
- p95 retrieval latency ms: 4169.57
- avg generation latency ms: 370.70
- median generation latency ms: 204.45
- p95 generation latency ms: 1392.87

## Coverage

- total questions: 40
- questions by domain: announcements=8, curriculum=19, multi=3, regulations=10
- questions by difficulty: unspecified=40
- questions by question type: unspecified=40

## Retrieval By Domain

- announcements: total=8, top1=0.3750, top3=0.5000, top5=0.6250, mrr=0.5250
- curriculum: total=19, top1=0.8421, top3=0.8421, top5=0.8421, mrr=0.8421
- multi: total=3, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- regulations: total=10, top1=0.7000, top3=0.7000, top5=0.7000, mrr=0.7000

## By Category

- announcements_schedule: total=6, overall=1.0000, answer=1.0000, retrieval=1.0000, top1=0.1667, top3=0.3333, top5=0.5000, citation=1.0000
- curriculum_fact_lookup: total=10, overall=0.9000, answer=0.9000, retrieval=1.0000, top1=1.0000, top3=1.0000, top5=1.0000, citation=1.0000
- multi_intent_multi_doc: total=6, overall=0.3333, answer=0.3333, retrieval=0.8333, top1=0.5000, top3=0.5000, top5=0.5000, citation=0.8333
- prerequisite_course_code: total=8, overall=0.6250, answer=0.7500, retrieval=0.6250, top1=0.6250, top3=0.6250, top5=0.6250, citation=1.0000
- regulations: total=8, overall=0.5000, answer=0.5000, retrieval=0.8750, top1=0.6250, top3=0.6250, top5=0.6250, citation=1.0000
- typo_noisy_query: total=2, overall=0.5000, answer=0.5000, retrieval=1.0000, top1=1.0000, top3=1.0000, top5=1.0000, citation=1.0000

## Error Tag Counts

- pass_or_unclassified: 27
- retrieve_found_but_answer_incomplete: 8
- retrieve_not_found: 5
- context_conflict: 1
- hallucination: 1

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

## Failed Cases Top 20

- regulations_003 (regulations): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=884.1, tags=retrieve_found_but_answer_incomplete, error=none
- multi_003 (multi_intent_multi_doc): coverage=0.00, retrieval=False, citation=False, must_not=False, latency_ms=102.4, tags=retrieve_not_found,context_conflict,hallucination, error=none
- prereq_001 (prerequisite_course_code): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=137.9, tags=retrieve_not_found, error=none
- regulations_008 (regulations): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=319.1, tags=retrieve_found_but_answer_incomplete, error=none
- prereq_003 (prerequisite_course_code): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=355.0, tags=retrieve_not_found, error=none
- multi_006 (multi_intent_multi_doc): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=1035.2, tags=retrieve_found_but_answer_incomplete, error=none
- curriculum_009 (curriculum_fact_lookup): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=87.2, tags=retrieve_found_but_answer_incomplete, error=none
- regulations_007 (regulations): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=353.1, tags=retrieve_found_but_answer_incomplete, error=none
- typo_002 (typo_noisy_query): coverage=0.67, retrieval=True, citation=True, must_not=True, latency_ms=470.2, tags=retrieve_found_but_answer_incomplete, error=none
- regulations_004 (regulations): coverage=0.67, retrieval=False, citation=True, must_not=True, latency_ms=2762.9, tags=retrieve_not_found, error=none
- multi_002 (multi_intent_multi_doc): coverage=0.75, retrieval=True, citation=True, must_not=True, latency_ms=476.1, tags=retrieve_found_but_answer_incomplete, error=none
- multi_001 (multi_intent_multi_doc): coverage=0.75, retrieval=True, citation=True, must_not=True, latency_ms=539.2, tags=retrieve_found_but_answer_incomplete, error=none
- prereq_002 (prerequisite_course_code): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=100.7, tags=retrieve_not_found, error=none
