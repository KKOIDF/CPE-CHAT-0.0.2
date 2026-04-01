.PHONY: eval-regression eval-qball eval-qball-gate eval-qball-compare ingest run-server

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
