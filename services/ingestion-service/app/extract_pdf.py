import re
import unicodedata
from pathlib import Path
from typing import List, Optional

import fitz  # PyMuPDF
from pdf2image import convert_from_path
import pytesseract

from .config import POPPLER_PATH, OCR_LANG_DEFAULT, OCR_DPI
from .validation import text_quality_score
from .utils import normalize_text, choose_ocr_lang_for_text, clean_for_index


def extract_text_mupdf(pdf_path: str) -> str:
    texts: List[str] = []
    with fitz.open(str(pdf_path)) as doc:
        for page in doc:
            try:
                txt = page.get_text('text')
            except Exception:
                txt = page.get_text()
            texts.append(txt or '')
    return '\n'.join(texts)


def ocr_page_images(pdf_path: str, page_index: int, dpi: int = OCR_DPI, lang: str = 'tha+eng') -> str:
    kwargs = {}
    if POPPLER_PATH:
        kwargs['poppler_path'] = POPPLER_PATH
    images = convert_from_path(pdf_path, dpi=dpi, first_page=page_index + 1, last_page=page_index + 1, **kwargs)
    if not images:
        return ''
    return pytesseract.image_to_string(images[0], lang=lang) or ''


def extract_pages_with_fallback(pdf_path: str,
                                min_length: int = 50,
                                min_score: float = 0.2,
                                dynamic_lang: bool = True) -> List[str]:
    """Return list of cleaned page texts with OCR fallback when low-quality."""
    raw_pages: List[str] = []
    with fitz.open(pdf_path) as doc:
        for p in range(doc.page_count):
            try:
                txt = doc.load_page(p).get_text('text') or ''
            except Exception:
                txt = doc.load_page(p).get_text() or ''
            raw_pages.append(txt)

    preview = '\n'.join(raw_pages[: min(3, len(raw_pages))])
    default_lang = choose_ocr_lang_for_text(preview) if dynamic_lang else OCR_LANG_DEFAULT

    cleaned_pages: List[str] = []
    for idx, txt in enumerate(raw_pages):
        score = text_quality_score(txt)
        decide_ocr = (not txt.strip()) or (len(txt.strip()) < min_length) or (score < min_score)
        if decide_ocr:
            lang_page = default_lang
            if dynamic_lang:
                lang_page = choose_ocr_lang_for_text(txt or '', default=default_lang)
            ocr_txt = ocr_page_images(pdf_path, idx, lang=lang_page)
            cleaned_pages.append(clean_for_index(ocr_txt))
        else:
            cleaned_pages.append(clean_for_index(txt))
    return cleaned_pages


def extract_pdf_full(pdf_path: str) -> str:
    """Full-file extraction with OCR fallback."""
    raw = extract_text_mupdf(pdf_path)
    if raw.strip():
        return clean_for_index(raw)
    # fallback full-file OCR
    kwargs = {}
    if POPPLER_PATH:
        kwargs['poppler_path'] = POPPLER_PATH
    images = convert_from_path(pdf_path, dpi=OCR_DPI, **kwargs)
    texts = [pytesseract.image_to_string(img, lang=OCR_LANG_DEFAULT) for img in images]
    return clean_for_index('\n'.join(texts))
