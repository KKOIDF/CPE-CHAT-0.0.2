import os
import json
import re
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Optional, List, Tuple

from .normalization import normalize_question, search_query_from_question, extract_lexical_anchors
from .routing import (
    decompose_question,
    infer_domain,
    is_multi_doc_question,
    fallback_domains_for_domain,
    fallback_min_results,
    _reference_candidates,
    _filter_chunks_by_reference,
)
from .retrieval import retrieve_by_domain, retrieve_all_domains, retrieve_multi_document
from .context_packing import pack_context, pack_context_grouped, est_tokens
from .prompting import build_prompt
from .perf import time_block, add_metric
from .config import RRF_K, MAX_CONTEXTS, RAG_RESPONSE_PROFILE, RAG_FAST_MAX_CONTEXTS
from .llm import generate_text
from .chroma_client import embed_texts, semantic_search_domain, fetch_embeddings_for_docs
from .neo4j_client import extract_course_codes
from .rerank import fuse_rrf_lists


_SYSTEM_MSG: dict[str, str] = {
    'role': 'system',
    'content': (
        'คุณคือผู้ช่วยของภาควิชาวิศวกรรมคอมพิวเตอร์ '
        'ใช้เฉพาะข้อมูลในบริบทเท่านั้น ตอบโดยตรงและชัดเจน '
        'ห้ามให้ลิงก์/URL ภายนอก เว้นแต่ปรากฏอยู่ในบริบท '
        'หากคำถามกำกวมให้ถามกลับ 1 คำถามสั้น ๆ เพื่อขอรายละเอียดที่จำเป็น '
        'หากไม่พบคำตอบแบบชัดเจน ให้สรุปเท่าที่สรุปได้จากบริบท และระบุว่าเอกสารไม่ได้กล่าวตรง ๆ '
        'หรือไม่มีข้อความยืนยันโดยตรง'
    ),
}

_MULTIQUERY_ENABLE = os.getenv('RAG_LC_MULTIQUERY', '0') in ('1', 'true', 'True')
_MULTIQUERY_N = int(os.getenv('RAG_LC_MULTIQUERY_N', '1') or '1')
_MULTIQUERY_ALL = os.getenv('RAG_LC_MULTIQUERY_ALL', '0') in ('1', 'true', 'True')

_PARALLEL_ENABLE = os.getenv('RAG_LC_PARALLEL', '1') in ('1', 'true', 'True')
_PARALLEL_WORKERS = int(os.getenv('RAG_LC_PARALLEL_WORKERS', '4') or '4')

_RERANK_ENABLE = os.getenv('RAG_LC_RERANK', '1') in ('1', 'true', 'True')
_RERANK_TOPN = int(os.getenv('RAG_LC_RERANK_TOPN', '24') or '24')
_RERANK_ALL = os.getenv('RAG_LC_RERANK_ALL', '1') in ('1', 'true', 'True')

_RERANK_SKIP_HIGH_CONF = os.getenv('RAG_LC_RERANK_SKIP_HIGH_CONF', '1') in ('1', 'true', 'True')
try:
    _RERANK_SKIP_HIGH_CONF_THRESHOLD = float(os.getenv('RAG_LC_RERANK_SKIP_HIGH_CONF_THRESHOLD', '0.18') or '0.18')
except Exception:
    _RERANK_SKIP_HIGH_CONF_THRESHOLD = 0.18
try:
    _RERANK_MIN_DOCS = max(2, int(os.getenv('RAG_LC_RERANK_MIN_DOCS', '10') or '10'))
except Exception:
    _RERANK_MIN_DOCS = 10

_MULTIQUERY_FOR_ANCHORED = os.getenv('RAG_LC_MULTIQUERY_FOR_ANCHORED', '0') in ('1', 'true', 'True')

_COMPRESS_ENABLE = os.getenv('RAG_LC_COMPRESS', '1') in ('1', 'true', 'True')
_COMPRESS_MAX_CHARS = int(os.getenv('RAG_LC_COMPRESS_MAX_CHARS', '700') or '700')
_COMPRESS_ALL = os.getenv('RAG_LC_COMPRESS_ALL', '1') in ('1', 'true', 'True')

_ROUTE_LLM_ENABLE = os.getenv('RAG_LC_ROUTE_LLM', '0') in ('1', 'true', 'True')

_STRUCTURED_ENABLE = os.getenv('RAG_LC_STRUCTURED', '0') in ('1', 'true', 'True')

_ENFORCE_CITATIONS = os.getenv('RAG_LC_ENFORCE_CITATIONS', '1') in ('1', 'true', 'True')
_SEARCH_ALL_DOMAINS = os.getenv('RAG_SEARCH_ALL_DOMAINS', '1') in ('1', 'true', 'True')
_ADAPTIVE_ORCHESTRATION = (os.getenv('RAG_ADAPTIVE_ORCHESTRATION', '1') or '1').strip().lower() in (
    '1', 'true', 'yes', 'on'
)
_FAST_PROFILE = RAG_RESPONSE_PROFILE == 'fast'
try:
    _LOW_SCORE_THRESHOLD = float(os.getenv('RAG_ADAPTIVE_LOW_SCORE', '0.06') or '0.06')
except Exception:
    _LOW_SCORE_THRESHOLD = 0.06
try:
    _MIN_DOCS_FOR_CONFIDENT = max(1, int(os.getenv('RAG_ADAPTIVE_MIN_DOCS', '2') or '2'))
except Exception:
    _MIN_DOCS_FOR_CONFIDENT = 2


