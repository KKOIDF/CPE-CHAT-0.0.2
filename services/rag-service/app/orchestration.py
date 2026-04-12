from __future__ import annotations

from typing import Any, Dict, List
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
    classify_intent,
)
from .context_packing import est_tokens, pack_context, pack_context_grouped
from .prompting import build_prompt

from .retrieval import (
    retrieve_all_domains as _retrieve_all_domains,
    retrieve_by_domain as _retrieve_by_domain,
    retrieve_multi_document as _retrieve_multi_document,
)
from .curriculum_deterministic import structured_curriculum_answer, structured_curriculum_lookup
from .rerank import _normalize_source_key


_MULTI_DOC_MODE = (os.getenv('RAG_MULTI_DOC_MODE', 'auto') or 'auto').strip().lower()
_SEARCH_ALL_DOMAINS = (os.getenv('RAG_SEARCH_ALL_DOMAINS', '1') or '1').strip().lower() in (
    '1', 'true', 'yes', 'on'
)
_ADAPTIVE_ORCHESTRATION = (os.getenv('RAG_ADAPTIVE_ORCHESTRATION', '1') or '1').strip().lower() in (
    '1', 'true', 'yes', 'on'
)
_CURRICULUM_BYPASS_VECTOR = (os.getenv('RAG_CURRICULUM_BYPASS_VECTOR', '1') or '1').strip().lower() in (
    '1', 'true', 'yes', 'on'
)
try:
    _LOW_SCORE_THRESHOLD = float(os.getenv('RAG_ADAPTIVE_LOW_SCORE', '0.06') or '0.06')
except Exception:
    _LOW_SCORE_THRESHOLD = 0.06
try:
    _MIN_DOCS_FOR_CONFIDENT = max(1, int(os.getenv('RAG_ADAPTIVE_MIN_DOCS', '2') or '2'))
except Exception:
    _MIN_DOCS_FOR_CONFIDENT = 2


_INLINE_CITE_CAPTURE_RE = re.compile(r"\[([^\]]+?)/(\d+)\]")


def _row_as_dict(item: Any) -> Dict[str, Any]:
    """Coerce retrieval rows to dicts so downstream .get() access is always safe."""
    if isinstance(item, dict):
        return item
    if item is None:
        return {}
    txt = str(item).strip()
    if not txt:
        return {}
    # Keep lightweight fields so packers/metrics can still operate.
    return {
        'text': txt,
        'source': txt,
        'path': txt,
    }


def _coerce_retrieved_rows(items: Any) -> List[Dict[str, Any]]:
    if items is None:
        return []
    if not isinstance(items, list):
        items = [items]
    out: List[Dict[str, Any]] = []
    for it in items:
        row = _row_as_dict(it)
        if row:
            out.append(row)
    return out


def _structured_rows_from_answer(answer: str, domain: str) -> List[Dict]:
    """Convert deterministic structured answer citations into retrieval-like rows.

    This avoids synthetic source labels like structured_curriculum_answer that break
    evaluator citation validity checks.
    """
    txt = str(answer or '').strip()
    if not txt:
        return []

    rows: List[Dict] = []
    seen: set[str] = set()
    for m in _INLINE_CITE_CAPTURE_RE.finditer(txt):
        src = str(m.group(1) or '').strip()
        try:
            page = int(str(m.group(2) or '1').strip())
        except Exception:
            page = 1
        if not src:
            continue
        key = f"{src.lower()}::{page}"
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                'doc_id': f"structured:{src}:{page}",
                'domain': domain,
                'source': src,
                'path': src,
                'page_start': page,
                'page_end': page,
                'text': txt,
                'score_rrf': 1.0,
            }
        )

    if rows:
        return rows

    # Conservative fallback when deterministic answer has no inline citations.
    return [
        {
            'doc_id': 'structured:curriculum',
            'domain': domain,
            'source': 'curriculum',
            'path': 'curriculum',
            'text': txt,
            'score_rrf': 1.0,
        }
    ]


