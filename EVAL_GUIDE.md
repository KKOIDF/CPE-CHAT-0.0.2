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

### 4. Week 2 Hardening Workflow (recommended)
This workflow executes:
- double canary smoke runs,
- ranking robustness checks,
- baseline refresh from current commit,
- baseline alias update for canary guard.

```bash
bash scripts/run_week2_hardening.sh
```

Useful overrides:
```bash
BASE_URL=http://127.0.0.1:8001 LIMIT=40 BASELINE_COMMIT=$(git rev-parse --short HEAD) bash scripts/run_week2_hardening.sh
```

### 5. Ranking Robustness Check (standalone)
Run this on any eval JSON output to ensure retrieval ranking stays healthy by domain:
```bash
python3 scripts/check_ranking_robustness.py --report-json qball_canary_guard.json
```

## Per-Question Schema (eval_cases.json)
`eval_runner.py` now supports richer metadata per question for thesis-style evaluation.

Required core fields (existing):
- `id`
- `category`
- `question`
- `expected_domain`
- `expected_answer_keywords`
- `expected_source_contains`

Optional fields (new):
- `reference_answer`: canonical/ground-truth answer text
- `domain`: explicit question domain override (for domain-level breakdown)
- `expected_answerable`: `true/false`
- `difficulty`: `easy|medium|hard`
- `question_type` (or `reasoning_type`): e.g. `factual|procedural|multi-hop`
- `human_correctness_score`: 1-5
- `human_completeness_score`: 1-5
- `human_clarity_score`: 1-5
- `human_hallucination`: `true/false`

Example:
```json
{
	"id": "curriculum_001",
	"category": "curriculum_fact_lookup",
	"question": "CPE 342 คือวิชาอะไร",
	"expected_domain": "curriculum",
	"domain": "curriculum",
	"expected_answer_keywords": ["CPE 342", "Machine Learning"],
	"expected_source_contains": ["foe10", "curriculum"],
	"reference_answer": "CPE 342 คือวิชา Machine Learning ...",
	"expected_answerable": true,
	"difficulty": "medium",
	"question_type": "factual",
	"human_correctness_score": 5,
	"human_completeness_score": 4,
	"human_clarity_score": 4,
	"human_hallucination": false
}
```

## Output Coverage
`reports/eval_runner_*.json` now includes per-case fields for:
- retrieval top-1/top-3/top-5 pass
- best rank + MRR
- top retrieved contexts with similarity scores (`retrieval_top_contexts`)
- generation latency (derived from total - retrieval)
- answer quality labels/scores and computed quality average
- auto error tags for analysis (`retrieve_not_found`, `context_conflict`, etc.)

Summary metrics now include:
- Retrieval: Top-1/Top-3/Top-5 hit rate, MRR, by-domain breakdown
- Answer quality: average quality score, `% correct`, `% hallucination`, `% answerable handled correctly`
- Latency: average/median/p95 for retrieval, generation, total
- Coverage: counts by domain, difficulty, question type
- Error analysis: tag counts + failed case examples (up to 20)

## Reproducible Ingestion
The ingestion pipeline strictly enforces a separation between source facts and database clusters. To re-index the RAG system from data files gracefully:
```bash
make ingest
```
This will:
1. Scan `data/raw/<domain>` for updated sources.
2. Convert and embed files into `data/db/<domain>`.
3. Output a checksum manifest into `indexes/<domain>_manifest.txt` guaranteeing the exact state of processed documents that form the index.
