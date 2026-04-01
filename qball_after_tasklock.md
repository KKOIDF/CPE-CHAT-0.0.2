# Regression Eval Summary

Generated: 2026-03-31T20:04:20.513169
Input: /tmp/eval_cases_qball_342.json
Base URL: http://127.0.0.1:8011

## Headline

- total cases: 342
- overall pass rate: 0.2690

### Retrieval Metrics
- top-1 hit rate: 0.5029
- top-3 hit rate: 0.7164
- top-5 hit rate: 0.7690
- top-K hit rate: 0.8304
- mean reciprocal rank (mrr): 0.6169

### Answer Quality Metrics
- answer keyword hit rate: 0.3012
- average quality score (1-5): 0.0000
- % correct answers: 0.3012
- % hallucination: 0.0000
- % answerable handled correctly: 0.3158
- citation validity (groundedness): 0.9737
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 2608.45
- median total latency ms: 1614.10
- p95 total latency ms: 8649.63
- avg retrieval latency ms: 1702.23
- median retrieval latency ms: 940.08
- p95 retrieval latency ms: 4306.76
- avg generation latency ms: 2645.36
- median generation latency ms: 2092.30
- p95 generation latency ms: 6446.88

## Coverage

- total questions: 342
- questions by domain: announcements=156, curriculum=102, regulations=81, unknown=3
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=156, top1=0.3526, top3=0.5769, top5=0.6795, mrr=0.4898
- curriculum: total=102, top1=0.6569, top3=0.9608, top5=0.9608, mrr=0.7958
- regulations: total=81, top1=0.5802, top3=0.6667, top5=0.6914, mrr=0.6223
- unknown: total=3, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000

## By Category

- uncategorized: total=342, overall=0.2690, answer=0.3012, retrieval=0.8304, top1=0.5029, top3=0.7164, top5=0.7690, citation=0.9737

## Error Tag Counts

- retrieve_found_but_answer_incomplete: 192
- pass_or_unclassified: 92
- retrieve_not_found: 58
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

- announcement_procedure: cases=52, attempted=52, success=50, attempt_rate=1.0000, success_rate_of_attempts=0.9615, avg_missing_before=3.5577, avg_missing_after=1.3846
- course_factual: cases=36, attempted=7, success=0, attempt_rate=0.1944, success_rate_of_attempts=0.0000, avg_missing_before=0.5833, avg_missing_after=0.5833
- course_study_plan: cases=20, attempted=20, success=20, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=1.3000, avg_missing_after=0.0500
- none: cases=182, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- regulation_procedure: cases=52, attempted=42, success=37, attempt_rate=0.8077, success_rate_of_attempts=0.8810, avg_missing_before=2.1346, avg_missing_after=0.8654

## Failed Cases Top 20

- qb_179 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=224.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_177 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=232.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_099 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=316.0, tags=retrieve_not_found, error=none
- qb_301 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=366.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_184 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=371.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_014 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=392.0, tags=retrieve_not_found,answer_out_of_domain, error=none
- qb_292 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=426.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_236 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=499.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_167 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=503.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_320 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=535.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_319 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=543.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_321 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=567.3, tags=retrieve_not_found, error=none
- qb_105 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=592.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_261 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=596.8, tags=retrieve_not_found, error=none
- qb_101 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=599.7, tags=retrieve_not_found, error=none
- qb_227 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=610.9, tags=retrieve_not_found, error=none
- qb_161 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=612.6, tags=retrieve_not_found, error=none
- qb_336 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=624.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_291 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=630.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_046 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=636.4, tags=retrieve_not_found, error=none
