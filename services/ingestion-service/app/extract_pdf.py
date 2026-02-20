from typing import List
import fitz  # PyMuPDF
try:
    import pytesseract  # type: ignore
except Exception:
    pytesseract = None  # type: ignore

# pdf2image is an optional dependency. We only need it for OCR fallback paths.
try:
    from pdf2image import convert_from_path  # type: ignore
except Exception:
    convert_from_path = None  # type: ignore

from .config import POPPLER_PATH, TESSERACT_PATH, OCR_LANG_DEFAULT, OCR_DPI, MUPDF_ONLY
from .validation import text_quality_score
from .utils import choose_ocr_lang_for_text, clean_for_index

# Set Tesseract path if configured
if TESSERACT_PATH and pytesseract is not None:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


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
    if convert_from_path is None or pytesseract is None:
        # OCR fallback unavailable; caller should handle empty result.
        return ''
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
    """Return list of cleaned page texts.
    Priority (normal): MuPDF -> Tesseract on low-quality pages.
    If MUPDF_ONLY is set: just return MuPDF text cleaned (skip all OCR).
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

    if MUPDF_ONLY or convert_from_path is None or pytesseract is None:
        return [clean_for_index(t) for t in raw_pages]

    preview = '\n'.join(raw_pages[: min(3, len(raw_pages))])
    default_lang = choose_ocr_lang_for_text(preview) if dynamic_lang else OCR_LANG_DEFAULT

    cleaned_pages: List[str] = []
    need_indices = []
    for idx, txt in enumerate(raw_pages):
        score = text_quality_score(txt)
        decide = (not txt.strip()) or (len(txt.strip()) < min_length) or (score < min_score)
        if decide:
            need_indices.append(idx)
    for idx, txt in enumerate(raw_pages):
        score = text_quality_score(txt)
        decide = (not txt.strip()) or (len(txt.strip()) < min_length) or (score < min_score)
        if decide:
            lang_page = default_lang
            if dynamic_lang:
                lang_page = choose_ocr_lang_for_text(txt or '', default=default_lang)
            tess_text = ocr_page_images(pdf_path, idx, lang=lang_page)

            cleaned_pages.append(clean_for_index(tess_text))
        else:
            cleaned_pages.append(clean_for_index(txt))
    return cleaned_pages


def extract_pdf_full(pdf_path: str) -> str:
    """Full-file extraction with OCR fallback.
    If MUPDF_ONLY set: return MuPDF text only (cleaned).
    """
    raw = extract_text_mupdf(pdf_path)
    if MUPDF_ONLY or convert_from_path is None or pytesseract is None:
        return clean_for_index(raw)

    # If MuPDF got something usable, keep it.
    if raw.strip():
        raw_score = text_quality_score(raw)
        # For scanned PDFs MuPDF often returns very low-quality text.
        # In that case, try a full Tesseract pass and take it only if it improves quality.
        if raw_score >= 0.15:
            return clean_for_index(raw)

        if convert_from_path is not None and pytesseract is not None:
            kwargs = {}
            if POPPLER_PATH:
                kwargs['poppler_path'] = POPPLER_PATH
            images = convert_from_path(pdf_path, dpi=OCR_DPI, **kwargs)
            tess = '\n'.join((pytesseract.image_to_string(img, lang=OCR_LANG_DEFAULT) or '') for img in images)
            if tess.strip() and text_quality_score(tess) > raw_score:
                return clean_for_index(tess)
        return clean_for_index(raw)

    # MuPDF returned empty: do full Tesseract OCR.
    if convert_from_path is None or pytesseract is None:
        return clean_for_index(raw)
    kwargs = {}
    if POPPLER_PATH:
        kwargs['poppler_path'] = POPPLER_PATH
    images = convert_from_path(pdf_path, dpi=OCR_DPI, **kwargs)
    texts = [pytesseract.image_to_string(img, lang=OCR_LANG_DEFAULT) for img in images]
    return clean_for_index('\n'.join(texts))
