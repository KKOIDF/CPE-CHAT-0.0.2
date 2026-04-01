# Regression Eval Summary

Generated: 2026-04-01T21:32:15.863417
Input: data/question_bank_250_general_th.json
Base URL: http://127.0.0.1:8011

## Headline

- total cases: 342
- overall pass rate: 0.3596

### Retrieval Metrics
- top-1 hit rate: 0.4854
- top-3 hit rate: 0.6901
- top-5 hit rate: 0.7632
- top-K hit rate: 0.7544
- mean reciprocal rank (mrr): 0.5922

### Answer Quality Metrics
- answer keyword hit rate: 0.4678
- average quality score (1-5): 0.0000
- % correct answers: 0.4678
- % hallucination: 0.0000
- % answerable handled correctly: 0.4883
- citation validity (groundedness): 0.9708
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 3286.25
- median total latency ms: 1016.71
- p95 total latency ms: 11466.95
- avg retrieval latency ms: 2313.35
- median retrieval latency ms: 1128.75
- p95 retrieval latency ms: 5814.00
- avg generation latency ms: 3487.62
- median generation latency ms: 3240.20
- p95 generation latency ms: 9497.86

## Coverage

- total questions: 342
- questions by domain: announcements=135, curriculum=99, general=29, regulations=79
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=135, top1=0.2296, top3=0.4667, top5=0.6296, mrr=0.3690
- curriculum: total=99, top1=0.6465, top3=0.9596, top5=0.9697, mrr=0.7921
- general: total=29, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- regulations: total=79, top1=0.5316, top3=0.6203, top5=0.6456, mrr=0.5732

## By Category

- uncategorized: total=342, overall=0.3596, answer=0.4678, retrieval=0.7544, top1=0.4854, top3=0.6901, top5=0.7632, citation=0.9708

## Error Tag Counts

- retrieve_found_but_answer_incomplete: 135
- pass_or_unclassified: 123
- retrieve_not_found: 81
- context_conflict: 10
- answer_out_of_domain: 8

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.0175
- retrieval_adaptive_retry_succeeded: 0.0175
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.0000
- low_confidence_detected: 0.0380
- initial_retrieval_doc_count: 0.7895
- retry_retrieval_doc_count: 0.0877
- initial_top_score: 0.0463
- retry_top_score: 0.0158

## Answer Schema Metrics By Task

- announcement_procedure: cases=89, attempted=89, success=89, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=3.6742, avg_missing_after=0.0000
- course_factual: cases=35, attempted=12, success=0, attempt_rate=0.3429, success_rate_of_attempts=0.0000, avg_missing_before=0.5429, avg_missing_after=0.5429
- course_study_plan: cases=20, attempted=18, success=14, attempt_rate=0.9000, success_rate_of_attempts=0.7778, avg_missing_before=1.9000, avg_missing_after=0.5000
- none: cases=162, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- prerequisite: cases=1, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- regulation_procedure: cases=35, attempted=29, success=29, attempt_rate=0.8286, success_rate_of_attempts=1.0000, avg_missing_before=2.1714, avg_missing_after=0.7143

## Failed Cases Top 20

- qb_179 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=253.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_184 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=313.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_177 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=392.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_167 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=418.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_301 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=467.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_342 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=472.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_236 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=559.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_014 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=566.1, tags=retrieve_not_found,answer_out_of_domain, error=none
- qb_099 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=573.8, tags=retrieve_not_found, error=none
- qb_321 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=584.3, tags=retrieve_not_found, error=none
- qb_316 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=628.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_161 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=628.9, tags=retrieve_not_found, error=none
- qb_320 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=679.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_169 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=714.0, tags=retrieve_not_found, error=none
- qb_292 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=720.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_256 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=819.7, tags=retrieve_not_found, error=none
- qb_263 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=845.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_261 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=848.2, tags=retrieve_not_found, error=none
- qb_341 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=848.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_097 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=865.2, tags=retrieve_found_but_answer_incomplete, error=none