def _boost_regulations_for_exam_intent(items: List[Dict], question: str) -> List[Dict]:
    ql = (question or '').strip().lower()
    exam_core = any(t in ql for t in ('สอบ', 'ห้องสอบ', 'คุมสอบ', 'มาสาย', 'ทุจริต', 'อุทธรณ์', 'ออกจากห้องสอบ', 'สอบไม่ผ่าน', 'สอบตก'))
    policy_shape = any(t in ql for t in ('ได้กี่', 'กี่นาที', 'กี่วัน', 'ระเบียบ', 'ข้อ', 'นโยบาย', 'อนุญาต', 'ขั้นตอน', 'ทำได้หรือไม่ได้', 'ต้องทำอย่างไร', 'ดำเนินการต่อ'))
    exam_policy_intent = (
        exam_core and policy_shape
    )
    if not exam_policy_intent or not items:
        return items

    boosted: List[Dict] = []
    for d in items:
        u = dict(d)
        dom = str(u.get('domain') or '').strip().lower()
        src = str(u.get('source') or '').strip().lower()
        score = float(u.get('score_rrf') or 0.0)
        if dom == 'regulations':
            score += 0.35
        if ('rule_exam' in src) or ('สอบ' in src and 'ระเบียบ' in src):
            score += 0.70
        if 'regulation' in src:
            score += 0.18
        if ('ออกจากห้องสอบ' in ql or 'ชั่วคราว' in ql) and ('ข้อ 12' in src or 'rule_exam' in src):
            score += 0.35
        if ('สอบไม่ผ่าน' in ql or 'สอบตก' in ql) and ('rule_exam' in src or 'regulation' in src):
            score += 0.28
        if src.endswith('forms.txt'):
            score -= 0.20
        if dom == 'curriculum':
            score -= 0.20
        if dom == 'announcements':
            score -= 0.12
        u['score_rrf'] = score
        boosted.append(u)

    boosted.sort(key=lambda x: float(x.get('score_rrf') or 0.0), reverse=True)
    return boosted


def _inject_exam_rule_anchors(items: List[Dict], question: str, cap: int) -> List[Dict]:
    ql = (question or '').strip().lower()
    exam_late_intent = (
        ('สอบ' in ql or 'ห้องสอบ' in ql)
        and ('มาสาย' in ql or 'สาย' in ql or 'เข้าห้องสอบ' in ql)
    )
    exam_temp_leave_intent = (
        ('สอบ' in ql or 'ห้องสอบ' in ql)
        and ('ออกจากห้องสอบ' in ql or 'ชั่วคราว' in ql)
    )
    exam_fail_intent = (
        ('สอบไม่ผ่าน' in ql or 'สอบตก' in ql)
        and any(t in ql for t in ('ทำอย่างไร', 'ทำยังไง', 'ดำเนินการ', 'ต่อ', 'ยื่น', 'แก้'))
    )
    if (not (exam_late_intent or exam_temp_leave_intent or exam_fail_intent)) or (not items):
        return items[:cap]

    anchor_query = 'ข้อสอบ ระเบียบการสอบ rule_exam regulation ออกจากห้องสอบชั่วคราว สอบไม่ผ่าน สอบตก'
    if exam_late_intent:
        anchor_query = 'ข้อ 12 ห้องสอบ มาสาย สิบห้านาที 15 หกสิบนาที 60 ระเบียบการสอบ rule_exam regulation'
    elif exam_temp_leave_intent:
        anchor_query = 'ข้อ 12 ออกจากห้องสอบชั่วคราว ระหว่างสอบ อนุญาต ระเบียบการสอบ rule_exam regulation'
    elif exam_fail_intent:
        anchor_query = 'สอบไม่ผ่าน สอบตก ขั้นตอน ดำเนินการต่อ ระเบียบการสอบ rule_exam regulation'

    try:
        regs = semantic_search_domain(
            anchor_query,
            top_k=40,
            domain='regulations',
            source_allowlist=None,
        )
    except Exception:
        return items[:cap]
    if not regs:
        return items[:cap]

    anchors: List[Dict] = []
    for d in regs:
        src = str(d.get('source') or '').strip().lower()
        txt = str(d.get('text') or '')
        if ('rule_exam' in src) or ('regulation' in src):
            anchors.append(d)
            if len(anchors) >= 2:
                break
        if exam_late_intent and ('ข้อ 12' in txt and 'ห้องสอบ' in txt and ('สิบห้านาที' in txt or '15' in txt)):
            anchors.append(d)
            if len(anchors) >= 2:
                break
        if exam_temp_leave_intent and ('ออกจากห้องสอบ' in txt or 'ชั่วคราว' in txt):
            anchors.append(d)
            if len(anchors) >= 2:
                break
        if exam_fail_intent and ('สอบไม่ผ่าน' in txt or 'สอบตก' in txt):
            anchors.append(d)
            if len(anchors) >= 2:
                break
    if not anchors:
        return items[:cap]

    out: List[Dict] = []
    seen: set[str] = set()
    for d in [*anchors, *items]:
        did = d.get('doc_id')
        key = str(did) if did is not None else f"{d.get('source')}::{len(out)}"
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
        if len(out) >= cap:
            break
    return out


def _extract_citations_from_text(answer: str) -> List[str]:
    cites: List[str] = []
    for m in re.finditer(r"\[([^\[\]]+?)\]", answer or ''):
        c = (m.group(1) or '').strip()
        if c:
            cites.append(c)
    return cites


def _ensure_bullet_has_cite(line: str, fallback_cite: str) -> str:
    s = (line or '').rstrip()
    if not s.strip().startswith('- '):
        return s
    # If the line already contains at least one [..] citation, keep as-is.
    if re.search(r"\[[^\[\]]+\]", s):
        return s
    if not fallback_cite:
        return s
    return f"{s} [{fallback_cite}]"


def _enforce_citations(answer: str, allowed_cites: List[str]) -> str:
    if not answer or not allowed_cites:
        return answer
    fallback = (allowed_cites[0] or '').strip()
    if not fallback:
        return answer
    lines = (answer or '').splitlines()
    out_lines: List[str] = []
    for ln in lines:
        out_lines.append(_ensure_bullet_has_cite(ln, fallback))
    return "\n".join(out_lines).strip()


