# Regression Eval Summary

Generated: 2026-03-31T16:21:25.079765
Input: data/question_bank_250_general_th.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 342
- overall pass rate: 0.2105

### Retrieval Metrics
- top-1 hit rate: 0.5526
- top-3 hit rate: 0.7427
- top-5 hit rate: 0.7573
- top-K hit rate: 0.7573
- mean reciprocal rank (mrr): 0.6408

### Answer Quality Metrics
- answer keyword hit rate: 0.2895
- average quality score (1-5): 0.0000
- % correct answers: 0.2895
- % hallucination: 0.0000
- % answerable handled correctly: 0.3129
- citation validity (groundedness): 0.9708
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 2715.76
- median total latency ms: 947.56
- p95 total latency ms: 10591.54
- avg retrieval latency ms: 2191.82
- median retrieval latency ms: 1160.57
- p95 retrieval latency ms: 6126.57
- avg generation latency ms: 3130.42
- median generation latency ms: 2450.22
- p95 generation latency ms: 8689.59

## Coverage

- total questions: 342
- questions by domain: announcements=135, curriculum=99, general=29, regulations=79
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=135, top1=0.4148, top3=0.6074, top5=0.6296, mrr=0.5077
- curriculum: total=99, top1=0.6465, top3=0.9596, top5=0.9596, mrr=0.7845
- general: total=29, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- regulations: total=79, top1=0.5063, top3=0.6076, top5=0.6329, mrr=0.5563

## By Category

- uncategorized: total=342, overall=0.2105, answer=0.2895, retrieval=0.7573, top1=0.5526, top3=0.7427, top5=0.7573, citation=0.9708

## Error Tag Counts

- retrieve_found_but_answer_incomplete: 187
- retrieve_not_found: 83
- pass_or_unclassified: 72
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

## Failed Cases Top 20

- qb_179 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=292.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_177 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=293.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_342 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=309.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_184 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=333.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_167 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=339.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_301 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=358.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_236 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=367.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_099 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=403.8, tags=retrieve_not_found, error=none
- qb_014 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=449.5, tags=retrieve_not_found,answer_out_of_domain, error=none
- qb_292 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=467.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_182 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=476.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_160 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=481.9, tags=retrieve_not_found, error=none
- qb_104 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=547.7, tags=retrieve_not_found, error=none
- qb_341 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=630.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_210 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=718.0, tags=retrieve_not_found, error=none
- qb_227 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=732.0, tags=retrieve_not_found,answer_out_of_domain, error=none
- qb_314 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=749.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_253 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=773.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_137 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=789.1, tags=retrieve_not_found, error=none
- qb_157 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=814.0, tags=retrieve_not_found, error=none
