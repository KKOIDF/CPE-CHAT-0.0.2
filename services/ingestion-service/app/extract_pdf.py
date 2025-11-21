from typing import List, Optional
from difflib import SequenceMatcher
import fitz  # PyMuPDF
from pdf2image import convert_from_path
import pytesseract

from .config import POPPLER_PATH, OCR_LANG_DEFAULT, OCR_DPI, TY_OCR_ENABLE
from .validation import text_quality_score
from .utils import choose_ocr_lang_for_text, clean_for_index
from .typhoon_ocr import ocr_pdf_typhoon_pages, ocr_pdf_typhoon_full


def extract_text_mupdf(pdf_path: str) -> str:
    texts: List[str] = []
    with fitz.open(str(pdf_path)) as doc:
        for page in doc:
            try:
                txt = page.get_text('text') or ''
            except Exception:
                txt = page.get_text() or ''
            if not isinstance(txt, str):  # safety guard
                txt = str(txt)
            texts.append(txt)
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
    """Return list of cleaned page texts with OCR fallback.
    Priority: MuPDF -> Typhoon OCR (if enabled) -> Tesseract.
    """
    raw_pages: List[str] = []
    with fitz.open(pdf_path) as doc:
        for p in range(doc.page_count):
            try:
                txt = doc.load_page(p).get_text('text') or ''
            except Exception:
                txt = doc.load_page(p).get_text() or ''
            if not isinstance(txt, str):
                txt = str(txt)
            raw_pages.append(txt)

    preview = '\n'.join(raw_pages[: min(3, len(raw_pages))])
    default_lang = choose_ocr_lang_for_text(preview) if dynamic_lang else OCR_LANG_DEFAULT

    cleaned_pages: List[str] = []
    need_indices = []
    for idx, txt in enumerate(raw_pages):
        score = text_quality_score(txt)
        decide = (not txt.strip()) or (len(txt.strip()) < min_length) or (score < min_score)
        if decide:
            need_indices.append(idx)
    typhoon_results = {}
    if TY_OCR_ENABLE and need_indices:
        typhoon_results = ocr_pdf_typhoon_pages(pdf_path, need_indices)
    for idx, txt in enumerate(raw_pages):
        score = text_quality_score(txt)
        decide = (not txt.strip()) or (len(txt.strip()) < min_length) or (score < min_score)
        if decide:
            # Run both OCR engines when Typhoon enabled to compare quality
            ty_text = typhoon_results.get(idx, '') if TY_OCR_ENABLE else ''
            lang_page = default_lang
            if dynamic_lang:
                lang_page = choose_ocr_lang_for_text(txt or '', default=default_lang)
            tess_text = ocr_page_images(pdf_path, idx, lang=lang_page)

            chosen = ''
            if ty_text and tess_text:
                ratio = SequenceMatcher(None, ty_text, tess_text).ratio()
                ty_score = text_quality_score(ty_text)
                tess_score = text_quality_score(tess_text)
                # Prefer Typhoon if similarity high OR Typhoon has better score; else Tesseract
                if ratio >= 0.60 or ty_score >= tess_score:
                    chosen = ty_text
                else:
                    chosen = tess_text
            else:
                chosen = ty_text or tess_text
            cleaned_pages.append(clean_for_index(chosen))
        else:
            cleaned_pages.append(clean_for_index(txt))
    return cleaned_pages


def extract_pdf_full(pdf_path: str) -> str:
    """Full-file extraction with OCR fallback."""
    raw = extract_text_mupdf(pdf_path)
    if raw.strip():
        # assess quality; if very low quality attempt Typhoon full-file before returning
        if TY_OCR_ENABLE and text_quality_score(raw) < 0.15:
            ty_full = ocr_pdf_typhoon_full(pdf_path, strip_md=True)
            if ty_full.strip():
                return clean_for_index(ty_full)
        return clean_for_index(raw)
    # fallback full-file OCR sequence: Typhoon first (if enabled) then Tesseract
    if TY_OCR_ENABLE:
        ty_full = ocr_pdf_typhoon_full(pdf_path, strip_md=True)
        if ty_full.strip():
            return clean_for_index(ty_full)
    kwargs = {}
    if POPPLER_PATH:
        kwargs['poppler_path'] = POPPLER_PATH
    images = convert_from_path(pdf_path, dpi=OCR_DPI, **kwargs)
    texts = [pytesseract.image_to_string(img, lang=OCR_LANG_DEFAULT) for img in images]
    return clean_for_index('\n'.join(texts))