def _parse_query_list(raw: str) -> List[str]:
    """Parse LLM output into a compact list of query strings."""
    txt = (raw or '').strip()
    if not txt:
        return []

    # Try JSON array first.
    try:
        # Some models wrap JSON in extra text; try to extract the first [...] block.
        m = re.search(r"\[[\s\S]*\]", txt)
        candidate = m.group(0) if m else txt
        data = json.loads(candidate)
        if isinstance(data, list):
            out: List[str] = []
            for x in data:
                if isinstance(x, str) and x.strip():
                    out.append(x.strip())
            return out
    except Exception:
        pass

    # Fallback: lines like "- ..." or "1) ..."
    items: List[str] = []
    for ln in txt.splitlines():
        s = (ln or '').strip()
        if not s:
            continue
        s = re.sub(r"^[-•\*]+\s+", "", s)
        s = re.sub(r"^\d+[\.)]\s+", "", s)
        if s:
            items.append(s)
    return items


def _dedupe_keep_order(items: List[str], cap: int) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for it in items:
        s = (it or '').strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= cap:
            break
    return out


def _multiquery_variants(question_display: str, base_query: str, domain: str | None) -> List[str]:
    """Generate retrieval queries (best-effort).

    If LLM is disabled/unavailable, returns [] and the caller should fall back.
    """
    if not _MULTIQUERY_ENABLE:
        return []
    n = max(0, min(6, int(_MULTIQUERY_N)))
    if n <= 0:
        return []

    dom = (domain or '').strip().lower() or 'auto'
    prompt = (
        "สร้างคำค้น (search query) ทางเลือกเพื่อค้นหาเอกสารที่เกี่ยวข้องกับคำถามนี้ ให้มีความหลากหลายแต่ยังเกี่ยวข้อง\n"
        f"คำถาม: {question_display}\n"
        f"คำค้นตั้งต้น: {base_query}\n"
        f"โดเมน (ถ้าทราบ): {dom}\n\n"
        f"ขอ {n} คำค้นใหม่ โดย:\n"
        "- ต้องสั้น กระชับ เหมาะกับค้นหาในเอกสาร\n"
        "- คงคำสำคัญ (เช่น รหัสวิชา, ปี พ.ศ., คำเฉพาะ)\n"
        "- อนุญาตให้เติมคำอังกฤษในวงเล็บเพื่อช่วย recall ได้\n\n"
        "ตอบกลับเป็น JSON array ของ string เท่านั้น เช่น [\"...\", \"...\"]"
    )

    raw = generate_text(prompt, task='multiquery')
    if not raw or raw.strip().startswith('('):
        return []
    candidates = _parse_query_list(raw)
    # Clean: drop extremely long lines
    candidates = [c for c in candidates if 2 <= len(c) <= 180]
    return _dedupe_keep_order(candidates, cap=n)


def _safe_json_obj(raw: str) -> Optional[Dict[str, Any]]:
    txt = (raw or '').strip()
    if not txt:
        return None
    # Try to extract the first {...} block if the model wrapped it.
    try:
        m = re.search(r"\{[\s\S]*\}", txt)
        candidate = m.group(0) if m else txt
        data = json.loads(candidate)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _route_domain_llm(question_display: str) -> Optional[str]:
    if not _ROUTE_LLM_ENABLE:
        return None
    prompt = (
        "คุณเป็นตัวจัดเส้นทางโดเมนเอกสารให้ระบบ RAG\n"
        "เลือกโดเมนที่เหมาะสมที่สุดสำหรับคำถามนี้ จากรายการ: announcements, regulations, curriculum, auto\n"
        "- announcements: ข่าว/ประกาศ/ปฏิทิน/กำหนดการ\n"
        "- regulations: ระเบียบ/ข้อบังคับ/คำร้อง/วินัย\n"
        "- curriculum: หลักสูตร/รายวิชา/หน่วยกิต/รหัสวิชา\n"
        "- auto: ถ้าไม่แน่ใจหรือข้ามโดเมน\n\n"
        f"คำถาม: {question_display}\n\n"
        "ตอบเป็น JSON เท่านั้น เช่น {\"domain\":\"curriculum\",\"confidence\":0.7}"
    )
    raw = generate_text(prompt, task='routing')
    if not raw or raw.strip().startswith('('):
        return None
    obj = _safe_json_obj(raw)
    if not obj:
        return None
    dom = str(obj.get('domain') or '').strip().lower()
    if dom in ('announcements', 'regulations', 'curriculum'):
        return dom
    return None


def _compress_text_extractive(query: str, text: str, max_chars: int) -> str:
    """Cheap, deterministic compression for context packing.

    Goal: keep only likely-relevant lines/sentences to fit token budget.
    """
    q = (query or '').strip()
    t = (text or '').strip()
    if not t:
        return ''
    if not q or max_chars <= 0:
        return t[: max(0, max_chars)]

    # Keywords: keep longer tokens + course codes.
    # Note: Thai phrases in questions often include particles like 'ของ' (e.g., 'ภาระงานสอนของ')
    # while the source text uses a different form (e.g., 'ภาระงานสอนในปัจจุบัน').
    # To avoid losing the actual course list, we add a few robust anchors and also keep
    # course-code lines when the question asks about teaching load / course lists.
    raw_toks = re.findall(r"[A-Za-z]{2,6}\s*\d{3}|[A-Za-z]{2,6}|[\u0E00-\u0E7F]{2,}", q)
    toks: list[str] = []
    seen: set[str] = set()

    def _add(tok: str) -> None:
        t2 = (tok or '').strip()
        if len(t2) < 2:
            return
        if t2 in seen:
            return
        toks.append(t2)
        seen.add(t2)

    # Basic tokens (in order)
    for rt in raw_toks:
        _add(rt)

        # Thai sub-token robustness: keep shorter prefix/suffix slices and strip a couple
        # common trailing particles.
        if re.search(r"[\u0E00-\u0E7F]", rt or ''):
            s = (rt or '').strip()
            if len(s) >= 6:
                _add(s[:6])
                _add(s[-6:])
            if s.endswith('ของ') and len(s) > 2:
                _add(s[:-2])
            if s.endswith('ใน') and len(s) > 2:
                _add(s[:-1])

    # When users ask to list taught courses / teaching load, keep course-code lines.
    wants_course_list = any(k in q for k in ('รายวิชา', 'วิชาอะไร', 'วิชาอะไรบ้าง', 'ภาระงานสอน', 'สอน'))
    if wants_course_list:
        for extra in ('ภาระงานสอน', 'รายวิชา', 'หน่วยกิต', 'ระดับปริญญาตรี', 'ระดับบัณฑิตศึกษา'):
            if extra in q or extra in t:
                _add(extra)

    # Cap for safety.
    toks = toks[:24]

    course_code_re = re.compile(r"\b[A-Za-z]{2,6}\s*\d{3}\b")

    lines: List[str] = []
    for ln in t.splitlines():
        s = (ln or '').strip()
        if not s:
            continue
        if any(k in s for k in toks) or (wants_course_list and course_code_re.search(s) is not None):
            lines.append(s)
        if sum(len(x) for x in lines) >= max_chars:
            break

    if not lines:
        return t[:max_chars]

    out = "\n".join(lines).strip()
    if len(out) > max_chars:
        out = out[:max_chars].rstrip() + ' ...'
    return out


