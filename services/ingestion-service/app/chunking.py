import math, time, re
from pathlib import Path
from typing import List, Dict

from .config import CHUNK_MIN_TOKENS, CHUNK_MAX_TOKENS, CHUNK_OVERLAP_RATIO, CHAR_PER_TOKEN
from .utils import split_paragraphs_smart

_HEADING_PATTS = [r"^บท\s*ที่\s*\d+", r"^หมวด\s*ที่?\s*\d+", r"^ภาคผนวก", r"^บท\s*\d+", r"^(?:\d+\.)+\s+", r"^\d+\)\s+", r"^[A-Za-zก-๙]+\s*:\s+"]
_HEADING_RE = re.compile("|".join(_HEADING_PATTS))
_BULLET_PATTS = [r"^[\-\•\–]\s+", r"^[ก-ฮ]\)\s+", r"^\([ก-ฮ]\)\s+", r"^\([0-9]+\)\s+"]
_BULLET_RE = re.compile("|".join(_BULLET_PATTS))


def est_tokens(text: str) -> int:
    return max(1, int(math.ceil(len(text) / CHAR_PER_TOKEN)))


def is_heading(text: str) -> bool:
    return bool(_HEADING_RE.search(text.strip()))


def is_bullet(text: str) -> bool:
    return bool(_BULLET_RE.search(text.strip()))


def group_bullets(paragraphs: List[Dict]) -> List[Dict]:
    grouped = []
    buf = []
    for p in paragraphs:
        if is_bullet(p['text']):
            buf.append(p)
        else:
            if buf:
                merged = {**buf[0]}
                merged['text'] = '\n'.join(x['text'] for x in buf)
                grouped.append(merged)
                buf = []
            grouped.append(p)
    if buf:
        merged = {**buf[0]}
        merged['text'] = '\n'.join(x['text'] for x in buf)
        grouped.append(merged)
    return grouped


def paragraphs_from_records(records: List[Dict]) -> List[Dict]:
    out = []
    for r in records:
        page_raw = r.get('page_no')
        try:
            page = int(page_raw) if page_raw is not None else 0
        except (ValueError, TypeError):
            page = 0
        paras = r.get('paragraphs') or [r.get('text', '')]
        for t in paras:
            if not t or not t.strip():
                continue
            out.append({'page': page, 'text': t.strip(), 'is_heading': is_heading(t)})
    return group_bullets(out)


def normalize_doc_name(src_path: str) -> str:
    name = Path(src_path).stem.lower()
    name = re.sub(r"[^0-9A-Za-z\u0E00-\u0E7F]+", "_", name).strip("_")
    if not name:
        name = 'document'
    if not name.endswith('.txt'):
        name = f'{name}.txt'
    return name


def make_chunks(paragraphs: List[Dict], source_path: str) -> List[Dict]:
    chunks = []
    cur_texts: List[str] = []
    cur_pages: List[int] = []
    cur_tokens = 0

    def add_paragraph(p):
        nonlocal cur_tokens
        cur_texts.append(p['text'])
        cur_pages.append(p['page'])
        cur_tokens += est_tokens(p['text'])

    def finalize_chunk(overlap_tail: str | None = None):
        nonlocal cur_texts, cur_pages, cur_tokens
        if not cur_texts:
            return
        text = (overlap_tail + '\n' if overlap_tail else '') + '\n\n'.join(cur_texts).strip()
        valid_pages = []
        for pg in cur_pages:
            try:
                if pg is not None:
                    valid_pages.append(int(pg))
            except (ValueError, TypeError):
                pass
        page_start = min(valid_pages) if valid_pages else 0
        page_end = max(valid_pages) if valid_pages else 0
        chunks.append({
            'source': normalize_doc_name(source_path),
            'path': str(Path(source_path).resolve()),
            'page': page_start,
            'page_start': page_start,
            'page_end': page_end,
            'owner': 'owner:unknown',
            'sensitivity': 'internal',
            'updated_at': int(time.time()),
            'text': text,
            'tokens_est': est_tokens(text),
        })
        cur_texts = []
        cur_pages = []
        cur_tokens = 0

    for p in paragraphs:
        if p['is_heading'] and cur_texts:
            joined = '\n\n'.join(cur_texts)
            overlap_chars = int(CHUNK_OVERLAP_RATIO * len(joined))
            tail = joined[-overlap_chars:] if overlap_chars > 0 else None
            finalize_chunk(tail)
        if cur_tokens + est_tokens(p['text']) <= CHUNK_MAX_TOKENS:
            add_paragraph(p)
        else:
            joined = '\n\n'.join(cur_texts)
            overlap_chars = int(CHUNK_OVERLAP_RATIO * len(joined))
            tail = joined[-overlap_chars:] if overlap_chars > 0 else None
            finalize_chunk(tail)
            if est_tokens(p['text']) > CHUNK_MAX_TOKENS:
                # split long paragraph by simple sentence heuristic
                sents = re.split(r'(?<=[\.!?…\u0E2F\u0E5B\u0E46])\s+', p['text'])
                buf = []
                for s in sents:
                    tentative = '\n'.join(buf + [s])
                    if est_tokens(tentative) > CHUNK_MAX_TOKENS:
                        finalize_chunk()
                        buf = [s]
                    else:
                        buf.append(s)
                if buf:
                    final = ' '.join(buf)
                    cur_texts = [final]
                    cur_pages = [p['page']]
                    cur_tokens = est_tokens(final)
            else:
                cur_texts = [p['text']]
                cur_pages = [p['page']]
                cur_tokens = est_tokens(p['text'])

    finalize_chunk()
    return chunks
