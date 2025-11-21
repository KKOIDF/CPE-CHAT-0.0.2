"""Reprocess flagged chunks with alternative OCR engines."""

import json
import sys
import os
from pathlib import Path
from typing import List, Dict
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.extract_pdf import extract_pages_with_fallback
from app.quality import ocr_quality_score, is_valid_ocr, make_quality_entry
from app.utils import split_paragraphs_smart
from app.chunking import make_chunks, paragraphs_from_records
from app.db import init_db, insert_chunks, log_ocr_quality
from app.chroma_client import upsert_chunks
from app.config import OCR_ENGINE, TY_OCR_ENABLE


def load_flagged(review_file: str) -> List[Dict]:
    '''Load flagged chunks from review JSONL.'''
    with open(review_file, 'r', encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def reprocess_with_engine(pdf_path: str, engine: str = 'typhoon') -> List[str]:
    '''Reprocess PDF with specified engine.'''
    # Temporarily override OCR_ENGINE
    original = os.environ.get('OCR_ENGINE', 'auto')
    os.environ['OCR_ENGINE'] = engine
    
    try:
        from app.ocr_pipeline import ingest_pdf
        records = ingest_pdf(pdf_path)
        return [rec.get('text', '') for rec in records]
    finally:
        os.environ['OCR_ENGINE'] = original


def reprocess_flagged(review_file: str, engine: str = 'typhoon',
                     store: bool = True, embed: bool = True,
                     quality_threshold: float = 0.3):
    '''Reprocess flagged chunks with alternative OCR engine.'''
    
    print(f'Loading flagged chunks from {review_file}...')
    flagged = load_flagged(review_file)
    
    if not flagged:
        print('No flagged chunks found.')
        return
    
    print(f'Found {len(flagged)} flagged chunks.')
    print(f'Reprocessing with engine={engine}, quality_threshold={quality_threshold}')
    
    # Group by source file
    by_file = defaultdict(set)
    for chunk in flagged:
        path = chunk.get('path', chunk.get('source', ''))
        page = chunk.get('page_start', 1)
        if path:
            by_file[path].add(page)
    
    improved_records = []
    improved_count = 0
    still_flagged = 0
    
    for pdf_path, pages in by_file.items():
        if not Path(pdf_path).exists():
            print(f'Skipping {pdf_path} (not found)')
            continue
        
        print(f'\nProcessing {Path(pdf_path).name} ({len(pages)} pages)...')
        
        try:
            page_texts = reprocess_with_engine(pdf_path, engine)
            
            for page_no in sorted(pages):
                idx = page_no - 1
                if idx >= len(page_texts):
                    continue
                    
                text = page_texts[idx]
                quality = ocr_quality_score(text)
                
                if quality >= quality_threshold and is_valid_ocr(text):
                    improved_records.append({
                        'source': pdf_path,
                        'page_no': page_no,
                        'method': f'reprocess-{engine}',
                        'text': text,
                        'paragraphs': split_paragraphs_smart(text)
                    })
                    improved_count += 1
                    print(f'  ✓ Page {page_no}: quality {quality:.2f}')
                else:
                    still_flagged += 1
                    print(f'  ✗ Page {page_no}: still low ({quality:.2f})')
                    
        except Exception as e:
            print(f'  Error: {e}')
            still_flagged += len(pages)
    
    if not improved_records:
        print(f'\nNo improvements. {still_flagged} chunks still flagged.')
        return
    
    print(f'\n✓ Improved: {improved_count}, Still flagged: {still_flagged}')
    
    # Rebuild chunks
    paragraphs = paragraphs_from_records(improved_records)
    new_chunks = make_chunks(paragraphs, source_path='')
    
    enriched = []
    quality_entries = []
    for idx, ch in enumerate(new_chunks):
        doc_id = f'reprocess_{engine}_{idx}'
        ch.update({
            'doc_id': doc_id,
            'file_type': 'pdf',
            'chunk_id': idx,
            'status': 'ok'
        })
        enriched.append(ch)
        quality_entries.append(make_quality_entry(
            doc_id, ch.get('page_start', 0), ch.get('text', ''),
            f'reprocess-{engine}', 'ok'
        ))
    
    # Save improved chunks
    out_dir = Path(review_file).parent
    out_file = out_dir / f'improved_{engine}_{Path(review_file).stem}.jsonl'
    with out_file.open('w', encoding='utf-8') as f:
        for ch in enriched:
            f.write(json.dumps(ch, ensure_ascii=False) + '\n')
    print(f'Saved {len(enriched)} improved chunks to {out_file}')
    
    if store:
        init_db()
        insert_chunks(enriched)
        log_ocr_quality(quality_entries)
        print(f'✓ Stored to database')
    
    if embed:
        upsert_chunks(enriched)
        print(f'✓ Embedded to Chroma')


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Reprocess flagged chunks')
    parser.add_argument('review_file', help='Path to flagged review JSONL')
    parser.add_argument('--engine', choices=['auto', 'typhoon', 'tesseract', 'poppler'],
                       default='typhoon', help='OCR engine (default: typhoon)')
    parser.add_argument('--no-store', action='store_true', help='Skip database')
    parser.add_argument('--no-embed', action='store_true', help='Skip embedding')
    parser.add_argument('--quality-threshold', type=float, default=0.3,
                       help='Min quality score (default: 0.3)')
    
    args = parser.parse_args()
    
    reprocess_flagged(
        args.review_file,
        engine=args.engine,
        store=not args.no_store,
        embed=not args.no_embed,
        quality_threshold=args.quality_threshold
    )
