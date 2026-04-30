# Regression Eval Summary

Generated: 2026-04-30T15:12:33.474875
Input: data/question_bank_250_general_th.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 342
- overall pass rate: 0.6170

### Retrieval Metrics
- top-1 hit rate: 0.8216
- top-3 hit rate: 0.9444
- top-5 hit rate: 0.9503
- top-K hit rate: 0.9240
- mean reciprocal rank (mrr): 0.8694

### Answer Quality Metrics
- answer keyword hit rate: 0.6462
- average quality score (1-5): 0.0000
- % correct answers: 0.6462
- % hallucination: 0.0000
- % answerable handled correctly: 0.6637
- citation validity (groundedness): 0.9737
- citation precision: 0.9114
- citation recall: 0.9627
- citation micro precision: 0.9075
- citation micro recall: 0.2823
- must-not contain pass rate: 1.0000
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 1215.96
- median total latency ms: 827.13
- p95 total latency ms: 3669.02
- avg retrieval latency ms: 569.79
- median retrieval latency ms: 517.67
- p95 retrieval latency ms: 1543.01
- avg generation latency ms: 1277.41
- median generation latency ms: 1058.38
- p95 generation latency ms: 3230.52

## Coverage

- total questions: 342
- questions by domain: announcements=135, curriculum=99, general=29, regulations=79
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=135, top1=0.7259, top3=0.9407, top5=0.9556, mrr=0.8148
- curriculum: total=99, top1=0.8485, top3=0.9091, top5=0.9091, mrr=0.8687
- general: total=29, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- regulations: total=79, top1=0.8861, top3=0.9747, top5=0.9747, mrr=0.9156

## Domain Monitor

- announcements: total=135, overall=0.6741, answer=0.7037, retrieval=0.9556, citation=1.0000, avg_latency_ms=1557.82, p95_latency_ms=2788.61
- curriculum: total=99, overall=0.5657, answer=0.6061, retrieval=0.9091, citation=1.0000, avg_latency_ms=1235.43, p95_latency_ms=4196.56
- general: total=29, overall=0.4138, answer=0.4138, retrieval=0.6897, citation=0.6897, avg_latency_ms=1429.56, p95_latency_ms=3669.02
- regulations: total=79, overall=0.6582, answer=0.6835, retrieval=0.9747, citation=1.0000, avg_latency_ms=528.98, p95_latency_ms=2649.18

## By Category

- uncategorized: total=342, overall=0.6170, answer=0.6462, retrieval=0.9240, top1=0.8216, top3=0.9444, top5=0.9503, citation=0.9737

## Error Tag Counts

- pass_or_unclassified: 211
- retrieve_found_but_answer_incomplete: 105
- retrieve_not_found: 17
- context_conflict: 9
- answer_out_of_domain: 4

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.1053
- retrieval_adaptive_retry_succeeded: 0.0702
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.0526
- low_confidence_detected: 0.1111
- initial_retrieval_doc_count: 0.6199
- retry_retrieval_doc_count: 0.3041
- initial_top_score: 0.0169
- retry_top_score: 0.0228

## Answer Schema Metrics By Task

- announcement_procedure: cases=98, attempted=98, success=98, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=3.2041, avg_missing_after=0.0000
- announcement_temporal: cases=7, attempted=0, success=4, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- announcement_verification: cases=30, attempted=30, success=30, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=2.1667, avg_missing_after=0.0000
- case_appeal_rejected_strict: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- case_cheating_penalty: cases=2, attempted=0, success=2, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- case_cheating_rejected_strict: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- case_device_warning_rejected_strict: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- case_emergency_exception_strict: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- case_emergency_rejected_strict: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- case_exam_emergency: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- case_late_15_60: cases=4, attempted=0, success=4, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- case_late_over_60: cases=8, attempted=0, success=8, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- case_phone_forbidden: cases=5, attempted=0, success=5, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- course_factual: cases=29, attempted=10, success=6, attempt_rate=0.3448, success_rate_of_attempts=0.6000, avg_missing_before=0.6552, avg_missing_after=0.2759
- exact_code: cases=31, attempted=0, success=31, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- exam_phrase_calculator: cases=5, attempted=0, success=5, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- exam_phrase_late_15: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- exam_phrase_late_60: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- exam_phrase_late_generic: cases=4, attempted=0, success=4, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- exam_phrase_leave_60: cases=5, attempted=0, success=5, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- exam_phrase_leave_temp_structured: cases=5, attempted=0, success=5, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- exam_topic_การหมดสิทธิ์สอบ: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- exam_topic_บทลงโทษ: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- exam_topic_อุทธรณ์ผลการสอบ: cases=2, attempted=0, success=2, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- none: cases=38, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- prereq_exact: cases=2, attempted=0, success=2, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- prerequisite: cases=1, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- regulation_procedure: cases=12, attempted=8, success=8, attempt_rate=0.6667, success_rate_of_attempts=1.0000, avg_missing_before=2.5833, avg_missing_after=0.0000
- strict_qb_007: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- strict_qb_027: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- strict_qb_060: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- strict_qb_069: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- strict_qb_099: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- strict_qb_132: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- strict_qb_141: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- strict_qb_167: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- strict_qb_177: cases=1, attempted=0, success=1, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- study_plan_course: cases=20, attempted=0, success=20, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- unanswerable_refusal: cases=15, attempted=15, success=15, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=0.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- qb_118 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=83.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_231 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=87.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_128 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=91.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_184 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=91.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_272 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=98.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_274 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=577.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_320 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=881.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_267 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=923.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_321 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1123.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_316 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1251.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_314 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1342.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_325 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1350.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_315 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1373.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_290 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1442.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_306 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1593.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_260 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=1873.2, tags=retrieve_not_found, error=none
- qb_310 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1950.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_300 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1963.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_214 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1963.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_324 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=2005.7, tags=retrieve_found_but_answer_incomplete, error=none