def _rerank_by_embedding(query: str, items: List[Dict], topn: int) -> List[Dict]:
    if not items:
        return []
    n = max(0, min(len(items), int(topn)))
    if n <= 0:
        return items

    head = items[:n]
    tail = items[n:]

    add_metric('top_k_rerank_n_docs', n)
    add_metric('top_k_rerank_mode', 'embedding_only')

    # Min fraction of docs that must have embeddings to proceed with rerank.
    # Below this threshold we skip rerank entirely (avoids CPU re-embedding cost).
    _RERANK_MIN_COVERAGE = float(os.getenv('RAG_RERANK_MIN_COVERAGE', '0.5') or '0.5')

    with time_block('embedding_fetch_ms'):
        qvec = embed_texts([query], is_query=True)[0]

        dvecs: List = [None] * len(head)
        cached_count = 0
        missing_indices: List[int] = []

        for i, d in enumerate(head):
            emb = d.get('embedding')
            if emb is not None:
                dvecs[i] = emb
                cached_count += 1
            else:
                missing_indices.append(i)

        missing_n = len(missing_indices)
        add_metric('top_k_rerank_used_cached_embeddings', cached_count)
        add_metric('embedding_fetch_requested_n', n)
        add_metric('embedding_fetch_returned_n', cached_count)
        add_metric('embedding_fetch_missing_n', missing_n)
        # embedding_fetch_chroma_calls is logged by the caller after fetch_embeddings_for_docs() returns.
        if n > 0:
            add_metric('top_k_rerank_cache_hit_ratio', cached_count / float(n))

        # ── Guard: skip rerank if coverage is too low ──────────────────────────
        # Avoids triggering CPU re-embedding of BGE-M3 which costs ~40s/doc.
        coverage = cached_count / float(n) if n > 0 else 0.0
        if coverage < _RERANK_MIN_COVERAGE:
            add_metric('top_k_rerank_skipped_low_coverage', 1)
            add_metric('top_k_rerank_coverage', round(coverage, 3))
            return items  # return original ranking unchanged

        # ── Score only docs that have embeddings; leave missing ones at 0.0 ────
        # DO NOT call embed_texts() here — that would run BGE-M3 on CPU (~88s).

    with time_block('embedding_deserialize_ms'):
        scored: List[Dict] = []

    with time_block('embedding_score_ms'):
        for d, v in zip(head, dvecs):
            # embed_texts already normalizes; dot product is cosine.
            # v may be None if Chroma had no embedding for this doc
            # (but coverage was still above threshold for other docs).
            s = 0.0
            if v is not None:
                try:
                    s = float(sum(float(a) * float(b) for a, b in zip(qvec, v)))
                    if math.isnan(s) or math.isinf(s):
                        s = 0.0
                except Exception:
                    s = 0.0
            scored.append({**d, 'score_rerank': s})

        scored.sort(key=lambda x: (x.get('score_rerank', 0.0), x.get('score_rrf', 0.0)), reverse=True)
        
    return scored + tail


def _fuse_rrf(lists: List[Tuple[str, List[Dict]]], cap: int) -> List[Dict]:
    """Fuse multiple ranked lists via Reciprocal Rank Fusion."""
    ranked_lists = [items for _q, items in (lists or [])]
    merged = fuse_rrf_lists(ranked_lists, k=RRF_K)
    return merged[:cap]


def _top_retrieval_score(items: List[Dict]) -> float:
    top = 0.0
    for it in (items or []):
        try:
            s = float(it.get('score_final') or it.get('score_rrf') or 0.0)
        except Exception:
            s = 0.0
        if s > top:
            top = s
    return top


def _is_low_confidence(items: List[Dict]) -> bool:
    if len(items or []) < _MIN_DOCS_FOR_CONFIDENT:
        return True
    return _top_retrieval_score(items) < _LOW_SCORE_THRESHOLD


def _has_precision_anchors(question: str) -> bool:
    q = (question or '').strip()
    if not q:
        return False
    if bool(re.search(r"\b[a-z]{2,6}\s*[- ]?\s*\d{3}\b", q, flags=re.IGNORECASE)):
        return True
    if bool(re.search(r"ข้อ\s*[๐-๙0-9]+(?:\.[๐-๙0-9]+)?", q)):
        return True
    return False


def _expand_query_for_retry(question: str, domain: str | None) -> str:
    q = (question or '').strip()
    dom = (domain or '').strip().lower()
    if not q:
        return q

    dom_hints = {
        'curriculum': 'รายวิชา course code หน่วยกิต วิชาบังคับก่อน ปีที่ ภาคการศึกษา',
        'regulations': 'ข้อบังคับ ระเบียบการสอบ regulation rule_exam เกณฑ์ เงื่อนไข ประกาศ เครื่องคำนวณ calculator calc อุทธรณ์ appeal ออกจากห้องสอบชั่วคราว leave exam room สอบไม่ผ่าน สอบตก ขั้นตอน ดำเนินการต่อ นาที',
        'announcements': 'ประกาศ กำหนดการ วันเวลา หมายเหตุ',
    }
    hints = dom_hints.get(dom, 'รายละเอียด เงื่อนไข เอกสารอ้างอิง')
    subqs = decompose_question(q, max_parts=2)
    if subqs:
        q = f"{q} {' '.join(subqs)}"
    return f"{q} {hints}".strip()


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
    return exam_late_anchor


