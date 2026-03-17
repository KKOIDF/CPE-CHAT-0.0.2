# MLflow Native LLM Judge

This is the MLflow-native version of an LLM judge.

It uses these APIs directly:

- `mlflow.genai.evaluate()`
- `mlflow.genai.make_judge()`
- built-in MLflow scorers such as `ExpectationsGuidelines` and `Safety`

Script:

```bash
python scripts/mlflow_genai_judge_eval.py
```

## What It Evaluates

The script loads an existing eval report such as [reports/testqa_v2_live_eval_20260310_210644.json](../reports/testqa_v2_live_eval_20260310_210644.json) and converts it into an MLflow GenAI dataset with:

- `inputs`: question, domain, predicted behavior, sources
- `outputs`: model answer
- `expectations`: expected behavior, answerability, reference hint, per-row guidelines, and expected answer when available

It then runs four MLflow-native judges/scorers:

1. `mlflow_behavior_match`: custom MLflow judge created by `make_judge()`
2. `mlflow_overall_quality`: custom MLflow judge created by `make_judge()`
3. `ExpectationsGuidelines`: built-in MLflow scorer
4. `Safety`: built-in MLflow scorer

## Required Configuration

Set MLflow tracking:

```bash
export MLFLOW_TRACKING_URI=http://127.0.0.1:5000
export MLFLOW_JUDGE_EXPERIMENT=cpe-chat-llm-judge
```

Set an OpenAI-compatible judge backend.

For OpenAI:

```bash
export OPENAI_API_KEY=your_openai_key
export OPENAI_BASE_URL=https://api.openai.com/v1
```

For Typhoon via OpenAI-compatible API:

```bash
export OPENAI_API_KEY=your_typhoon_key
export OPENAI_BASE_URL=https://api.opentyphoon.ai/v1
```

Set the MLflow judge model URI:

```bash
export MLFLOW_JUDGE_MODEL_URI=openai:/typhoon-v2.5-30b-a3b-instruct
```

## Example

```bash
source venv/bin/activate
export MLFLOW_TRACKING_URI=http://127.0.0.1:5000
export MLFLOW_JUDGE_EXPERIMENT=cpe-chat-llm-judge
export OPENAI_API_KEY=your_typhoon_key
export OPENAI_BASE_URL=https://api.opentyphoon.ai/v1
export MLFLOW_JUDGE_MODEL_URI=openai:/typhoon-v2.5-30b-a3b-instruct

python scripts/mlflow_genai_judge_eval.py \
  --eval-report reports/testqa_v2_live_eval_20260310_210644.json
```

## Outputs

- `reports/mlflow_genai_judge_<timestamp>.json`
- `reports/mlflow_genai_judge_<timestamp>.md`

The MLflow run stores:

- aggregate judge metrics from `mlflow.genai.evaluate()`
- row-level judge results in the evaluation result table
- artifacts with exported JSON and Markdown summaries

## Current Limitation

This script requires a configured model backend for MLflow GenAI judges. In the current shell snapshot, no backend credentials are set, so it cannot be executed successfully until the environment variables above are provided.
