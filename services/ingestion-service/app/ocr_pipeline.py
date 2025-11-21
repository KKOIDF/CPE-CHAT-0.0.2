from pathlib import Path
from typing import List, Dict
import json
import fitz  # PyMuPDF
from pdf2image import convert_from_path
import pytesseract
from datetime import datetime

from .extract_pdf import extract_pages_with_fallback, extract_text_mupdf, ocr_page_images
from .extract_excel import extract_excel_to_records
from .utils import split_paragraphs_smart, clean_for_index
from .typhoon_ocr import ocr_pdf_typhoon_pages
from .config import OCR_ENGINE, TY_OCR_ENABLE, POPPLER_PATH, TESSERACT_PATH, OCR_DPI, OCR_LANG_DEFAULT

# Set Tesseract path if configured
if TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def _pages_poppler(pdf_path: str) -> List[str]:
    pages: List[str] = []
    with fitz.open(pdf_path) as doc:
        for p in doc:
            try:
                txt = p.get_text('text') or ''
            except Exception:
                txt = p.get_text() or ''
            if not isinstance(txt, str):
                txt = str(txt)
            pages.append(clean_for_index(txt))
    return pages


def _pages_tesseract(pdf_path: str) -> List[str]:
    kwargs = {}
    if POPPLER_PATH:
        kwargs['poppler_path'] = POPPLER_PATH
    images = convert_from_path(pdf_path, dpi=OCR_DPI, **kwargs)
    out: List[str] = []
    for img in images:
        txt = pytesseract.image_to_string(img, lang=OCR_LANG_DEFAULT) or ''
        out.append(clean_for_index(txt))
    return out


def _pages_typhoon(pdf_path: str) -> List[str]:
    pages: List[str] = []
    with fitz.open(pdf_path) as doc:
        indices = list(range(doc.page_count))
    results = ocr_pdf_typhoon_pages(pdf_path, indices)
    for i in indices:
        pages.append(clean_for_index(results.get(i, '')))
    return pages


def ingest_pdf(pdf_path: str) -> List[Dict]:
    engine = OCR_ENGINE  # auto | poppler | tesseract | typhoon
    if engine not in ('auto', 'poppler', 'tesseract', 'typhoon'):
        engine = 'auto'

    if engine == 'poppler':
        pages = _pages_poppler(pdf_path)
        method = 'pdf-poppler'
    elif engine == 'tesseract':
        pages = _pages_tesseract(pdf_path)
        method = 'pdf-tesseract'
    elif engine == 'typhoon' and TY_OCR_ENABLE:
        pages = _pages_typhoon(pdf_path)
        method = 'pdf-typhoon'
    else:
        # auto fallback chain (MuPDF -> Typhoon -> Tesseract per page)
        pages = extract_pages_with_fallback(pdf_path)
        method = 'pdf-auto'

    records = []
    for i, ptxt in enumerate(pages, start=1):
        records.append({
            'source': str(Path(pdf_path).resolve()),
            'page_no': i,
            'method': method,
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
