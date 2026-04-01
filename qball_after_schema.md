# Regression Eval Summary

Generated: 2026-03-31T17:35:03.918109
Input: /tmp/eval_cases_qball_342.json
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
- citation validity (groundedness): 0.9737
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 2785.68
- median total latency ms: 924.68
- p95 total latency ms: 11052.91
- avg retrieval latency ms: 2214.54
- median retrieval latency ms: 1106.87
- p95 retrieval latency ms: 6040.79
- avg generation latency ms: 3059.08
- median generation latency ms: 2644.88
- p95 generation latency ms: 9175.73

## Coverage

- total questions: 342
- questions by domain: announcements=155, curriculum=102, regulations=82, unknown=3
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=155, top1=0.4903, top3=0.6581, top5=0.6774, mrr=0.5712
- curriculum: total=102, top1=0.6569, top3=0.9608, top5=0.9608, mrr=0.7908
- regulations: total=82, top1=0.5244, top3=0.6220, top5=0.6463, mrr=0.5726
- unknown: total=3, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000

## By Category

- uncategorized: total=342, overall=0.2105, answer=0.2895, retrieval=0.7573, top1=0.5526, top3=0.7427, top5=0.7573, citation=0.9737

## Error Tag Counts

- retrieve_found_but_answer_incomplete: 187
- retrieve_not_found: 83
- pass_or_unclassified: 72
- answer_out_of_domain: 10
- context_conflict: 9

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

- qb_179 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=294.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_177 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=296.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_167 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=328.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_184 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=346.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_342 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=370.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_301 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=380.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_099 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=418.7, tags=retrieve_not_found, error=none
- qb_014 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=438.9, tags=retrieve_not_found,answer_out_of_domain, error=none
- qb_236 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=439.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_292 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=454.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_104 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=474.3, tags=retrieve_not_found, error=none
- qb_182 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=492.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_160 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=538.3, tags=retrieve_not_found, error=none
- qb_321 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=747.6, tags=retrieve_not_found, error=none
- qb_320 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=750.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_314 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=754.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_274 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=776.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_210 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=799.1, tags=retrieve_not_found, error=none
- qb_223 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=814.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_065 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=815.3, tags=retrieve_found_but_answer_incomplete, error=none
