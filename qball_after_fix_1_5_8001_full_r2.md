# Regression Eval Summary

Generated: 2026-04-12T17:32:26.367885
Input: data/question_bank_250_general_th.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 342
- overall pass rate: 0.3596

### Retrieval Metrics
- top-1 hit rate: 0.7310
- top-3 hit rate: 0.9269
- top-5 hit rate: 0.9298
- top-K hit rate: 0.8772
- mean reciprocal rank (mrr): 0.8034

### Answer Quality Metrics
- answer keyword hit rate: 0.3860
- average quality score (1-5): 0.0000
- % correct answers: 0.3860
- % hallucination: 0.0000
- % answerable handled correctly: 0.4269
- citation validity (groundedness): 0.7982
- must-not contain pass rate: 1.0000
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 5871.87
- median total latency ms: 1545.78
- p95 total latency ms: 21922.34
- avg retrieval latency ms: 3620.63
- median retrieval latency ms: 1764.43
- p95 retrieval latency ms: 8657.49
- avg generation latency ms: 7363.25
- median generation latency ms: 6687.02
- p95 generation latency ms: 14366.50

## Coverage

- total questions: 342
- questions by domain: announcements=135, curriculum=99, general=29, regulations=79
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=135, top1=0.7407, top3=0.8963, top5=0.9037, mrr=0.8031
- curriculum: total=99, top1=0.7879, top3=0.9596, top5=0.9596, mrr=0.8552
- general: total=29, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- regulations: total=79, top1=0.5443, top3=0.9114, top5=0.9114, mrr=0.6667

## By Category

- uncategorized: total=342, overall=0.3596, answer=0.3860, retrieval=0.8772, top1=0.7310, top3=0.9269, top5=0.9298, citation=0.7982

## Error Tag Counts

- retrieve_found_but_answer_incomplete: 177
- pass_or_unclassified: 123
- context_conflict: 69
- retrieve_not_found: 24
- answer_out_of_domain: 7

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.3158
- retrieval_adaptive_retry_succeeded: 0.2661
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.1228
- structured_rescue_succeeded: 0.1228
- curriculum_bypass_vector_triggered: 0.2222
- low_confidence_detected: 0.3392
- initial_retrieval_doc_count: 2.8918
- retry_retrieval_doc_count: 1.2836
- initial_top_score: 0.2010
- retry_top_score: 0.0949

## Answer Schema Metrics By Task

- announcement_procedure: cases=89, attempted=89, success=88, attempt_rate=1.0000, success_rate_of_attempts=0.9888, avg_missing_before=3.5730, avg_missing_after=0.0449
- course_factual: cases=32, attempted=4, success=0, attempt_rate=0.1250, success_rate_of_attempts=0.0000, avg_missing_before=2.3438, avg_missing_after=2.3438
- course_study_plan: cases=20, attempted=20, success=0, attempt_rate=1.0000, success_rate_of_attempts=0.0000, avg_missing_before=2.3500, avg_missing_after=2.3500
- none: cases=165, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- prerequisite: cases=1, attempted=1, success=1, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=1.0000, avg_missing_after=0.0000
- regulation_procedure: cases=35, attempted=28, success=19, attempt_rate=0.8000, success_rate_of_attempts=0.6786, avg_missing_before=3.4286, avg_missing_after=2.6000

## Failed Cases Top 20

- qb_301 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=157.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_014 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=246.7, tags=retrieve_not_found,answer_out_of_domain, error=none
- qb_179 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=288.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_177 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=302.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_184 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=337.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_236 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=339.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_167 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=347.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_099 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=373.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_292 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=597.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_342 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=889.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_306 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=986.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_188 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=1090.0, tags=retrieve_not_found, error=none
- qb_064 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=1162.1, tags=retrieve_not_found, error=none
- qb_163 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=1200.0, tags=retrieve_not_found, error=none
- qb_320 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1386.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_256 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1406.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_161 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1455.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_097 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1478.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_169 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1598.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_101 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1610.5, tags=retrieve_found_but_answer_incomplete, error=none
