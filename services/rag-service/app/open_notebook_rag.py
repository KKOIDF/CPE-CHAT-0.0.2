"""Compatibility facade for the Open Notebook-derived RAG engine.

Adapted to preserve imports used by the existing CPE-CHAT API/orchestration.
Core behavior now lives in app/onb_rag/.
"""

from __future__ import annotations

from .onb_rag.context_builder import build_source_labeled_context
from .onb_rag.retriever import (
    enforce_source_diversity,
    generate_query_variants,
    infer_candidate_domains,
    normalize_question_text,
    rerank_results,
    rrf_merge,
)


def token_count(text: str) -> int:
    from .onb_rag.tokenizer import count_tokens

    return count_tokens(text)


def not_found_payload(question: str) -> dict[str, object]:
    return {
        "question": question,
        "formatted_context": "",
        "answer": "ไม่พบข้อมูลนี้ในเอกสารที่ค้นได้",
        "sources_used": [],
        "chunks_used": [],
        "context_token_count": 0,
        "warnings": ["no_context"],
    }
