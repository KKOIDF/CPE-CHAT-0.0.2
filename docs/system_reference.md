# CPE-CHAT System Reference (End-to-End)

Last updated: 2026-04-12

This document is a technical reference for understanding and operating the full CPE-CHAT system, from document ingestion to online question answering and regression gating.

## 1) What This Project Is

CPE-CHAT is a domain-aware RAG system for Thai academic QA.

Core domains:
- announcements
- regulations
- curriculum

Core capabilities:
- Hybrid retrieval (vector + SQLite FTS keyword)
- Domain inference and adaptive orchestration
- Deterministic structured paths for high-precision intents
- OpenAI-compatible endpoint for OpenWeb-UI
- Evaluation runners and regression gates
- Optional observability via MLflow

## 2) High-Level Architecture

Main runtime services:
- rag-service (FastAPI): query/answer pipeline and OpenAI-compatible interface
- openweb-ui: chat frontend using `/v1/chat/completions`
- mlflow (optional): tracking and observability

Ingestion side:
- ingestion-service: PDF/TXT/XLSX/CSV ingestion, OCR, chunking, SQLite + Chroma indexing

Important storage paths:
- `indexes/<domain>/vector/chroma`
- `indexes/<domain>/vector/sqlite/ingestion.db`
- input raw data usually at `data/raw/<domain>`

Primary runtime wiring is in:
- `docker-compose.yml`

## 3) Repository Map (What To Read First)

Backend (RAG):
- `services/rag-service/app/main.py` (API, request handling, routing entry)
- `services/rag-service/app/orchestration.py` (adaptive orchestration, query path selection)
- `services/rag-service/app/retrieval.py` (hybrid retrieval and multi-doc retrieval)
- `services/rag-service/app/routing.py` (intent/domain heuristics and strategy)
- `services/rag-service/app/llm.py` (LLM provider abstraction: local HF / OpenAI / Typhoon)
- `services/rag-service/app/config.py` (runtime config and paths)
- `services/rag-service/app/langchain_rag.py` (optional LangChain orchestration path)

Ingestion:
- `services/ingestion-service/app/main.py` (CLI pipeline entry)
- `services/ingestion-service/app/config.py` (domain-aware indexing and chunk config)
- `services/ingestion-service/app/db.py` (SQLite + FTS sync logic)
- `services/ingestion-service/app/chroma_client.py` (embeddings + Chroma upsert)
- `scripts/ingest_domain.sh`
- `scripts/ingest_all_domains.sh`

Evaluation and gating:
- `eval_runner.py` (JSON-based eval harness)
- `scripts/eval_testqa_csv_live_v2.py` (live QA CSV evaluator)
- `scripts/run_regression_gate.sh` (gate thresholds and pass/fail)
- `Makefile` (common commands)

Client:
- `client/src/App.jsx` (simple React prototype client)
- `client/vite.config.js` (dev proxy to `http://127.0.0.1:8001`)

## 4) Data Lifecycle

### 4.1 Ingestion Input

Supported file types:
- `.pdf`
- `.txt`
- `.xlsx`, `.xls`, `.csv`, `.tsv`

Typical raw data layout:
- `data/raw/announcements`
- `data/raw/regulations`
- `data/raw/curriculum`

### 4.2 Ingestion Pipeline

`services/ingestion-service/app/main.py` performs:
1. File discovery
2. Extraction:
   - PDF: text extraction + OCR fallback (quality-driven)
   - TXT/Excel/CSV parsing
3. Paragraph build + chunking (domain-aware strategy)
4. Stable `doc_id` generation
5. Quality flagging (`ok` / `flagged`)
6. SQLite write (`documents`, `docs_fts`, `ocr_quality`)
7. Chroma embedding upsert (optionally skip flagged chunks)
8. Optional curriculum graph upsert to Neo4j

### 4.3 Index Outputs

Per domain outputs:
- SQLite: `indexes/<domain>/vector/sqlite/ingestion.db`
- Chroma: `indexes/<domain>/vector/chroma`

Legacy/non-domain fallback exists, but production flow should use explicit domain indexing.

## 5) Retrieval and Answering Flow

### 5.1 API Entry Points

Defined in `services/rag-service/app/main.py`:
- `POST /rag/query`
- `POST /rag/answer`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `GET /health`
- `GET /debug/config` (guarded by env flag)

### 5.2 Route Analysis

`analyze_route()` in `routing.py` computes:
- inferred domain
- primary intent
- structured eligibility
- multi-intent flags
- timeout/fallback policy hints

`select_resolution_strategy()` selects path such as:
- `structured_exact`
- `structured_fuzzy`
- `structured_regulation_form`
- `multi_intent_split`
- `multi_intent_structured_or_extract`
- `full_rag`

### 5.3 Retrieval Modes

In `orchestration.py` + `retrieval.py`:
- domain-constrained retrieval
- all-domain retrieval
- adaptive retry on low confidence
- all-domain fallback when in-domain recall is weak
- multi-document retrieval for multi-clause questions
- reranking/penalty/boost logic by domain and source

### 5.4 Structured Fast Paths

For selected intents, deterministic answerers can bypass generic generation:
- curriculum deterministic lookup/answer
- regulation form/policy structured path

This is used to reduce hallucination for factual, schema-like questions.

### 5.5 Prompt and Context Packing

Context packing modules:
- `context_packing.py`

Behavior:
- token budget-constrained context packing
- grouped packing for multi-document mode
- citation labels generated from source/page

### 5.6 Generation Layer

`llm.py` supports providers:
- local HuggingFace model
- OpenAI-compatible remote
- Typhoon API

