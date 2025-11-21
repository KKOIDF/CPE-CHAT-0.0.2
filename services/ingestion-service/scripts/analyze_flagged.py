"""Analyze flagged chunks from review JSONL files."""

import json
import sys
from pathlib import Path
from collections import defaultdict, Counter
from typing import List, Dict

def analyze_flagged(review_file: str):
    '''Analyze and report statistics of flagged chunks.'''
    
    if not Path(review_file).exists():
        print(f'Error: File not found: {review_file}')
        return
    
    with open(review_file, 'r', encoding='utf-8') as f:
        chunks = [json.loads(line) for line in f if line.strip()]
    
    if not chunks:
        print('No flagged chunks found.')
        return
    
    print(f'\n=== Flagged Chunks Analysis ===')
    print(f'Total flagged: {len(chunks)}')
    
    # Group by source file
    by_file = defaultdict(list)
    for chunk in chunks:
        path = chunk.get('path', chunk.get('source', 'unknown'))
        by_file[path].append(chunk)
    
    print(f'\nFiles with flagged chunks: {len(by_file)}')
    print('\nTop files by flagged count:')
    file_counts = [(path, len(chs)) for path, chs in by_file.items()]
    for path, count in sorted(file_counts, key=lambda x: -x[1])[:10]:
        print(f'  {count:3d} chunks - {Path(path).name}')
    
    # Analyze text length
    lengths = [len(chunk.get('text', '')) for chunk in chunks]
    print(f'\nText length statistics:')
    print(f'  Min: {min(lengths)} chars')
    print(f'  Max: {max(lengths)} chars')
    print(f'  Avg: {sum(lengths) // len(lengths)} chars')
    print(f'  Empty: {sum(1 for l in lengths if l == 0)} chunks')
    
    # Sample preview
    print(f'\n=== Sample Flagged Chunks (first 3) ===')
    for i, chunk in enumerate(chunks[:3], 1):
        print(f'\n[{i}] {Path(chunk.get("path", "?")).name} - Page {chunk.get("page_start", "?")}')
        text = chunk.get('text', '')
        preview = text[:150] + '...' if len(text) > 150 else text
        print(f'Text: {preview}')
        print(f'Length: {len(text)} chars, Method: {chunk.get("method", "?")}, Status: {chunk.get("status", "?")}')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python analyze_flagged.py <review_jsonl_file>')
        print('Example: python analyze_flagged.py data/db/review/flagged_20251121111219.jsonl')
        sys.exit(1)
    
    analyze_flagged(sys.argv[1])
