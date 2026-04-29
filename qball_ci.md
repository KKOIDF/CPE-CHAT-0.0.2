# Regression Eval Summary

Generated: 2026-04-29T15:26:04.978420
Input: data/question_bank_250_general_th.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 342
- overall pass rate: 0.6316

### Retrieval Metrics
- top-1 hit rate: 0.8099
- top-3 hit rate: 0.8567
- top-5 hit rate: 0.8655
- top-K hit rate: 0.8363
- mean reciprocal rank (mrr): 0.8302

### Answer Quality Metrics
- answer keyword hit rate: 0.7573
- average quality score (1-5): 0.0000
- % correct answers: 0.7573
- % hallucination: 0.0000
- % answerable handled correctly: 0.7749
- citation validity (groundedness): 0.9708
- citation precision: 0.9292
- citation recall: 0.9787
- citation micro precision: 0.9281
- citation micro recall: 0.2878
- must-not contain pass rate: 1.0000
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 500.17
- median total latency ms: 93.06
- p95 total latency ms: 2669.72
- avg retrieval latency ms: 294.76
- median retrieval latency ms: 93.06
- p95 retrieval latency ms: 1359.59
- avg generation latency ms: 1033.10
- median generation latency ms: 980.58
- p95 generation latency ms: 2349.79

## Coverage

- total questions: 342
- questions by domain: announcements=135, curriculum=99, general=29, regulations=79
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=135, top1=0.6074, top3=0.6741, top5=0.6741, mrr=0.6358
- curriculum: total=99, top1=0.9697, top3=0.9697, top5=1.0000, mrr=0.9773
- general: total=29, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- regulations: total=79, top1=0.8861, top3=0.9747, top5=0.9747, mrr=0.9156

## Domain Monitor

- announcements: total=135, overall=0.5407, answer=0.8444, retrieval=0.6741, citation=1.0000, avg_latency_ms=329.49, p95_latency_ms=1642.70
- curriculum: total=99, overall=0.7677, answer=0.7677, retrieval=1.0000, citation=1.0000, avg_latency_ms=412.33, p95_latency_ms=2104.29
- general: total=29, overall=0.4828, answer=0.4828, retrieval=0.6552, citation=0.6552, avg_latency_ms=1418.24, p95_latency_ms=4289.94
- regulations: total=79, overall=0.6709, answer=0.6962, retrieval=0.9747, citation=1.0000, avg_latency_ms=564.91, p95_latency_ms=2745.57

## By Category

- uncategorized: total=342, overall=0.6316, answer=0.7573, retrieval=0.8363, top1=0.8099, top3=0.8567, top5=0.8655, citation=0.9708

## Error Tag Counts

- pass_or_unclassified: 216
- retrieve_found_but_answer_incomplete: 70
- retrieve_not_found: 46
- context_conflict: 10

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.0556
- retrieval_adaptive_retry_succeeded: 0.0234
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.0058
- low_confidence_detected: 0.0614
- initial_retrieval_doc_count: 0.2398
- retry_retrieval_doc_count: 0.0936
- initial_top_score: 0.0077
- retry_top_score: 0.0110

## Answer Schema Metrics By Task

- announcement_procedure: cases=22, attempted=22, success=22, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=2.5909, avg_missing_after=0.0000
- course_factual: cases=10, attempted=4, success=1, attempt_rate=0.4000, success_rate_of_attempts=0.2500, avg_missing_before=0.6000, avg_missing_after=0.5000
- none: cases=297, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- prerequisite: cases=1, attempted=1, success=1, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=1.0000, avg_missing_after=0.0000
- regulation_procedure: cases=12, attempted=7, success=7, attempt_rate=0.5833, success_rate_of_attempts=1.0000, avg_missing_before=2.4167, avg_missing_after=0.0000

## Failed Cases Top 20

- qb_118 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=83.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_184 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=87.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_231 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=91.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_314 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1337.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_315 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1630.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_324 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1802.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_214 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1950.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_310 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=2047.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_266 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=2271.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_300 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=2323.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_330 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=2351.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_342 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=2474.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_301 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=4181.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_042 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=4973.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_341 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=1501.5, tags=context_conflict, error=none
- qb_305 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=1969.5, tags=context_conflict, error=none
- qb_237 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=2628.3, tags=context_conflict, error=none
- qb_335 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=2669.7, tags=context_conflict, error=none
- qb_329 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=2804.8, tags=context_conflict, error=none
- qb_192 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=2921.9, tags=context_conflict, error=none
