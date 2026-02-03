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
import time
import requests
from .config import (
    TY_OCR_ENABLE,
    TY_OCR_API_KEY,
    TY_OCR_MODEL,
    TY_OCR_BASE,
    TY_OCR_TIMEOUT,
    TY_OCR_RETRIES,
    TY_OCR_RETRY_BACKOFF,
    TY_OCR_BATCH_SIZE,
    TY_OCR_MAX_TIMEOUTS,
)

MD_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
MD_LIST = re.compile(r"^\s*([\-*+]\s+)", re.MULTILINE)
MD_CODE_FENCE = re.compile(r"```[\s\S]*?```", re.MULTILINE)

# Global counters/state for disabling Typhoon after repeated timeouts
_TY_OCR_TIMEOUT_COUNT = 0
_TY_OCR_DISABLED = False


def _strip_markdown(md: str) -> str:
    t = MD_CODE_FENCE.sub('', md)
    t = MD_HEADING.sub('', t)
    t = MD_LIST.sub('', t)
    return t.strip()


def _api_call(file_path: str, pages: Optional[List[int]] = None) -> List[str]:
    """Call Typhoon OCR API with retry/backoff for a batch of pages.

    Returns empty list on failure to allow graceful fallback.
    """
    global _TY_OCR_TIMEOUT_COUNT, _TY_OCR_DISABLED
    if not (TY_OCR_ENABLE and TY_OCR_API_KEY):
        return []
    if _TY_OCR_DISABLED:
        # Short-circuit if previously disabled due to excessive timeouts
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

    for attempt in range(TY_OCR_RETRIES):
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                resp = requests.post(url, files=files, data=data, headers=headers, timeout=TY_OCR_TIMEOUT)
            if resp.status_code == 200:
                try:
                    payload = resp.json()
                except Exception as je:
                    print(f"Typhoon API JSON parse error: {je}")
                    return []
                out: List[str] = []
                for page_result in payload.get('results', []):
                    if page_result.get('success') and page_result.get('message'):
                        content = page_result['message']['choices'][0]['message']['content']
                        try:
                            parsed = json.loads(content)
                            text = parsed.get('natural_text', content)
                        except json.JSONDecodeError:
                            text = content
                        out.append(text)
                    else:
                        err = page_result.get('error', 'Unknown error')
                        print(f"Typhoon page error: {err}")
                        out.append('')
                return out
            else:
                print(f"Typhoon API error {resp.status_code}: {resp.text[:200]}")
                # Retry only on transient server errors (5xx) or timeouts
                if resp.status_code >= 500 and attempt < TY_OCR_RETRIES - 1:
                    sleep_s = TY_OCR_RETRY_BACKOFF * (2 ** attempt)
                    print(f"[Typhoon OCR] Transient error. Retrying in {sleep_s:.1f}s (attempt {attempt+1}/{TY_OCR_RETRIES})")
                    time.sleep(sleep_s)
                    continue
                return []
        except requests.Timeout:
            if attempt < TY_OCR_RETRIES - 1:
                sleep_s = TY_OCR_RETRY_BACKOFF * (2 ** attempt)
                print(f"[Typhoon OCR] Timeout. Retrying in {sleep_s:.1f}s (attempt {attempt+1}/{TY_OCR_RETRIES})")
                time.sleep(sleep_s)
                _TY_OCR_TIMEOUT_COUNT += 1
                if _TY_OCR_TIMEOUT_COUNT >= TY_OCR_MAX_TIMEOUTS:
                    _TY_OCR_DISABLED = True
                    print(f"[Typhoon OCR] Disabled after {_TY_OCR_TIMEOUT_COUNT} timeouts; will fallback to other OCR.")
                continue
            print("[Typhoon OCR] Final timeout; giving up.")
            _TY_OCR_TIMEOUT_COUNT += 1
            if _TY_OCR_TIMEOUT_COUNT >= TY_OCR_MAX_TIMEOUTS:
                _TY_OCR_DISABLED = True
                print(f"[Typhoon OCR] Disabled after {_TY_OCR_TIMEOUT_COUNT} timeouts; will fallback to other OCR.")
            return []
        except Exception as e:
            print(f"Typhoon request exception: {e}")
            if attempt < TY_OCR_RETRIES - 1:
                sleep_s = TY_OCR_RETRY_BACKOFF * (2 ** attempt)
                print(f"[Typhoon OCR] Exception. Retrying in {sleep_s:.1f}s (attempt {attempt+1}/{TY_OCR_RETRIES})")
                time.sleep(sleep_s)
                continue
            return []
    return []


def ocr_pdf_typhoon_pages(pdf_path: str, page_indices: List[int], markdown: bool = True, strip_md: bool = False) -> Dict[int, str]:
    """OCR selected pages using Typhoon API with batching to mitigate timeouts.

    If a batch fails (timeout / error), its pages return empty strings so upstream
    logic can fall back to Tesseract.
    """
    if not (TY_OCR_ENABLE and TY_OCR_API_KEY):
        return {i: '' for i in page_indices}
    out: Dict[int, str] = {i: '' for i in page_indices}
    if not page_indices:
        return out
    # Sort and batch pages to keep API requests small
    sorted_pages = sorted(page_indices)
    batch_size = max(1, TY_OCR_BATCH_SIZE)
    for start in range(0, len(sorted_pages), batch_size):
        batch = sorted_pages[start:start + batch_size]
        page_nums = [i + 1 for i in batch]  # 1-based
        texts = _api_call(pdf_path, pages=page_nums)
        # Fill output mapping
        for local_i, original_index in enumerate(batch):
            txt = texts[local_i] if local_i < len(texts) else ''
            if txt:
                if strip_md or (not markdown):
                    txt = _strip_markdown(txt)
            out[original_index] = txt
    return out


def ocr_pdf_typhoon_full(pdf_path: str, max_pages: int | None = None, strip_md: bool = False) -> str:
    """OCR full PDF with batching to reduce per-request latency and timeouts.

    If any batch fails, those pages yield empty strings allowing caller to
    decide further fallback.
    """
    if not (TY_OCR_ENABLE and TY_OCR_API_KEY):
        return ''
    pages: Optional[List[int]] = None
    if max_pages and max_pages > 0:
        pages = list(range(1, max_pages + 1))
    # If pages unspecified, we rely on API to process entire file, but we still
    # attempt batching by first probing page count (not available here). So if pages
    # is None, keep single call behaviour.
    if pages is None:
        texts = _api_call(pdf_path, pages=None)
        cleaned: List[str] = []
        for t in texts:
            if strip_md and t:
                t = _strip_markdown(t)
            cleaned.append(t)
        return '\n\n'.join(cleaned)
    # Batch the explicit pages list
    batch_size = max(1, TY_OCR_BATCH_SIZE)
    all_texts: List[str] = []
    for start in range(0, len(pages), batch_size):
        batch = pages[start:start + batch_size]
        texts = _api_call(pdf_path, pages=batch)
        for t in texts:
            if strip_md and t:
                t = _strip_markdown(t)
            all_texts.append(t)
        # If API returned fewer results (failure), pad to maintain ordering
        if len(texts) < len(batch):
            all_texts.extend([''] * (len(batch) - len(texts)))
    return '\n\n'.join(all_texts)