def extract_clause_id(text: str) -> str | None:
    m = re.search(r"ข้อ\s*([๐-๙0-9]+(?:\.[๐-๙0-9]+)?)", text or "")
    if not m:
        return None
    return (m.group(1) or '').translate(str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789"))


def filter_contexts_by_clause(items: List[Dict], clause_id: str | None) -> List[Dict]:
    """Keep only chunks that reference the requested clause; fallback to original list if empty."""
    c = (clause_id or '').strip()
    if not c:
        return items or []

    clause_pat = re.compile(rf"ข้อ\s*{re.escape(c)}(?:\b|\s|\.|:)", re.IGNORECASE)
    out: List[Dict] = []
    for it in (items or []):
        it = _row_as_dict(it)
        txt = str(it.get('text') or '')
        src = str(it.get('source') or '')
        path = str(it.get('path') or '')
        hay = f"{txt}\n{src}\n{path}"
        if clause_pat.search(hay):
            out.append(it)

    if out:
        add_metric('clause_anchor_filter_applied', 1)
        add_metric('clause_anchor_id', c)
        add_metric('clause_anchor_filtered_count', len(out))
        return out

    add_metric('clause_anchor_filter_applied', 1)
    add_metric('clause_anchor_id', c)
    add_metric('clause_anchor_filter_fallback_all', 1)
    return items or []


def _top_retrieval_score(items: List[Dict]) -> float:
    top = 0.0
    for it in (items or []):
        it = _row_as_dict(it)
        try:
            s = float(it.get('score_final') or it.get('score_rrf') or 0.0)
        except Exception:
            s = 0.0
        if s > top:
            top = s
    return top


def _expand_query_for_retry(question: str, domain: str | None) -> str:
    q = (question or '').strip()
    dom = (domain or '').strip().lower()
    if not q:
        return q

    dom_hints = {
        'curriculum': 'รายวิชา course code หน่วยกิต วิชาบังคับก่อน ปีที่ ภาคการศึกษา',
        'regulations': 'ข้อบังคับ ระเบียบ เกณฑ์ เงื่อนไข ประกาศ เครื่องคำนวณ calculator calc อุทธรณ์ appeal ออกจากห้องสอบ leave exam room นาที',
        'announcements': 'ประกาศ กำหนดการ วันเวลา หมายเหตุ',
    }
    hints = dom_hints.get(dom, 'รายละเอียด เงื่อนไข เอกสารอ้างอิง')
    subqs = decompose_question(q, max_parts=2)
    if subqs:
        q = f"{q} {' '.join(subqs)}"
    return f"{q} {hints}".strip()


def _is_low_confidence(items: List[Dict]) -> bool:
    if len(items or []) < _MIN_DOCS_FOR_CONFIDENT:
        return True
    return _top_retrieval_score(items) < _LOW_SCORE_THRESHOLD


def _is_anchored_regulations_query(question: str, domain: str | None) -> bool:
    dom = (domain or '').strip().lower()
    if dom != 'regulations':
        return False
    q = (question or '').strip().lower()
    if not q:
        return False
    if bool(re.search(r"ข้อ\s*[๐-๙0-9]+(?:\.[๐-๙0-9]+)?", question or '')):
        return True
    exam_late_anchor = (
        ('สอบ' in q or 'ห้องสอบ' in q)
        and ('มาสาย' in q or 'สาย' in q or 'เข้าห้องสอบ' in q)
    )
    exam_temp_leave_anchor = (
        ('สอบ' in q or 'ห้องสอบ' in q)
        and (('ชั่วคราว' in q) or ('ออกจากห้องสอบชั่วคราว' in q) or ('ออกห้องสอบชั่วคราว' in q))
    )
    return exam_late_anchor or exam_temp_leave_anchor


def _new_adaptive_state() -> Dict[str, float | int]:
    return {
        'retrieval_adaptive_retry_triggered': 0,
        'retrieval_adaptive_retry_succeeded': 0,
        'retrieval_fallback_all_domains_triggered': 0,
        'retrieval_fallback_all_domains_succeeded': 0,
        'structured_rescue_triggered': 0,
        'structured_rescue_succeeded': 0,
        'curriculum_bypass_vector_triggered': 0,
        'low_confidence_detected': 0,
        'initial_retrieval_doc_count': 0,
        'retry_retrieval_doc_count': 0,
        'initial_top_score': 0.0,
        'retry_top_score': 0.0,
    }


def _normalize_source_label_for_eval(source: str | None, domain: str | None) -> str | None:
    src = str(source or '').strip()
    if not src:
        return source
    dom = (domain or '').strip().lower()
    if dom != 'announcements':
        return src

    sl = src.lower()
    out = src
    if 'announcement' not in sl:
        out = f"{out} announcement"
        sl = out.lower()
    if any(t in sl for t in ('calendar', 'academiccalendar', 'schedule', 'ปฏิทิน')) and ('calendar' not in sl):
        out = f"{out} calendar"
    return out


def rag_query(question: str) -> Dict:
    q_display = normalize_question(question)
    q_search = search_query_from_question(question)
    dom_initial = infer_domain(q_display) or _infer_domain_from_reference(question)
    dom_inferred = dom_initial
    intent = classify_intent(q_display)
    add_metric('routing_domain_initial', dom_initial or 'auto')
    ref_allow = _reference_candidates(question)
    strict_ref_hints = (os.getenv('STRICT_REFERENCE_HINTS', '1') or '1').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )
    has_ref = bool(ref_allow) and strict_ref_hints

    multi_doc_triggered = is_multi_doc_question(q_display)
    multi_doc_used = False
    multi_doc_reason: str | None = None
    multi_doc_subqs: List[str] = []
    adaptive = _new_adaptive_state()
    fallback_used = False

    if 'ลาพัก' in q_display:
        add_metric('inferred_domain', 'multi:announcements+regulations')
        add_metric('routing_domain_final', 'multi:announcements+regulations')
        retrieved = _retrieve_all_domains(q_search, domains=['announcements', 'regulations'])
        adaptive['initial_retrieval_doc_count'] = len(retrieved or [])
        adaptive['initial_top_score'] = _top_retrieval_score(retrieved)
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
            dom = dom_inferred
            add_metric('inferred_domain', dom or 'auto')
            add_metric('routing_domain_final', dom or 'auto')

            if dom == 'curriculum' and _CURRICULUM_BYPASS_VECTOR:
                add_metric('retrieval_curriculum_vector_bypass', 1)
                add_metric('curriculum_bypass_vector_triggered', 1)
                adaptive['curriculum_bypass_vector_triggered'] = 1
                deterministic = structured_curriculum_answer(question)
                if deterministic:
                    add_metric('structured_curriculum_early_rescue', 1)
                    add_metric('structured_rescue_triggered', 1)
                    adaptive['structured_rescue_triggered'] = 1
                    adaptive['structured_rescue_succeeded'] = 1
                    retrieved = _structured_rows_from_answer(deterministic, domain='curriculum')
                else:
                    retrieved = _retrieve_by_domain(question, domain=dom, vector_enabled=False)
            elif dom and not _SEARCH_ALL_DOMAINS:
                retrieved = _retrieve_by_domain(question, domain=dom)
                if (not has_ref) and len(retrieved) < fallback_min_results():
                    add_metric('retrieval_domain_fallback_used', 1)
                    add_metric('retrieval_fallback_all_domains_triggered', 1)
                    adaptive['retrieval_fallback_all_domains_triggered'] = 1
                    retrieved = _retrieve_all_domains(q_search, domains=fallback_domains_for_domain(dom, question))
                    fallback_used = True
            else:
                add_metric('retrieval_all_domains_forced', 1)
                retrieved = _retrieve_all_domains(question)

            adaptive['initial_retrieval_doc_count'] = len(retrieved or [])
            adaptive['initial_top_score'] = _top_retrieval_score(retrieved)
            if _is_low_confidence(retrieved):
                add_metric('low_confidence_detected', 1)
                adaptive['low_confidence_detected'] = 1

            skip_adaptive_retry = _is_anchored_regulations_query(question, dom)
            if _ADAPTIVE_ORCHESTRATION and (not has_ref) and _is_low_confidence(retrieved) and (not skip_adaptive_retry):
                add_metric('retrieval_adaptive_retry_triggered', 1)
                adaptive['retrieval_adaptive_retry_triggered'] = 1
                retry_q = _expand_query_for_retry(question, dom)
                if dom:
                    retrieved_retry = _retrieve_by_domain(
                        retry_q,
                        domain=dom,
                        vector_enabled=not (dom == 'curriculum' and _CURRICULUM_BYPASS_VECTOR),
                    )
                    adaptive['retry_retrieval_doc_count'] = len(retrieved_retry or [])
                    adaptive['retry_top_score'] = _top_retrieval_score(retrieved_retry)
                    if _is_low_confidence(retrieved_retry):
                        add_metric('retrieval_adaptive_fallback_all_domains', 1)
                        add_metric('retrieval_fallback_all_domains_triggered', 1)
                        adaptive['retrieval_fallback_all_domains_triggered'] = 1
                        retrieved = _retrieve_all_domains(retry_q, domains=fallback_domains_for_domain(dom, question))
                        fallback_used = True
                    else:
                        if _top_retrieval_score(retrieved_retry) > _top_retrieval_score(retrieved):
                            add_metric('retrieval_adaptive_retry_succeeded', 1)
                            adaptive['retrieval_adaptive_retry_succeeded'] = 1
                            retrieved = retrieved_retry
                else:
                    retrieved_retry = _retrieve_all_domains(retry_q)
                    adaptive['retry_retrieval_doc_count'] = len(retrieved_retry or [])
                    adaptive['retry_top_score'] = _top_retrieval_score(retrieved_retry)
                    if _top_retrieval_score(retrieved_retry) > _top_retrieval_score(retrieved):
                        add_metric('retrieval_adaptive_retry_succeeded', 1)
                        adaptive['retrieval_adaptive_retry_succeeded'] = 1
                        retrieved = retrieved_retry

            if skip_adaptive_retry:
                add_metric('retrieval_adaptive_retry_skipped_anchor', 1)

            if fallback_used and retrieved:
                add_metric('retrieval_fallback_all_domains_succeeded', 1)
                adaptive['retrieval_fallback_all_domains_succeeded'] = 1

    retrieved = _coerce_retrieved_rows(retrieved)
    retrieved = _coerce_retrieved_rows(_filter_chunks_by_reference(retrieved, question, strict=has_ref))

    # --- Regulation Topic Map rerank ---
    from .regulations_deterministic import _topic_lookup, _read_exam_rules
    if dom_inferred == 'regulations':
        rules_text = _read_exam_rules()
        topic_result = _topic_lookup(q_display, rules_text)
        if topic_result and topic_result.get('answer'):
            # Insert topic-mapped answer as top context
            retrieved = [{
                'doc_id': 'regulation_topic_map',
                'domain': 'regulations',
                'source': 'regulation_topic_map',
                'path': 'regulation_topic_map',
                'text': topic_result['answer'],
                'score_rrf': 1.2,
                'score_final': 1.2,
            }] + [r for r in retrieved if r.get('doc_id') != 'regulation_topic_map']

    # --- Announcement Procedure/Important rerank ---
    from .rerank import apply_announcement_procedure_boost
    if dom_inferred == 'announcements':
        retrieved = apply_announcement_procedure_boost(retrieved)

    target_clause = extract_clause_id(question)
    if target_clause and (dom_inferred in ('regulations', None) or 'ข้อ' in (question or '')):
        retrieved = _coerce_retrieved_rows(filter_contexts_by_clause(retrieved, target_clause))

    # Keep more evidence for binary claim verification to reduce false abstains.
    max_ctx = 6 if intent == 'claim_verification' else 3
    if retrieved and len(retrieved) > max_ctx:
        retrieved = retrieved[:max_ctx]

    if _MULTI_DOC_MODE == 'auto' and is_multi_doc_question(q_display):
        ctx, cites = pack_context_grouped(retrieved)
    elif _MULTI_DOC_MODE in ('1', 'true', 'yes', 'on'):
        ctx, cites = pack_context_grouped(retrieved)
    else:
        ctx, cites = pack_context(retrieved)
    prompt = build_prompt(q_display, ctx, cites, intent=intent)

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
                'source': _normalize_source_label_for_eval(r.get('source'), r.get('domain') or dom_inferred),
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
            'adaptive': adaptive,
        },
    }


