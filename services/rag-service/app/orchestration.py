from __future__ import annotations

from typing import Dict, List
import os
import re

from .perf import add_metric
from .normalization import normalize_question, search_query_from_question
from .routing import (
    _filter_chunks_by_reference,
    _infer_domain_from_reference,
    _reference_candidates,
    decompose_question,
    fallback_domains_for_domain,
    fallback_min_results,
    infer_domain,
    is_multi_doc_question,
)
from .context_packing import est_tokens, pack_context, pack_context_grouped
from .prompting import build_prompt

from .retrieval import (
    retrieve_all_domains as _retrieve_all_domains,
    retrieve_by_domain as _retrieve_by_domain,
    retrieve_multi_document as _retrieve_multi_document,
)
from .curriculum_deterministic import structured_curriculum_answer
from .rerank import _normalize_source_key


_MULTI_DOC_MODE = (os.getenv('RAG_MULTI_DOC_MODE', 'auto') or 'auto').strip().lower()
_SEARCH_ALL_DOMAINS = (os.getenv('RAG_SEARCH_ALL_DOMAINS', '1') or '1').strip().lower() in (
    '1', 'true', 'yes', 'on'
)


def rag_query(question: str) -> Dict:
    q_display = normalize_question(question)
    q_search = search_query_from_question(question)
    ref_allow = _reference_candidates(question)
    strict_ref_hints = (os.getenv('STRICT_REFERENCE_HINTS', '1') or '1').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )
    has_ref = bool(ref_allow) and strict_ref_hints

    multi_doc_triggered = is_multi_doc_question(q_display)
    multi_doc_used = False
    multi_doc_reason: str | None = None
    multi_doc_subqs: List[str] = []

    if 'ลาพัก' in q_display:
        add_metric('inferred_domain', 'multi:announcements+regulations')
        retrieved = _retrieve_all_domains(q_search, domains=['announcements', 'regulations'])
    else:
        multi_doc_on = False
        if _MULTI_DOC_MODE in ('1', 'true', 'yes', 'on'):
            multi_doc_on = True
        elif _MULTI_DOC_MODE == 'auto':
            multi_doc_on = multi_doc_triggered

        if multi_doc_on:
            add_metric('retrieval_multi_doc_mode', 1)
            multi_doc_used = True
            multi_doc_reason = 'forced' if _MULTI_DOC_MODE in ('1', 'true', 'yes', 'on') else 'auto'
            multi_doc_subqs = decompose_question(question, max_parts=3)
            retrieved = _retrieve_multi_document(question)
        else:
            dom = infer_domain(q_display) or _infer_domain_from_reference(question)
            add_metric('inferred_domain', dom or 'auto')
            if dom and not _SEARCH_ALL_DOMAINS:
                retrieved = _retrieve_by_domain(question, domain=dom)
                if (not has_ref) and len(retrieved) < fallback_min_results():
                    add_metric('retrieval_domain_fallback_used', 1)
                    retrieved = _retrieve_all_domains(q_search, domains=fallback_domains_for_domain(dom))
            else:
                add_metric('retrieval_all_domains_forced', 1)
                retrieved = _retrieve_all_domains(question)

    retrieved = _filter_chunks_by_reference(retrieved, question, strict=has_ref)
    if _MULTI_DOC_MODE == 'auto' and is_multi_doc_question(q_display):
        ctx, cites = pack_context_grouped(retrieved)
    elif _MULTI_DOC_MODE in ('1', 'true', 'yes', 'on'):
        ctx, cites = pack_context_grouped(retrieved)
    else:
        ctx, cites = pack_context(retrieved)
    prompt = build_prompt(q_display, ctx, cites)

    unique_sources: set[str] = set()
    unique_domains: set[str] = set()
    for r in (retrieved or []):
        src = str(r.get('source') or r.get('path') or '').strip()
        if src:
            unique_sources.add(_normalize_source_key(src) or src)
        dom2 = str(r.get('domain') or '').strip().lower()
        if dom2:
            unique_domains.add(dom2)

    return {
        'prompt': prompt,
        'contexts': [
            {
                'doc_id': r.get('doc_id'),
                'domain': r.get('domain'),
                'source': r.get('source'),
                'path': r.get('path'),
                'page_start': r.get('page_start'),
                'page_end': r.get('page_end'),
                'score_rrf': r.get('score_rrf'),
            }
            for r in retrieved
        ],
        'token_est': est_tokens(ctx),
        'meta': {
            'multi_doc_mode': _MULTI_DOC_MODE,
            'multi_doc_triggered': bool(multi_doc_triggered),
            'multi_doc_used': bool(multi_doc_used),
            'multi_doc_reason': multi_doc_reason,
            'multi_doc_subqs': list(multi_doc_subqs or []),
            'retrieved_unique_sources': len(unique_sources),
            'retrieved_unique_domains': len(unique_domains),
        },
    }


def rag_query_domain(question: str, domain: str | None) -> Dict:
    q_display = normalize_question(question)
    add_metric('inferred_domain', (domain or '').strip().lower() or 'auto')
    retrieved = _retrieve_by_domain(question, domain=domain)

    strict_ref_hints = (os.getenv('STRICT_REFERENCE_HINTS', '1') or '1').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )
    retrieved = _filter_chunks_by_reference(
        retrieved,
        question,
        strict=bool(_reference_candidates(question)) and strict_ref_hints,
    )
    wants_lng_list = (
        re.search(r"LNG", q_display, re.IGNORECASE) is not None
        and any(t in q_display for t in ('เลือกเรียน', 'มีวิชา', 'วิชาอะไร', 'เลือกได้', 'ตัวเลือก'))
    )
    ctx, cites = pack_context(retrieved, truncate_chars=(450 if wants_lng_list else None))
    prompt = build_prompt(q_display, ctx, cites)
    return {
        'prompt': prompt,
        'contexts': [
            {
                'doc_id': r.get('doc_id'),
                'source': r.get('source') or (r.get('metadata') or {}).get('source'),
                'path': r.get('path') or (r.get('metadata') or {}).get('path'),
                'page_start': r.get('page_start') or (r.get('metadata') or {}).get('page_start'),
                'page_end': r.get('page_end') or (r.get('metadata') or {}).get('page_end'),
                'score_rrf': r.get('score_rrf'),
            }
            for r in retrieved
        ],
        'token_est': est_tokens(ctx),
    }
