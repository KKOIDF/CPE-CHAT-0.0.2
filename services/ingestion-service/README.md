# Ingestion Service

Python service to ingest PDF / TXT / Excel files, perform OCR (Tesseract, placeholder for Typhoon OCR), validate text quality, chunk content, store metadata and full text in SQLite (with FTS5) and semantic embeddings in ChromaDB.

## Workflow
1. Detect file type by extension.
2. Extract text:
   - PDF: Try native extraction (pdfminer). If low text ratio, run OCR (pdf2image + pytesseract). Typhoon OCR can be integrated later.
   - Excel: Flatten sheets to CSV-like text.
   - TXT: Direct read.
3. Validate quality (length, alpha ratio, language if possible).
4. Chunk text into sentence-based segments.
5. Insert document + chunk metadata into SQLite (`documents`, `chunks_fts`, `chunks_meta`).
6. Add chunks to ChromaDB collection for semantic search; record embedding IDs.

## Directory Structure
```
services/ingestion-service/
  app/
    main.py
    db.py
    chroma_client.py
    extract_pdf.py
    ocr_pipeline.py
    extract_excel.py
    validation.py
    chunking.py
  data/
    raw_files/    # place source files here (mount in Docker)
    text/         # optional for intermediate saved texts
    db/           # SQLite database file
    chroma/       # ChromaDB persistence directory
  requirements.txt
  Dockerfile
```

## Running Locally
Install system deps (Tesseract, Poppler) then Python requirements:
```bash
pip install -r requirements.txt
python app/main.py path/to/file.pdf
```

## Docker Usage
Build:
```bash
docker build -t ingestion-service .
```
Run (mount host raw files directory):
```bash
docker run --rm -v "$(pwd)/data/raw_files:/app/data/raw_files" ingestion-service /app/data/raw_files/your.pdf
```

## Notes
- Typhoon / LLaMA embedding & OCR integration: replace placeholder in `ocr_pipeline.py` and swap Chroma default embedding with custom embeddings.
- Adjust chunk sizes in `chunking.py` as needed for downstream RAG context window.
- SQLite FTS5 search available via `search_fulltext` in `db.py`.

## Next Steps
- Add FastAPI or Flask wrapper for ingestion requests.
- Integrate Typhoon OCR & embedding API.
- Add retry / logging / metrics.
