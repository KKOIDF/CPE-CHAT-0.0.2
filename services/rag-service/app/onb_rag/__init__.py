"""Open Notebook-derived RAG engine for CPE-CHAT.

Core behavior in this package is adapted from:
- open-notebook/open_notebook/utils/chunking.py
- open-notebook/open_notebook/utils/context_builder.py
- open-notebook/open_notebook/utils/token_utils.py
- open-notebook/open_notebook/utils/text_utils.py
- open-notebook/prompts/source_chat/system.jinja
"""

from .context_builder import build_source_labeled_context
from .engine import answer_with_context, build_forced_context_messages, retrieve_context
from .prompting import build_prompt
from .retriever import (
    enforce_source_diversity,
    generate_query_variants,
    infer_candidate_domains,
    normalize_question_text,
    rerank_results,
    rrf_merge,
)

__all__ = [
    "answer_with_context",
    "build_forced_context_messages",
    "build_prompt",
    "build_source_labeled_context",
    "enforce_source_diversity",
    "generate_query_variants",
    "infer_candidate_domains",
    "normalize_question_text",
    "rerank_results",
    "retrieve_context",
    "rrf_merge",
]