Runtime defaults in docker-compose are Typhoon-based.

## 6) Domain and Retrieval Strategy

`KNOWN_DOMAINS`:
- announcements
- regulations
- curriculum

Design notes:
- curriculum often prefers deterministic/structured behavior for code-like queries
- regulations has clause-sensitive heuristics
- announcements has schedule/procedure oriented boosts/guards
- optional all-domain search can improve recall at latency cost

## 7) OpenAI-Compatible Integration

Endpoint:
- `POST /v1/chat/completions`

Used by OpenWeb-UI in `docker-compose.yml`:
- `OPENAI_API_BASE_URL=http://rag-service:8001/v1`
- `OPENAI_API_KEY=not-required`

The service extracts the effective user question from message history and applies follow-up handling before retrieval/generation.

## 8) Environment Configuration (Most Important)

### 8.1 Core Runtime

From `docker-compose.yml` and `config.py`:
- `CPE_INDEX_ROOT`
- `RAG_HOST`, `RAG_PORT`
- `TOKEN_BUDGET`, `MAX_CONTEXTS`
- `LLM_ENABLE`, `LLM_PROVIDER`, `LLM_MODEL`
- `TYPHOON_API_KEY`, `TYPHOON_BASE_URL`

### 8.2 Retrieval Tuning

Common knobs:
- `RAG_SEARCH_ALL_DOMAINS`
- `RAG_VECTOR_ONLY`
- `RAG_RETRIEVAL_PARALLEL`
- `RAG_HYBRID_SEMANTIC_WEIGHT`
- `RAG_HYBRID_KEYWORD_WEIGHT`
- `RAG_MULTI_DOC_MODE`

### 8.3 LangChain Optional Path

- `RAG_USE_LANGCHAIN`
- `RAG_LC_MULTIQUERY`
- `RAG_LC_RERANK`
- `RAG_LC_COMPRESS`

### 8.4 Observability

- `MLFLOW_TRACKING_URI`
- `MLFLOW_OBSERVABILITY_ENABLE`
- `MLFLOW_TRACING_ENABLE`

## 9) Local and Docker Runbooks

### 9.1 Docker Full Stack

Use:
- `docker-compose up -d`

Quick script:
- `start.sh`

Health check:
- `GET /health`

### 9.2 Local Backend Only

Use:
- `./start_rag_service.sh`

It sets key env vars and runs:
- `services/rag-service/run_server.py`

### 9.3 Ingest All Domains

Use:
- `./scripts/ingest_all_domains.sh`

Per-domain ingest:
- `./scripts/ingest_domain.sh --domain <domain> --input <path>`

## 10) Evaluation and Quality Gates

### 10.1 Eval Runner (JSON Cases)

Use:
- `python3 eval_runner.py --input eval_cases.json`

Also available via Makefile:
- `make eval-regression`
- `make eval-qball`
- `make eval-qball-gate`

### 10.2 CSV Live Evaluator

Use:
- `python3 scripts/eval_testqa_csv_live_v2.py --input <csv> --base-url http://127.0.0.1:8001`

### 10.3 Regression Gate

Use:
- `bash scripts/run_regression_gate.sh`

Gate script controls thresholds (exactness, citation validity, p95 latency, required groups).

## 11) API Contracts (Practical)

### 11.1 `POST /rag/query`

Request:
```json
{
  "question": "...",
  "domain": "curriculum",
  "session_id": "optional"
}
```

Response (shape):
- `prompt`
- `contexts[]`
- `token_est`
- `meta`

### 11.2 `POST /rag/answer`

Request:
```json
{
  "question": "...",
  "domain": "regulations",
  "eval_mode": false,
  "session_id": "optional"
}
```

Response (shape):
- `question`
- `prompt`
- `answer`
- `contexts[]`
- `token_est`
- `meta`

### 11.3 `POST /v1/chat/completions`

OpenAI-compatible message payload. The backend handles message extraction and returns `choices[0].message.content`.

## 12) Troubleshooting Playbook

1. No/poor answers for a domain:
- verify data exists in `data/raw/<domain>`
- re-run ingest for that domain
- inspect `indexes/<domain>/vector/sqlite/ingestion.db`

2. Good retrieval but bad final answer:
- check `LLM_PROVIDER`, model, timeout settings
- run with `RAG_TIMING=1`
- compare `/rag/query` vs `/rag/answer`

3. Slow responses:
- reduce all-domain search (`RAG_SEARCH_ALL_DOMAINS=0`)
- reduce multiquery/rerank/compress settings
- tune `MAX_CONTEXTS` and token budget

4. OpenWeb-UI cannot answer:
- verify `OPENAI_API_BASE_URL` points to rag-service `/v1`
- check `GET /v1/models` and `GET /health`

5. Citation regressions in eval:
- run gate scripts and inspect report artifacts in `reports/`
- compare candidate vs baseline via `scripts/eval_compare.py`

## 13) Operational Conventions

- Keep indexes domain-isolated.
- Re-ingest after chunking/embedding strategy changes.
- Treat old eval reports as historical artifacts, but keep a small baseline set for comparison.
- Prefer scripted run paths (`Makefile`, `scripts/*.sh`) over ad-hoc commands.

## 14) Suggested Onboarding Path (New Engineer)

1. Read this file once end-to-end.
2. Run local health path:
   - start backend
   - call `/health`
   - call `/rag/query`
3. Run one domain ingest on a small sample.
4. Run one eval set and inspect output report.
5. Tune one retrieval knob and re-run eval.

---

If you want this reference split into team-specific guides (Backend, Data/Ingest, Evaluation, Ops), use this file as the source-of-truth and generate role-focused docs from it.
