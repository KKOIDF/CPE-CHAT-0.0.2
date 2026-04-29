# Regression Eval Summary

Generated: 2026-04-29T14:35:10.736847
Input: data/question_bank_250_general_th.json
Base URL: http://127.0.0.1:8014

## Headline

- total cases: 342
- overall pass rate: 0.8743

### Retrieval Metrics
- top-1 hit rate: 0.9444
- top-3 hit rate: 0.9591
- top-5 hit rate: 0.9620
- top-K hit rate: 0.9620
- mean reciprocal rank (mrr): 0.9505

### Answer Quality Metrics
- answer keyword hit rate: 0.9444
- average quality score (1-5): 0.0000
- % correct answers: 0.9444
- % hallucination: 0.0000
- % answerable handled correctly: 0.9444
- citation validity (groundedness): 1.0000
- citation precision: 0.9152
- citation recall: 0.9979
- citation micro precision: 0.9157
- citation micro recall: 0.2925
- must-not contain pass rate: 1.0000
- runtime error rate: 0.0322
- runtime error count: 11

### Latency Metrics
- avg total latency ms: 252.74
- median total latency ms: 2.34
- p95 total latency ms: 2779.27
- avg retrieval latency ms: 61.22
- median retrieval latency ms: 2.34
- p95 retrieval latency ms: 646.18
- avg generation latency ms: 2620.00
- median generation latency ms: 2613.81
- p95 generation latency ms: 4282.88

## Coverage

- total questions: 342
- questions by domain: announcements=135, curriculum=99, general=29, regulations=79
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=135, top1=0.8741, top3=0.9037, top5=0.9037, mrr=0.8852
- curriculum: total=99, top1=0.9899, top3=0.9899, top5=1.0000, mrr=0.9924
- general: total=29, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- regulations: total=79, top1=0.9873, top3=1.0000, top5=1.0000, mrr=0.9916

## Domain Monitor

- announcements: total=135, overall=0.8074, answer=0.9037, retrieval=0.9037, citation=1.0000, avg_latency_ms=460.85, p95_latency_ms=3627.33
- curriculum: total=99, overall=0.9899, answer=0.9899, retrieval=1.0000, citation=1.0000, avg_latency_ms=125.27, p95_latency_ms=4.28
- general: total=29, overall=0.5517, answer=0.9310, retrieval=1.0000, citation=1.0000, avg_latency_ms=233.33, p95_latency_ms=2748.97
- regulations: total=79, overall=0.9620, answer=0.9620, retrieval=1.0000, citation=1.0000, avg_latency_ms=63.96, p95_latency_ms=4.62

## By Category

- uncategorized: total=342, overall=0.8743, answer=0.9444, retrieval=0.9620, top1=0.9444, top3=0.9591, top5=0.9620, citation=1.0000

## Error Tag Counts

- pass_or_unclassified: 299
- retrieve_found_but_answer_incomplete: 19
- retrieve_not_found: 13
- runtime_error: 11

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.0468
- retrieval_adaptive_retry_succeeded: 0.0468
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0058
- structured_rescue_succeeded: 0.0058
- curriculum_bypass_vector_triggered: 0.0029
- low_confidence_detected: 0.0497
- initial_retrieval_doc_count: 0.2456
- retry_retrieval_doc_count: 0.1871
- initial_top_score: 0.0029
- retry_top_score: 0.0121

## Answer Schema Metrics By Task

- announcement_procedure: cases=12, attempted=12, success=12, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=3.0000, avg_missing_after=0.0000
- announcement_temporal: cases=1, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- announcement_verification: cases=6, attempted=6, success=6, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=2.0000, avg_missing_after=0.0000
- course_factual: cases=1, attempted=1, success=0, attempt_rate=1.0000, success_rate_of_attempts=0.0000, avg_missing_before=2.0000, avg_missing_after=2.0000
- none: cases=320, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- regulation_procedure: cases=2, attempted=2, success=0, attempt_rate=1.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=2.0000

## Failed Cases Top 20

- qb_293 (uncategorized): coverage=1.00, retrieval=True, citation=True, must_not=True, latency_ms=2.2, tags=runtime_error, error=HTTPError: 500 Server Error: Internal Server Error for url: http://127.0.0.1:8014/rag/query
- qb_305 (uncategorized): coverage=1.00, retrieval=True, citation=True, must_not=True, latency_ms=2.3, tags=runtime_error, error=HTTPError: 500 Server Error: Internal Server Error for url: http://127.0.0.1:8014/rag/query
- qb_341 (uncategorized): coverage=1.00, retrieval=True, citation=True, must_not=True, latency_ms=2.3, tags=runtime_error, error=HTTPError: 500 Server Error: Internal Server Error for url: http://127.0.0.1:8014/rag/query
- qb_249 (uncategorized): coverage=1.00, retrieval=True, citation=True, must_not=True, latency_ms=2.3, tags=runtime_error, error=HTTPError: 500 Server Error: Internal Server Error for url: http://127.0.0.1:8014/rag/query
- qb_335 (uncategorized): coverage=1.00, retrieval=True, citation=True, must_not=True, latency_ms=2.3, tags=runtime_error, error=HTTPError: 500 Server Error: Internal Server Error for url: http://127.0.0.1:8014/rag/query
- qb_301 (uncategorized): coverage=1.00, retrieval=True, citation=True, must_not=True, latency_ms=2.3, tags=runtime_error, error=HTTPError: 500 Server Error: Internal Server Error for url: http://127.0.0.1:8014/rag/query
- qb_330 (uncategorized): coverage=1.00, retrieval=True, citation=True, must_not=True, latency_ms=2.4, tags=runtime_error, error=HTTPError: 500 Server Error: Internal Server Error for url: http://127.0.0.1:8014/rag/query
- qb_213 (uncategorized): coverage=1.00, retrieval=True, citation=True, must_not=True, latency_ms=2.6, tags=runtime_error, error=HTTPError: 500 Server Error: Internal Server Error for url: http://127.0.0.1:8014/rag/query
- qb_329 (uncategorized): coverage=1.00, retrieval=True, citation=True, must_not=True, latency_ms=2.6, tags=runtime_error, error=HTTPError: 500 Server Error: Internal Server Error for url: http://127.0.0.1:8014/rag/query
- qb_237 (uncategorized): coverage=1.00, retrieval=True, citation=True, must_not=True, latency_ms=2.6, tags=runtime_error, error=HTTPError: 500 Server Error: Internal Server Error for url: http://127.0.0.1:8014/rag/query
- qb_192 (uncategorized): coverage=1.00, retrieval=True, citation=True, must_not=True, latency_ms=4.4, tags=runtime_error, error=HTTPError: 500 Server Error: Internal Server Error for url: http://127.0.0.1:8014/rag/query
- qb_274 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=467.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_267 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=752.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_092 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=2749.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_311 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=2779.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_324 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=3245.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_214 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=3390.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_300 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=3412.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_295 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=3894.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_266 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=4356.5, tags=retrieve_found_but_answer_incomplete, error=none
