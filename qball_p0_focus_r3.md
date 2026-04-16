# Regression Eval Summary

Generated: 2026-04-16T18:05:31.147696
Input: eval_cases_p0_focus.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 5
- overall pass rate: 0.0000

### Retrieval Metrics
- top-1 hit rate: 0.0000
- top-3 hit rate: 0.0000
- top-5 hit rate: 0.0000
- top-K hit rate: 0.0000
- mean reciprocal rank (mrr): 0.0000

### Answer Quality Metrics
- answer keyword hit rate: 0.0000
- average quality score (1-5): 0.0000
- % correct answers: 0.0000
- % hallucination: 0.0000
- % answerable handled correctly: 0.0000
- citation validity (groundedness): 0.0000
- citation precision: 0.0000
- citation recall: 0.0000
- citation micro precision: 0.0000
- citation micro recall: 0.0000
- must-not contain pass rate: 1.0000
- runtime error rate: 1.0000
- runtime error count: 5

### Latency Metrics
- avg total latency ms: 0.98
- median total latency ms: 0.93
- p95 total latency ms: 1.21
- avg retrieval latency ms: 1.24
- median retrieval latency ms: 1.16
- p95 retrieval latency ms: 1.78
- avg generation latency ms: 0.11
- median generation latency ms: 0.11
- p95 generation latency ms: 0.19

## Coverage

- total questions: 5
- questions by domain: curriculum=3, multi=1, regulations=1
- questions by difficulty: unspecified=5
- questions by question type: unspecified=5

## Retrieval By Domain

- curriculum: total=3, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- multi: total=1, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- regulations: total=1, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000

## Domain Monitor

- curriculum: total=3, overall=0.0000, answer=0.0000, retrieval=0.0000, citation=0.0000, avg_latency_ms=1.02, p95_latency_ms=1.21
- multi: total=1, overall=0.0000, answer=0.0000, retrieval=0.0000, citation=0.0000, avg_latency_ms=0.79, p95_latency_ms=0.79
- regulations: total=1, overall=0.0000, answer=0.0000, retrieval=0.0000, citation=0.0000, avg_latency_ms=1.06, p95_latency_ms=1.06

## By Category

- multi_intent_multi_doc: total=1, overall=0.0000, answer=0.0000, retrieval=0.0000, top1=0.0000, top3=0.0000, top5=0.0000, citation=0.0000
- prerequisite_course_code: total=3, overall=0.0000, answer=0.0000, retrieval=0.0000, top1=0.0000, top3=0.0000, top5=0.0000, citation=0.0000
- regulations: total=1, overall=0.0000, answer=0.0000, retrieval=0.0000, top1=0.0000, top3=0.0000, top5=0.0000, citation=0.0000

## Error Tag Counts

- context_conflict: 5
- retrieve_not_found: 5
- runtime_error: 5
- answer_out_of_domain: 4

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.0000
- retrieval_adaptive_retry_succeeded: 0.0000
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.0000
- low_confidence_detected: 0.0000
- initial_retrieval_doc_count: 0.0000
- retry_retrieval_doc_count: 0.0000
- initial_top_score: 0.0000
- retry_top_score: 0.0000

## Answer Schema Metrics By Task

- none: cases=5, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- multi_003 (multi_intent_multi_doc): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.8, tags=runtime_error,retrieve_not_found,context_conflict, error=ConnectionError: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
- prereq_002 (prerequisite_course_code): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.9, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
- prereq_003 (prerequisite_course_code): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.9, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
- regulations_004 (regulations): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=1.1, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
- prereq_001 (prerequisite_course_code): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=1.2, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
