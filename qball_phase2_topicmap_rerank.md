# Regression Eval Summary

Generated: 2026-03-31T23:04:25.579183
Input: data/question_bank_250_general_th.json
Base URL: http://127.0.0.1:8011

## Headline

- total cases: 342
- overall pass rate: 0.2807

### Retrieval Metrics
- top-1 hit rate: 0.5058
- top-3 hit rate: 0.7164
- top-5 hit rate: 0.7719
- top-K hit rate: 0.8246
- mean reciprocal rank (mrr): 0.6194

### Answer Quality Metrics
- answer keyword hit rate: 0.3041
- average quality score (1-5): 0.0000
- % correct answers: 0.3041
- % hallucination: 0.0000
- % answerable handled correctly: 0.3246
- citation validity (groundedness): 0.9737
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 2841.86
- median total latency ms: 730.67
- p95 total latency ms: 11215.68
- avg retrieval latency ms: 1796.03
- median retrieval latency ms: 942.32
- p95 retrieval latency ms: 4901.11
- avg generation latency ms: 3475.85
- median generation latency ms: 2790.39
- p95 generation latency ms: 8548.06

## Coverage

- total questions: 342
- questions by domain: announcements=135, curriculum=99, general=29, regulations=79
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=135, top1=0.2519, top3=0.5111, top5=0.6296, mrr=0.4104
- curriculum: total=99, top1=0.6566, top3=0.9596, top5=0.9697, mrr=0.7983
- general: total=29, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- regulations: total=79, top1=0.5696, top3=0.6582, top5=0.6835, mrr=0.6128

## By Category

- uncategorized: total=342, overall=0.2807, answer=0.3041, retrieval=0.8246, top1=0.5058, top3=0.7164, top5=0.7719, citation=0.9737

## Error Tag Counts

- retrieve_found_but_answer_incomplete: 186
- pass_or_unclassified: 96
- retrieve_not_found: 57
- context_conflict: 9
- answer_out_of_domain: 7

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.0175
- retrieval_adaptive_retry_succeeded: 0.0175
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.0000
- low_confidence_detected: 0.0380
- initial_retrieval_doc_count: 1.2632
- retry_retrieval_doc_count: 0.1404
- initial_top_score: 0.0463
- retry_top_score: 0.0158

## Answer Schema Metrics By Task

- announcement_procedure: cases=52, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=3.5577, avg_missing_after=3.5577
- course_factual: cases=36, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.5556, avg_missing_after=0.5556
- course_study_plan: cases=20, attempted=19, success=19, attempt_rate=0.9500, success_rate_of_attempts=1.0000, avg_missing_before=1.3500, avg_missing_after=0.0500
- none: cases=182, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- regulation_procedure: cases=52, attempted=42, success=35, attempt_rate=0.8077, success_rate_of_attempts=0.8333, avg_missing_before=2.1538, avg_missing_after=0.9808

## Failed Cases Top 20

- qb_179 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=233.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_177 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=234.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_342 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=264.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_167 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=273.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_184 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=280.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_236 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=280.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_301 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=314.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_099 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=320.2, tags=retrieve_not_found, error=none
- qb_014 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=395.8, tags=retrieve_not_found,answer_out_of_domain, error=none
- qb_321 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=530.5, tags=retrieve_not_found, error=none
- qb_320 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=531.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_253 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=549.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_157 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=574.6, tags=retrieve_not_found, error=none
- qb_325 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=577.9, tags=retrieve_not_found, error=none
- qb_319 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=580.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_105 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=593.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_261 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=594.1, tags=retrieve_not_found, error=none
- qb_101 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=595.3, tags=retrieve_not_found, error=none
- qb_097 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=602.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_265 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=603.3, tags=retrieve_found_but_answer_incomplete, error=none