def _is_curriculum_group_list_query(question: str) -> bool:
    q = normalize_question(question or '')
    if not q:
        return False
    if not any(t in q for t in ('วิชาบังคับ', 'วิชาบังครับ', 'วิชาชีพบังคับ', 'วิชาเลือก')):
        return False
    return any(t in q for t in ('มีอะไร', 'อะไรบ้าง', 'ทั้งหมด', 'กี่ตัว', 'กี่วิชา', 'รายวิชา', 'หมวด', 'คือวิชา', 'วิชาอะไร'))


def _has_contexts_from_domain(items: List[Dict], domain: str | None) -> bool:
    dom = (domain or '').strip().lower()
    if not dom:
        return False
    for item in items or []:
        if str(item.get('domain') or '').strip().lower() == dom:
            return True
    return False


def _should_preserve_domain_retrieval(question: str, domain: str | None, items: List[Dict]) -> bool:
    dom = (domain or '').strip().lower()
    rows = list(items or [])
    if not dom or not rows:
        return False
    if _has_contexts_from_domain(rows, dom):
        return True
    if dom == 'regulations' and _is_anchored_regulations_query(question, dom):
        return True
    if dom == 'curriculum' and _is_curriculum_group_list_query(question):
        return True
    return False


def _is_announcement_temporal_query(question: str, domain: str | None) -> bool:
    dom = (domain or '').strip().lower()
    if dom != 'announcements':
        return False
    q = (question or '').strip().lower()
    if not q:
        return False
    temporal_tokens = (
        'กำหนดการ', 'ปฏิทิน', 'วัน', 'วันที่', 'ช่วงวัน', 'ช่วงเวลา',
        'deadline', 'calendar', 'schedule', 'ลงทะเบียน', 'ชำระเงิน',
        'เปิดระบบ', 'ปิดระบบ', 'โมดูล', 'สัปดาห์',
    )
    return any(t in q for t in temporal_tokens)


