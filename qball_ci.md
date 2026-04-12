# Regression Eval Summary

Generated: 2026-04-12T13:19:43.185026
Input: data/question_bank_250_general_th.json
Base URL: http://127.0.0.1:8011

## Headline

- total cases: 342
- overall pass rate: 0.0000

### Retrieval Metrics
- top-1 hit rate: 0.0848
- top-3 hit rate: 0.0848
- top-5 hit rate: 0.0848
- top-K hit rate: 0.0000
- mean reciprocal rank (mrr): 0.0848

### Answer Quality Metrics
- answer keyword hit rate: 0.0000
- average quality score (1-5): 0.0000
- % correct answers: 0.0000
- % hallucination: 0.0000
- % answerable handled correctly: 0.0000
- citation validity (groundedness): 0.0000
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 1.06
- median total latency ms: 1.06
- p95 total latency ms: 1.66
- avg retrieval latency ms: 1.05
- median retrieval latency ms: 1.07
- p95 retrieval latency ms: 1.76
- avg generation latency ms: 0.33
- median generation latency ms: 0.12
- p95 generation latency ms: 0.66

## Coverage

- total questions: 342
- questions by domain: announcements=135, curriculum=99, general=29, regulations=79
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=135, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- curriculum: total=99, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- general: total=29, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- regulations: total=79, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000

## By Category

- uncategorized: total=342, overall=0.0000, answer=0.0000, retrieval=0.0000, top1=0.0848, top3=0.0848, top5=0.0848, citation=0.0000

## Error Tag Counts

- context_conflict: 342
- runtime_error: 342
- answer_out_of_domain: 313
- retrieve_not_found: 313

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

- none: cases=342, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- qb_064 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_085 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_012 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_043 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_075 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_084 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_076 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_011 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_071 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_046 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_038 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_068 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_039 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_009 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_047 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_079 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_042 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_097 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_067 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
- qb_037 (uncategorized): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=0.5, tags=runtime_error,retrieve_not_found,answer_out_of_domain,context_conflict, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8011): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8011): Failed to establish a new connection: [Errno 111] Connection refused"))
