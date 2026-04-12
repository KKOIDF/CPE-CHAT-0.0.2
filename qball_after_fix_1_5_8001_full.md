# Regression Eval Summary

Generated: 2026-04-12T15:27:17.205638
Input: data/question_bank_250_general_th.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 342
- overall pass rate: 0.4181

### Retrieval Metrics
- top-1 hit rate: 0.7193
- top-3 hit rate: 0.9327
- top-5 hit rate: 0.9357
- top-K hit rate: 0.8830
- mean reciprocal rank (mrr): 0.8024

### Answer Quality Metrics
- answer keyword hit rate: 0.4444
- average quality score (1-5): 0.0000
- % correct answers: 0.4444
- % hallucination: 0.0000
- % answerable handled correctly: 0.4854
- citation validity (groundedness): 0.8801
- must-not contain pass rate: 1.0000
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 4485.09
- median total latency ms: 1462.93
- p95 total latency ms: 15528.49
- avg retrieval latency ms: 2733.08
- median retrieval latency ms: 1646.56
- p95 retrieval latency ms: 7767.44
- avg generation latency ms: 5467.31
- median generation latency ms: 5913.82
- p95 generation latency ms: 13912.56

## Coverage

- total questions: 342
- questions by domain: announcements=135, curriculum=99, general=29, regulations=79
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=135, top1=0.7407, top3=0.8963, top5=0.9037, mrr=0.8031
- curriculum: total=99, top1=0.7475, top3=0.9798, top5=0.9798, mrr=0.8519
- general: total=29, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- regulations: total=79, top1=0.5443, top3=0.9114, top5=0.9114, mrr=0.6667

## By Category

- uncategorized: total=342, overall=0.4181, answer=0.4444, retrieval=0.8830, top1=0.7193, top3=0.9327, top5=0.9357, citation=0.8801

## Error Tag Counts

- retrieve_found_but_answer_incomplete: 159
- pass_or_unclassified: 143
- context_conflict: 41
- retrieve_not_found: 22
- answer_out_of_domain: 7

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.2924
- retrieval_adaptive_retry_succeeded: 0.2427
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0673
- structured_rescue_succeeded: 0.0673
- curriculum_bypass_vector_triggered: 0.1374
- low_confidence_detected: 0.3158
- initial_retrieval_doc_count: 2.6608
- retry_retrieval_doc_count: 1.1901
- initial_top_score: 0.1426
- retry_top_score: 0.0817

## Answer Schema Metrics By Task

- announcement_procedure: cases=89, attempted=89, success=88, attempt_rate=1.0000, success_rate_of_attempts=0.9888, avg_missing_before=3.5730, avg_missing_after=0.0449
- course_factual: cases=32, attempted=10, success=0, attempt_rate=0.3125, success_rate_of_attempts=0.0000, avg_missing_before=0.8125, avg_missing_after=0.8125
- course_study_plan: cases=20, attempted=20, success=14, attempt_rate=1.0000, success_rate_of_attempts=0.7000, avg_missing_before=2.2500, avg_missing_after=0.7000
- none: cases=165, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- prerequisite: cases=1, attempted=1, success=1, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=1.0000, avg_missing_after=0.0000
- regulation_procedure: cases=35, attempted=29, success=27, attempt_rate=0.8286, success_rate_of_attempts=0.9310, avg_missing_before=2.7143, avg_missing_after=0.9143

## Failed Cases Top 20

- qb_301 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=166.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_177 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=337.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_179 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=353.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_014 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=365.9, tags=retrieve_not_found,answer_out_of_domain, error=none
- qb_184 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=370.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_167 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=383.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_292 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=391.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_099 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=397.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_236 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=446.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_342 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=929.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_306 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=950.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_188 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=1087.4, tags=retrieve_not_found, error=none
- qb_163 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=1139.6, tags=retrieve_not_found, error=none
- qb_274 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1189.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_064 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=1232.9, tags=retrieve_not_found, error=none
- qb_320 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1241.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_287 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1262.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_256 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1294.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_035 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1368.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_316 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=1457.2, tags=retrieve_found_but_answer_incomplete, error=none
