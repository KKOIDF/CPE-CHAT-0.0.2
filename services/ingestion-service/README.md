# Ingestion Service (OCR + Chunk + Store)

## Overview
Python service for batch ingestion of PDF and Excel/CSV documents:
- Extract text (PyMuPDF) with OCR fallback (pdf2image + Tesseract)
- Thai/English mixed handling + basic normalization
- Sheet ingestion for tabular files
- Quality-based OCR decisions (length + signal score)
- Paragraph + sentence aware chunking (token target 400–800 with overlap)
- Persist chunks in SQLite (FTS5) for keyword search
- Store embeddings & metadata in ChromaDB for semantic search

## Directory Layout
```
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
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python -m app.main --input /path/to/input_dir
```
Generated:
- `data/db/records.jsonl` per page/sheet
- `data/db/chunks.jsonl` chunk objects
- SQLite file `data/db/ingestion.db` with FTS5 (table `documents`)
- Chroma persistent collection under `data/chroma`

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
| CHUNK_MIN_TOKENS | Lower token target | 400 |
| CHUNK_MAX_TOKENS | Upper token target | 800 |
| CHUNK_OVERLAP_RATIO | Overlap ratio for tail carry | 0.12 |
| EMBEDDING_MODEL | SentenceTransformer model | BAAI/bge-m3 |
| EMBEDDING_API_BASE | External embedding API base | (unset) |
| EMBEDDING_API_KEY | Embedding API key | (unset) |
| POPPLER_PATH | Poppler bin directory (Windows) | (unset) |
| TESSERACT_PATH | Tesseract binary path if not on PATH | (unset) |

## Extending
- Add Typhoon OCR: implement new function in `extract_pdf.py` and select based on env.
- Replace embedding with Typhoon/LLaMA: modify `_embed_texts` in `chroma_client.py` to call external service.
- Add API layer: create FastAPI app wrapping `run_ingest` for remote triggering.

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
- FTS query syntax: use simple terms or phrase quotes.
- Chroma stores normalized embeddings (if model supports). Dummy hash embedding used if no model/API available.
- Token estimation heuristic (Thai ~4 chars/token) guides chunk size only; adjust if needed.

## Next Steps
1. Wrap service with ingestion API (FastAPI) for `chat-backend` to call.
2. Implement RAG service combining Chroma semantic + SQLite keyword results.
3. Add incremental update & re-chunk logic.
4. Integrate Typhoon OCR / LLaMA embedding endpoints.
