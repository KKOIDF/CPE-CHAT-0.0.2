# Regression Eval Summary

Generated: 2026-03-30T00:31:28.369429
Input: data/question_bank_250_general_th.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 342
- overall pass rate: 0.1608

### Retrieval Metrics
- top-1 hit rate: 0.4912
- top-3 hit rate: 0.6491
- top-5 hit rate: 0.6608
- top-K hit rate: 0.6608
- mean reciprocal rank (mrr): 0.5647

### Answer Quality Metrics
- answer keyword hit rate: 0.2719
- average quality score (1-5): 0.0000
- % correct answers: 0.2719
- % hallucination: 0.0000
- % answerable handled correctly: 0.2982
- citation validity (groundedness): 0.9883
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 2956.06
- median total latency ms: 1022.22
- p95 total latency ms: 9250.40
- avg retrieval latency ms: 2019.83
- median retrieval latency ms: 1196.68
- p95 retrieval latency ms: 4838.13
- avg generation latency ms: 3257.21
- median generation latency ms: 3101.27
- p95 generation latency ms: 8670.27

## Coverage

- total questions: 342
- questions by domain: announcements=85, curriculum=99, general=29, internship=50, regulations=79
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=85, top1=0.4235, top3=0.5765, top5=0.6000, mrr=0.5000
- curriculum: total=99, top1=0.6263, top3=0.9596, top5=0.9596, mrr=0.7744
- general: total=29, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- internship: total=50, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000
- regulations: total=79, top1=0.5190, top3=0.6203, top5=0.6456, mrr=0.5690

## By Category

- uncategorized: total=342, overall=0.1608, answer=0.2719, retrieval=0.6608, top1=0.4912, top3=0.6491, top5=0.6608, citation=0.9883

## Error Tag Counts

- retrieve_found_but_answer_incomplete: 171
- retrieve_not_found: 116
- pass_or_unclassified: 55
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

- qb_034 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=245.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_132 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=307.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_177 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=309.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_184 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=326.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_179 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=326.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_342 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=327.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_118 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=331.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_167 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=340.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_301 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=408.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_236 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=450.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_014 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=460.0, tags=retrieve_not_found,answer_out_of_domain, error=none
- qb_099 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=481.5, tags=retrieve_not_found, error=none
- qb_292 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=483.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_182 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=515.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_049 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=519.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_079 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=521.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_247 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=542.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_104 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=556.7, tags=retrieve_not_found, error=none
- qb_160 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=586.2, tags=retrieve_not_found, error=none
- qb_006 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=635.2, tags=retrieve_found_but_answer_incomplete, error=none
