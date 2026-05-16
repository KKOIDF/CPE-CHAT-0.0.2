# RAG Open Notebook Style

`CPE-CHAT-0.0.2` now has an incremental RAG path inspired by Open Notebook and NotebookLM for document QA.

## Architecture

- Global Chroma collection: `cpe_chat_sources`
- Domain is metadata, not the default search boundary
- Retrieval defaults to cross-domain hybrid search
- Legacy per-domain indexes remain in place for compatibility

Flow:

`file -> existing extractor -> normalize text -> content-aware chunking -> metadata enrichment -> embed -> domain Chroma + global Chroma -> domain SQLite + global SQLite -> hybrid retrieval -> source diversity -> source-labeled context -> existing LLM`

## Why Global Chroma

- Multi-file and multi-domain questions should not fail because the router picked one domain too early
- A single collection lets us retrieve curriculum, regulations, and announcements together
- Domain metadata is still used for boost, filtering, and debugging

## Ingestion

- Entry points are unchanged: `make ingest` and `scripts/ingest_all_domains.sh`
- Existing loaders/extractors are preserved
- The new chunker keeps section headings when possible and adds deterministic `stable_chunk_id`
- Global SQLite FTS is updated alongside domain SQLite

## Retrieval

- Query normalization + query variants
- Soft candidate-domain scoring
- Global vector search in Chroma
- Global chunk-level keyword search in SQLite FTS
- RRF-style merge + heuristic rerank
- Source diversity before context packing

## Context Builder

Context is emitted in source-labeled blocks:

```text
[Source 1]
source_name: curriculum_2024.pdf
domain: curriculum
page: 12
section: เงื่อนไขการสำเร็จการศึกษา
chunk_id: ...
content:
...
```

## Debug

```bash
python scripts/check_chroma_index.py
python scripts/check_rag_pipeline.py
python scripts/debug_question.py --question "จบหลักสูตรต้องผ่านอะไรบ้าง มีประกาศอะไรเกี่ยวไหม" --show-candidates --show-context
```

## Commands

```bash
docker-compose up -d
make ingest
curl http://localhost:8001/health
curl -X POST http://localhost:8001/rag/query -H "Content-Type: application/json" -d '{"question":"จบหลักสูตรต้องผ่านอะไรบ้าง มีประกาศอะไรเกี่ยวไหม"}'
curl -X POST http://localhost:8001/rag/answer -H "Content-Type: application/json" -d '{"question":"ถ้าจะจบปีนี้ต้องดูหลักสูตร ข้อบังคับ และประกาศอะไรบ้าง"}'
curl -X POST http://localhost:8001/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"gemma4:26b","messages":[{"role":"user","content":"ถ้าจะจบหลักสูตรต้องผ่านเงื่อนไขอะไรบ้าง"}]}'
```

