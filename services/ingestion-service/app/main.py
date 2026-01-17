import argparse
import json
import hashlib
import os
from pathlib import Path
from typing import List, Dict
from datetime import datetime


def gather_files(input_dir: str) -> List[Path]:
    base = Path(input_dir)
    pdfs = list(base.rglob('*.pdf'))
    excs = []
    for patt in ['*.xlsx', '*.xls', '*.csv', '*.tsv']:
        excs.extend(base.rglob(patt))
    return sorted(set(pdfs + excs))


def process_file(fp: Path) -> List[dict]:
    # Delay import so env (domain paths) can be set before loading config
    from .ocr_pipeline import ingest_pdf, ingest_excel
    if fp.suffix.lower() == '.pdf':
        return ingest_pdf(str(fp))
    if fp.suffix.lower() in ['.xlsx', '.xls', '.csv', '.tsv']:
        return ingest_excel(str(fp))
    return []


def _gen_doc_id(path: str, page: int, chunk_id: int) -> str:
    basis = f"{path}|{page}|{chunk_id}"
    return hashlib.sha1(basis.encode('utf-8', 'ignore')).hexdigest()[:32]


def run_ingest(input_dir: str, output_base: str, store: bool = True, embed: bool = True):
    """Run ingestion pipeline with TOON format as default"""
    # Delay imports so env (domain paths) can be set before loading config
    from .chunking import paragraphs_from_records, make_chunks
    from .db import init_db, insert_chunks, log_ocr_quality
    from .chroma_client import upsert_chunks
    from .quality import is_valid_ocr, make_quality_entry
    from .config import EMBED_FLAGGED, REVIEW_DIR, DOMAIN
    from .toon_converter import write_toon
    try:
        from .neo4j_graph import upsert_chunks_to_neo4j
    except Exception:
        upsert_chunks_to_neo4j = None  # type: ignore

    files = gather_files(input_dir)
    all_records: List[dict] = []
    quality_entries: List[Dict] = []

    # ingest raw pages/sheets
    for f in files:
        recs = process_file(f)
        all_records.extend(recs)
    
    # Write records in TOON format (default)
    records_out = output_base.replace('.jsonl', '.toon') if '.jsonl' in output_base else f"{output_base}_records.toon"
    write_toon({'records': all_records}, records_out)
    print(f"✅ Wrote {len(all_records)} records → {records_out}")

    # build paragraphs then chunks
    paragraphs = paragraphs_from_records(all_records)
    # Group paragraphs by original source file path to avoid losing per-file provenance
    grouped: Dict[str, List[Dict]] = {}
    for p in paragraphs:
        src = p.get('src') or input_dir
        grouped.setdefault(src, []).append(p)
    raw_chunks: List[Dict] = []
    for src, plist in grouped.items():
        raw_chunks.extend(make_chunks(plist, source_path=src))

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

    # Write chunks in TOON format (default)
    chunks_out = output_base.replace('.jsonl', '.toon') if '.jsonl' in output_base else f"{output_base}_chunks.toon"
    write_toon({'chunks': enriched_chunks}, chunks_out)
    print(f"✅ Wrote {len(enriched_chunks)} chunks → {chunks_out}")

    if store:
        init_db()
        insert_chunks(enriched_chunks)
        log_ocr_quality(quality_entries)
    # Prepare review file for flagged chunks when not embedding them
    flagged_chunks = [c for c in enriched_chunks if c.get('status') == 'flagged']
    embed_candidates = enriched_chunks if EMBED_FLAGGED else [c for c in enriched_chunks if c.get('status') != 'flagged']

    if flagged_chunks and not EMBED_FLAGGED:
        review_dir = REVIEW_DIR
        review_path = review_dir / f"flagged_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jsonl"
        with review_path.open('w', encoding='utf-8') as rf:
            for c in flagged_chunks:
                rf.write(json.dumps(c, ensure_ascii=False) + '\n')
        print(f"Wrote flagged review file: {review_path}")

    if embed:
        upsert_chunks(embed_candidates)

    # Curriculum: optional Neo4j graph upsert (hybrid graph RAG)
    if DOMAIN == 'curriculum' and upsert_chunks_to_neo4j:
        try:
            upsert_chunks_to_neo4j(enriched_chunks)
        except Exception as e:
            print(f"[Neo4j] Graph upsert skipped/failed: {e}")

    flagged = len(flagged_chunks)
    embedded = len(embed_candidates) if embed else 0
    print(f"Ingested {len(files)} file(s), {len(all_records)} page/sheet records, {len(enriched_chunks)} chunks (flagged={flagged}, embedded={embedded}).")


def cli():
    p = argparse.ArgumentParser(description='Ingestion Service CLI - Uses TOON format by default')
    p.add_argument('--domain', default=os.getenv('CPE_DOMAIN', ''), help='announcements|regulations|curriculum (optional; isolates indexes)')
    p.add_argument('--input', required=True, help='Input directory containing PDF/Excel files')
    p.add_argument('--output', default='data/db/data', help='Output base path (default: data/db/data)')
    p.add_argument('--no-store', action='store_true', help='Skip database storage')
    p.add_argument('--no-embed', action='store_true', help='Skip embedding generation')
    args = p.parse_args()

    # Ensure domain is set before config/db/chroma modules are imported
    if args.domain:
        os.environ['CPE_DOMAIN'] = str(args.domain).strip().lower()
    run_ingest(args.input, args.output, store=not args.no_store, embed=not args.no_embed)

if __name__ == '__main__':
    cli()
