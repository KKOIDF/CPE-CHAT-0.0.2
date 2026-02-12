import math, time, re
from pathlib import Path
from typing import List, Dict, Optional

from .config import CHUNK_MIN_TOKENS, CHUNK_MAX_TOKENS, CHUNK_OVERLAP_RATIO, CHAR_PER_TOKEN
from .utils import split_paragraphs_smart, segment_sentences_thai

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
            out.append({'page': page, 'text': t.strip(), 'is_heading': is_heading(t), 'src': r.get('source')})
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
    chunks: List[Dict] = []
    resolved_source = normalize_doc_name(source_path)
    resolved_path = str(Path(source_path).resolve())

    cur_texts: List[str] = []
    cur_pages: List[int] = []
    cur_tokens = 0
    overlap_prefix: Optional[str] = None

    # Keep a short heading context to prefix chunks created by max-length splits.
    active_headings: List[str] = []

    def _valid_pages(pages: List[int]) -> List[int]:
        out: List[int] = []
        for pg in pages:
            try:
                if pg is not None:
                    out.append(int(pg))
            except (ValueError, TypeError):
                pass
        return out

    def _sent_tail_for_overlap(text: str, want_tokens: int) -> Optional[str]:
        if not text or want_tokens <= 0:
            return None
        flat = " ".join((text or "").split())
        if not flat:
            return None
        sents = segment_sentences_thai(flat) or [flat]
        sents = [s.strip() for s in sents if s and s.strip()]
        if not sents:
            return None
        buf: List[str] = []
        tok = 0
        for s in reversed(sents):
            buf.insert(0, s)
            tok = est_tokens(" ".join(buf))
            if tok >= want_tokens:
                break
        tail = " ".join(buf).strip()
        # Guard: don't let overlap become the whole chunk.
        if est_tokens(tail) >= max(1, int(0.8 * est_tokens(flat))):
            return None
        return tail

    def _maybe_add_section_prefix():
        nonlocal cur_tokens
        if cur_texts:
            return
        prefix_lines: List[str] = []
        if overlap_prefix:
            prefix_lines.append(overlap_prefix.strip())
        # Only prefix headings when the next chunk isn't starting with a heading paragraph.
        if active_headings:
            prefix_lines.extend(active_headings[-2:])
        if not prefix_lines:
            return
        prefix = "\n".join([ln for ln in prefix_lines if ln and ln.strip()]).strip()
        if prefix:
            cur_texts.append(prefix)
            cur_tokens += est_tokens(prefix)

    def _add_paragraph_text(text: str, page: int):
        nonlocal cur_tokens
        if not text or not text.strip():
            return
        _maybe_add_section_prefix()
        cur_texts.append(text.strip())
        cur_pages.append(page)
        cur_tokens += est_tokens(text)

    def _finalize_current(allow_overlap: bool) -> None:
        nonlocal cur_texts, cur_pages, cur_tokens, overlap_prefix
        if not cur_texts:
            overlap_prefix = None
            return
        text = "\n\n".join(cur_texts).strip()
        if not text:
            cur_texts = []
            cur_pages = []
            cur_tokens = 0
            overlap_prefix = None
            return
        pages = _valid_pages(cur_pages)
        page_start = min(pages) if pages else 0
        page_end = max(pages) if pages else 0
        chunks.append({
            'source': resolved_source,
            'path': resolved_path,
            'page': page_start,
            'page_start': page_start,
            'page_end': page_end,
            'owner': 'owner:unknown',
            'sensitivity': 'internal',
            'updated_at': int(time.time()),
            'text': text,
            'tokens_est': est_tokens(text),
        })

        if allow_overlap and CHUNK_OVERLAP_RATIO > 0:
            want = int(max(1, round(CHUNK_OVERLAP_RATIO * est_tokens(text))))
            overlap_prefix = _sent_tail_for_overlap(text, want)
        else:
            overlap_prefix = None

        cur_texts = []
        cur_pages = []
        cur_tokens = 0

    def _emit_long_text_as_chunks(text: str, page: int) -> None:
        """Split a single long paragraph into chunks using sentence packing + overlap."""
        nonlocal overlap_prefix
        sents = segment_sentences_thai(text) or [text]
        sents = [s.strip() for s in sents if s and s.strip()]
        if not sents:
            return
        buf: List[str] = []
        for s in sents:
            tentative = (" ".join(buf + [s])).strip()
            if buf and est_tokens(tentative) > CHUNK_MAX_TOKENS:
                part = " ".join(buf).strip()
                if part:
                    # Write as its own chunk
                    local_texts: List[str] = []
                    if overlap_prefix:
                        local_texts.append(overlap_prefix)
                    if active_headings:
                        local_texts.extend(active_headings[-2:])
                    local_texts.append(part)
                    final = "\n".join([x for x in local_texts if x and x.strip()]).strip()
                    chunks.append({
                        'source': resolved_source,
                        'path': resolved_path,
                        'page': page,
                        'page_start': page,
                        'page_end': page,
                        'owner': 'owner:unknown',
                        'sensitivity': 'internal',
                        'updated_at': int(time.time()),
                        'text': final,
                        'tokens_est': est_tokens(final),
                    })
                    want = int(max(1, round(CHUNK_OVERLAP_RATIO * est_tokens(final))))
                    overlap_prefix = _sent_tail_for_overlap(final, want)
                buf = [s]
            else:
                buf.append(s)

        if buf:
            part = " ".join(buf).strip()
            if part:
                local_texts = []
                if overlap_prefix:
                    local_texts.append(overlap_prefix)
                if active_headings:
                    local_texts.extend(active_headings[-2:])
                local_texts.append(part)
                final = "\n".join([x for x in local_texts if x and x.strip()]).strip()
                chunks.append({
                    'source': resolved_source,
                    'path': resolved_path,
                    'page': page,
                    'page_start': page,
                    'page_end': page,
                    'owner': 'owner:unknown',
                    'sensitivity': 'internal',
                    'updated_at': int(time.time()),
                    'text': final,
                    'tokens_est': est_tokens(final),
                })
                want = int(max(1, round(CHUNK_OVERLAP_RATIO * est_tokens(final))))
                overlap_prefix = _sent_tail_for_overlap(final, want)

    for p in paragraphs:
        page_raw = p.get('page', 0)
        try:
            page = int(page_raw) if page_raw is not None else 0
        except (ValueError, TypeError):
            page = 0
        text = (p.get('text') or '').strip()
        if not text:
            continue

        # Heading handling: treat as a strong boundary *only* if we already have a decent chunk.
        if p.get('is_heading'):
            # Update heading context.
            active_headings.append(text)
            active_headings = active_headings[-3:]

            if cur_texts and cur_tokens >= CHUNK_MIN_TOKENS:
                # New section: do not carry overlap across headings.
                _finalize_current(allow_overlap=False)
                overlap_prefix = None
            # Always include the heading in the next content chunk.
            _add_paragraph_text(text, page)
            continue

        p_tokens = est_tokens(text)

        # Very long paragraph: flush current then emit sentence-packed chunks.
        if p_tokens > CHUNK_MAX_TOKENS:
            if cur_texts:
                _finalize_current(allow_overlap=True)
            _emit_long_text_as_chunks(text, page)
            continue

        # Need to start a new chunk due to max size.
        # Always respect CHUNK_MAX_TOKENS; if the current chunk is still small,
        # finalize without overlap rather than exceeding the max budget.
        if cur_texts and (cur_tokens + p_tokens > CHUNK_MAX_TOKENS):
            _finalize_current(allow_overlap=(cur_tokens >= CHUNK_MIN_TOKENS))

        _add_paragraph_text(text, page)

    # Final chunk: no need to compute overlap.
    _finalize_current(allow_overlap=False)
    return chunks