def _normalize_code_text(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", (text or '').upper())


def _meta_get(item: Dict[str, Any], key: str):
    if key in item:
        return item.get(key)
    md = item.get('metadata') or {}
    if isinstance(md, dict):
        return md.get(key)
    return None


def _section_path_values(item: Dict[str, Any]) -> List[str]:
    raw = _meta_get(item, 'section_path')
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except Exception:
            pass
        return [s]
    return []


def _is_faculty_course_relation(item: Dict[str, Any]) -> bool:
    dt = str(_meta_get(item, 'doc_type') or '').strip().lower()
    if dt == 'faculty_course_relation':
        return True
    sec = str(_meta_get(item, 'section') or '').strip().lower()
    if sec == 'facultycourserelation':
        return True
    section_path = '/'.join(_section_path_values(item)).lower()
    return 'facultycourserelation' in section_path


def _item_matches_course_codes(item: Dict[str, Any], target_codes: set[str]) -> bool:
    if not target_codes:
        return False
    candidates: List[str] = []
    for k in ('course_code', 'course', 'course_id'):
        v = _meta_get(item, k)
        if v is not None:
            candidates.append(str(v))
    candidates.extend(_section_path_values(item))
    txt = item.get('text')
    if isinstance(txt, str) and txt:
        candidates.append(txt[:240])

    for c in candidates:
        norm = _normalize_code_text(c)
        if not norm:
            continue
        for t in target_codes:
            if t and (t == norm or t in norm):
                return True
    return False


def _boost_faculty_relation_for_teacher_intent(
    items: List[Dict[str, Any]],
    question_display: str,
    domain: Optional[str],
) -> List[Dict[str, Any]]:
    if (domain or '').strip().lower() != 'curriculum' or not items:
        return items

    q = (question_display or '')
    ql = q.lower()
    codes = {_normalize_code_text(c) for c in extract_course_codes(q) if _normalize_code_text(c)}
    teacher_markers = (
        'ใครสอน',
        'ผู้สอน',
        'อาจารย์',
        'สอนวิชา',
        'คนสอน',
        'ผู้รับผิดชอบวิชา',
        'instructor',
        'teacher',
        'teaches',
    )
    if not codes or not any(m in ql for m in teacher_markers):
        return items

    try:
        boost = float(os.getenv('RAG_LC_FACULTY_RELATION_BOOST', os.getenv('RAG_FACULTY_RELATION_BOOST', '1.2')) or '1.2')
    except Exception:
        boost = 1.2

    boosted: List[Dict[str, Any]] = []
    for d in items:
        score = float(d.get('score_rrf') or 0.0)
        if _is_faculty_course_relation(d) and _item_matches_course_codes(d, codes):
            score += boost
        boosted.append({**d, 'score_rrf': score})

    boosted.sort(key=lambda x: float(x.get('score_rrf') or 0.0), reverse=True)
    return boosted


def rag_answer_langchain(question: str, domain: Optional[str] = None, requested_model: str = '') -> Dict[str, Any]:
    """End-to-end RAG using LangChain (LCEL) for orchestration.

    Returns the same shape as the legacy endpoint:
    { question, prompt, answer, contexts, token_est }

    Retrieval intentionally reuses the repo's tuned hybrid logic to keep quality.
    """
    built = _build_rag_prompt_langchain(question=question, domain=domain)
    q_display = built['q_display']
    retrieved = built['retrieved']
    ctx = built['ctx']
    cites = built['cites']
    prompt = built['prompt']
    meta = built.get('meta')

    if _STRUCTURED_ENABLE:
        prompt = (
            f"{prompt}\n\n"
            "ตอบกลับเป็น JSON object เท่านั้น (ห้ามมีข้อความอื่น) โดยมีคีย์:\n"
            "- answer: string (คำตอบเป็น bullet ภาษาไทย)\n"
            "- follow_up_question: string (ถ้าคำถามกำกวมให้ถามกลับ 1 คำถามสั้น ๆ; ถ้าไม่ต้องถามให้เป็น \"\")\n"
            "- citations: array of string (รายการ [source/page] ที่คุณใช้จริงในคำตอบ; ต้องเป็น subset ของรายการที่อนุญาต)\n"
            "ตัวอย่าง: {\"answer\":\"- ... [file/1]\",\"follow_up_question\":\"\",\"citations\":[\"file/1\"]}"
        )

    # If no context, leave answer blank for the caller to apply hard guardrails.
    answer = ''
    structured: Optional[Dict[str, Any]] = None
    follow_up_question = ''
    if retrieved:
        from .llm import LLMTimeoutError
        user_msg = {'role': 'user', 'content': prompt}
        try:
            raw = generate_text(
                prompt,
                messages=[_SYSTEM_MSG, user_msg],
                task='answer',
                requested_model=requested_model,
            )
        except LLMTimeoutError as e:
            raw = "(TIMEOUT_FALLBACK)"
            add_metric('fallback_reason', f"{e.stage}_timeout")
            add_metric('timeout_stage', e.stage)
        except Exception as e:
            if "LLMTimeoutError" in str(e) or "timeout" in str(e).lower():
                raw = "(TIMEOUT_FALLBACK)"
                add_metric('fallback_reason', 'nested_timeout')
                add_metric('timeout_stage', 'nested')
            else:
                raw = f"เกิดข้อผิดพลาดจาก LLM: {e}"
            
        if raw == "(TIMEOUT_FALLBACK)":
            answer = "ขออภัย ระบบใช้เวลาประมวลผลนานเกินกำหนด โปรดอ้างอิงข้อมูลเบื้องต้นจากเอกสาร:\n"
            for c in (retrieved or [])[:2]:
                row = c if isinstance(c, dict) else {'text': str(c), 'source': ''}
                txt = str(row.get('text') or '').replace('\n', ' ')[:150].strip()
                cite = str(row.get('source') or row.get('doc_id') or 'เอกสาร').split('/')[-1]
                answer += f"- {txt}... [{cite}]\n"
            answer = answer.strip()
        elif _STRUCTURED_ENABLE and "เกิดข้อผิดพลาดจาก LLM" not in raw:
            structured = _safe_json_obj(raw)
            if structured is None:
                # Best-effort retry: some models ignore JSON-only constraints on first attempt.
                retry_prompt = (
                    f"{prompt}\n\n"
                    "คำตอบก่อนหน้าของคุณไม่ใช่ JSON object ที่ถูกต้องตามที่ขอ\n"
                    "กรุณาตอบใหม่อีกครั้ง โดยตอบเป็น JSON object เท่านั้น ห้ามมีข้อความอื่นใดนอกจาก JSON\n"
                    "รูปแบบ: {\"answer\":\"...\",\"follow_up_question\":\"\",\"citations\":[\"source/page\"]}"
                )
                try:
                    retry_user_msg = {'role': 'user', 'content': retry_prompt}
                    raw2 = generate_text(
                        retry_prompt,
                        messages=[_SYSTEM_MSG, retry_user_msg],
                        task='answer',
                        requested_model=requested_model,
                    )
                    structured = _safe_json_obj(raw2)
                except Exception:
                    raw2 = raw
                if structured is None:
                    # Fall back to raw (first attempt) if still not structured.
                    structured = None
                else:
                    raw = raw2
            if structured and isinstance(structured.get('answer'), str):
                answer = (structured.get('answer') or '').strip()
                fu = structured.get('follow_up_question')
                if isinstance(fu, str):
                    follow_up_question = fu.strip()
            else:
                answer = (raw or '').strip()
        else:
            answer = (raw or '').strip()

    # Optional: enforce at least one citation per bullet line using allowed cites.
    # This never invents new citations; it only uses the ones we already allowed.
    if _ENFORCE_CITATIONS and answer:
        try:
            allowed = [str(x) for x in (cites or {}).values() if (x or '').strip()]
            answer = _enforce_citations(answer, allowed)
        except Exception:
            pass

    out: Dict[str, Any] = {
        'question': question,
        'prompt': prompt,
        'answer': answer,
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
        'meta': meta,
    }

    if _STRUCTURED_ENABLE:
        # Keep structured.citations aligned with the final answer when possible.
        if isinstance(structured, dict):
            used = _extract_citations_from_text(answer)
            allowed_set = {str(x) for x in (cites or {}).values() if (x or '').strip()}
            used = [c for c in used if c in allowed_set]
            structured = {**structured}
            structured.setdefault('citations', used)
            # If enforcement appended a fallback cite, ensure it's reflected.
            if used:
                structured['citations'] = _dedupe_keep_order([str(x) for x in used], cap=24)
        out['structured'] = structured
        out['follow_up_question'] = follow_up_question

    return out


def _build_rag_prompt_langchain(question: str, domain: Optional[str] = None) -> Dict[str, Any]:
    """Shared retrieval+prompt builder used by both query and answer endpoints."""
    q_display = normalize_question(question)
    q_search = search_query_from_question(question)

    # If an evaluation-style reference hint is provided, make it strict (configurable)
    # to prevent cross-document contamination of numeric facts.
    strict_ref_hints = (os.getenv('STRICT_REFERENCE_HINTS', '1') or '1').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )
    has_ref = bool(_reference_candidates(question)) and strict_ref_hints

    dom = (domain or '').strip().lower()
    initial_dom = dom or 'unknown'
    if not dom:
        # Prefer deterministic heuristic routing first (stable + fast).
        dom = infer_domain(q_display) or ''
        initial_dom = dom or 'unknown'
        # Use LLM router only when heuristic is unclear.
        if not dom:
            dom = _route_domain_llm(q_display) or ''
            initial_dom = dom or 'unknown'
    dom = dom or None
    search_all_domains = _SEARCH_ALL_DOMAINS
    if _FAST_PROFILE and dom:
        search_all_domains = False
        add_metric('fast_profile_domain_scoped', 1)

    add_metric('routing_domain_initial', initial_dom)
    add_metric('routing_domain_final', str(dom) if dom else 'auto')

    # Multi-document retrieval mode (shared with legacy rag_logic): when enabled,
    # bypass multi-query and use the tuned multi-doc retrieval pipeline.
    multi_doc_mode = (os.getenv('RAG_MULTI_DOC_MODE', 'auto') or 'auto').strip().lower()
    multi_doc_triggered = False
    multi_doc_used = False
    multi_doc_reason = ''
    multi_doc_subqs: List[str] = []

    if multi_doc_mode in ('1', 'true', 'yes', 'on'):
        multi_doc_triggered = True
        multi_doc_used = True
        multi_doc_reason = 'forced'
    elif multi_doc_mode == 'auto' and is_multi_doc_question(q_display):
        multi_doc_triggered = True
        multi_doc_used = True
        multi_doc_reason = 'auto'

    if multi_doc_used:
        try:
            multi_doc_subqs = decompose_question(
                question,
                max_parts=max(1, int(os.getenv('RAG_MULTI_DOC_MAX_SUBQS', '3') or '3')),
            )
        except Exception:
            multi_doc_subqs = []

        retrieved = retrieve_multi_document(question)
        try:
            retrieved = _filter_chunks_by_reference(retrieved, question, strict=has_ref)
        except Exception:
            pass

        with time_block('post_rerank_prompt_ms'):
            ctx, cites = pack_context_grouped(retrieved)
            prompt = build_prompt(q_display, ctx, cites)

        unique_sources: set[str] = set()
        unique_domains: set[str] = set()
        for r in (retrieved or []):
            src = str(r.get('source') or r.get('path') or '').strip()
            if src:
                unique_sources.add(src)
            d2 = str(r.get('domain') or '').strip().lower()
            if d2:
                unique_domains.add(d2)

        return {
            'q_display': q_display,
            'q_search': q_search,
            'domain': dom,
            'retrieved': retrieved,
            'ctx': ctx,
            'cites': cites,
            'prompt': prompt,
            'meta': {
                'multi_doc_mode': multi_doc_mode,
                'multi_doc_triggered': bool(multi_doc_triggered),
                'multi_doc_used': bool(multi_doc_used),
                'multi_doc_reason': multi_doc_reason,
                'multi_doc_subqs': list(multi_doc_subqs or []),
                'retrieved_unique_sources': len(unique_sources),
                'retrieved_unique_domains': len(unique_domains),
            },
        }

    # Multi-query retrieval (best-effort): use LLM to generate query variants,
    # retrieve for each query, then fuse with RRF.
    variants: List[str] = []
    anchored = _has_precision_anchors(question)
    allow_multiquery = (not anchored) or _MULTIQUERY_FOR_ANCHORED
    if _FAST_PROFILE:
        add_metric('multiquery_skipped_fast_profile', 1)
    elif (not has_ref) and allow_multiquery and _MULTIQUERY_ENABLE and (_MULTIQUERY_ALL or (dom == 'curriculum') or (dom is None)):
        variants = _multiquery_variants(q_display, q_search, dom)
    elif anchored and (not has_ref):
        add_metric('multiquery_skipped_anchored', 1)

    # Prevent multi-query drift: generated variants must preserve lexical anchors
    # like clause numbers (ข้อ 12), course codes (CPE123), and key numbers (15, 60).
    if (not has_ref) and variants:
        anchors = extract_lexical_anchors(question)
        if anchors:
            safe: List[str] = []
            for v in variants:
                vl = (v or '').lower()
                if not vl:
                    continue
                vl_compact = re.sub(r"[\s\-_]", "", vl)
                ok = True
                for a in anchors:
                    a2 = (a or '').lower().strip()
                    if not a2:
                        continue
                    a_compact = re.sub(r"[\s\-_]", "", a2)
                    if a_compact and a_compact not in vl_compact:
                        ok = False
                        break
                if ok:
                    safe.append(v)
            variants = safe

    # If we have an explicit reference hint, pass the full question down so
    # retrieve_by_domain can apply source allowlisting.
    if has_ref:
        queries = [question]
    else:
        # Always include original query; cap total queries to avoid drifting.
        queries = _dedupe_keep_order([q_search, *variants], cap=4)

    wants_listy = (
        'LNG' in q_display.upper()
        and any(t in q_display for t in ('เลือกเรียน', 'มีวิชา', 'วิชาอะไร', 'เลือกได้', 'ตัวเลือก'))
    )
    if _FAST_PROFILE:
        fast_cap = max(2, int(RAG_FAST_MAX_CONTEXTS or 4))
        cap = fast_cap
    else:
        cap = min(max(MAX_CONTEXTS, 8), 12) if wants_listy else MAX_CONTEXTS

    retrieved_lists: List[Tuple[str, List[Dict]]] = []

    def _retrieve_one(q: str) -> Tuple[str, List[Dict]]:
        if dom and not search_all_domains:
            items = retrieve_by_domain(q, domain=dom)
            if (not has_ref) and len(items) < fallback_min_results() and (not _should_preserve_domain_retrieval(question, dom, items)):
                doms = fallback_domains_for_domain(dom, q_display)
                items = retrieve_all_domains(q, domains=doms)
        else:
            items = retrieve_all_domains(q)
        return q, items

    with time_block('vector_search'):
        if _PARALLEL_ENABLE and len(queries) > 1:
            workers = max(1, min(12, int(_PARALLEL_WORKERS)))
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futs = [ex.submit(_retrieve_one, q) for q in queries]
                for fut in as_completed(futs):
                    try:
                        retrieved_lists.append(fut.result())
                    except Exception:
                        continue
            order = {q: i for i, q in enumerate(queries)}
            retrieved_lists.sort(key=lambda x: order.get(x[0], 10**9))
        else:
            for q in queries:
                retrieved_lists.append(_retrieve_one(q))

    retrieved = _fuse_rrf(retrieved_lists, cap=cap)
    retrieved = _boost_regulations_for_exam_intent(retrieved, q_display)
    retrieved = _inject_exam_rule_anchors(retrieved, q_display, cap=cap)
    retrieved = _boost_faculty_relation_for_teacher_intent(retrieved, q_display, dom)

    # If question explicitly references a file, keep contexts from that file.
    try:
        retrieved = _filter_chunks_by_reference(retrieved, question, strict=has_ref)
    except Exception:
        pass

    add_metric('initial_retrieval_doc_count', len(retrieved or []))
    add_metric('initial_top_score', _top_retrieval_score(retrieved))
    if _is_low_confidence(retrieved):
        add_metric('low_confidence_detected', 1)

    skip_adaptive_retry = (
        _is_anchored_regulations_query(question, dom)
        or _is_announcement_temporal_query(question, dom)
        or (dom == 'curriculum' and _is_curriculum_group_list_query(question))
    )
    if _ADAPTIVE_ORCHESTRATION and (not has_ref) and _is_low_confidence(retrieved) and (not skip_adaptive_retry):
        add_metric('retrieval_adaptive_retry_triggered', 1)
        retry_q = _expand_query_for_retry(question, dom)
        try:
            if dom and not search_all_domains:
                retry = retrieve_by_domain(retry_q, domain=dom)
                add_metric('retry_retrieval_doc_count', len(retry or []))
                add_metric('retry_top_score', _top_retrieval_score(retry))
                if _is_low_confidence(retry) and (not _should_preserve_domain_retrieval(question, dom, retry)):
                    add_metric('retrieval_fallback_all_domains_triggered', 1)
                    retry = retrieve_all_domains(retry_q, domains=fallback_domains_for_domain(dom, q_display))
                    if retry:
                        add_metric('retrieval_fallback_all_domains_succeeded', 1)
            else:
                retry = retrieve_all_domains(retry_q)
                add_metric('retry_retrieval_doc_count', len(retry or []))
                add_metric('retry_top_score', _top_retrieval_score(retry))

            if (_top_retrieval_score(retry) > _top_retrieval_score(retrieved)) or (len(retry or []) > len(retrieved or [])):
                retrieved = retry
                add_metric('retrieval_adaptive_retry_succeeded', 1)
        except Exception:
            pass

    # Optional rerank (embedding-based) to reduce noise.
    if _RERANK_ENABLE and retrieved and (_RERANK_ALL or (dom == 'curriculum')):
        if _FAST_PROFILE:
            add_metric('top_k_rerank_skipped_fast_profile', 1)
        # Announcement temporal queries are extractor-driven; rerank rarely helps
        # and adds avoidable latency variance.
        elif _is_announcement_temporal_query(question, dom):
            add_metric('top_k_rerank_skipped_announcement_temporal', 1)
        else:
        # Mismatch intent skip: if top 3 docs don't match our initial domain intent, skip expensive rerank.
            mismatch_skip = False
            if initial_dom and initial_dom != 'unknown':
                top_domains = [str(d.get('domain') or '').strip().lower() for d in retrieved[:3]]
                if top_domains and initial_dom not in top_domains:
                    mismatch_skip = True

            high_conf_skip = False
            if _RERANK_SKIP_HIGH_CONF:
                top_score = _top_retrieval_score(retrieved)
                if (top_score >= _RERANK_SKIP_HIGH_CONF_THRESHOLD) and (len(retrieved or []) < _RERANK_MIN_DOCS):
                    high_conf_skip = True

            if not mismatch_skip and not high_conf_skip:
                with time_block('top_k_rerank'):
                    try:
                        _chroma_calls = fetch_embeddings_for_docs(retrieved, dom)
                        add_metric('embedding_fetch_chroma_calls', _chroma_calls)
                        retrieved = _rerank_by_embedding(q_search, retrieved, topn=_RERANK_TOPN)
                        retrieved = retrieved[:cap]
                    except Exception:
                        pass
            else:
                if mismatch_skip:
                    add_metric('top_k_rerank_skipped_mismatch', 1)
                if high_conf_skip:
                    add_metric('top_k_rerank_skipped_high_conf', 1)

    # Optional extractive compression to pack more relevant context.
    if _COMPRESS_ENABLE and retrieved and (_COMPRESS_ALL or (dom == 'curriculum')):
        try:
            max_chars = max(200, int(_COMPRESS_MAX_CHARS))
            compressed: List[Dict] = []
            for d in retrieved:
                txt = (d.get('text') or '')
                ctxt = _compress_text_extractive(q_display, txt, max_chars=max_chars)
                compressed.append({**d, 'text': ctxt or txt})
            retrieved = compressed
        except Exception:
            pass

    with time_block('post_rerank_prompt_ms'):
        ctx, cites = pack_context(retrieved)
        prompt = build_prompt(q_display, ctx, cites)

    unique_sources: set[str] = set()
    unique_domains: set[str] = set()
    for r in (retrieved or []):
        src = str(r.get('source') or r.get('path') or '').strip()
        if src:
            unique_sources.add(src)
        d2 = str(r.get('domain') or '').strip().lower()
        if d2:
            unique_domains.add(d2)

    return {
        'q_display': q_display,
        'q_search': q_search,
        'domain': dom,
        'retrieved': retrieved,
        'ctx': ctx,
        'cites': cites,
        'prompt': prompt,
        'meta': {
            'multi_doc_mode': multi_doc_mode,
            'multi_doc_triggered': bool(multi_doc_triggered),
            'multi_doc_used': bool(multi_doc_used),
            'multi_doc_reason': multi_doc_reason,
            'multi_doc_subqs': list(multi_doc_subqs or []),
            'retrieved_unique_sources': len(unique_sources),
            'retrieved_unique_domains': len(unique_domains),
        },
    }


def rag_query_langchain(question: str, domain: Optional[str] = None) -> Dict[str, Any]:
    """Query-only RAG using the LangChain orchestration retrieval path.

    Shape matches legacy rag_query/rag_query_domain outputs:
    { prompt, contexts, token_est }
    """
    built = _build_rag_prompt_langchain(question=question, domain=domain)
    retrieved = built['retrieved']
    prompt = built['prompt']
    ctx = built['ctx']
    meta = built.get('meta')

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
            for r in (retrieved or [])
        ],
        'token_est': est_tokens(ctx),
        'meta': meta,
    }
