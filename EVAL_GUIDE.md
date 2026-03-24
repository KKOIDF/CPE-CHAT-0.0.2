# CPE-CHAT Evaluation & Regression Guide

## Systematic Evaluation
To ensure RAG pipeline modifications (retrieval indexing, vector similarity limits, LLM prompting) do not degrade the chatbot's performance, we have introduced a **3-Layer Metric System**:
1. **Retrieval Metrics**: Top-K hit rate, Mean Reciprocal Rank (MRR), and Top-1 hit rate.
2. **Answer Quality Metrics**: Keyword hit rate, citation groundedness, and "must-not-contain" strict filters.
3. **Latency Metrics**: P95 and Average latency tracking.

## Workflows

### 1. Running an Evaluation
To evaluate your current branch against `eval_cases.json`, run:
```bash
make eval-regression
```
This generates a comprehensive markdown report in the `reports/` directory titled `eval_runner_YYYYMMDD_HHMMSS.md`.

### 2. Setting a Baseline
When you have a stable model, you can snapshot its metrics to serve as a baseline:
```bash
python3 eval_runner.py --input eval_cases.json --baseline-commit "$(git rev-parse --short HEAD)"
```
This produces `reports/baseline_<commit>.md` and a JSON file.

### 3. Running automated gating (CI Context)
To block regressions on PRs or major changes, run the evaluator against a saved baseline:
```bash
python3 eval_runner.py --input eval_cases.json --compare-baseline reports/baseline_<commit>.json
```
If your new code falls behind the baseline MRR or hit rates, the script returns a non-zero exit code.

## Reproducible Ingestion
The ingestion pipeline strictly enforces a separation between source facts and database clusters. To re-index the RAG system from data files gracefully:
```bash
make ingest
```
This will:
1. Scan `data/raw/<domain>` for updated sources.
2. Convert and embed files into `data/db/<domain>`.
3. Output a checksum manifest into `indexes/<domain>_manifest.txt` guaranteeing the exact state of processed documents that form the index.
