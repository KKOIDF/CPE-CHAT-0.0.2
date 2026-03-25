"""Backward-compatible exports for legacy imports.

Primary implementations now live in focused modules:
- normalization.py
- routing.py
- rerank.py
- context_packing.py
- prompting.py
- retrieval.py
- orchestration.py
"""

from .normalization import (
    CHAR_PER_TOKEN,
    build_retrieval_queries,
    extract_lexical_anchors,
    normalize_query_for_keyword,
    normalize_query_for_retrieval,
    normalize_question,
    search_query_from_question,
)
from .routing import (
    _filter_chunks_by_reference,
    _infer_domain_from_reference,
    _reference_candidates,
    decompose_question,
    fallback_domains_for_domain,
    fallback_min_results,
    infer_domain,
    infer_domain_bias,
    is_multi_doc_question,
    classify_intent,
)
from .rerank import (
    _normalize_source_key,
    apply_domain_prior,
    apply_overbroad_source_penalty,
    diversify_by_source,
    ensure_min_sources,
    fuse_rrf_lists,
    fuse_semantic_keyword,
    majority_domain_rescue,
    promote_exact_anchor_hits,
    select_chunks_from_top_documents,
)
from .context_packing import est_tokens, pack_context, pack_context_grouped
from .prompting import build_prompt
from .retrieval import (
    hybrid_retrieve,
    retrieve_all_domains,
    retrieve_by_domain,
    retrieve_multi_document,
)
from .curriculum_deterministic import structured_curriculum_answer
from .orchestration import rag_query, rag_query_domain


__all__ = [
    'CHAR_PER_TOKEN',
    'build_retrieval_queries',
    'extract_lexical_anchors',
    'normalize_query_for_keyword',
    'normalize_query_for_retrieval',
    'normalize_question',
    'search_query_from_question',
    '_filter_chunks_by_reference',
    '_infer_domain_from_reference',
    '_reference_candidates',
    'decompose_question',
    'fallback_domains_for_domain',
    'fallback_min_results',
    'infer_domain',
    'infer_domain_bias',
    'is_multi_doc_question',
    'classify_intent',
    '_normalize_source_key',
    'apply_domain_prior',
    'apply_overbroad_source_penalty',
    'diversify_by_source',
    'ensure_min_sources',
    'fuse_rrf_lists',
    'fuse_semantic_keyword',
    'majority_domain_rescue',
    'promote_exact_anchor_hits',
    'select_chunks_from_top_documents',
    'est_tokens',
    'pack_context',
    'pack_context_grouped',
    'build_prompt',
    'hybrid_retrieve',
    'retrieve_all_domains',
    'retrieve_by_domain',
    'retrieve_multi_document',
    'structured_curriculum_answer',
    'rag_query',
    'rag_query_domain',
]
