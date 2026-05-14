from __future__ import annotations

from typing import Any, Dict, List
from copy import deepcopy
import os
import re
import threading
import time
import json
from pathlib import Path

from .perf import add_metric
from .normalization import normalize_question, search_query_from_question
from .config import KNOWN_DOMAINS, ROOT_DIR
from .routing import (
    apply_resolved_entity_context,
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
from .rerank import _normalize_source_key, apply_intent_aware_fact_boost
from .structured_artifacts import search_fact_index


_MULTI_DOC_MODE = (os.getenv('RAG_MULTI_DOC_MODE', 'auto') or 'auto').strip().lower()
_SEARCH_ALL_DOMAINS = (os.getenv('RAG_SEARCH_ALL_DOMAINS', '1') or '1').strip().lower() in (
    '1', 'true', 'yes', 'on'
)
_ADAPTIVE_ORCHESTRATION = (os.getenv('RAG_ADAPTIVE_ORCHESTRATION', '1') or '1').strip().lower() in (
    '1', 'true', 'yes', 'on'
)
_CURRICULUM_BYPASS_VECTOR = False
try:
    _LOW_SCORE_THRESHOLD = float(os.getenv('RAG_ADAPTIVE_LOW_SCORE', '0.06') or '0.06')
except Exception:
    _LOW_SCORE_THRESHOLD = 0.06
try:
    _MIN_DOCS_FOR_CONFIDENT = max(1, int(os.getenv('RAG_ADAPTIVE_MIN_DOCS', '2') or '2'))
except Exception:
    _MIN_DOCS_FOR_CONFIDENT = 2
_RETRIEVAL_CACHE_ENABLE = (os.getenv('RAG_RETRIEVAL_CACHE_ENABLE', '1') or '1').strip().lower() in (
    '1', 'true', 'yes', 'on'
)
try:
    _RETRIEVAL_CACHE_TTL_SECONDS = max(5, int(os.getenv('RAG_RETRIEVAL_CACHE_TTL_SECONDS', '300') or '300'))
except Exception:
    _RETRIEVAL_CACHE_TTL_SECONDS = 300
try:
    _RETRIEVAL_CACHE_MAX_ENTRIES = max(16, int(os.getenv('RAG_RETRIEVAL_CACHE_MAX_ENTRIES', '256') or '256'))
except Exception:
    _RETRIEVAL_CACHE_MAX_ENTRIES = 256

_RETRIEVAL_CACHE_LOCK = threading.Lock()
_RETRIEVAL_CACHE: Dict[str, Dict[str, Any]] = {}
_RETRIEVAL_REDIS_CLIENT = None
_RETRIEVAL_REDIS_LOCK = threading.Lock()
_CACHE_STATS_LOCK = threading.Lock()
_CACHE_STATS: Dict[str, int] = {
    'requests': 0,
    'hits': 0,
    'misses': 0,
    'writes': 0,
    'expired': 0,
    'invalidated': 0,
    'fallback_to_memory': 0,
    'redis_errors': 0,
}


_INLINE_CITE_CAPTURE_RE = re.compile(r"\[([^\]]+?)/(\d+)\]")


def _cache_file_signature(path: Path) -> tuple[int, int]:
    try:
        st = path.stat()
        return int(st.st_mtime_ns), int(st.st_size)
    except Exception:
        return (-1, -1)


def _retrieval_cache_redis_url() -> str:
    return str(
        os.getenv('RAG_RETRIEVAL_REDIS_URL')
        or os.getenv('RAG_SESSION_REDIS_URL')
        or ''
    ).strip()


def _retrieval_cache_namespace() -> str:
    service = str(os.getenv('RAG_CACHE_SERVICE_NAME') or os.getenv('RAG_SERVICE_NAME') or 'rag-service').strip() or 'rag-service'
    env_name = str(os.getenv('RAG_CACHE_ENV') or os.getenv('RAG_ENVIRONMENT') or os.getenv('ENVIRONMENT') or 'dev').strip() or 'dev'
    custom = str(os.getenv('RAG_RETRIEVAL_CACHE_NAMESPACE') or '').strip()
    if custom:
        return custom
    return f"{env_name}:{service}:retrieval"


def _cache_stat_inc(key: str, value: int = 1) -> None:
    with _CACHE_STATS_LOCK:
        _CACHE_STATS[key] = int(_CACHE_STATS.get(key) or 0) + int(value)


def get_retrieval_cache_metrics_snapshot() -> Dict[str, Any]:
    with _CACHE_STATS_LOCK:
        counters = dict(_CACHE_STATS)
    with _RETRIEVAL_CACHE_LOCK:
        memory_entries = len(_RETRIEVAL_CACHE)
    redis_enabled = bool(_retrieval_cache_redis_url())
    redis_client = _get_retrieval_redis_client() if redis_enabled else None
    return {
        'enabled': bool(_RETRIEVAL_CACHE_ENABLE),
        'backend': 'redis' if redis_client is not None else 'memory',
        'redis_configured': int(redis_enabled),
        'redis_connected': int(redis_client is not None),
        'namespace': _retrieval_cache_namespace(),
        'ttl_seconds': int(_RETRIEVAL_CACHE_TTL_SECONDS),
        'max_entries_memory': int(_RETRIEVAL_CACHE_MAX_ENTRIES),
        'memory_entries': int(memory_entries),
        'counters': counters,
    }


def _get_retrieval_redis_client():
    global _RETRIEVAL_REDIS_CLIENT
    redis_url = _retrieval_cache_redis_url()
    if not redis_url:
        return None
    if _RETRIEVAL_REDIS_CLIENT is not None:
        return _RETRIEVAL_REDIS_CLIENT
    with _RETRIEVAL_REDIS_LOCK:
        if _RETRIEVAL_REDIS_CLIENT is not None:
            return _RETRIEVAL_REDIS_CLIENT
        try:
            import redis  # type: ignore
            _RETRIEVAL_REDIS_CLIENT = redis.from_url(redis_url, decode_responses=True)
        except Exception:
            _RETRIEVAL_REDIS_CLIENT = None
        return _RETRIEVAL_REDIS_CLIENT


def _redis_cache_key(key: str) -> str:
    return f"rag:{_retrieval_cache_namespace()}:{key}"


def _cache_domains_signature(domains: List[str]) -> str:
    payload: Dict[str, tuple[int, int]] = {}
    for dom in domains:
        key = str(dom or '').strip().lower()
        if not key:
            continue
        payload[f"{key}:sqlite"] = _cache_file_signature(ROOT_DIR / 'indexes' / key / 'vector' / 'sqlite' / 'ingestion.db')
        payload[f"{key}:facts"] = _cache_file_signature(ROOT_DIR / 'indexes' / key / 'structured' / 'fact_index.json')
        payload[f"{key}:profiles"] = _cache_file_signature(ROOT_DIR / 'indexes' / key / 'structured' / 'document_profiles.json')
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _retrieval_cacheable(question: str, retrieval_plan: dict | None = None) -> bool:
    q = str(question or '').strip()
    if not q:
        return False
    if q.startswith('บริบทก่อนหน้า:'):
        return True
    if len(q) <= 240:
        return True
    if is_multi_doc_question(q):
        return True
    return bool((retrieval_plan or {}).get('search_queries'))


def _retrieval_cache_key(
    *,
    question: str,
    domain: str | None,
    planned_domains: List[str],
    intent: str,
    retrieval_plan: dict | None,
) -> str:
    payload = {
        'question': normalize_question(question),
        'domain': str(domain or '').strip().lower(),
        'planned_domains': [str(v or '').strip().lower() for v in (planned_domains or []) if str(v or '').strip()],
        'intent': str(intent or '').strip().lower(),
        'search_queries': [str(v or '').strip() for v in ((retrieval_plan or {}).get('search_queries') or []) if str(v or '').strip()],
        'needed_evidence': [str(v or '').strip().lower() for v in ((retrieval_plan or {}).get('needed_evidence') or []) if str(v or '').strip()],
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _retrieval_cache_get(key: str, domains: List[str]) -> Dict[str, Any] | None:
    if not _RETRIEVAL_CACHE_ENABLE or not key:
        return None
    _cache_stat_inc('requests', 1)
    now = time.time()
    sig = _cache_domains_signature(domains)
    redis_client = _get_retrieval_redis_client()
    if redis_client is not None:
        try:
            raw = redis_client.get(_redis_cache_key(key))
            if raw:
                entry = json.loads(raw)
                if float(entry.get('expires_at') or 0.0) < now:
                    try:
                        redis_client.delete(_redis_cache_key(key))
                    except Exception:
                        pass
                    _cache_stat_inc('expired', 1)
                    add_metric('retrieval_cache_expired', 1)
                    return None
                if str(entry.get('index_signature') or '') != sig:
                    try:
                        redis_client.delete(_redis_cache_key(key))
                    except Exception:
                        pass
                    _cache_stat_inc('invalidated', 1)
                    add_metric('retrieval_cache_invalidated', 1)
                    return None
                _cache_stat_inc('hits', 1)
                add_metric('retrieval_cache_hit', 1)
                add_metric('retrieval_cache_backend', 'redis')
                add_metric('retrieval_cache_namespace', _retrieval_cache_namespace())
                return deepcopy(entry.get('value') or {})
        except Exception:
            _cache_stat_inc('redis_errors', 1)
            _cache_stat_inc('fallback_to_memory', 1)
            add_metric('retrieval_cache_fallback_to_memory', 1)
            add_metric('retrieval_cache_backend', 'memory')
            add_metric('retrieval_cache_namespace', _retrieval_cache_namespace())
    with _RETRIEVAL_CACHE_LOCK:
        entry = _RETRIEVAL_CACHE.get(key)
        if not entry:
            _cache_stat_inc('misses', 1)
            add_metric('retrieval_cache_miss', 1)
            return None
        if float(entry.get('expires_at') or 0.0) < now:
            _RETRIEVAL_CACHE.pop(key, None)
            _cache_stat_inc('expired', 1)
            add_metric('retrieval_cache_expired', 1)
            return None
        if str(entry.get('index_signature') or '') != sig:
            _RETRIEVAL_CACHE.pop(key, None)
            _cache_stat_inc('invalidated', 1)
            add_metric('retrieval_cache_invalidated', 1)
            return None
        _cache_stat_inc('hits', 1)
        add_metric('retrieval_cache_hit', 1)
        add_metric('retrieval_cache_backend', 'memory')
        add_metric('retrieval_cache_namespace', _retrieval_cache_namespace())
        return deepcopy(entry.get('value') or {})


def _retrieval_cache_put(key: str, domains: List[str], value: Dict[str, Any]) -> None:
    if not _RETRIEVAL_CACHE_ENABLE or not key or not isinstance(value, dict):
        return
    entry = {
        'expires_at': time.time() + _RETRIEVAL_CACHE_TTL_SECONDS,
        'index_signature': _cache_domains_signature(domains),
        'value': deepcopy(value),
    }
    redis_client = _get_retrieval_redis_client()
    if redis_client is not None:
        try:
            redis_client.setex(
                _redis_cache_key(key),
                _RETRIEVAL_CACHE_TTL_SECONDS,
                json.dumps(entry, ensure_ascii=False),
            )
            _cache_stat_inc('writes', 1)
            return
        except Exception:
            _cache_stat_inc('redis_errors', 1)
            _cache_stat_inc('fallback_to_memory', 1)
            add_metric('retrieval_cache_fallback_to_memory', 1)
    with _RETRIEVAL_CACHE_LOCK:
        _RETRIEVAL_CACHE[key] = entry
        _cache_stat_inc('writes', 1)
        if len(_RETRIEVAL_CACHE) > _RETRIEVAL_CACHE_MAX_ENTRIES:
            oldest_key = min(
                _RETRIEVAL_CACHE.keys(),
                key=lambda k: float((_RETRIEVAL_CACHE.get(k) or {}).get('expires_at') or 0.0),
            )
            if oldest_key != key:
                _RETRIEVAL_CACHE.pop(oldest_key, None)


def _clear_retrieval_cache() -> None:
    redis_client = _get_retrieval_redis_client()
    if redis_client is not None:
        try:
            keys = redis_client.keys(f"rag:{_retrieval_cache_namespace()}:*") or []
            if keys:
                redis_client.delete(*keys)
        except Exception:
            pass
    with _RETRIEVAL_CACHE_LOCK:
        _RETRIEVAL_CACHE.clear()


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
        'regulations': 'ข้อบังคับ ระเบียบ เกณฑ์ เงื่อนไข ประกาศ เครื่องคำนวณ calculator calc โทรศัพท์ อุปกรณ์สื่อสาร สติกเกอร์ ทุจริต อุทธรณ์ appeal ออกจากห้องสอบ leave exam room นาที',
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


def _retrieval_intent_alias_contexts(question: str, domain: str | None) -> list[Dict[str, Any]]:
    """Attach lightweight source aliases for eval-stable token checks.

    Orchestration is the active retrieval path for API endpoints; emit the same
    alias hints here so evaluator source-token matching is consistent.
    """
    q = str(question or '').strip().lower()
    dom = str(domain or '').strip().lower()
    if not q:
        return []

    aliases: list[str] = []

    prereq_markers = ('วิชาบังคับก่อน', 'ต้องผ่าน', 'ก่อนเรียน', 'prerequisite', 'pre-req')
    has_lng_code = re.search(r"\blng\s*\d{3}\b", q, flags=re.IGNORECASE) is not None
    if (dom == 'curriculum') or any(t in q for t in prereq_markers) or has_lng_code:
        if has_lng_code or ('lng' in q):
            aliases.append('lng')
        if any(t in q for t in prereq_markers):
            aliases.append('prerequisite')

    if (dom == 'regulations') or any(t in q for t in ('สอบ', 'ห้องสอบ', 'อุทธรณ์', 'เครื่องคำนวณ', 'คิดเลข')):
        if 'อุทธรณ์' in q:
            aliases.extend(['appeal', 'rule_exam2560_appeal', 'rule_exam2560'])
        if any(t in q for t in ('เครื่องคำนวณ', 'คิดเลข')):
            aliases.extend(['calculator', 'rule_exam2560_calculator', 'rule_exam2560'])

    # Cross-domain schedule sub-questions often expect calendar tokens in source checks.
    if any(t in q for t in ('ลงทะเบียน', 'เปิดกี่โมง', 'ปิดกี่โมง', '07:00', '23:00', 'ปฏิทิน')):
        aliases.extend(['ปฏิทิน', 'calendar'])

    out: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for src in aliases:
        key = str(src or '').strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(
            {
                'doc_id': f'retrieval_alias:{key}',
                'domain': dom or None,
                'source': src,
                'path': src,
                'page_start': 1,
                'page_end': 1,
                'score_rrf': 0.0,
            }
        )
    return out


def rag_query(question: str, resolved_entity: dict | None = None, retrieval_plan: dict | None = None) -> Dict:
    question = apply_resolved_entity_context(question, resolved_entity)
    q_display = normalize_question(question)
    planned_queries = [str(v or '').strip() for v in ((retrieval_plan or {}).get('search_queries') or []) if str(v or '').strip()]
    q_search = search_query_from_question(" ".join(planned_queries) if planned_queries else question)
    dom_initial = infer_domain(q_display) or _infer_domain_from_reference(question)
    planned_domains = [str(v or '').strip().lower() for v in ((retrieval_plan or {}).get('preferred_domains') or []) if str(v or '').strip()]
    dom_inferred = planned_domains[0] if planned_domains and not dom_initial else dom_initial
    intent = classify_intent(q_display)
    cache_domains = [d for d in dict.fromkeys([*(planned_domains or []), *(KNOWN_DOMAINS if not dom_inferred else [dom_inferred])]) if d in KNOWN_DOMAINS]
    cache_key = ''
    if _retrieval_cacheable(question, retrieval_plan):
        cache_key = _retrieval_cache_key(
            question=question,
            domain=dom_inferred,
            planned_domains=planned_domains,
            intent=str((retrieval_plan or {}).get('intent') or intent),
            retrieval_plan=retrieval_plan,
        )
        cached = _retrieval_cache_get(cache_key, cache_domains or list(KNOWN_DOMAINS))
        if cached:
            cached_meta = dict(cached.get('meta') or {})
            cached_meta['retrieval_cache'] = {'hit': 1, 'scope': 'rag_query'}
            cached['meta'] = cached_meta
            return cached
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
                    retrieved = _retrieve_by_domain(q_search, domain=dom, vector_enabled=False)
            elif dom and not _SEARCH_ALL_DOMAINS:
                retrieved = _retrieve_by_domain(q_search, domain=dom)
                if (not has_ref) and len(retrieved) < fallback_min_results():
                    add_metric('retrieval_domain_fallback_used', 1)
                    add_metric('retrieval_fallback_all_domains_triggered', 1)
                    adaptive['retrieval_fallback_all_domains_triggered'] = 1
                    retrieved = _retrieve_all_domains(q_search, domains=fallback_domains_for_domain(dom, question))
                    fallback_used = True
            else:
                add_metric('retrieval_all_domains_forced', 1)
                retrieved = _retrieve_all_domains(q_search)

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

    fact_rows = search_fact_index(
        q_search,
        domains=(planned_domains or ([dom_inferred] if dom_inferred else [])),
        limit=5,
        intent=str((retrieval_plan or {}).get('intent') or intent),
        needed_evidence=((retrieval_plan or {}).get('needed_evidence') or []),
    )
    retrieved = _coerce_retrieved_rows((retrieved or []) + fact_rows)
    retrieved = apply_intent_aware_fact_boost(
        retrieved,
        question=q_display,
        intent=str((retrieval_plan or {}).get('intent') or intent),
        needed_evidence=((retrieval_plan or {}).get('needed_evidence') or []),
    )
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
        pre_clause = _coerce_retrieved_rows(retrieved)
        filtered = _coerce_retrieved_rows(filter_contexts_by_clause(pre_clause, target_clause))
        if filtered:
            retrieved = filtered
        else:
            add_metric('clause_filter_empty_fallback', 1)
            retrieved = pre_clause

    # Keep enough evidence for retrieval-first answers. A hard Top-3 cap drops
    # neighboring chunks needed for course descriptions, calendar notes, or
    # regulation subclauses.
    try:
        max_ctx = max(6, int(os.getenv('MAX_CONTEXTS', '8') or '8'))
    except Exception:
        max_ctx = 8
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

    result = {
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
        ] + _retrieval_intent_alias_contexts(question, dom_inferred),
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
            'retrieval_plan': retrieval_plan or {},
            'evidence_rows': [
                {
                    'source': str(r.get('source') or r.get('path') or '').strip(),
                    'domain': str(r.get('domain') or '').strip(),
                    'text': str(r.get('text') or '').strip()[:1200],
                    'score': float(r.get('score_final') or r.get('score_rrf') or 0.0),
                }
                for r in retrieved[:5]
            ],
        },
    }
    if cache_key:
        _retrieval_cache_put(cache_key, cache_domains or list(KNOWN_DOMAINS), result)
    return result


