from pathlib import Path
from typing import List, Dict
import json
import fitz  # PyMuPDF
from datetime import datetime

from .extract_pdf import extract_pages_with_fallback, extract_text_mupdf, ocr_page_images
from .extract_excel import extract_excel_to_records
from .utils import split_paragraphs_smart, clean_for_index
from .ocr_postprocess import postprocess_ocr_text
from .toon_converter import write_toon
from .config import (
    OCR_ENGINE,
    POPPLER_PATH,
    TESSERACT_PATH,
    OCR_DPI,
    OCR_LANG_DEFAULT,
    MUPDF_ONLY,
    OCR_POSTPROCESS,
    OCR_MERGE_LINES,
    OCR_NORMALIZE_THAI_DIGITS,
    OCR_SPELL_CORRECT_THAI,
)

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
    # Lazy imports so txt-only ingestion doesn't require OCR extras.
    try:
        from pdf2image import convert_from_path  # type: ignore
        import pytesseract  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Tesseract OCR requested but required packages are missing. "
            "Install 'pdf2image' and 'pytesseract' (and ensure poppler/tesseract binaries exist). "
            f"Original error: {e}"
        )

    # Set Tesseract binary path if configured
    if TESSERACT_PATH:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

    kwargs = {}
    if POPPLER_PATH:
        kwargs['poppler_path'] = POPPLER_PATH
    images = convert_from_path(pdf_path, dpi=OCR_DPI, **kwargs)
    out: List[str] = []
    for img in images:
        txt = pytesseract.image_to_string(img, lang=OCR_LANG_DEFAULT) or ''
        out.append(clean_for_index(txt))
    return out


def ingest_pdf(pdf_path: str) -> List[Dict]:
    # Highest priority fast path if explicitly requested
    if MUPDF_ONLY:
        pages = _pages_poppler(pdf_path)
        method = 'pdf-mupdf-only'
    else:
        engine = OCR_ENGINE  # auto | poppler | tesseract
        if engine not in ('auto', 'poppler', 'tesseract'):
            engine = 'auto'

        if engine == 'poppler':
            pages = _pages_poppler(pdf_path)
            method = 'pdf-poppler'
        elif engine == 'tesseract':
            pages = _pages_tesseract(pdf_path)
            method = 'pdf-tesseract'
        else:
            # auto fallback chain (MuPDF -> Tesseract per page)
            pages = extract_pages_with_fallback(pdf_path)
            method = 'pdf-auto'

    records = []
    for i, ptxt in enumerate(pages, start=1):
        if OCR_POSTPROCESS:
            ptxt = postprocess_ocr_text(
                ptxt,
                merge_lines=OCR_MERGE_LINES,
                normalize_thai_digits=OCR_NORMALIZE_THAI_DIGITS,
                spell_correct_thai=OCR_SPELL_CORRECT_THAI,
            )
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


def ingest_txt(path: str) -> List[Dict]:
    p = Path(path)
    try:
        raw = p.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        raw = ''
    txt = clean_for_index(raw)
    if OCR_POSTPROCESS:
        txt = postprocess_ocr_text(
            txt,
            merge_lines=OCR_MERGE_LINES,
            normalize_thai_digits=OCR_NORMALIZE_THAI_DIGITS,
            spell_correct_thai=OCR_SPELL_CORRECT_THAI,
        )
    return [{
        'source': str(p.resolve()),
        'page_no': 1,
        'method': 'txt',
        'text': txt,
        'paragraphs': split_paragraphs_smart(txt),
    }]


def write_jsonl(records: List[Dict], out_path: str) -> str:
    """Legacy JSONL writer - use write_toon for new code"""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8') as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    return str(p)


def write_records_toon(records: List[Dict], out_path: str) -> str:
    """Write records to TOON format (default)"""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_toon({'records': records}, str(p))
    return str(p)
