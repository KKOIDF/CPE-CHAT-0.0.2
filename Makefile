.PHONY: eval-regression ingest run-server

eval-regression:
	@echo "Running regression evaluation against eval_cases.json..."
	@python3 eval_runner.py --input eval_cases.json

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
