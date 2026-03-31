# Regression Eval Summary

Generated: 2026-03-30T23:48:38.915917
Input: data/question_bank_250_general_th.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 342
- overall pass rate: 0.1579

### Retrieval Metrics
- top-1 hit rate: 0.5614
- top-3 hit rate: 0.7456
- top-5 hit rate: 0.7602
- top-K hit rate: 0.7602
- mean reciprocal rank (mrr): 0.6481

### Answer Quality Metrics
- answer keyword hit rate: 0.2193
- average quality score (1-5): 0.0000
- % correct answers: 0.2193
- % hallucination: 0.0000
- % answerable handled correctly: 0.2368
- citation validity (groundedness): 0.9854
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 2903.82
- median total latency ms: 971.16
- p95 total latency ms: 10785.40
- avg retrieval latency ms: 2149.30
- median retrieval latency ms: 1181.49
- p95 retrieval latency ms: 5430.95
- avg generation latency ms: 3459.71
- median generation latency ms: 3060.80
- p95 generation latency ms: 9420.48

## Coverage

- total questions: 342
- questions by domain: announcements=135, curriculum=99, general=29, regulations=79
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=135, top1=0.4148, top3=0.6074, top5=0.6296, mrr=0.5077
- curriculum: total=99, top1=0.6667, top3=0.9596, top5=0.9596, mrr=0.7997
- general: total=29, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- regulations: total=79, top1=0.5190, top3=0.6203, top5=0.6456, mrr=0.5690

## By Category

- uncategorized: total=342, overall=0.1579, answer=0.2193, retrieval=0.7602, top1=0.5614, top3=0.7456, top5=0.7602, citation=0.9854

## Error Tag Counts

- retrieve_found_but_answer_incomplete: 206
- retrieve_not_found: 82
- pass_or_unclassified: 54
- answer_out_of_domain: 7
- context_conflict: 5

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

- qb_034 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=237.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_118 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=276.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_177 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=287.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_179 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=301.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_236 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=327.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_167 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=334.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_132 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=337.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_301 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=339.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_184 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=346.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_342 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=361.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_099 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=379.3, tags=retrieve_not_found, error=none
- qb_292 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=425.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_014 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=436.8, tags=retrieve_not_found,answer_out_of_domain, error=none
- qb_160 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=470.3, tags=retrieve_not_found, error=none
- qb_104 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=484.3, tags=retrieve_not_found, error=none
- qb_079 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=515.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_247 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=543.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_006 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=627.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_182 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=656.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_341 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=699.4, tags=retrieve_found_but_answer_incomplete, error=none
