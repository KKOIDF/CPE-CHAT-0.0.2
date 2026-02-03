"""Export flagged pages as images for manual review."""

import json
import sys
from pathlib import Path
from pdf2image import convert_from_path
import os

# Load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def export_flagged_images(review_file: str, output_dir: str = None, max_pages: int = None):
    '''Export flagged PDF pages as PNG images.'''
    
    if not Path(review_file).exists():
        print(f'Error: File not found: {review_file}')
        return
    
    # Default output directory
    if output_dir is None:
        output_dir = str(Path(review_file).parent / 'flagged_images')
    
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    with open(review_file, 'r', encoding='utf-8') as f:
        chunks = [json.loads(line) for line in f if line.strip()]
    
    if not chunks:
        print('No flagged chunks found.')
        return
    
    print(f'Found {len(chunks)} flagged chunks.')
    if max_pages:
        chunks = chunks[:max_pages]
        print(f'Processing first {max_pages} pages only.')
    
    poppler_path = os.environ.get('POPPLER_PATH')
    kwargs = {'poppler_path': poppler_path} if poppler_path else {}
    
    exported = 0
    errors = 0
    
    for i, chunk in enumerate(chunks, 1):
        # Try to construct valid PDF path
        path_raw = chunk.get('path', chunk.get('source', ''))
        source_raw = chunk.get('source', '')
        page_no = chunk.get('page_start', 1)
        
        # If path is a directory and source is a filename, combine them
        pdf_path = Path(path_raw)
        if pdf_path.is_dir() and source_raw:
            # Try appending source to path
            pdf_path = pdf_path / source_raw
        
        # If source looks like a better candidate, use it
        if not pdf_path.exists() and source_raw and not Path(source_raw).is_dir():
            pdf_path = Path(source_raw)
        
        # Still not found? Search in directory
        if not pdf_path.exists() and Path(path_raw).is_dir():
            # Find PDF files in that directory
            pdf_files = list(Path(path_raw).glob('*.pdf'))
            if pdf_files:
                # Use first PDF found (heuristic: probably the source)
                pdf_path = pdf_files[0]
                print(f'[{i}/{len(chunks)}] ⚠ Using {pdf_path.name} from directory')
        
        if not pdf_path.exists():
            print(f'[{i}/{len(chunks)}] ✗ File not found: {path_raw}')
            errors += 1
            continue
        
        try:
            # Check if page exists first
            import fitz
            with fitz.open(str(pdf_path)) as doc:
                total_pages = doc.page_count
            
            if page_no > total_pages:
                print(f'[{i}/{len(chunks)}] ✗ Page {page_no} exceeds total pages ({total_pages})')
                errors += 1
                continue
            
            images = convert_from_path(
                str(pdf_path),
                first_page=page_no,
                last_page=page_no,
                dpi=300,
                **kwargs
            )
            
            if images:
                filename = f'{Path(pdf_path).stem}_page{page_no}.png'
                img_path = out_path / filename
                images[0].save(img_path, 'PNG')
                print(f'[{i}/{len(chunks)}] ✓ {filename}')
                exported += 1
            else:
                print(f'[{i}/{len(chunks)}] ✗ No image rendered')
                errors += 1
                
        except Exception as e:
            print(f'[{i}/{len(chunks)}] ✗ Error: {e}')
            errors += 1
    
    print(f'\nExported: {exported} images')
    print(f'Errors: {errors}')
    print(f'Output: {out_path}')


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Export flagged pages as images')
    parser.add_argument('review_file', help='Path to flagged review JSONL')
    parser.add_argument('--output', '-o', help='Output directory (default: review_file_dir/flagged_images)')
    parser.add_argument('--max-pages', '-n', type=int, help='Maximum pages to export')
    
    args = parser.parse_args()
    
    export_flagged_images(args.review_file, args.output, args.max_pages)
