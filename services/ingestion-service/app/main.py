import argparse
import json
from pathlib import Path
from typing import List

from .ocr_pipeline import ingest_pdf, ingest_excel, write_jsonl
from .chunking import paragraphs_from_records, make_chunks
from .db import init_db, insert_chunks
from .chroma_client import upsert_chunks


def gather_files(input_dir: str) -> List[Path]:
    base = Path(input_dir)
    pdfs = list(base.rglob('*.pdf'))
    excs = []
    for patt in ['*.xlsx', '*.xls', '*.csv', '*.tsv']:
        excs.extend(base.rglob(patt))
    return sorted(set(pdfs + excs))


def process_file(fp: Path) -> List[dict]:
    if fp.suffix.lower() == '.pdf':
        return ingest_pdf(str(fp))
    if fp.suffix.lower() in ['.xlsx', '.xls', '.csv', '.tsv']:
        return ingest_excel(str(fp))
    return []


def run_ingest(input_dir: str, jsonl_out: str, chunk_out: str, store: bool = True, embed: bool = True):
    files = gather_files(input_dir)
    all_records: List[dict] = []
    for f in files:
        recs = process_file(f)
        all_records.extend(recs)
    write_jsonl(all_records, jsonl_out)

    paragraphs = paragraphs_from_records(all_records)
    chunks = make_chunks(paragraphs, source_path=input_dir)

    write_jsonl(chunks, chunk_out)

    if store:
        init_db()
        insert_chunks(chunks)
    if embed:
        upsert_chunks(chunks)

    print(f"Ingested {len(files)} file(s), {len(all_records)} page/sheet records, {len(chunks)} chunks.")


def cli():
    p = argparse.ArgumentParser(description='Ingestion Service CLI')
    p.add_argument('--input', required=True, help='Input directory containing PDF/Excel files')
    p.add_argument('--records-jsonl', default='data/db/records.jsonl')
    p.add_argument('--chunks-jsonl', default='data/db/chunks.jsonl')
    p.add_argument('--no-store', action='store_true')
    p.add_argument('--no-embed', action='store_true')
    args = p.parse_args()
    run_ingest(args.input, args.records_jsonl, args.chunks_jsonl, store=not args.no_store, embed=not args.no_embed)

if __name__ == '__main__':
    cli()
