import argparse
from pathlib import Path
from typing import Dict, Any

from db import init_db, insert_document, add_to_fts, insert_ocr_quality
from chroma_client import add_chunks as chroma_add_chunks
from extract_pdf import extract_pdf_text
from extract_excel import extract_excel_text
from validation import assess_quality, is_acceptable
from chunking import chunk_text
from uuid import uuid4

SUPPORTED_TYPES = {'.pdf': 'pdf', '.txt': 'txt', '.xlsx': 'excel', '.xls': 'excel'}


def read_txt(path: str) -> str:
    return Path(path).read_text(encoding='utf-8', errors='ignore')


def extract(path: str, file_type: str) -> Dict[str, Any]:
    if file_type == 'pdf':
        text, used_ocr = extract_pdf_text(path)
        return {'text': text, 'used_ocr': used_ocr}
    if file_type == 'excel':
        text, sheet_count = extract_excel_text(path)
        return {'text': text, 'sheet_count': sheet_count}
    if file_type == 'txt':
        return {'text': read_txt(path)}
    raise ValueError(f"Unsupported file type: {file_type}")


def pipeline(file_path: str) -> Dict[str, Any]:
    init_db()
    ext = Path(file_path).suffix.lower()
    if ext not in SUPPORTED_TYPES:
        raise ValueError(f"Extension {ext} not supported")
    file_type = SUPPORTED_TYPES[ext]
    extraction = extract(file_path, file_type)
    text = extraction['text']
    quality = assess_quality(text)
    if not is_acceptable(quality):
        return {'status': 'rejected', 'quality': quality}
    chunks = chunk_text(text)
    metadata = {**extraction, 'quality': quality, 'chunk_count': len(chunks)}
    # generate stable doc_id (UUID) and insert document record
    doc_uuid = str(uuid4())
    doc_numeric_id = insert_document(doc_uuid, file_path, file_type)

    # add chunks to FTS (docs_fts) and to Chroma
    for ch in chunks:
        add_to_fts(doc_uuid, ch)

    embedding_ids = chroma_add_chunks(doc_numeric_id, chunks)

    # if OCR was used, add a flag in ocr_quality for review
    if extraction.get('used_ocr'):
        # use a placeholder quality_score; downstream processes can update with real scores
        insert_ocr_quality(doc_uuid, None, 0.0, 'tesseract/typhoon', status='flagged', notes='OCR used - needs review')

    return {
        'status': 'ingested',
        'document_id': doc_uuid,
        'numeric_id': doc_numeric_id,
        'chunks': len(chunks),
        'quality': quality,
        'embedding_ids_count': len(embedding_ids)
    }


def cli():
    p = argparse.ArgumentParser(description='Ingest a document into SQLite + Chroma')
    p.add_argument('path', help='Path to file (.pdf, .txt, .xlsx)')
    args = p.parse_args()
    res = pipeline(args.path)
    print(res)

if __name__ == '__main__':
    cli()
