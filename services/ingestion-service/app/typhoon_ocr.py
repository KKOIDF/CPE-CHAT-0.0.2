"""Typhoon OCR via HTTP API (OpenTyphoon) integration.

Switches from local typhoon-ocr library to remote API call so the same
functions remain compatible: `ocr_pdf_typhoon_pages` and `ocr_pdf_typhoon_full`.

Environment variables used (loaded in config):
  TY_OCR_ENABLE  -> bool toggle
  TY_OCR_API_KEY -> bearer token
  TY_OCR_MODEL   -> model name (default typhoon-ocr)
  TY_OCR_BASE    -> optional base URL (default https://api.opentyphoon.ai)
"""

from typing import List, Dict, Optional
import re
import json
import requests
from .config import TY_OCR_ENABLE, TY_OCR_API_KEY, TY_OCR_MODEL, TY_OCR_BASE

MD_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
MD_LIST = re.compile(r"^\s*([\-*+]\s+)", re.MULTILINE)
MD_CODE_FENCE = re.compile(r"```[\s\S]*?```", re.MULTILINE)


def _strip_markdown(md: str) -> str:
    t = MD_CODE_FENCE.sub('', md)
    t = MD_HEADING.sub('', t)
    t = MD_LIST.sub('', t)
    return t.strip()


def _api_call(file_path: str, pages: Optional[List[int]] = None) -> List[str]:
    if not (TY_OCR_ENABLE and TY_OCR_API_KEY):
        return []
    base = TY_OCR_BASE.rstrip('/') if TY_OCR_BASE else 'https://api.opentyphoon.ai'
    url = f"{base}/v1/ocr"
    model = TY_OCR_MODEL or 'typhoon-ocr'
    data = {
        'model': model,
        'task_type': 'v1.5',
        'max_tokens': '16000',
        'temperature': '0.1',
        'top_p': '0.6',
        'repetition_penalty': '1.1'
    }
    if pages:
        data['pages'] = json.dumps(pages)  # API expects JSON string
    headers = {'Authorization': f'Bearer {TY_OCR_API_KEY}'}
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            resp = requests.post(url, files=files, data=data, headers=headers, timeout=120)
        if resp.status_code != 200:
            print(f"Typhoon API error {resp.status_code}: {resp.text[:300]}")
            return []
        payload = resp.json()
        out: List[str] = []
        for page_result in payload.get('results', []):
            if page_result.get('success') and page_result.get('message'):
                content = page_result['message']['choices'][0]['message']['content']
                # Attempt to parse structured JSON content
                try:
                    parsed = json.loads(content)
                    text = parsed.get('natural_text', content)
                except json.JSONDecodeError:
                    text = content
                out.append(text)
            else:
                # keep positional alignment
                err = page_result.get('error', 'Unknown error')
                print(f"Typhoon page error: {err}")
                out.append('')
        return out
    except Exception as e:
        print(f"Typhoon request exception: {e}")
        return []


def ocr_pdf_typhoon_pages(pdf_path: str, page_indices: List[int], markdown: bool = True, strip_md: bool = False) -> Dict[int, str]:
    if not (TY_OCR_ENABLE and TY_OCR_API_KEY):
        return {i: '' for i in page_indices}
    # API expects 1-based page numbers
    page_nums = [i + 1 for i in page_indices]
    texts = _api_call(pdf_path, pages=page_nums)
    out: Dict[int, str] = {}
    for i, original_index in enumerate(page_indices):
        txt = texts[i] if i < len(texts) else ''
        if strip_md and txt:
            txt = _strip_markdown(txt)
        elif (not markdown) and txt:
            txt = _strip_markdown(txt)
        out[original_index] = txt
    return out


def ocr_pdf_typhoon_full(pdf_path: str, max_pages: int | None = None, strip_md: bool = False) -> str:
    if not (TY_OCR_ENABLE and TY_OCR_API_KEY):
        return ''
    pages = None
    if max_pages and max_pages > 0:
        pages = list(range(1, max_pages + 1))
    texts = _api_call(pdf_path, pages=pages)
    cleaned: List[str] = []
    for t in texts:
        if strip_md and t:
            t = _strip_markdown(t)
        cleaned.append(t)
    return '\n\n'.join(cleaned)
