# Regression Eval Summary

Generated: 2026-04-01T22:29:26.554248
Input: data/eval_new_not_found_subset.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 26
- overall pass rate: 0.0385

### Retrieval Metrics
- top-1 hit rate: 0.0385
- top-3 hit rate: 0.0385
- top-5 hit rate: 0.1154
- top-K hit rate: 0.1154
- mean reciprocal rank (mrr): 0.0577

### Answer Quality Metrics
- answer keyword hit rate: 0.4231
- average quality score (1-5): 0.0000
- % correct answers: 0.4231
- % hallucination: 0.0000
- % answerable handled correctly: 0.4231
- citation validity (groundedness): 1.0000
- must-not contain pass rate: 1.0000

### Latency Metrics
- avg total latency ms: 1226.90
- median total latency ms: 475.32
- p95 total latency ms: 4307.34
- avg retrieval latency ms: 568.41
- median retrieval latency ms: 421.02
- p95 retrieval latency ms: 2066.86
- avg generation latency ms: 1326.26
- median generation latency ms: 128.07
- p95 generation latency ms: 3939.52

## Coverage

- total questions: 26
- questions by domain: announcements=20, curriculum=1, regulations=5
- questions by difficulty: easy=4, hard=5, medium=17
- questions by question type: ambiguous=2, factual=3, multi-hop=3, noisy=1, policy_conflict=1, procedural=10, verification=6

## Retrieval By Domain

- announcements: total=20, top1=0.0000, top3=0.0000, top5=0.1000, mrr=0.0250
- curriculum: total=1, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- regulations: total=5, top1=0.0000, top3=0.0000, top5=0.0000, mrr=0.0000

## By Category

- uncategorized: total=26, overall=0.0385, answer=0.4231, retrieval=0.1154, top1=0.0385, top3=0.0385, top5=0.1154, citation=1.0000

## Error Tag Counts

- retrieve_not_found: 23
- retrieve_found_but_answer_incomplete: 2
- pass_or_unclassified: 1

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.0000
- retrieval_adaptive_retry_succeeded: 0.0000
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.0000
- structured_rescue_succeeded: 0.0000
- curriculum_bypass_vector_triggered: 0.0000
- low_confidence_detected: 0.0769
- initial_retrieval_doc_count: 0.5769
- retry_retrieval_doc_count: 0.0000
- initial_top_score: 0.0056
- retry_top_score: 0.0000

## Answer Schema Metrics By Task

- none: cases=26, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000

## Failed Cases Top 20

- qb_256 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=391.5, tags=retrieve_not_found, error=none
- qb_257 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=405.6, tags=retrieve_not_found, error=none
- qb_054 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=419.9, tags=retrieve_not_found, error=none
- qb_070 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=462.4, tags=retrieve_not_found, error=none
- qb_080 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=466.2, tags=retrieve_not_found, error=none
- qb_265 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=479.5, tags=retrieve_not_found, error=none
- qb_032 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=486.8, tags=retrieve_not_found, error=none
- qb_154 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=494.8, tags=retrieve_not_found, error=none
- qb_170 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=501.5, tags=retrieve_not_found, error=none
- qb_137 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=545.3, tags=retrieve_not_found, error=none
- qb_334 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=4307.3, tags=retrieve_not_found, error=none
- qb_004 (uncategorized): coverage=0.25, retrieval=True, citation=True, must_not=True, latency_ms=528.3, tags=retrieve_found_but_answer_incomplete, error=none
- qb_116 (uncategorized): coverage=0.33, retrieval=False, citation=True, must_not=True, latency_ms=537.8, tags=retrieve_not_found, error=none
- qb_009 (uncategorized): coverage=0.50, retrieval=False, citation=True, must_not=True, latency_ms=471.2, tags=retrieve_not_found, error=none
- qb_255 (uncategorized): coverage=0.50, retrieval=True, citation=True, must_not=True, latency_ms=7275.1, tags=retrieve_found_but_answer_incomplete, error=none
- qb_122 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=226.7, tags=retrieve_not_found, error=none
- qb_176 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=306.0, tags=retrieve_not_found, error=none
- qb_033 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=335.3, tags=retrieve_not_found, error=none
- qb_100 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=413.4, tags=retrieve_not_found, error=none
- qb_121 (uncategorized): coverage=1.00, retrieval=False, citation=True, must_not=True, latency_ms=449.8, tags=retrieve_not_found, error=none