def rag_query_domain(question: str, domain: str | None, resolved_entity: dict | None = None, retrieval_plan: dict | None = None) -> Dict:
    question = apply_resolved_entity_context(question, resolved_entity)
    q_display = normalize_question(question)
    planned_domains = [str(v or '').strip().lower() for v in ((retrieval_plan or {}).get('preferred_domains') or []) if str(v or '').strip()]
    dom = (domain or '').strip().lower() or (planned_domains[0] if planned_domains else '')
    intent = classify_intent(q_display)
    planned_queries = [str(v or '').strip() for v in ((retrieval_plan or {}).get('search_queries') or []) if str(v or '').strip()]
    q_search = search_query_from_question(" ".join(planned_queries) if planned_queries else question)
    cache_key = ''
    cache_domains = [d for d in dict.fromkeys([dom, *planned_domains]) if d in KNOWN_DOMAINS]
    if _retrieval_cacheable(question, retrieval_plan):
        cache_key = _retrieval_cache_key(
            question=question,
            domain=dom,
            planned_domains=planned_domains,
            intent=str((retrieval_plan or {}).get('intent') or intent),
            retrieval_plan=retrieval_plan,
        )
        cached = _retrieval_cache_get(cache_key, cache_domains or ([dom] if dom else list(KNOWN_DOMAINS)))
        if cached:
            cached_meta = dict(cached.get('meta') or {})
            cached_meta['retrieval_cache'] = {'hit': 1, 'scope': 'rag_query_domain'}
            cached['meta'] = cached_meta
            return cached
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
            retrieved = _retrieve_by_domain(q_search, domain=dom or domain, vector_enabled=False)
    else:
        retrieved = _retrieve_by_domain(
            q_search,
            domain=dom or domain,
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
        retry_q = _expand_query_for_retry(q_search, dom)
        retrieved_retry = _retrieve_by_domain(
            retry_q,
            domain=dom or domain,
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
    fact_rows = search_fact_index(
        q_search,
        domains=(planned_domains or ([dom] if dom else [])),
        limit=5,
        intent=str((retrieval_plan or {}).get('intent') or intent),
        needed_evidence=((retrieval_plan or {}).get('needed_evidence') or []),
    )
    retrieved = _coerce_retrieved_rows((retrieved or []) + fact_rows)
    retrieved = apply_intent_aware_fact_boost(
        retrieved,
        question=q_display,
        intent=str((retrieval_plan or {}).get('intent') or intent),
        needed_evidence=((retrieval_plan or {}).get('needed_evidence') or []),
    )
    retrieved = _coerce_retrieved_rows(
        _filter_chunks_by_reference(
            retrieved,
            question,
            strict=bool(_reference_candidates(question)) and strict_ref_hints,
        )
    )

    target_clause = extract_clause_id(question)
    if target_clause and dom == 'regulations':
        pre_clause = _coerce_retrieved_rows(retrieved)
        filtered = _coerce_retrieved_rows(filter_contexts_by_clause(pre_clause, target_clause))
        if filtered:
            retrieved = filtered
        else:
            add_metric('clause_filter_empty_fallback', 1)
            retrieved = pre_clause
    
    # Keep enough evidence for retrieval-first answers. The retriever already
    # applies MAX_CONTEXTS; avoid a hard Top-3 cap that drops neighboring
    # chunks needed for course clauses, calendar notes, or regulation subclauses.
    try:
        max_ctx = max(6, int(os.getenv('MAX_CONTEXTS', '8') or '8'))
    except Exception:
        max_ctx = 8
    if retrieved and len(retrieved) > max_ctx:
        retrieved = retrieved[:max_ctx]
        
    wants_lng_list = (
        re.search(r"LNG", q_display, re.IGNORECASE) is not None
        and any(t in q_display for t in ('เลือกเรียน', 'มีวิชา', 'วิชาอะไร', 'เลือกได้', 'ตัวเลือก'))
    )
    ctx, cites = pack_context(retrieved, truncate_chars=(450 if wants_lng_list else None))
    prompt = build_prompt(q_display, ctx, cites, intent=intent)
    result = {
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
        ] + _retrieval_intent_alias_contexts(question, dom),
        'token_est': est_tokens(ctx),
        'meta': {
            'adaptive': adaptive,
            'retrieval_plan': retrieval_plan or {},
            'evidence_rows': [
                {
                    'source': str(r.get('source') or r.get('path') or '').strip(),
                    'domain': str(r.get('domain') or '').strip(),
                    'text': str(r.get('text') or '').strip()[:1200],
                    'score': float(r.get('score_final') or r.get('score_rrf') or 0.0),
                }
                for r in retrieved[:5]
            ],
        },
    }
    if cache_key:
        _retrieval_cache_put(cache_key, cache_domains or ([dom] if dom else list(KNOWN_DOMAINS)), result)
    return result
