.PHONY: eval-regression eval-qball eval-qball-gate eval-qball-compare eval-domain-monitor eval-canary-guard ingest run-server

eval-regression:
	@echo "Running regression evaluation against eval_cases.json..."
	@python3 eval_runner.py --input eval_cases.json

eval-qball:
	@echo "Running qball evaluation against data/question_bank_250_general_th.json..."
	@python3 eval_runner.py --input data/question_bank_250_general_th.json --base-url $${BASE_URL:-http://127.0.0.1:8011} --timeout $${TIMEOUT:-120} --output-prefix qball_ci

eval-qball-gate:
	@echo "Running qball evaluation with baseline gate..."
	@python3 eval_runner.py --input data/question_bank_250_general_th.json --base-url $${BASE_URL:-http://127.0.0.1:8011} --timeout $${TIMEOUT:-120} --output-prefix qball_ci_gate --compare-baseline reports/eval_runner_qball_20260331_155326.json --gate-overall-drop-pct $${GATE_OVERALL_DROP_PCT:-3} --gate-citation-drop-pct $${GATE_CITATION_DROP_PCT:-0} --gate-p95-increase-pct $${GATE_P95_INCREASE_PCT:-25} --gate-protected-categories $${GATE_PROTECTED_CATEGORIES:-curriculum_fact_lookup,regulations}

eval-qball-compare:
	@echo "Comparing candidate report against baseline..."
	@python3 scripts/eval_compare.py --baseline reports/eval_runner_qball_20260331_155326.json --candidate $${CANDIDATE:-qball_phase3_schema_enforced.json} --top-n $${TOPN:-20} --out reports/qball_compare_latest.json

eval-domain-monitor:
	@echo "Running domain monitor with global p95 guard..."
	@python3 eval_runner.py --input $${INPUT:-eval_cases.json} --base-url $${BASE_URL:-http://127.0.0.1:8001} --timeout $${TIMEOUT:-120} --preflight-health --output-prefix $${OUTPUT_PREFIX:-qball_domain_monitor} --production-gate --prod-min-overall-pass-rate $${PROD_MIN_OVERALL_PASS_RATE:-0} --prod-min-answer-hit-rate $${PROD_MIN_ANSWER_HIT_RATE:-0} --prod-min-retrieval-hit-rate $${PROD_MIN_RETRIEVAL_HIT_RATE:-0} --prod-min-citation-validity-rate $${PROD_MIN_CITATION_VALIDITY_RATE:-0} --prod-min-citation-precision $${PROD_MIN_CITATION_PRECISION:-0} --prod-min-citation-recall $${PROD_MIN_CITATION_RECALL:-0} --prod-max-hallucination-rate $${PROD_MAX_HALLUCINATION_RATE:-1} --prod-min-must-not-contain-pass-rate $${PROD_MIN_MUST_NOT_CONTAIN_PASS_RATE:-0} --prod-max-p95-latency-ms $${PROD_MAX_P95_LATENCY_MS:-1400} --prod-max-p95-retrieval-latency-ms $${PROD_MAX_P95_RETRIEVAL_LATENCY_MS:-5000} --prod-category-min-overall-pass-rate "$${PROD_CATEGORY_MIN_OVERALL_PASS_RATE:-}" --prod-domain-min-overall-pass-rate "$${PROD_DOMAIN_MIN_OVERALL_PASS_RATE:-}" --prod-domain-max-p95-latency-ms "$${PROD_DOMAIN_MAX_P95_LATENCY_MS:-announcements=1400,regulations=2500,curriculum=2000,multi=2200}"

eval-canary-guard:
	@echo "Running canary 10% baseline guard (hold/continue)..."
	@bash scripts/run_canary_guard.sh

ingest:
	@echo "Running reproducible ingestion pipeline for all domains locally..."
	@./scripts/ingest_all_domains.sh

ingest-gpu:
	@if [ -z "$(GPU_HOST)" ]; then \
		echo "Usage: make ingest-gpu GPU_HOST=user@remote-host"; \
		exit 1; \
	fi
	@bash ./scripts/sync_and_ingest_gpu.sh $(GPU_HOST)

run-server:
	@echo "Starting RAG backend server..."
	@./start_rag_service.sh
