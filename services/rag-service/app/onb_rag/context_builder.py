from __future__ import annotations

import os
from typing import Any, Dict, Sequence

from .tokenizer import count_tokens


def _source_ref_label(chunk: Dict[str, Any]) -> str:
    source_name = str(chunk.get("source_name") or chunk.get("source") or chunk.get("file_name") or chunk.get("source_id") or "unknown").strip()
    page = chunk.get("page") or chunk.get("page_start")
    section = str(chunk.get("section_heading") or "").strip()
    if page not in (None, "", 0, "0"):
        return f"{source_name}, หน้า {page}"
    if section:
        return f"{source_name}, section {section}"
    return source_name


def build_source_labeled_context(
    question: str,
    chunks: Sequence[Dict[str, Any]],
    token_budget: int = 6000,
) -> Dict[str, Any]:
    max_chunks = max(1, int(os.getenv("RAG_CONTEXT_MAX_CHUNKS", "8") or "8"))
    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_signatures: set[tuple[str, str, str]] = set()
    blocks: list[str] = []
    sources_used: list[str] = []
    warnings: list[str] = []
    used = 0
    citation_map: dict[int, str] = {}
    source_number_by_key: dict[str, int] = {}

    for chunk in chunks[:max_chunks]:
        row = dict(chunk)
        text = str(row.get("text") or "").strip()
        chunk_id = str(row.get("stable_chunk_id") or row.get("doc_id") or row.get("chunk_id") or "").strip()
        if not text or not chunk_id or chunk_id in seen_ids:
            continue
        source_name = str(row.get("source_name") or row.get("source") or row.get("file_name") or "unknown")
        domain = str(row.get("domain") or "unknown")
        section = str(row.get("section_heading") or "").strip()
        page = row.get("page") or row.get("page_start")
        dedupe_sig = (source_name.strip().lower(), section.strip().lower(), text[:220].strip().lower())
        if dedupe_sig in seen_signatures:
            continue
        seen_ids.add(chunk_id)
        seen_signatures.add(dedupe_sig)

        source_key = str(row.get("source_id") or source_name or chunk_id)
        citation_number = source_number_by_key.get(source_key)
        if citation_number is None:
            citation_number = len(source_number_by_key) + 1
            source_number_by_key[source_key] = citation_number
            citation_map[citation_number] = _source_ref_label(row)

        header = [
            f"[{citation_number}]",
            f"source_id: {str(row.get('source_id') or source_key)}",
            f"source_name: {source_name}",
            f"domain: {domain}",
        ]
        if page not in (None, "", 0, "0"):
            header.append(f"page: {page}")
        if section:
            header.append(f"section: {section}")
        header.append("content:")
        block = "\n".join([*header, text])
        block_tokens = count_tokens(block)
        if used + block_tokens > token_budget:
            remaining = max(40, token_budget - used)
            approx_chars = max(160, remaining * 4)
            clipped = text[:approx_chars].rstrip()
            if clipped and clipped != text:
                block = "\n".join([*header, clipped + " ..."])
                block_tokens = count_tokens(block)
        if used + block_tokens > token_budget:
            warnings.append("context_truncated")
            break

        row["citation_number"] = citation_number
        used += block_tokens
        selected.append(row)
        blocks.append(block)
        if source_name not in sources_used:
            sources_used.append(source_name)

    return {
        "question": question,
        "formatted_context": "\n\n".join(blocks).strip(),
        "sources_used": sources_used,
        "chunks_used": selected,
        "context_token_count": used,
        "warnings": warnings,
        "citation_map": citation_map,
    }
