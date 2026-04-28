# Regression Eval Summary

Generated: 2026-04-28T17:39:00.113854
Input: data/question_bank_250_general_th.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 342
- overall pass rate: 0.5526

### Retrieval Metrics
- top-1 hit rate: 0.7456
- top-3 hit rate: 0.9211
- top-5 hit rate: 0.9357
- top-K hit rate: 0.9094
- mean reciprocal rank (mrr): 0.8141

### Answer Quality Metrics
- answer keyword hit rate: 0.5994
- average quality score (1-5): 0.0000
- % correct answers: 0.5994
- % hallucination: 0.0000
- % answerable handled correctly: 0.6140
- citation validity (groundedness): 0.9678
- citation precision: 0.8656
- citation recall: 0.9010
- citation micro precision: 0.8623
- citation micro recall: 0.2674
- must-not contain pass rate: 1.0000
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 1483.34
- median total latency ms: 1400.27
- p95 total latency ms: 3716.30
- avg retrieval latency ms: 705.42
- median retrieval latency ms: 570.34
- p95 retrieval latency ms: 1735.37
- avg generation latency ms: 1214.84
- median generation latency ms: 1067.53
- p95 generation latency ms: 2776.53

## Coverage

- total questions: 342
- questions by domain: announcements=135, curriculum=99, general=29, regulations=79
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=135, top1=0.7185, top3=0.9407, top5=0.9556, mrr=0.8111
- curriculum: total=99, top1=0.7576, top3=0.8283, top5=0.8586, mrr=0.7904
- general: total=29, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- regulations: total=79, top1=0.6835, top3=0.9747, top5=0.9747, mrr=0.7806

## Domain Monitor

- announcements: total=135, overall=0.6370, answer=0.6667, retrieval=0.9556, citation=1.0000, avg_latency_ms=1513.35, p95_latency_ms=2819.44
- curriculum: total=99, overall=0.5960, answer=0.6970, retrieval=0.8586, citation=1.0000, avg_latency_ms=1808.48, p95_latency_ms=3969.82
- general: total=29, overall=0.4483, answer=0.4483, retrieval=0.6897, citation=0.6552, avg_latency_ms=1477.06, p95_latency_ms=3716.30
- regulations: total=79, overall=0.3924, answer=0.4177, retrieval=0.9747, citation=0.9873, avg_latency_ms=1026.91, p95_latency_ms=2650.07

## By Category

- uncategorized: total=342, overall=0.5526, answer=0.5994, retrieval=0.9094, top1=0.7456, top3=0.9211, top5=0.9357, citation=0.9678

## Error Tag Counts

- pass_or_unclassified: 189
- retrieve_found_but_answer_incomplete: 122
- retrieve_not_found: 22
- context_conflict: 11
- answer_out_of_domain: 3

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.1345
- retrieval_adaptive_retry_succeeded: 0.0965
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.2222
- structured_rescue_succeeded: 0.2222
- curriculum_bypass_vector_triggered: 0.1374
- low_confidence_detected: 0.1579
- initial_retrieval_doc_count: 1.2749
- retry_retrieval_doc_count: 0.4094
- initial_top_score: 0.0625
- retry_top_score: 0.0412

## Answer Schema Metrics By Task

- announcement_procedure: cases=98, attempted=98, success=98, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=3.2449, avg_missing_after=0.0000
- announcement_temporal: cases=7, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- announcement_verification: cases=30, attempted=30, success=30, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=2.2000, avg_missing_after=0.0000
- course_factual: cases=59, attempted=38, success=33, attempt_rate=0.6441, success_rate_of_attempts=0.8684, avg_missing_before=0.3051, avg_missing_after=0.1356
- course_study_plan: cases=20, attempted=7, success=0, attempt_rate=0.3500, success_rate_of_attempts=0.0000, avg_missing_before=0.3500, avg_missing_after=0.3500
- none: cases=47, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- prerequisite: cases=3, attempted=3, success=1, attempt_rate=1.0000, success_rate_of_attempts=0.3333, avg_missing_before=0.3333, avg_missing_after=1.3333
- regulation_procedure: cases=63, attempted=56, success=15, attempt_rate=0.8889, success_rate_of_attempts=0.2679, avg_missing_before=0.6349, avg_missing_after=2.8730
- unanswerable_refusal: cases=15, attempted=15, success=15, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=0.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- qb_179 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=283.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_118 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=305.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_132 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=322.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_184 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=382.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_099 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=383.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_201 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=450.2, tags=retrieve_not_found, error=none
- qb_274 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=549.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_236 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=571.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_191 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=616.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_140 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=683.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_267 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=844.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_263 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=898.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_320 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1134.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_321 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1159.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_325 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1205.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_316 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1243.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_315 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1336.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_314 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1348.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_306 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1430.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_069 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1494.4, tags=retrieve_found_but_answer_incomplete, error=none
