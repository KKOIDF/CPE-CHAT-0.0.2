# Regression Eval Summary

Generated: 2026-03-24T21:14:43.360171
Input: eval_cases.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 40
- overall pass rate: 0.0000

### Retrieval Metrics
- top-1 hit rate: 0.0000
- top-K hit rate: 0.0000
- mean reciprocal rank (mrr): 0.0000

### Answer Quality Metrics
- answer keyword hit rate: 0.0000
- citation validity (groundedness): 0.0000
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 1.14
- p95 total latency ms: 1.43
- avg retrieval latency ms: 1.34
- p95 retrieval latency ms: 1.78

## By Category

- announcements_schedule: total=6, overall=0.0000, answer=0.0000, retrieval=0.0000, citation=0.0000
- curriculum_fact_lookup: total=10, overall=0.0000, answer=0.0000, retrieval=0.0000, citation=0.0000
- multi_intent_multi_doc: total=6, overall=0.0000, answer=0.0000, retrieval=0.0000, citation=0.0000
- prerequisite_course_code: total=8, overall=0.0000, answer=0.0000, retrieval=0.0000, citation=0.0000
- regulations: total=8, overall=0.0000, answer=0.0000, retrieval=0.0000, citation=0.0000
- typo_noisy_query: total=2, overall=0.0000, answer=0.0000, retrieval=0.0000, citation=0.0000

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

## Failed Cases Top 10

- multi_001 (multi_intent_multi_doc): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=1.0, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8001): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8001): Failed to establish a new connection: [Errno 111] Connection refused"))
- announcement_004 (announcements_schedule): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=1.0, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8001): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8001): Failed to establish a new connection: [Errno 111] Connection refused"))
- typo_001 (typo_noisy_query): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=1.0, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8001): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8001): Failed to establish a new connection: [Errno 111] Connection refused"))
- curriculum_009 (curriculum_fact_lookup): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=1.0, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8001): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8001): Failed to establish a new connection: [Errno 111] Connection refused"))
- announcement_001 (announcements_schedule): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=1.0, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8001): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8001): Failed to establish a new connection: [Errno 111] Connection refused"))
- typo_002 (typo_noisy_query): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=1.0, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8001): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8001): Failed to establish a new connection: [Errno 111] Connection refused"))
- curriculum_010 (curriculum_fact_lookup): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=1.0, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8001): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8001): Failed to establish a new connection: [Errno 111] Connection refused"))
- multi_006 (multi_intent_multi_doc): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=1.0, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8001): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8001): Failed to establish a new connection: [Errno 111] Connection refused"))
- multi_005 (multi_intent_multi_doc): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=1.0, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8001): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8001): Failed to establish a new connection: [Errno 111] Connection refused"))
- multi_002 (multi_intent_multi_doc): coverage=0.00, retrieval=False, citation=False, must_not=True, latency_ms=1.0, error=ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8001): Max retries exceeded with url: /rag/answer (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8001): Failed to establish a new connection: [Errno 111] Connection refused"))
