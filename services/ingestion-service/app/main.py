import argparse
import json
import hashlib
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from .ocr_pipeline import ingest_pdf, ingest_excel, write_jsonl
from .chunking import paragraphs_from_records, make_chunks
from .db import init_db, insert_chunks, log_ocr_quality
from .chroma_client import upsert_chunks
from .quality import is_valid_ocr, make_quality_entry
from .config import EMBED_FLAGGED


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


def _gen_doc_id(path: str, page: int, chunk_id: int) -> str:
    basis = f"{path}|{page}|{chunk_id}"
    return hashlib.sha1(basis.encode('utf-8', 'ignore')).hexdigest()[:32]


def run_ingest(
    input_dir: str,
    jsonl_out: str,
    chunk_out: str,
    store: bool = True,
    embed: bool = True,
    progress_callback=None,
):
    files = gather_files(input_dir)
    all_records: List[dict] = []
    quality_entries: List[Dict] = []
    total_steps = max(len(files), 1)
    total_steps += 1  # write_jsonl
    total_steps += 1  # make_chunks
    total_steps += 1 if store else 0
    total_steps += 1 if embed else 0
    completed_steps = 0

    def _report(progress: float, message: str):
        if progress_callback:
            progress_callback(progress=progress, message=message)

    # ingest raw pages/sheets
    for f in files:
        recs = process_file(f)
        all_records.extend(recs)
        completed_steps += 1
        _report(completed_steps / total_steps, f"Processed {f.name}")
    write_jsonl(all_records, jsonl_out)
    completed_steps += 1
    _report(completed_steps / total_steps, "Wrote records JSONL")

    # build paragraphs then chunks
    paragraphs = paragraphs_from_records(all_records)
    raw_chunks = make_chunks(paragraphs, source_path=input_dir)
    completed_steps += 1
    _report(completed_steps / total_steps, "Chunked paragraphs")

    # enrich chunks with doc_id + file_type + chunk_id and quality status (page-level)
    enriched_chunks: List[Dict] = []
    for idx, ch in enumerate(raw_chunks):
        # ensure page integer
        page_raw = ch.get('page_start')
        try:
            page = int(page_raw) if page_raw is not None else 0
        except (ValueError, TypeError):
            page = 0
        file_type = Path(ch.get('path','')).suffix.lower().lstrip('.') or 'pdf'
        doc_id = _gen_doc_id(ch.get('path',''), page, idx)
        status = 'ok' if is_valid_ocr(ch.get('text','')) else 'flagged'
        quality_entries.append(make_quality_entry(doc_id, page, ch.get('text',''), 'auto', status))
        ch.update({'doc_id': doc_id, 'file_type': file_type, 'chunk_id': idx, 'status': status})
        enriched_chunks.append(ch)

    write_jsonl(enriched_chunks, chunk_out)

    if store:
        init_db()
        insert_chunks(enriched_chunks)
        log_ocr_quality(quality_entries)
        completed_steps += 1
        _report(completed_steps / total_steps, "Stored chunks + quality logs")
    # Prepare review file for flagged chunks when not embedding them
    flagged_chunks = [c for c in enriched_chunks if c.get('status') == 'flagged']
    embed_candidates = enriched_chunks if EMBED_FLAGGED else [c for c in enriched_chunks if c.get('status') != 'flagged']

    if flagged_chunks and not EMBED_FLAGGED:
        review_dir = Path('data/db/review')
        review_dir.mkdir(parents=True, exist_ok=True)
        review_path = review_dir / f"flagged_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jsonl"
        with review_path.open('w', encoding='utf-8') as rf:
            for c in flagged_chunks:
                rf.write(json.dumps(c, ensure_ascii=False) + '\n')
        print(f"Wrote flagged review file: {review_path}")

    if embed:
        upsert_chunks(embed_candidates)
        completed_steps += 1
        _report(completed_steps / total_steps, "Embedded chunks")

    flagged = len(flagged_chunks)
    embedded = len(embed_candidates) if embed else 0
    print(f"Ingested {len(files)} file(s), {len(all_records)} page/sheet records, {len(enriched_chunks)} chunks (flagged={flagged}, embedded={embedded}).")


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
