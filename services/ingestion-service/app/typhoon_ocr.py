"""Direct Typhoon OCR library integration using typhoon-ocr's ocr_document.

If typhoon-ocr isn't installed or import fails, functions return empty results.
We treat returned Markdown as text; simple optional stripping is supported.
"""

from typing import List, Dict
import re
from .config import TY_OCR_ENABLE

try:
    from typhoon_ocr import ocr_document  # type: ignore
    _HAS_TY_LIB = True
except Exception:
    _HAS_TY_LIB = False


def _ty_call(path: str, page_num: int) -> str:
    if not _HAS_TY_LIB:
        return ''
    try:
        return ocr_document(pdf_or_image_path=path, page_num=page_num)  # type: ignore
    except Exception:
        return ''


MD_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
MD_LIST = re.compile(r"^\s*([\-*+]\s+)", re.MULTILINE)
MD_CODE_FENCE = re.compile(r"```[\s\S]*?```", re.MULTILINE)


def _strip_markdown(md: str) -> str:
    # Remove code fences, headings markers, list bullets; keep line breaks
    t = MD_CODE_FENCE.sub('', md)
    t = MD_HEADING.sub('', t)
    t = MD_LIST.sub('', t)
    return t.strip()


def ocr_pdf_typhoon_pages(pdf_path: str, page_indices: List[int], markdown: bool = True, strip_md: bool = False) -> Dict[int, str]:
    if not (TY_OCR_ENABLE and _HAS_TY_LIB):
        return {i: '' for i in page_indices}
    out: Dict[int, str] = {}
    for i in page_indices:
        try:
            txt = _ty_call(pdf_path, i+1)
            if not markdown and txt:
                # crude fallback: strip markdown if caller wants plain text
                txt = _strip_markdown(txt)
            elif strip_md and txt:
                txt = _strip_markdown(txt)
            out[i] = txt or ''
        except Exception as e:
            print(f"Typhoon OCR lib page {i+1} failed: {e}")
            out[i] = ''
    return out


def ocr_pdf_typhoon_full(pdf_path: str, max_pages: int | None = None, strip_md: bool = False) -> str:
    if not (TY_OCR_ENABLE and _HAS_TY_LIB):
        return ''
    # Iterate pages sequentially until page fails or reaches max_pages
    texts: List[str] = []
    page_num = 1
    while True:
        if max_pages and page_num > max_pages:
            break
        try:
            md = _ty_call(pdf_path, page_num)
            if not md:
                break  # assume end of document if empty
            if strip_md:
                md = _strip_markdown(md)
            texts.append(md.strip())
            page_num += 1
        except Exception:
            break
    return '\n\n'.join(texts)
