"""Open Notebook-derived chunking for ingestion.

Adapted from:
- open-notebook/open_notebook/utils/chunking.py
- open-notebook/open_notebook/utils/token_utils.py
- open-notebook/open_notebook/utils/text_utils.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict, Iterable, List
import os
import re

try:
    from langchain_text_splitters import HTMLHeaderTextSplitter, MarkdownHeaderTextSplitter
except Exception:  # pragma: no cover
    HTMLHeaderTextSplitter = None  # type: ignore
    MarkdownHeaderTextSplitter = None  # type: ignore

from .utils import normalize_text, tokenize_thai_words


MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
THAI_SECTION_RE = re.compile(r"^(หมวด\s*\d+|ข้อ\s*\d+(?:\.\d+)?|บท\s*\d+|โครงสร้างหลักสูตร|เงื่อนไขการสำเร็จการศึกษา|ประกาศ.*|หลักสูตร.*)$")
HTML_TAG_RE = re.compile(r"<[^>]+>")
THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
ANCHOR_RE = re.compile(r"\b[A-Za-z]{2,6}\s*-?\s*\d{3}\b|\b\d+\.\d+\b|ข้อ\s*\d+(?:\.\d+)?|หมวด\s*\d+", re.IGNORECASE)

try:
    from pythainlp.tokenize import word_tokenize
except Exception:  # pragma: no cover
    word_tokenize = None  # type: ignore


@dataclass
class ChunkingConfig:
    corpus_id: str
    domain: str
    embedding_provider: str
    embedding_model: str
    chunk_size: int = 400
    chunk_overlap: int = 60
    min_tokens: int = 40
    max_tokens: int = 650
    char_fallback_size: int = 1200
    char_fallback_overlap: int = 180


def _tokenizer_engine() -> str:
    return (os.getenv('THAI_TOKENIZER_ENGINE', 'newmm') or 'newmm').strip().lower()


def contains_thai(text: str) -> bool:
    return bool(THAI_RE.search(text or ''))


def _protect_anchors(text: str) -> tuple[str, dict[str, str]]:
    mapping: dict[str, str] = {}
    def repl(match: re.Match[str]) -> str:
        key = f"__ANCHOR_{len(mapping)}__"
        mapping[key] = match.group(0)
        return f" {key} "
    return ANCHOR_RE.sub(repl, text or ''), mapping


def tokenize(text: str) -> List[str]:
    raw = (text or '').strip()
    if not raw:
        return []
    if contains_thai(raw) and word_tokenize is not None:
        protected, mapping = _protect_anchors(raw)
        try:
            tokens = word_tokenize(protected, engine=_tokenizer_engine(), keep_whitespace=False)
        except TypeError:
            tokens = word_tokenize(protected, engine=_tokenizer_engine())
        out: list[str] = []
        for token in tokens:
            value = mapping.get(str(token).strip(), str(token).strip())
            if value:
                out.append(value)
        return out
    return tokenize_thai_words(raw, engine='newmm') if contains_thai(raw) else [tok for tok in re.split(r"\s+", raw) if tok]


def token_count(text: str) -> int:
    raw = (text or '').strip()
    if not raw:
        return 0
    return len(tokenize(raw)) if contains_thai(raw) else max(1, int(len(raw.split()) * 1.3))


def split_by_tokens(text: str, max_tokens: int, overlap_tokens: int) -> List[str]:
    raw = (text or '').strip()
    tokens = tokenize(raw)
    if not tokens:
        return []
    if len(tokens) <= max_tokens:
        return [raw]
    step = max(1, max_tokens - max(0, overlap_tokens))
    out: list[str] = []
    for start in range(0, len(tokens), step):
        piece = tokens[start : start + max_tokens]
        if piece:
            out.append(' '.join(piece).strip())
        if start + max_tokens >= len(tokens):
            break
    return [piece for piece in out if piece]


def detect_content_type(file_path: str, text: str) -> str:
    suffix = Path(file_path or '').suffix.lower()
    if suffix in {'.md', '.markdown'}:
        return 'markdown'
    if suffix in {'.html', '.htm'}:
        return 'html'
    if suffix == '.pdf':
        return 'pdf_text'
    if suffix in {'.csv', '.xls', '.xlsx', '.tsv'}:
        return 'table_like'
    sample = (text or '')[:4000]
    if '<html' in sample.lower() or bool(HTML_TAG_RE.search(sample)):
        return 'html'
    if bool(MARKDOWN_HEADING_RE.search(sample)):
        return 'markdown'
    if '|' in sample or re.search(r'\s{2,}', sample):
        return 'table_like'
    return 'plain'


def _infer_domain(source_path: str, default_domain: str) -> str:
    parts = {part.lower() for part in Path(source_path or '').parts}
    for name in ('announcements', 'regulations', 'curriculum', 'test_domain'):
        if name in parts:
            return name
    if default_domain and default_domain not in {'other', 'unknown'}:
        return default_domain
    print(f"[WARN] domain not found in source path: {source_path}; using unknown")
    return 'unknown'


def _section_heading(line: str, content_type: str) -> str | None:
    if content_type == 'markdown':
        match = MARKDOWN_HEADING_RE.match(line)
        if match:
            return (match.group(2) or '').strip()
    if THAI_SECTION_RE.match(line):
        return line.strip()
    return None


def _split_sections(text: str, content_type: str) -> List[Dict[str, Any]]:
    if content_type == 'markdown' and MarkdownHeaderTextSplitter is not None:
        splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[('#', 'Header 1'), ('##', 'Header 2'), ('###', 'Header 3')], strip_headers=False)
        docs = splitter.split_text(text)
        cursor = 0
        out: list[dict[str, Any]] = []
        for doc in docs:
            body = str(getattr(doc, 'page_content', doc) or '').strip()
            if not body:
                continue
            metadata = getattr(doc, 'metadata', {}) or {}
            heading = str(metadata.get('Header 3') or metadata.get('Header 2') or metadata.get('Header 1') or '').strip()
            out.append({'section_heading': heading, 'text': body, 'char_start': cursor, 'char_end': cursor + len(body)})
            cursor += len(body) + 2
        if out:
            return out
    if content_type == 'html' and HTMLHeaderTextSplitter is not None:
        splitter = HTMLHeaderTextSplitter(headers_to_split_on=[('h1', 'Header 1'), ('h2', 'Header 2'), ('h3', 'Header 3')])
        docs = splitter.split_text(text)
        cursor = 0
        out: list[dict[str, Any]] = []
        for doc in docs:
            body = str(getattr(doc, 'page_content', doc) or '').strip()
            if not body:
                continue
            metadata = getattr(doc, 'metadata', {}) or {}
            heading = str(metadata.get('Header 3') or metadata.get('Header 2') or metadata.get('Header 1') or '').strip()
            out.append({'section_heading': heading, 'text': body, 'char_start': cursor, 'char_end': cursor + len(body)})
            cursor += len(body) + 2
        if out:
            return out

    lines = text.splitlines()
    sections: list[dict[str, Any]] = []
    current_heading = ''
    current_lines: list[str] = []
    char_start = 0
    cursor = 0
    for line in lines:
        heading = _section_heading(line, content_type)
        if heading and current_lines:
            body = '\n'.join(current_lines).strip()
            if body:
                sections.append({'section_heading': current_heading, 'text': body, 'char_start': char_start, 'char_end': char_start + len(body)})
            current_lines = [line]
            current_heading = heading
            char_start = cursor
        else:
            if not current_lines:
                char_start = cursor
            current_lines.append(line)
            if heading and not current_heading:
                current_heading = heading
        cursor += len(line) + 1
    body = '\n'.join(current_lines).strip()
    if body:
        sections.append({'section_heading': current_heading, 'text': body, 'char_start': char_start, 'char_end': char_start + len(body)})
    return sections or [{'section_heading': '', 'text': text, 'char_start': 0, 'char_end': len(text)}]


def _secondary_split(section: Dict[str, Any], cfg: ChunkingConfig) -> List[Dict[str, Any]]:
    text = str(section.get('text') or '').strip()
    if not text:
        return []
    if token_count(text) <= cfg.max_tokens:
        return [section]
    parts = split_by_tokens(text, max_tokens=cfg.chunk_size, overlap_tokens=cfg.chunk_overlap)
    out: list[dict[str, Any]] = []
    local_start = int(section.get('char_start') or 0)
    offset = 0
    for part in parts:
        out.append({'section_heading': section.get('section_heading') or '', 'text': part, 'char_start': local_start + offset, 'char_end': local_start + offset + len(part)})
        offset += max(1, len(part) - cfg.char_fallback_overlap)
    return out


def _infer_title(file_name: str, text: str) -> str:
    for line in (text or '').splitlines()[:10]:
        stripped = line.strip()
        if len(stripped) >= 6:
            return stripped[:180]
    return Path(file_name).stem


def _content_hash(text: str) -> str:
    return sha1((text or '').encode('utf-8', 'ignore')).hexdigest()


def build_chunks_from_records(records: Iterable[Dict[str, Any]], source_path: str, cfg: ChunkingConfig) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    pages: list[tuple[int, str]] = []
    for record in records:
        text = '\n'.join([str(p or '').strip() for p in (record.get('paragraphs') or [record.get('text', '')]) if str(p or '').strip()]).strip()
        if not text:
            continue
        try:
            page_no = int(record.get('page_no') or 0)
        except Exception:
            page_no = 0
        pages.append((page_no, text))

    raw_text = '\n\n'.join(text for _, text in pages).strip()
    normalized = normalize_text(raw_text)
    content_type = detect_content_type(source_path, normalized)
    source_name = Path(source_path).name
    domain = _infer_domain(source_path, cfg.domain)
    source_id = sha1(f"{cfg.corpus_id}|{domain}|{source_path}".encode('utf-8', 'ignore')).hexdigest()[:24]
    title = _infer_title(source_name, normalized)
    indexed_at = datetime.now(timezone.utc).isoformat()
    sections = _split_sections(normalized, content_type)
    chunk_rows: list[dict[str, Any]] = []
    oversized_chunks = 0
    for section in sections:
        parts = _secondary_split(section, cfg)
        if len(parts) > 1:
            oversized_chunks += 1
        chunk_rows.extend(parts)

    chunks: list[dict[str, Any]] = []
    for idx, piece in enumerate(chunk_rows):
        text = str(piece.get('text') or '').strip()
        if not text:
            continue
        content_hash = _content_hash(text)
        stable_chunk_id = sha1(f"{cfg.corpus_id}|{domain}|{source_path}|{content_hash}|{idx}".encode('utf-8', 'ignore')).hexdigest()
        page = 0
        for candidate_page, page_text in pages:
            if text[:80] and text[:80] in page_text:
                page = candidate_page
                break
        chunks.append({
            'chunk_id': stable_chunk_id,
            'stable_chunk_id': stable_chunk_id,
            'doc_id': stable_chunk_id,
            'corpus_id': cfg.corpus_id,
            'source_id': source_id,
            'domain': domain,
            'source_name': source_name,
            'source': source_name,
            'source_path': source_path,
            'path': source_path,
            'file_name': source_name,
            'file_ext': Path(source_path).suffix.lower(),
            'document_type': content_type,
            'title': title,
            'doc_title': title,
            'indexed_at': indexed_at,
            'content_hash': content_hash,
            'section_heading': piece.get('section_heading') or '',
            'page': page,
            'page_start': page,
            'page_end': page,
            'chunk_index': idx,
            'char_start': int(piece.get('char_start') or 0),
            'char_end': int(piece.get('char_end') or 0),
            'token_count': token_count(text),
            'tokens_est': token_count(text),
            'char_count': len(text),
            'content_type': content_type,
            'embedding_provider': cfg.embedding_provider,
            'embedding_model': cfg.embedding_model,
            'text': text,
            'status': 'ok',
        })

    report = {
        'source_name': source_name,
        'domain': domain,
        'content_type': content_type,
        'raw_text_chars': len(raw_text),
        'chunk_count': len(chunks),
        'avg_chunk_chars': round(sum(len(chunk['text']) for chunk in chunks) / len(chunks), 2) if chunks else 0,
        'avg_chunk_tokens': round(sum(int(chunk['token_count']) for chunk in chunks) / len(chunks), 2) if chunks else 0,
        'oversized_chunks': oversized_chunks,
    }
    return chunks, report
