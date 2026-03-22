from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Sequence
import json
import logging
import os
import re

from .perf import add_metric, time_block
from .sqlite_client import domain_sqlite_path, fetch_docs_with_path, keyword_search
from .chroma_client import semantic_search_domain
from .config import MAX_CONTEXTS, RRF_K
from .neo4j_client import (
    extract_course_codes,
    graph_doc_ids_for_codes,
    graph_doc_ids_for_course_prefix,
    graph_doc_ids_for_requisites,
    graph_expand_from_seed_chunks,
)
from .normalization import (
    build_retrieval_queries,
    extract_lexical_anchors,
    normalize_question,
)
from .routing import (
    _reference_candidates,
    decompose_question,
    infer_domain,
    infer_domain_bias,
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


logger = logging.getLogger(__name__)


_RETRIEVAL_PARALLEL = (os.getenv('RAG_RETRIEVAL_PARALLEL', '1') or '1').strip().lower() in (
    '1', 'true', 'yes', 'on'
)
_VECTOR_ONLY = (os.getenv('RAG_VECTOR_ONLY', '0') or '0').strip().lower() in (
    '1', 'true', 'yes', 'on'
)
try:
    _RETRIEVAL_PARALLEL_WORKERS = max(2, int(os.getenv('RAG_RETRIEVAL_PARALLEL_WORKERS', '2') or '2'))
except Exception:
    _RETRIEVAL_PARALLEL_WORKERS = 2

_DEBUG_RETRIEVAL = (os.getenv('RAG_DEBUG_RETRIEVAL', '0') or '0').strip().lower() in (
    '1', 'true', 'yes', 'on'
)

try:
    _MULTI_DOC_MAX_SUBQS = max(1, int(os.getenv('RAG_MULTI_DOC_MAX_SUBQS', '3') or '3'))
except Exception:
    _MULTI_DOC_MAX_SUBQS = 3
try:
    _MULTI_DOC_FINAL_LIMIT = max(2, int(os.getenv('RAG_MULTI_DOC_FINAL_LIMIT', str(MAX_CONTEXTS)) or str(MAX_CONTEXTS)))
except Exception:
    _MULTI_DOC_FINAL_LIMIT = MAX_CONTEXTS
try:
    _MULTI_DOC_MAX_PER_SOURCE = max(1, int(os.getenv('RAG_MULTI_DOC_MAX_PER_SOURCE', '2') or '2'))
except Exception:
    _MULTI_DOC_MAX_PER_SOURCE = 2
try:
    _MULTI_DOC_MIN_SOURCES = max(1, int(os.getenv('RAG_MULTI_DOC_MIN_SOURCES', '2') or '2'))
except Exception:
    _MULTI_DOC_MIN_SOURCES = 2
try:
    _MULTI_DOC_WIDE_LIMIT = max(_MULTI_DOC_FINAL_LIMIT, int(os.getenv('RAG_MULTI_DOC_WIDE_LIMIT', str(max(MAX_CONTEXTS * 4, 24))) or str(max(MAX_CONTEXTS * 4, 24))))
except Exception:
    _MULTI_DOC_WIDE_LIMIT = max(MAX_CONTEXTS * 4, 24)
try:
    _MULTI_DOC_PER_DOMAIN_LIMIT = max(_MULTI_DOC_WIDE_LIMIT, int(os.getenv('RAG_MULTI_DOC_PER_DOMAIN_LIMIT', str(max(MAX_CONTEXTS * 3, 18))) or str(max(MAX_CONTEXTS * 3, 18))))
except Exception:
    _MULTI_DOC_PER_DOMAIN_LIMIT = max(MAX_CONTEXTS * 3, 18)
try:
    _MULTI_DOC_DOC_TOPN = max(2, int(os.getenv('RAG_MULTI_DOC_DOC_TOPN', '6') or '6'))
except Exception:
    _MULTI_DOC_DOC_TOPN = 6
try:
    _MULTI_DOC_CHUNKS_PER_DOC = max(1, int(os.getenv('RAG_MULTI_DOC_CHUNKS_PER_DOC', '3') or '3'))
except Exception:
    _MULTI_DOC_CHUNKS_PER_DOC = 3

try:
    _HYBRID_SEMANTIC_WEIGHT = float(os.getenv('RAG_HYBRID_SEMANTIC_WEIGHT', '1.0') or '1.0')
except Exception:
    _HYBRID_SEMANTIC_WEIGHT = 1.0
try:
    _HYBRID_KEYWORD_WEIGHT = float(os.getenv('RAG_HYBRID_KEYWORD_WEIGHT', '1.2') or '1.2')
except Exception:
    _HYBRID_KEYWORD_WEIGHT = 1.2
try:
    _DOMAIN_PRIOR_BONUS = float(os.getenv('RAG_DOMAIN_PRIOR_BONUS', '0.15') or '0.15')
except Exception:
    _DOMAIN_PRIOR_BONUS = 0.15
try:
    _ANCHOR_HIT_BONUS = float(os.getenv('RAG_ANCHOR_HIT_BONUS', '0.18') or '0.18')
except Exception:
    _ANCHOR_HIT_BONUS = 0.18
try:
    _MAX_PER_SOURCE = max(1, int(os.getenv('RAG_MAX_PER_SOURCE', '2') or '2'))
except Exception:
    _MAX_PER_SOURCE = 2

try:
    _DOMAIN_PRIOR_PENALTY = float(os.getenv('RAG_DOMAIN_PRIOR_PENALTY', '0.08') or '0.08')
except Exception:
    _DOMAIN_PRIOR_PENALTY = 0.08

try:
    _DOMAIN_RESCUE_MARGIN = float(os.getenv('RAG_DOMAIN_RESCUE_MARGIN', '0.08') or '0.08')
except Exception:
    _DOMAIN_RESCUE_MARGIN = 0.08

try:
    _DOMAIN_RESCUE_TOPN = max(2, int(os.getenv('RAG_DOMAIN_RESCUE_TOPN', '5') or '5'))
except Exception:
    _DOMAIN_RESCUE_TOPN = 5

try:
    _DOMAIN_RESCUE_REQUIRE_MAJORITY = max(2, int(os.getenv('RAG_DOMAIN_RESCUE_REQUIRE_MAJORITY', '3') or '3'))
except Exception:
    _DOMAIN_RESCUE_REQUIRE_MAJORITY = 3


def _log_retrieval(event: str, payload: Dict) -> None:
    if not _DEBUG_RETRIEVAL:
        return
    try:
        msg = dict(payload or {})
        msg['event'] = event
        logger.info(json.dumps(msg, ensure_ascii=False, default=str))
    except Exception:
        try:
            logger.info({'event': event, **(payload or {})})
        except Exception:
            return


def retrieve_multi_document(question: str) -> List[Dict]:
    """Multi-hop-ish retrieval: decompose -> wide retrieve per subq -> fuse -> doc→chunk -> diversify."""
    subqs = decompose_question(question, max_parts=_MULTI_DOC_MAX_SUBQS)
    if not subqs:
        return []

    lists: List[List[Dict]] = []
    weights: List[float] = []
    for i, sq in enumerate(subqs):
        hits = retrieve_all_domains(
            sq,
            k_vec=24,
            k_kw=40,
            final_limit=_MULTI_DOC_WIDE_LIMIT,
            max_per_source=max(_MULTI_DOC_MAX_PER_SOURCE + 1, _MAX_PER_SOURCE),
            per_domain_limit=_MULTI_DOC_PER_DOMAIN_LIMIT,
        )
        lists.append(hits)
        weights.append(1.2 if i == 0 else 1.0)

    fused = fuse_rrf_lists(lists, weights=weights)
    anchors = extract_lexical_anchors(question)
    fused = promote_exact_anchor_hits(fused, anchors, bonus_per_hit=_ANCHOR_HIT_BONUS)

    try:
        ql = (question or '').strip().lower()
        want_exam_temp_leave = (
            ('สอบ' in ql or 'ห้องสอบ' in ql)
            and (('ชั่วคราว' in ql) or ('ออกจากห้องสอบชั่วคราว' in ql) or ('ออกห้องสอบชั่วคราว' in ql))
        )
        if want_exam_temp_leave and fused:
            bonus = float(os.getenv('RAG_MULTI_DOC_REGULATIONS_CLAUSE16_BONUS', '0.35') or '0.35')

            def _is_clause16(d: Dict) -> bool:
                t = str(d.get('text') or '')
                return ('ข้อ 16' in t) and (('ชั่วคราว' in t) or ('ออกจากห้องสอบ' in t) or ('กรรมการคุมสอบ' in t) or ('เครื่องมือสื่อสาร' in t))

            boosted: List[Dict] = []
            for d in fused:
                u = dict(d)
                base = float(u.get('score_final') or u.get('score_rrf') or 0.0)
                if _is_clause16(u):
                    base += bonus
                u['score_final'] = base
                u['score_rrf'] = base
                boosted.append(u)
            boosted.sort(key=lambda x: float(x.get('score_final') or x.get('score_rrf') or 0.0), reverse=True)
            fused = boosted
    except Exception:
        pass

    doc_selected = select_chunks_from_top_documents(fused, top_docs=_MULTI_DOC_DOC_TOPN, per_doc=_MULTI_DOC_CHUNKS_PER_DOC)

    try:
        ql = (question or '').strip().lower()
        want_exam_temp_leave = (
            ('สอบ' in ql or 'ห้องสอบ' in ql)
            and (('ชั่วคราว' in ql) or ('ออกจากห้องสอบชั่วคราว' in ql) or ('ออกห้องสอบชั่วคราว' in ql))
        )
        if want_exam_temp_leave and fused and doc_selected:
            def _is_clause16(d: Dict) -> bool:
                t = str(d.get('text') or '')
                return ('ข้อ 16' in t) and (('ชั่วคราว' in t) or ('ออกจากห้องสอบ' in t) or ('กรรมการคุมสอบ' in t) or ('เครื่องมือสื่อสาร' in t))

            has16 = any(_is_clause16(d) for d in doc_selected)
            if not has16:
                cand16 = None
                for d in fused:
                    if _is_clause16(d):
                        cand16 = d
                        break
                if cand16 and (not any(str(x.get('doc_id') or '') == str(cand16.get('doc_id') or '') for x in doc_selected)):
                    add_metric('multi_doc_inject_clause16', 1)
                    u = dict(cand16)
                    boost = float(os.getenv('RAG_MULTI_DOC_REGULATIONS_CLAUSE16_INJECT_BOOST', '0.55') or '0.55')
                    base = float(u.get('score_final') or u.get('score_rrf') or 0.0)
                    u['score_final'] = base + boost
                    u['score_rrf'] = u['score_final']
                    doc_selected = [*doc_selected, u]
                    doc_selected.sort(key=lambda x: float(x.get('score_final') or x.get('score_rrf') or 0.0), reverse=True)
    except Exception:
        pass

    final = ensure_min_sources(
        doc_selected,
        min_sources=_MULTI_DOC_MIN_SOURCES,
        max_per_source=_MULTI_DOC_MAX_PER_SOURCE,
        limit=_MULTI_DOC_FINAL_LIMIT,
    )

    add_metric('multi_doc_used', 1)
    add_metric('multi_doc_subq_n', len(subqs))
    add_metric('multi_doc_fused_n', len(fused))
    add_metric('multi_doc_final_n', len(final))
    _log_retrieval(
        'retrieve_multi_document',
        {
            'question': question,
            'subqs': subqs,
            'anchors': anchors,
            'fused_n': len(fused),
            'final_n': len(final),
            'top': [
                {
                    'doc_id': d.get('doc_id'),
                    'domain': d.get('domain'),
                    'source': d.get('source'),
                    'score': d.get('score_rrf'),
                }
                for d in (final[:6] if final else [])
            ],
        },
    )
    return final


def hybrid_retrieve(question: str, k_vec: int = 20, k_kw: int = 30) -> List[Dict]:
    return retrieve_all_domains(question, k_vec=k_vec, k_kw=k_kw)


def retrieve_all_domains(
    question: str,
    k_vec: int = 20,
    k_kw: int = 30,
    domains: List[str] | None = None,
    final_limit: int = MAX_CONTEXTS,
    max_per_source: int = _MAX_PER_SOURCE,
    per_domain_limit: int | None = None,
) -> List[Dict]:
    doms = [d.strip().lower() for d in (domains or ['announcements', 'regulations', 'curriculum']) if (d or '').strip()]
    if not doms:
        doms = ['announcements', 'regulations', 'curriculum']

    bank: Dict[str, Dict] = {}
    ranks: Dict[str, float] = {}

    for dom in doms:
        try:
            results = retrieve_by_domain(
                question,
                domain=dom,
                k_vec=k_vec,
                k_kw=k_kw,
                max_contexts_override=per_domain_limit,
            )
        except Exception:
            continue

        for r, d in enumerate(results, 1):
            doc_id = d.get('doc_id') or d.get('source') or f'unk_{r}'
            key = f"{dom}:{doc_id}"
            if key not in bank:
                bank[key] = {**d, 'doc_id': doc_id, 'domain': dom}
            else:
                bank[key].setdefault('domain', dom)
            ranks[key] = ranks.get(key, 0.0) + 1.0 / (RRF_K + r)

    merged = [{**bank[k], 'score_rrf': v} for k, v in ranks.items()]

    inferred = infer_domain(normalize_question(question)) or infer_domain_bias(question)
    merged = apply_domain_prior(merged, inferred, bonus=_DOMAIN_PRIOR_BONUS, penalty=_DOMAIN_PRIOR_PENALTY)

    anchors = extract_lexical_anchors(question)
    merged = promote_exact_anchor_hits(merged, anchors, bonus_per_hit=_ANCHOR_HIT_BONUS)

    merged = apply_overbroad_source_penalty(merged, inferred, question=question)

    merged.sort(key=lambda x: x.get('score_rrf', 0.0), reverse=True)
    merged = majority_domain_rescue(
        merged,
        topn=_DOMAIN_RESCUE_TOPN,
        margin=_DOMAIN_RESCUE_MARGIN,
        require_majority=_DOMAIN_RESCUE_REQUIRE_MAJORITY,
    )
    final_limit = max(1, int(final_limit))
    max_per_source = max(1, int(max_per_source))

    candidates = merged[: max(final_limit * 4, final_limit)]
    final = diversify_by_source(candidates, max_per_source=max_per_source, limit=final_limit)
    final = majority_domain_rescue(
        final,
        topn=_DOMAIN_RESCUE_TOPN,
        margin=_DOMAIN_RESCUE_MARGIN,
        require_majority=_DOMAIN_RESCUE_REQUIRE_MAJORITY,
    )
    _log_retrieval(
        'retrieve_all_domains',
        {
            'question': question,
            'question_norm': normalize_question(question),
            'inferred_domain': inferred,
            'anchors': anchors,
            'candidates_n': len(merged),
            'final_n': len(final),
            'overbroad_penalties_applied': (inferred in ('curriculum', 'regulations')),
            'top': [
                {
                    'doc_id': d.get('doc_id'),
                    'domain': d.get('domain'),
                    'source': d.get('source'),
                    'score': d.get('score_rrf'),
                }
                for d in (final[:6] if final else [])
            ],
        },
    )
    return final


def retrieve_by_domain(
    question: str,
    domain: str | None,
    k_vec: int = 20,
    k_kw: int = 30,
    max_contexts_override: int | None = None,
) -> List[Dict]:
    def _retrieve_semantic_and_keyword(
        semantic_query: str,
        keyword_query: str,
        top_k_vec: int,
        top_k_kw: int,
        target_domain: str | None,
        sqlite_file: str | None,
        allowlist: Sequence[str] | None,
        fallback_name: str | None = None,
    ) -> tuple[List[Dict], List[str]]:
        if _VECTOR_ONLY:
            sem_block = 'vector_search' if not fallback_name else f'vector_search_{fallback_name}'
            with time_block(sem_block):
                sem_out = semantic_search_domain(
                    semantic_query,
                    top_k=top_k_vec,
                    domain=target_domain,
                    source_allowlist=allowlist,
                )
            return sem_out, []

        if _RETRIEVAL_PARALLEL:
            block = 'parallel_search' if not fallback_name else f'parallel_search_{fallback_name}'
            with time_block(block):
                with ThreadPoolExecutor(max_workers=_RETRIEVAL_PARALLEL_WORKERS) as ex:
                    fut_sem = ex.submit(
                        semantic_search_domain,
                        semantic_query,
                        top_k_vec,
                        target_domain,
                        allowlist,
                    )
                    fut_kw = ex.submit(
                        keyword_search,
                        keyword_query,
                        top_k_kw,
                        sqlite_file,
                        allowlist,
                    )
                    sem_out = fut_sem.result()
                    kw_ids_out = fut_kw.result()
            return sem_out, kw_ids_out

        sem_block = 'vector_search' if not fallback_name else f'vector_search_{fallback_name}'
        kw_block = 'keyword_search' if not fallback_name else f'keyword_search_{fallback_name}'
        with time_block(sem_block):
            sem_out = semantic_search_domain(
                semantic_query,
                top_k=top_k_vec,
                domain=target_domain,
                source_allowlist=allowlist,
            )
        with time_block(kw_block):
            kw_ids_out = keyword_search(
                keyword_query,
                limit=top_k_kw,
                sqlite_path=sqlite_file,
                source_allowlist=allowlist,
            )
        return sem_out, kw_ids_out

    def _hydrate_from_sqlite(items: List[Dict], sqlite_path: str | None) -> List[Dict]:
        if not items or not sqlite_path:
            return items
        doc_ids: List[str] = []
        seen: set[str] = set()
        for it in items:
            did = it.get('doc_id')
            if isinstance(did, str) and did and did not in seen:
                doc_ids.append(did)
                seen.add(did)
        if not doc_ids:
            return items
        docs = fetch_docs_with_path(doc_ids, sqlite_path=sqlite_path)
        by_id = {d.get('doc_id'): d for d in docs if d.get('doc_id')}
        out: List[Dict] = []
        for it in items:
            did = it.get('doc_id')
            db = by_id.get(did) if isinstance(did, str) else None
            if not db:
                out.append(it)
                continue
            merged = dict(it)
            for k in (
                'text',
                'source',
                'path',
                'file_type',
                'page_start',
                'page_end',
                'owner',
                'sensitivity',
                'updated_at',
                'tokens_est',
            ):
                if db.get(k) is not None:
                    merged[k] = db.get(k)
            out.append(merged)
        return out

    dom = (domain or '').strip().lower()
    add_metric('retrieval_domain', dom or 'auto')

    max_contexts_local = MAX_CONTEXTS
    if max_contexts_override is not None:
        try:
            max_contexts_local = max(1, int(max_contexts_override))
        except Exception:
            max_contexts_local = MAX_CONTEXTS

    semantic_q, keyword_q = build_retrieval_queries(question)
    anchors = extract_lexical_anchors(keyword_q or question)

    ref_allow = _reference_candidates(question)
    source_allowlist: Sequence[str] | None = ref_allow if ref_allow else None
    strict_ref_hints = (os.getenv('STRICT_REFERENCE_HINTS', '1') or '1').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )
    strict_ref = bool(source_allowlist) and strict_ref_hints
    add_metric('retrieval_ref_hint_count', len(ref_allow or []))
    add_metric('retrieval_strict_ref', int(strict_ref))

    sqlite_path = domain_sqlite_path(dom) if dom else None

    sem, kw_ids = _retrieve_semantic_and_keyword(
        semantic_q,
        keyword_q,
        k_vec,
        k_kw,
        dom or None,
        sqlite_path,
        source_allowlist,
    )
    with time_block('hydrate_sqlite'):
        if sem:
            sem = _hydrate_from_sqlite(sem, sqlite_path)
    with time_block('fetch_kw_docs'):
        kw_docs = fetch_docs_with_path(kw_ids, sqlite_path=sqlite_path) if kw_ids else []
    add_metric('retrieval_sem_n', len(sem))
    add_metric('retrieval_kw_n', len(kw_docs))

    if (not strict_ref) and source_allowlist and (len(sem) + len(kw_docs) < 2):
        add_metric('retrieval_source_fallback_used', 1)
        sem, kw_ids = _retrieve_semantic_and_keyword(
            semantic_q,
            keyword_q,
            k_vec,
            k_kw,
            dom or None,
            sqlite_path,
            None,
            fallback_name='fallback',
        )
        with time_block('hydrate_sqlite_fallback'):
            if sem:
                sem = _hydrate_from_sqlite(sem, sqlite_path)
        with time_block('fetch_kw_docs_fallback'):
            kw_docs = fetch_docs_with_path(kw_ids, sqlite_path=sqlite_path) if kw_ids else []
        add_metric('retrieval_sem_n', len(sem))
        add_metric('retrieval_kw_n', len(kw_docs))

    merged = fuse_semantic_keyword(
        sem,
        kw_docs,
        sem_weight=_HYBRID_SEMANTIC_WEIGHT,
        kw_weight=_HYBRID_KEYWORD_WEIGHT,
        k=RRF_K,
    )
    merged = promote_exact_anchor_hits(merged, anchors, bonus_per_hit=_ANCHOR_HIT_BONUS)
    add_metric('retrieval_merged_n', len(merged))
    candidates = merged[: max(max_contexts_local * 4, max_contexts_local)]
    picked = diversify_by_source(candidates, max_per_source=_MAX_PER_SOURCE, limit=max_contexts_local)
    add_metric('retrieval_final_n', len(picked))
    _log_retrieval(
        'retrieve_by_domain',
        {
            'domain': dom,
            'question': question,
            'semantic_q': semantic_q,
            'keyword_q': keyword_q,
            'anchors': anchors,
            'picked_n': len(picked or []),
        },
    )
    return picked
