# Ingestion Service (OCR + Chunk + Store)

docker build -t ingestion-service .
docker run --rm -v /absolute/path/input:/input ingestion-service --input /input

## Overview

Python service for batch ingestion of PDF and Excel/CSV documents:

* Extract text (PyMuPDF) with OCR fallback (pdf2image + Tesseract)
* Thai/English mixed handling + normalization
* Sheet ingestion for tabular files
* Quality-based OCR decisions (length + signal score)
* Paragraph + sentence aware chunking (token target 400–800 with overlap)
* Persist chunks in SQLite (FTS5) for keyword search
* Store embeddings & metadata in ChromaDB for semantic search

## Directory Layout

```text
services/ingestion-service/
  app/              # Source code
  data/
    raw_files/      # (optional staging for uploads)
    text/           # (optional plain text outputs)
    db/             # SQLite + jsonl outputs
    chroma/         # Chroma persistent storage
```

## Quick Start (Local)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.main --input /path/to/input_dir
```

### Run as HTTP API

```bash
uvicorn app.api:app --host 0.0.0.0 --port 8001
```

Health check:

```bash
curl http://localhost:8001/health
```

Trigger ingestion (runs in background by default):

```bash
curl -X POST http://localhost:8001/ingest \
  -H "Content-Type: application/json" \
  -d '{
        "input_dir": "/absolute/path/input",
        "records_jsonl": "data/db/records.jsonl",
        "chunks_jsonl": "data/db/chunks.jsonl",
        "store": true,
        "embed": true,
        "run_async": true
      }'
```

Set `run_async` to `false` if you prefer the request to block until ingestion completes.

Check progress (returns `status`, `progress` 0-1, and latest `message`):

```bash
curl http://localhost:8001/ingest/status
```

Generated:

* `data/db/records.jsonl` per page/sheet
* `data/db/chunks.jsonl` chunk objects
* SQLite file `data/db/ingestion.db` with tables `documents`, `ocr_quality`, FTS `docs_fts`
* Chroma persistent collection under `data/chroma`

## Docker

```bash
docker build -t ingestion-service .
# Example: mount host input directory
docker run --rm -v /absolute/path/input:/input ingestion-service --input /input
```

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| OCR_LANG | Base OCR language | tha |
| OCR_DPI | OCR image DPI | 450 |
| MIN_QUALITY_SCORE | Score threshold for OCR fallback | 0.2 |
| MIN_LENGTH | Min length for MuPDF accept | 50 |
| OCR_ENGINE | Force OCR backend (auto\|poppler\|tesseract\|typhoon) | auto |
| TY_OCR_ENABLE | Enable Typhoon OCR fallback usage | 0 |
| CHUNK_MIN_TOKENS | Lower token target | 400 |
| CHUNK_MAX_TOKENS | Upper token target | 800 |
| CHUNK_OVERLAP_RATIO | Overlap ratio for tail carry | 0.12 |
| EMBEDDING_MODEL | SentenceTransformer model | BAAI/bge-m3 |
| EMBEDDING_API_BASE | External embedding API base | (unset) |
| EMBEDDING_API_KEY | Embedding API key | (unset) |
| POPPLER_PATH | Poppler bin directory (Windows) | (unset) |
| TESSERACT_PATH | Tesseract binary path if not on PATH | (unset) |
| EMBED_FLAGGED | Embed low-quality (flagged) chunks (true/false) | false |

### OCR Engine Selection

Set `OCR_ENGINE` to:

* `auto` (default): MuPDF text, page-level quality check, fallback Typhoon (if enabled) then Tesseract.
* `poppler`: Use only MuPDF text (no OCR), fastest.
* `tesseract`: Force full Tesseract OCR for all pages.
* `typhoon`: Force Typhoon OCR for all pages (requires `TY_OCR_ENABLE=1`).

If `TY_OCR_ENABLE=0`, specifying `OCR_ENGINE=typhoon` automatically downgrades to `auto`.

### Flagged Chunk Handling

Chunks whose page text fails quality heuristics get `status=flagged`. When `EMBED_FLAGGED=false`, these are skipped during embedding and written to a timestamped review file under `data/db/review/flagged_*.jsonl` for manual inspection.

## Extending

* Alternate OCR: Control via `OCR_ENGINE` and `TY_OCR_ENABLE`.
* Replace embedding with Typhoon/LLaMA: modify `_embed_texts` in `chroma_client.py` to call external service.
* Add API layer: create FastAPI app wrapping `run_ingest` for remote triggering.

## Keyword Search

```python
from app.db import keyword_search
print(keyword_search('หลักเกณฑ์', limit=5))
```

## Semantic Search

```python
from app.chroma_client import semantic_search
print(semantic_search('หลักเกณฑ์การรับสมัคร', n_results=3))
```

## Notes

* FTS query syntax: use simple terms or phrase quotes.
* Chroma stores normalized embeddings (if model supports). Dummy hash embedding used if no model/API available.
* Token estimation heuristic (Thai ~4 chars/token) guides chunk size only; adjust if needed.

## Next Steps

1. Wrap service with ingestion API (FastAPI) for `chat-backend` to call.
2. Implement RAG service combining Chroma semantic + SQLite keyword results.
3. Add incremental update & re-chunk logic.
4. Integrate Typhoon OCR / LLaMA embedding endpoints.
