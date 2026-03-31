# Regression Eval Summary

Generated: 2026-03-30T10:58:34.288916
Input: data/question_bank_250_general_th.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 342
- overall pass rate: 0.1637

### Retrieval Metrics
- top-1 hit rate: 0.5556
- top-3 hit rate: 0.7456
- top-5 hit rate: 0.7602
- top-K hit rate: 0.7602
- mean reciprocal rank (mrr): 0.6442

### Answer Quality Metrics
- answer keyword hit rate: 0.2251
- average quality score (1-5): 0.0000
- % correct answers: 0.2251
- % hallucination: 0.0000
- % answerable handled correctly: 0.2485
- citation validity (groundedness): 0.9883
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 2523.99
- median total latency ms: 954.01
- p95 total latency ms: 9127.96
- avg retrieval latency ms: 1982.49
- median retrieval latency ms: 1105.58
- p95 retrieval latency ms: 4880.22
- avg generation latency ms: 2577.25
- median generation latency ms: 2148.23
- p95 generation latency ms: 8351.88

## Coverage

- total questions: 342
- questions by domain: announcements=135, curriculum=99, general=29, regulations=79
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=135, top1=0.4148, top3=0.6074, top5=0.6296, mrr=0.5077
- curriculum: total=99, top1=0.6465, top3=0.9596, top5=0.9596, mrr=0.7862
- general: total=29, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- regulations: total=79, top1=0.5190, top3=0.6203, top5=0.6456, mrr=0.5690

## By Category

- uncategorized: total=342, overall=0.1637, answer=0.2251, retrieval=0.7602, top1=0.5556, top3=0.7456, top5=0.7602, citation=0.9883

## Error Tag Counts

- retrieve_found_but_answer_incomplete: 204
- retrieve_not_found: 82
- pass_or_unclassified: 56
- answer_out_of_domain: 8
- context_conflict: 4

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.0234
- retrieval_adaptive_retry_succeeded: 0.0234
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.0000
- low_confidence_detected: 0.0439
- initial_retrieval_doc_count: 0.8187
- retry_retrieval_doc_count: 0.1170
- initial_top_score: 0.0464
- retry_top_score: 0.0214

## Failed Cases Top 20

- qb_034 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=238.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_342 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=299.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_132 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=300.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_177 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=305.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_179 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=322.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_184 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=329.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_236 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=336.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_167 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=356.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_099 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=383.5, tags=retrieve_not_found, error=none
- qb_301 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=393.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_118 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=394.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_292 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=461.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_182 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=472.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_160 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=476.9, tags=retrieve_not_found, error=none
- qb_079 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=494.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_104 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=506.4, tags=retrieve_not_found, error=none
- qb_247 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=521.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_049 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=533.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_014 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=536.5, tags=retrieve_not_found,answer_out_of_domain, error=none
- qb_006 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=646.6, tags=retrieve_found_but_answer_incomplete, error=none