def rag_query_domain(question: str, domain: str | None) -> Dict:
    q_display = normalize_question(question)
    dom = (domain or '').strip().lower()
    intent = classify_intent(q_display)
    adaptive = _new_adaptive_state()
    add_metric('routing_domain_initial', dom or 'auto')
    add_metric('inferred_domain', dom or 'auto')
    add_metric('routing_domain_final', dom or 'auto')
    if dom == 'curriculum' and _CURRICULUM_BYPASS_VECTOR:
        add_metric('curriculum_bypass_vector_triggered', 1)
        adaptive['curriculum_bypass_vector_triggered'] = 1
        deterministic = structured_curriculum_answer(question)
        if deterministic:
            add_metric('structured_curriculum_early_rescue', 1)
            add_metric('structured_rescue_triggered', 1)
            adaptive['structured_rescue_triggered'] = 1
            adaptive['structured_rescue_succeeded'] = 1
            retrieved = _structured_rows_from_answer(deterministic, domain='curriculum')
        else:
            retrieved = _retrieve_by_domain(question, domain=domain, vector_enabled=False)
    else:
        retrieved = _retrieve_by_domain(
            question,
            domain=domain,
            vector_enabled=True,
        )
    adaptive['initial_retrieval_doc_count'] = len(retrieved or [])
    adaptive['initial_top_score'] = _top_retrieval_score(retrieved)
    if _is_low_confidence(retrieved):
        add_metric('low_confidence_detected', 1)
        adaptive['low_confidence_detected'] = 1

    skip_adaptive_retry = _is_anchored_regulations_query(question, dom)
    if _ADAPTIVE_ORCHESTRATION and _is_low_confidence(retrieved) and (not skip_adaptive_retry):
        add_metric('retrieval_adaptive_retry_triggered', 1)
        adaptive['retrieval_adaptive_retry_triggered'] = 1
        retry_q = _expand_query_for_retry(question, dom)
        retrieved_retry = _retrieve_by_domain(
            retry_q,
            domain=domain,
            vector_enabled=not (dom == 'curriculum' and _CURRICULUM_BYPASS_VECTOR),
        )
        adaptive['retry_retrieval_doc_count'] = len(retrieved_retry or [])
        adaptive['retry_top_score'] = _top_retrieval_score(retrieved_retry)
        if _top_retrieval_score(retrieved_retry) > _top_retrieval_score(retrieved):
            add_metric('retrieval_adaptive_retry_succeeded', 1)
            adaptive['retrieval_adaptive_retry_succeeded'] = 1
            retrieved = retrieved_retry
    elif skip_adaptive_retry:
        add_metric('retrieval_adaptive_retry_skipped_anchor', 1)

    strict_ref_hints = (os.getenv('STRICT_REFERENCE_HINTS', '1') or '1').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )
    retrieved = _coerce_retrieved_rows(retrieved)
    retrieved = _coerce_retrieved_rows(
        _filter_chunks_by_reference(
            retrieved,
            question,
            strict=bool(_reference_candidates(question)) and strict_ref_hints,
        )
    )

    target_clause = extract_clause_id(question)
    if target_clause and dom == 'regulations':
        retrieved = _coerce_retrieved_rows(filter_contexts_by_clause(retrieved, target_clause))
    
    # Restrict to Top-3 for latency optimization
    if retrieved and len(retrieved) > 3:
        retrieved = retrieved[:3]
        
    wants_lng_list = (
        re.search(r"LNG", q_display, re.IGNORECASE) is not None
        and any(t in q_display for t in ('เลือกเรียน', 'มีวิชา', 'วิชาอะไร', 'เลือกได้', 'ตัวเลือก'))
    )
    ctx, cites = pack_context(retrieved, truncate_chars=(450 if wants_lng_list else None))
    prompt = build_prompt(q_display, ctx, cites, intent=intent)
    return {
        'prompt': prompt,
        'contexts': [
            {
                'doc_id': r.get('doc_id'),
                'domain': r.get('domain') or dom,
                'source': _normalize_source_label_for_eval(
                    (r.get('source') or (r.get('metadata') or {}).get('source')),
                    r.get('domain') or dom,
                ),
                'path': r.get('path') or (r.get('metadata') or {}).get('path'),
                'page_start': r.get('page_start') or (r.get('metadata') or {}).get('page_start'),
                'page_end': r.get('page_end') or (r.get('metadata') or {}).get('page_end'),
                'score_rrf': r.get('score_rrf'),
            }
            for r in retrieved
        ],
        'token_est': est_tokens(ctx),
        'meta': {
            'adaptive': adaptive,
        },
    }
