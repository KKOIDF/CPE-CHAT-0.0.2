import argparse
import json
import hashlib
import os
import time
from pathlib import Path
from typing import List, Dict
from datetime import datetime, timezone


def gather_files(input_dir: str) -> List[Path]:
    base = Path(input_dir)
    pdfs = list(base.rglob('*.pdf'))
    txts = list(base.rglob('*.txt'))
    excs = []
    for patt in ['*.xlsx', '*.xls', '*.csv', '*.tsv']:
        excs.extend(base.rglob(patt))
    return sorted(set(pdfs + txts + excs))


def process_file(fp: Path) -> List[dict]:
    # Delay import so env (domain paths) can be set before loading config
    from .ocr_pipeline import ingest_pdf, ingest_excel, ingest_txt
    if fp.suffix.lower() == '.pdf':
        return ingest_pdf(str(fp))
    if fp.suffix.lower() == '.txt':
        return ingest_txt(str(fp))
    if fp.suffix.lower() in ['.xlsx', '.xls', '.csv', '.tsv']:
        return ingest_excel(str(fp))
    return []


def _gen_doc_id(path: str, page: int, chunk_id: int, chunk_uid: str = '') -> str:
    # Prefer chunk_uid when available for deterministic IDs across re-ingestion.
    if chunk_uid:
        basis = f"{path}|{chunk_uid}"
    else:
        basis = f"{path}|{page}|{chunk_id}"
    return hashlib.sha1(basis.encode('utf-8', 'ignore')).hexdigest()[:32]


