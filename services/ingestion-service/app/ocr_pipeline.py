from pathlib import Path
from typing import List, Dict
import json

from .extract_pdf import extract_pages_with_fallback, extract_pdf_full
from .extract_excel import extract_excel_to_records
from .utils import split_paragraphs_smart


def ingest_pdf(pdf_path: str) -> List[Dict]:
    pages = extract_pages_with_fallback(pdf_path)
    records = []
    for i, ptxt in enumerate(pages, start=1):
        records.append({
            'source': str(Path(pdf_path).resolve()),
            'page_no': i,
            'method': 'pdf',
            'text': ptxt,
            'paragraphs': split_paragraphs_smart(ptxt),
        })
    return records


def ingest_excel(path: str) -> List[Dict]:
    return extract_excel_to_records(path)


def write_jsonl(records: List[Dict], out_path: str) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8') as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    return str(p)
