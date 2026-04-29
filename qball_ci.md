# Regression Eval Summary

Generated: 2026-04-28T23:25:31.120459
Input: data/question_bank_250_general_th.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 342
- overall pass rate: 0.5760

### Retrieval Metrics
- top-1 hit rate: 0.7485
- top-3 hit rate: 0.9211
- top-5 hit rate: 0.9357
- top-K hit rate: 0.9094
- mean reciprocal rank (mrr): 0.8155

### Answer Quality Metrics
- answer keyword hit rate: 0.6228
- average quality score (1-5): 0.0000
- % correct answers: 0.6228
- % hallucination: 0.0000
- % answerable handled correctly: 0.6374
- citation validity (groundedness): 0.9708
- citation precision: 0.8599
- citation recall: 0.8978
- citation micro precision: 0.8567
- citation micro recall: 0.2665
- must-not contain pass rate: 1.0000
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 1467.89
- median total latency ms: 1391.80
- p95 total latency ms: 3757.16
- avg retrieval latency ms: 703.35
- median retrieval latency ms: 556.77
- p95 retrieval latency ms: 1756.31
- avg generation latency ms: 1210.53
- median generation latency ms: 1073.63
- p95 generation latency ms: 2966.29

## Coverage

- total questions: 342
- questions by domain: announcements=135, curriculum=99, general=29, regulations=79
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=135, top1=0.7259, top3=0.9407, top5=0.9556, mrr=0.8148
- curriculum: total=99, top1=0.7576, top3=0.8283, top5=0.8586, mrr=0.7904
- general: total=29, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- regulations: total=79, top1=0.6835, top3=0.9747, top5=0.9747, mrr=0.7806

## Domain Monitor

- announcements: total=135, overall=0.6741, answer=0.7037, retrieval=0.9556, citation=1.0000, avg_latency_ms=1503.98, p95_latency_ms=2725.10
- curriculum: total=99, overall=0.5960, answer=0.6970, retrieval=0.8586, citation=1.0000, avg_latency_ms=1740.71, p95_latency_ms=4178.08
- general: total=29, overall=0.4483, answer=0.4483, retrieval=0.6897, citation=0.6552, avg_latency_ms=1418.45, p95_latency_ms=3371.60
- regulations: total=79, overall=0.4304, answer=0.4557, retrieval=0.9747, citation=1.0000, avg_latency_ms=1082.49, p95_latency_ms=2843.44

## By Category

- uncategorized: total=342, overall=0.5760, answer=0.6228, retrieval=0.9094, top1=0.7485, top3=0.9211, top5=0.9357, citation=0.9708

## Error Tag Counts

- pass_or_unclassified: 197
- retrieve_found_but_answer_incomplete: 114
- retrieve_not_found: 22
- context_conflict: 10
- answer_out_of_domain: 4

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.1257
- retrieval_adaptive_retry_succeeded: 0.0877
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.2222
- structured_rescue_succeeded: 0.2222
- curriculum_bypass_vector_triggered: 0.1374
- low_confidence_detected: 0.1491
- initial_retrieval_doc_count: 1.2281
- retry_retrieval_doc_count: 0.3743
- initial_top_score: 0.0620
- retry_top_score: 0.0389

## Answer Schema Metrics By Task

- announcement_procedure: cases=99, attempted=99, success=99, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=3.1515, avg_missing_after=0.0000
- announcement_temporal: cases=3, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- announcement_verification: cases=30, attempted=30, success=30, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=2.2333, avg_missing_after=0.0000
- course_factual: cases=59, attempted=38, success=33, attempt_rate=0.6441, success_rate_of_attempts=0.8684, avg_missing_before=0.3051, avg_missing_after=0.1695
- course_study_plan: cases=20, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- none: cases=50, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- prerequisite: cases=3, attempted=3, success=1, attempt_rate=1.0000, success_rate_of_attempts=0.3333, avg_missing_before=0.3333, avg_missing_after=1.3333
- regulation_procedure: cases=63, attempted=55, success=16, attempt_rate=0.8730, success_rate_of_attempts=0.2909, avg_missing_before=0.6190, avg_missing_after=2.7143
- unanswerable_refusal: cases=15, attempted=15, success=15, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=0.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- qb_179 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=314.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_184 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=317.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_236 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=333.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_118 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=342.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_274 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=666.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_267 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=873.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_321 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1077.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_320 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1182.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_316 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1207.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_314 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1266.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_325 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1316.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_315 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1372.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_290 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1381.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_306 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1466.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_069 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1531.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_094 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1694.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_092 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1842.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_266 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1852.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_342 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1905.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_300 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1909.5, tags=retrieve_found_but_answer_incomplete, error=none
