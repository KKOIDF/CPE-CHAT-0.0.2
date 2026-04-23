# Repository Tree Map

Generated: 2026-04-18
Scope: top-level + key subdirectories for agent navigation

## Top Level
- README.md
- README_DOMAINS.md
- Makefile
- docker-compose.yml
- services/
- scripts/
- tests/
- docs/
- data/
- reports/
- client/
- config/

## Key Backend Paths
- services/rag-service/
- services/ingestion-service/
- services/mlflow/

## Key Script Paths
- scripts/ingest_all_domains.sh
- scripts/ingest_domain.sh
- scripts/run_regression_gate.sh
- scripts/run_canary_guard.sh
- scripts/eval_targeted_mlflow.py

## Key Data/Artifacts Paths
- data/announcements/
- data/regulations/
- data/curriculum/
- data/db/
- indexes/ (generated index files)
- reports/ (evaluation outputs)

## Key Docs
- EVAL_GUIDE.md
- DEPLOYMENT_GUIDE.md
- GPU_INGEST_GUIDE.md
- docs/system_reference.md

## Update Policy
- Regenerate this file when top-level structure changes
- Keep it concise, oriented for fast agent onboarding
