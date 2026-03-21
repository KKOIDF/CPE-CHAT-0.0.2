# LLM Judge Eval

This repo now includes an LLM judge script for scoring existing eval reports with a second-pass model.

Script:

```bash
python scripts/llm_judge_eval_report.py
```

## What It Does

- Loads the latest [reports/testqa_v2_live_eval_*.json](../reports) report by default
- Optionally fetches fresh `/rag/query` contexts from the running rag-service to ground the judgment
- Calls an OpenAI-compatible judge model
- Produces per-case judge scores and explanations
- Logs summary metrics, artifacts, and per-case judge traces to MLflow

## Required Judge Backend Settings

Set these environment variables before running:

```bash
export JUDGE_BASE_URL=https://api.opentyphoon.ai/v1
export JUDGE_MODEL=typhoon-v2.5-30b-a3b-instruct
export JUDGE_API_KEY=your_api_key
```

If you want MLflow logging:

```bash
export MLFLOW_ENABLE=1
export MLFLOW_TRACKING_URI=http://127.0.0.1:5000
export MLFLOW_JUDGE_EXPERIMENT=cpe-chat-llm-judge
```

## Example

```bash
source venv/bin/activate
export JUDGE_BASE_URL=https://api.opentyphoon.ai/v1
export JUDGE_MODEL=typhoon-v2.5-30b-a3b-instruct
export JUDGE_API_KEY=your_api_key
export MLFLOW_ENABLE=1
export MLFLOW_TRACKING_URI=http://127.0.0.1:5000

python scripts/llm_judge_eval_report.py \
  --eval-report reports/testqa_v2_live_eval_20260310_210644.json \
  --rag-base-url http://127.0.0.1:8001 \
  --limit 20
```

## Outputs

- `reports/llm_judge_eval_<timestamp>.json`
- `reports/llm_judge_eval_<timestamp>.md`
- `reports/llm_judge_eval_<timestamp>.csv`

MLflow summary metrics include:

- `judge_pass_rate`
- `behavior_match_rate`
- `overall_score_avg`
- `factuality_score_avg`
- `groundedness_score_avg`
- `judge_latency_ms_avg`
- `trace_count`

## Notes

- The judge is separate from the RAG answer model; it should use a dedicated backend where possible.
- The script logs one MLflow trace per judged case when MLflow tracing is available.
- The script expects an OpenAI-compatible `/chat/completions` endpoint.
