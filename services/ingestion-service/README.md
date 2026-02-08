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
  data/             # (legacy; still supported)
    raw_files/
    text/
    db/
    chroma/

Workspace (recommended):
  data/<domain>/    # raw input files (announcements/regulations/curriculum)
  indexes/<domain>/vector/chroma/              # Chroma per domain
  indexes/<domain>/vector/sqlite/ingestion.db  # SQLite FTS per domain
```

## Quick Start (Local)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.main --input /path/to/input_dir

# Per-domain indexing (recommended)
# announcements/regulations/curriculum
python -m app.main --domain announcements --input ./data/announcements
python -m app.main --domain regulations --input ./data/regulations
python -m app.main --domain curriculum --input ./data/curriculum
```

Generated:

* `data/db/records.toon` per page/sheet (TOON format - 80% smaller than JSON)
* `data/db/chunks.toon` chunk objects (TOON format)
* If `--domain` is set:
  - SQLite: `indexes/<domain>/vector/sqlite/ingestion.db`
  - Chroma: `indexes/<domain>/vector/chroma`
* If `--domain` is not set (legacy):
  - SQLite: `data/db/ingestion.db`
  - Chroma: `data/chroma`

**Note:** Legacy JSONL format can still be written by passing `--use-toon false`.

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
| OCR_ENGINE | Force OCR backend (auto\|poppler\|tesseract) | auto |
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

* `auto` (default): MuPDF text, page-level quality check, fallback to Tesseract on low-quality pages.
* `poppler`: Use only MuPDF text (no OCR), fastest.
* `tesseract`: Force full Tesseract OCR for all pages.

### Flagged Chunk Handling

Chunks whose page text fails quality heuristics get `status=flagged`. When `EMBED_FLAGGED=false`, these are skipped during embedding and written to a timestamped review file under `data/db/review/flagged_*.jsonl` for manual inspection.

## Extending

* Alternate OCR: Control via `OCR_ENGINE`.
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
4. Integrate external embedding endpoints.
