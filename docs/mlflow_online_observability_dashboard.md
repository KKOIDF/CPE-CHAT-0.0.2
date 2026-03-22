# MLflow Online Observability Dashboard

This repo now emits always-on runtime observability into the MLflow experiment `cpe-chat-online-observability`.

Use the latest active run in that experiment as the live dashboard source for runtime traffic.

## Core Queries

Use this MLflow run filter in the UI:

```text
tags.service = 'rag-service' AND tags.kind = 'observability'
```

Use these metric groups for the main dashboard:

- Latency: `latency_ms_p50__rag_answer`, `latency_ms_p90__rag_answer`, `latency_ms_p99__rag_answer`, `latency_ms_avg__rag_answer`
- Retrieval stage latency (examples): `latency_ms_stage_p90__rag_query__rag_answer`, `latency_ms_stage_p90__llm_generate__rag_answer`, `latency_ms_stage_p90__repair_citations_llm__rag_answer`
- Guardrail volume: `sum__guardrail_triggered__rag_answer`, `sum__guardrail_missing_exact_date_evidence__rag_answer`
- Guardrail rate denominator: `requests_total__rag_answer`
- Domain fallback volume: `sum__retrieval_domain_fallback_used__rag_answer`
- Retrieval final context count: `avg__retrieval_final_n__rag_answer`
- Retrieval context size cross-check: `avg__ctx_n__rag_answer`
- Token estimate per question: `avg__token_est_per_question__rag_answer`
- Structured path metrics: `rate__structured_path_hit__rag_answer`, `rate__structured_path_fallback_nonstructured__rag_answer`
- Citation repair metrics: `rate__citation_repair_success__rag_answer`, `sum__citation_repair_attempt__rag_answer`
- Path fallback rates: `rate__path_langchain_used__rag_answer`, `rate__path_nonstructured_used__rag_answer`
- Top failure intents (examples): `count__failure_intent__exam_policy__rag_answer`, `count__failure_intent__calendar_deadline__rag_answer`

## Dashboard Formulas

Use these derived formulas when reading the latest points from the active run:

- Guardrail hit rate = `sum__guardrail_triggered__rag_answer / requests_total__rag_answer`
- Domain fallback rate = `sum__retrieval_domain_fallback_used__rag_answer / requests_total__rag_answer`
- Avg retrieval final context count = `avg__retrieval_final_n__rag_answer`
- Structured path hit rate = `rate__structured_path_hit__rag_answer`
- Structured fallback to non-structured rate = `rate__structured_path_fallback_nonstructured__rag_answer`
- Citation repair success rate = `rate__citation_repair_success__rag_answer`
- LangChain usage rate = `rate__path_langchain_used__rag_answer`
- Non-structured path rate = `rate__path_nonstructured_used__rag_answer`

These are cumulative counters and rolling averages emitted by the service every flush interval.

## CLI Dashboard

Run this script to generate a one-file dashboard from the latest online observability run:

```bash
source venv/bin/activate
python scripts/mlflow_online_dashboard.py \
  --tracking-uri http://127.0.0.1:5000 \
  --experiment cpe-chat-online-observability \
  --output reports/mlflow_online_dashboard_latest.md \
  --json-output reports/mlflow_online_dashboard_latest.json
```

The output contains:

- Latest KPI summary for latency, guardrail hits, fallback hits, and final context count
- Stage-level latency and path-routing rates
- Token-est-per-question and citation-repair success rate
- Recent metric history tail for the main dashboard metrics
- Ready-to-copy query names for the MLflow UI

## REST Queries

Get the experiment:

```bash
curl -s 'http://127.0.0.1:5000/api/2.0/mlflow/experiments/get-by-name?experiment_name=cpe-chat-online-observability'
```

Get the latest active run:

```bash
curl -s http://127.0.0.1:5000/api/2.0/mlflow/runs/search \
  -H 'Content-Type: application/json' \
  -d '{
    "experiment_ids": ["7"],
    "run_view_type": "ACTIVE_ONLY",
    "max_results": 1,
    "order_by": ["attribute.start_time DESC"]
  }'
```

Get metric history for one dashboard series with the Python client:

```bash
source venv/bin/activate
python - <<'PY'
from mlflow.tracking import MlflowClient

client = MlflowClient(tracking_uri='http://127.0.0.1:5000')
history = client.get_metric_history('<RUN_ID>', 'latency_ms_p90__rag_answer')
for item in history[-10:]:
  print(item.step, item.timestamp, item.value)
PY
```

## Suggested Panels

Create these panels in your dashboard notebook, wiki, or operational runbook:

1. Latency panel with `latency_ms_p50__rag_answer`, `latency_ms_p90__rag_answer`, and `latency_ms_p99__rag_answer`
2. Retrieval-stage latency panel with `latency_ms_stage_p90__rag_query__rag_answer`, `latency_ms_stage_p90__llm_generate__rag_answer`, and `latency_ms_stage_p90__repair_citations_llm__rag_answer`
3. Guardrail panel with `sum__guardrail_triggered__rag_answer` and derived guardrail hit rate
4. Retrieval robustness panel with `sum__retrieval_domain_fallback_used__rag_answer` and derived domain fallback rate
5. Path decision panel with `rate__structured_path_hit__rag_answer`, `rate__path_langchain_used__rag_answer`, and `rate__path_nonstructured_used__rag_answer`
6. Citation quality panel with `rate__citation_repair_success__rag_answer` and `sum__citation_repair_attempt__rag_answer`
7. Failure-intent panel using top `count__failure_intent__*__rag_answer` series

## Notes

- The online observability run is long-lived and stays in `RUNNING` while the service is up.
- Metric history should be read from the active run rather than assuming one run per request.
- Sampled traces are stored separately in MLflow tracing APIs and are useful for request-level drill-down after a dashboard spike.

## Request Logs (Questions/Answers)

If you want to see the *raw question/answer per request* ("what users asked"), it is stored as MLflow artifacts:

- Experiment: `cpe-chat-online-observability`
- Run: the latest active run (tags `service=rag-service`, `kind=observability`)
- Artifacts: `requests/requests_*.jsonl`

Each JSONL file contains one or more events (one JSON object per line). By default:

- `question` is always stored (truncated to `MLFLOW_OBS_REQUEST_LOG_MAX_CHARS`)
- `answer` and `ctx_sources` are stored when `MLFLOW_OBS_REQUEST_LOG_CONTENT=1`

Visibility gotchas:

- Artifacts are flushed periodically (default `MLFLOW_OBS_FLUSH_S=10`), so a new question may take ~10s to appear.
- Traces are sampled by `MLFLOW_TRACE_SAMPLE_RATE`; if you expect a trace for every request, set it to `1`.