def run_ingest(
    input_dir: str,
    output_base: str,
    store: bool = True,
    embed: bool = True,
    timing_out: str | None = None,
    timing_label: str = '',
):
    """Run ingestion pipeline with TOON format as default"""
    # Delay imports so env (domain paths) can be set before loading config
    from .chunking import paragraphs_from_records, make_chunks
    from .db import init_db, insert_chunks, log_ocr_quality
    from .quality import is_valid_ocr, make_quality_entry
    from .config import EMBED_FLAGGED, REVIEW_DIR, DOMAIN
    from .structured_artifacts import write_structured_artifacts
    from .toon_converter import write_toon
    try:
        from .neo4j_graph import upsert_chunks_to_neo4j
    except Exception:
        upsert_chunks_to_neo4j = None  # type: ignore

    total_started = time.perf_counter()
    files = gather_files(input_dir)
    all_records: List[dict] = []
    quality_entries: List[Dict] = []
    file_timings: List[Dict] = []
    phase_ms: Dict[str, float] = {
        'extract_total_ms': 0.0,
        'records_write_ms': 0.0,
        'chunking_ms': 0.0,
        'chunks_write_ms': 0.0,
        'db_store_ms': 0.0,
        'structured_artifacts_ms': 0.0,
        'embedding_ms': 0.0,
        'neo4j_ms': 0.0,
    }

    # ingest raw pages/sheets
    for f in files:
        file_started = time.perf_counter()
        recs = process_file(f)
        elapsed_ms = (time.perf_counter() - file_started) * 1000.0
        phase_ms['extract_total_ms'] += elapsed_ms
        file_timings.append({
            'path': str(f),
            'file_type': f.suffix.lower().lstrip('.') or 'unknown',
            'records': len(recs),
            'elapsed_ms': round(elapsed_ms, 3),
        })
        all_records.extend(recs)
    
    # Write records in TOON format (default)
    records_out = output_base.replace('.jsonl', '.toon') if '.jsonl' in output_base else f"{output_base}_records.toon"
    phase_started = time.perf_counter()
    write_toon({'records': all_records}, records_out)
    phase_ms['records_write_ms'] = (time.perf_counter() - phase_started) * 1000.0
    print(f"Wrote {len(all_records)} records -> {records_out}")

    # build paragraphs then chunks
    phase_started = time.perf_counter()
    paragraphs = paragraphs_from_records(all_records)
    # Group paragraphs by original source file path to avoid losing per-file provenance
    grouped: Dict[str, List[Dict]] = {}
    for p in paragraphs:
        src = p.get('src') or input_dir
        grouped.setdefault(src, []).append(p)
    raw_chunks: List[Dict] = []
    for src, plist in grouped.items():
        raw_chunks.extend(make_chunks(plist, source_path=src))
    phase_ms['chunking_ms'] = (time.perf_counter() - phase_started) * 1000.0

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
        # Keep deterministic chunk ordering when chunker provided it.
        chunk_id = ch.get('chunk_id')
        try:
            chunk_id_int = int(chunk_id) if chunk_id is not None else idx
        except (ValueError, TypeError):
            chunk_id_int = idx
        chunk_uid = str(ch.get('chunk_uid') or '').strip()
        doc_id = _gen_doc_id(ch.get('path',''), page, chunk_id_int, chunk_uid=chunk_uid)
        status = 'ok' if is_valid_ocr(ch.get('text','')) else 'flagged'
        quality_entries.append(make_quality_entry(doc_id, page, ch.get('text',''), 'auto', status))
        ch.update({'doc_id': doc_id, 'file_type': file_type, 'chunk_id': chunk_id_int, 'status': status})
        enriched_chunks.append(ch)

    # Write chunks in TOON format (default)
    chunks_out = output_base.replace('.jsonl', '.toon') if '.jsonl' in output_base else f"{output_base}_chunks.toon"
    phase_started = time.perf_counter()
    write_toon({'chunks': enriched_chunks}, chunks_out)
    phase_ms['chunks_write_ms'] = (time.perf_counter() - phase_started) * 1000.0
    print(f"Wrote {len(enriched_chunks)} chunks -> {chunks_out}")

    if store:
        phase_started = time.perf_counter()
        init_db()
        insert_chunks(enriched_chunks)
        log_ocr_quality(quality_entries)
        phase_ms['db_store_ms'] = (time.perf_counter() - phase_started) * 1000.0

    phase_started = time.perf_counter()
    artifact_outputs = write_structured_artifacts(files)
    phase_ms['structured_artifacts_ms'] = (time.perf_counter() - phase_started) * 1000.0
    for artifact_path in artifact_outputs:
        print(f"Wrote structured artifact -> {artifact_path}")
    # Prepare review file for flagged chunks when not embedding them
    flagged_chunks = [c for c in enriched_chunks if c.get('status') == 'flagged']
    embed_candidates = enriched_chunks if EMBED_FLAGGED else [c for c in enriched_chunks if c.get('status') != 'flagged']

    if flagged_chunks and not EMBED_FLAGGED:
        review_dir = REVIEW_DIR
        review_path = review_dir / f"flagged_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.jsonl"
        with review_path.open('w', encoding='utf-8') as rf:
            for c in flagged_chunks:
                rf.write(json.dumps(c, ensure_ascii=False) + '\n')
        print(f"Wrote flagged review file: {review_path}")

    if embed:
        # Import lazily to avoid importing heavy deps (e.g., torch) when --no-embed is used.
        from .chroma_client import upsert_chunks
        phase_started = time.perf_counter()
        upsert_chunks(embed_candidates)
        phase_ms['embedding_ms'] = (time.perf_counter() - phase_started) * 1000.0

    # Curriculum: optional Neo4j graph upsert (hybrid graph RAG)
    if DOMAIN == 'curriculum' and upsert_chunks_to_neo4j:
        try:
            phase_started = time.perf_counter()
            upsert_chunks_to_neo4j(enriched_chunks)
            phase_ms['neo4j_ms'] = (time.perf_counter() - phase_started) * 1000.0
        except Exception as e:
            print(f"[Neo4j] Graph upsert skipped/failed: {e}")

    flagged = len(flagged_chunks)
    embedded = len(embed_candidates) if embed else 0
    print(f"Ingested {len(files)} file(s), {len(all_records)} page/sheet records, {len(enriched_chunks)} chunks (flagged={flagged}, embedded={embedded}).")

    total_ms = (time.perf_counter() - total_started) * 1000.0
    timing_payload = {
        'label': timing_label,
        'domain': DOMAIN,
        'input_dir': input_dir,
        'output_base': output_base,
        'store': bool(store),
        'embed': bool(embed),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'counts': {
            'files': len(files),
            'records': len(all_records),
            'paragraphs': len(paragraphs),
            'chunks': len(enriched_chunks),
            'flagged_chunks': flagged,
            'embedded_chunks': embedded,
        },
        'phase_ms': {k: round(v, 3) for k, v in phase_ms.items()},
        'total_ms': round(total_ms, 3),
        'file_timings': file_timings,
    }
    if timing_out:
        timing_path = Path(timing_out)
        timing_path.parent.mkdir(parents=True, exist_ok=True)
        timing_path.write_text(json.dumps(timing_payload, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"Wrote timing report -> {timing_path}")
    return timing_payload


def cli():
    p = argparse.ArgumentParser(description='Ingestion Service CLI - Uses TOON format by default')
    p.add_argument('--domain', default=os.getenv('CPE_DOMAIN', ''), help='announcements|regulations|curriculum (optional; isolates indexes)')
    p.add_argument('--input', required=True, help='Input directory containing PDF/Excel files')
    p.add_argument('--output', default='data/db/data', help='Output base path (default: data/db/data)')
    p.add_argument('--chunk-strategy', default=os.getenv('CHUNK_STRATEGY', ''), help='Override chunking strategy (e.g., langchain_recursive)')
    p.add_argument('--langchain', action='store_true', help='Use LangChain recursive splitter chunking (sets CHUNK_STRATEGY=langchain_recursive)')
    p.add_argument('--no-store', action='store_true', help='Skip database storage')
    p.add_argument('--no-embed', action='store_true', help='Skip embedding generation')
    p.add_argument('--timing-out', default=os.getenv('INGEST_TIMING_OUT', ''), help='Write ingestion timing JSON to this path')
    p.add_argument('--timing-label', default=os.getenv('INGEST_TIMING_LABEL', ''), help='Optional label stored in timing report')
    args = p.parse_args()

    # Ensure domain is set before config/db/chroma modules are imported
    if args.domain:
        os.environ['CPE_DOMAIN'] = str(args.domain).strip().lower()

    # Ensure chunking strategy is set before importing chunking/config modules.
    if args.chunk_strategy and str(args.chunk_strategy).strip():
        os.environ['CHUNK_STRATEGY'] = str(args.chunk_strategy).strip().lower()
    elif args.langchain:
        os.environ.setdefault('CHUNK_STRATEGY', 'langchain_recursive')
    elif str(os.getenv('CPE_DOMAIN', '')).strip().lower() == 'curriculum':
        # Prevent accidental fallback to a generic global strategy for curriculum ingestion.
        os.environ.setdefault('CURRICULUM_CHUNK_STRATEGY', 'curriculum_course')
    run_ingest(
        args.input,
        args.output,
        store=not args.no_store,
        embed=not args.no_embed,
        timing_out=(args.timing_out or '').strip() or None,
        timing_label=str(args.timing_label or '').strip(),
    )

if __name__ == '__main__':
    cli()
