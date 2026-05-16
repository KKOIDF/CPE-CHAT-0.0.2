"""Open Notebook-derived chunking helpers for shared tests and future ingestion alignment.

Adapted from:
- open-notebook/open_notebook/utils/chunking.py
- open-notebook/open_notebook/utils/token_utils.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import re

try:
    from langchain_text_splitters import HTMLHeaderTextSplitter, MarkdownHeaderTextSplitter
except Exception:  # pragma: no cover
    HTMLHeaderTextSplitter = None  # type: ignore
    MarkdownHeaderTextSplitter = None  # type: ignore

from .document_processing import normalize_text
from .tokenizer import count_tokens, split_by_tokens


MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
THAI_SECTION_RE = re.compile(r"^(หมวด\s*\d+|ข้อ\s*\d+(?:\.\d+)?|บท\s*\d+|โครงสร้างหลักสูตร|เงื่อนไขการสำเร็จการศึกษา|ประกาศ.*|หลักสูตร.*)$")
HTML_TAG_RE = re.compile(r"<[^>]+>")


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


def detect_content_type(file_path: str, text: str) -> str:
    suffix = Path(file_path or "").suffix.lower()
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix in {".html", ".htm"}:
        return "html"
    if suffix == ".pdf":
        return "pdf_text"
    if suffix in {".csv", ".xls", ".xlsx", ".tsv"}:
        return "table_like"
    sample = (text or "")[:4000]
    if "<html" in sample.lower() or bool(HTML_TAG_RE.search(sample)):
        return "html"
    if bool(MARKDOWN_HEADING_RE.search(sample)):
        return "markdown"
    if "|" in sample or re.search(r"\s{2,}", sample):
        return "table_like"
    return "plain"


def _section_heading(line: str, content_type: str) -> str | None:
    if content_type == "markdown":
        match = MARKDOWN_HEADING_RE.match(line)
        if match:
            return (match.group(2) or "").strip()
    if THAI_SECTION_RE.match(line):
        return line.strip()
    return None


def _markdown_split(text: str) -> List[Dict[str, Any]]:
    if MarkdownHeaderTextSplitter is None:
        return _plain_split(text, 'markdown')
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")], strip_headers=False)
    docs = splitter.split_text(text)
    chunks: list[dict[str, Any]] = []
    cursor = 0
    for doc in docs:
        body = str(getattr(doc, 'page_content', doc) or '').strip()
        if not body:
            continue
        metadata = getattr(doc, 'metadata', {}) or {}
        heading = str(metadata.get('Header 3') or metadata.get('Header 2') or metadata.get('Header 1') or '').strip()
        chunks.append({'section_heading': heading, 'text': body, 'char_start': cursor, 'char_end': cursor + len(body)})
        cursor += len(body) + 2
    return chunks


def _html_split(text: str) -> List[Dict[str, Any]]:
    if HTMLHeaderTextSplitter is None:
        return _plain_split(text, 'html')
    splitter = HTMLHeaderTextSplitter(headers_to_split_on=[('h1', 'Header 1'), ('h2', 'Header 2'), ('h3', 'Header 3')])
    docs = splitter.split_text(text)
    chunks: list[dict[str, Any]] = []
    cursor = 0
    for doc in docs:
        body = str(getattr(doc, 'page_content', doc) or '').strip()
        if not body:
            continue
        metadata = getattr(doc, 'metadata', {}) or {}
        heading = str(metadata.get('Header 3') or metadata.get('Header 2') or metadata.get('Header 1') or '').strip()
        chunks.append({'section_heading': heading, 'text': body, 'char_start': cursor, 'char_end': cursor + len(body)})
        cursor += len(body) + 2
    return chunks


def _plain_split(text: str, content_type: str) -> List[Dict[str, Any]]:
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
    if count_tokens(text) <= cfg.max_tokens:
        return [section]
    parts = split_by_tokens(text, max_tokens=cfg.chunk_size, overlap_tokens=cfg.chunk_overlap)
    out: list[dict[str, Any]] = []
    local_start = int(section.get('char_start') or 0)
    offset = 0
    for part in parts:
        out.append({'section_heading': section.get('section_heading') or '', 'text': part, 'char_start': local_start + offset, 'char_end': local_start + offset + len(part)})
        offset += max(1, len(part) - cfg.char_fallback_overlap)
    return out


def split_document(text: str, file_path: str, cfg: ChunkingConfig) -> List[Dict[str, Any]]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    content_type = detect_content_type(file_path, normalized)
    if content_type == 'markdown':
        sections = _markdown_split(normalized)
    elif content_type == 'html':
        sections = _html_split(normalized)
    else:
        sections = _plain_split(normalized, content_type)
    out: list[dict[str, Any]] = []
    for section in sections:
        out.extend(_secondary_split(section, cfg))
    return [piece for piece in out if str(piece.get('text') or '').strip()]
