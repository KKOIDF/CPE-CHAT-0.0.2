from __future__ import annotations

from typing import Any, Dict
import os

from ..llm import generate_text
from .context_builder import build_source_labeled_context
from .prompting import build_answer_messages, build_prompt, finalize_answer
from .retriever import retrieve


def retrieve_context(question: str, requested_domain: str | None = None, strict_domain: bool = False) -> Dict[str, Any]:
    retrieval = retrieve(
        question,
        requested_domain=requested_domain,
        strict_domain=strict_domain,
        final_limit=max(1, int(os.getenv("RAG_FINAL_CONTEXT_K", "8") or "8")),
    )
    context = build_source_labeled_context(
        question=question,
        chunks=retrieval["selected_chunks"],
        token_budget=max(400, int(os.getenv("RAG_CONTEXT_MAX_TOKENS", "6000") or "6000")),
    )
    retrieval.update(context)
    print(
        f"[rag] engine=open_notebook_derived retrieval_mode=global_hybrid raw_vector_candidates={len(retrieval.get('vector_candidates') or [])} selected_chunks={len(retrieval.get('selected_chunks') or [])} context_chars={len(str(context.get('formatted_context') or ''))} sources_used={context.get('sources_used') or []}"
    )
    return retrieval


def build_forced_context_messages(question: str, formatted_context: str, citation_map: dict[int, str] | None = None) -> list[dict[str, str]]:
    return build_answer_messages(question, formatted_context, cites=citation_map)


def answer_with_context(question: str, formatted_context: str, citation_map: dict[int, str] | None = None) -> str:
    raw = str(generate_text("(onb_rag_answer)", messages=build_forced_context_messages(question, formatted_context, citation_map), task="answer") or "").strip()
    return finalize_answer(raw, citation_map=citation_map)


def build_answer_payload(question: str, requested_domain: str | None = None, strict_domain: bool = False) -> Dict[str, Any]:
    payload = retrieve_context(question, requested_domain=requested_domain, strict_domain=strict_domain)
    payload["prompt"] = build_prompt(question, str(payload.get("formatted_context") or ""), cites=payload.get("citation_map") or {})
    return payload
