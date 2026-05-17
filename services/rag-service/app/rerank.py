from __future__ import annotations

from typing import Dict, List
import json
import os
import re

from .config import MAX_CONTEXTS, RRF_K


def apply_announcement_procedure_boost(items: list[dict], keywords=None, boost=0.18):
    """Boost score for announcement contexts with procedure/important keywords."""
    if not items:
        return items
    keywords = keywords or ["ขั้นตอน", "procedure", "วิธีการ", "important", "ประกาศสำคัญ", "process", "ดำเนินการ"]
    for d in items:
        txt = str(d.get("text") or "")
        if any(k in txt for k in keywords):
            base = float(d.get("score_final") or d.get("score_rrf") or 0.0)
            d["score_final"] = base + boost
            d["score_rrf"] = base + boost
    items.sort(key=lambda x: float(x.get("score_final") or x.get("score_rrf") or 0.0), reverse=True)
    return items


def apply_intent_aware_fact_boost(
    items: list[dict],
    *,
    question: str,
    intent: str,
    needed_evidence: list[str] | None = None,
) -> list[dict]:
    if not items:
        return []
    q = str(question or '').strip().lower()
    intent_key = str(intent or '').strip().lower()
    needed = [str(v or '').strip().lower() for v in (needed_evidence or []) if str(v or '').strip()]

    entity_bonus: dict[str, float] = {}
    keyword_bonus = 0.0
    if intent_key in ('contact_lookup', 'person_contact', 'instructor_lookup'):
        entity_bonus = {'person_contact': 0.45, 'course_instructor': 0.32, 'course': -0.10}
        keyword_bonus = 0.14
    elif intent_key in ('course_lookup', 'credit_lookup', 'prerequisite_lookup'):
        entity_bonus = {'course': 0.38, 'course_instructor': 0.12, 'person_contact': -0.08}
    elif intent_key in ('form_lookup',):
        entity_bonus = {'form': 0.4, 'procedure': 0.18}
    elif intent_key in ('procedure_lookup', 'registration_policy'):
        entity_bonus = {'procedure': 0.42, 'regulation': 0.16, 'form': 0.12}
        keyword_bonus = 0.12
    elif intent_key in ('calendar_lookup', 'calendar_deadline'):
        entity_bonus = {'calendar_event': 0.42, 'regulation': 0.12}
        keyword_bonus = 0.10
    elif intent_key in ('policy_lookup', 'exam_policy', 'academic_status_policy'):
        entity_bonus = {'regulation': 0.34, 'procedure': 0.12, 'course': -0.42, 'course_instructor': -0.16}

    out: list[dict] = []
    for item in items:
        row = dict(item or {})
        meta = row.get('metadata') if isinstance(row.get('metadata'), dict) else {}
        entity_type = str(meta.get('entity_type') or '').strip().lower()
        base = float(row.get('score_final') or row.get('score_rrf') or 0.0)
        score = base + float(entity_bonus.get(entity_type, 0.0))
        text = str(row.get('text') or '').lower()
        if keyword_bonus > 0:
            if intent_key in ('contact_lookup', 'person_contact', 'instructor_lookup') and any(t in text for t in ('@', 'อีเมล', 'email', 'โทร', 'phone', 'contact')):
                score += keyword_bonus
            elif intent_key in ('procedure_lookup', 'registration_policy') and any(t in text for t in ('ขั้นตอน', 'ยื่น', 'ส่ง', 'กรอก', 'อนุมัติ')):
                score += keyword_bonus
            elif intent_key in ('calendar_lookup', 'calendar_deadline') and any(t in text for t in ('ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.', 'วัน')):
                score += keyword_bonus
        if needed and entity_type:
            if entity_type == 'person_contact' and any(k in needed for k in ('email', 'phone', 'contact')):
                score += 0.08
            if entity_type == 'course' and any(k in needed for k in ('course_code', 'credits', 'course_name')):
                score += 0.08
        row['score_final'] = score
        row['score_rrf'] = score
        out.append(row)
    out.sort(key=lambda x: float(x.get('score_final') or x.get('score_rrf') or 0.0), reverse=True)
    return out


def _normalize_source_key(s: str) -> str:
    txt = (s or '').strip().lower()
    if not txt:
        return ''
    try:
        txt = txt.replace('\\', '/')
        txt = txt.split('/')[-1]
    except Exception:
        pass
    txt = txt.replace(' ', '')
    txt = txt.replace('-', '_')
    return txt


def _doc_key_for_fusion(d: Dict, fallback_prefix: str, i: int) -> str:
    did = d.get('doc_id')
    if isinstance(did, str) and did.strip():
        return did.strip()
    src = d.get('source')
    if isinstance(src, str) and src.strip():
        return src.strip()
    path = d.get('path')
    if isinstance(path, str) and path.strip():
        return path.strip()
    return f"{fallback_prefix}_{i}"


def fuse_rrf_lists(lists: List[List[Dict]], weights: List[float] | None = None, k: int = RRF_K) -> List[Dict]:
    """Fuse multiple already-ranked lists using weighted RRF."""
    bank: Dict[str, Dict] = {}
    ranks: Dict[str, float] = {}

    ws = weights or [1.0] * len(lists)
    if len(ws) != len(lists):
        ws = [1.0] * len(lists)

    for li, docs in enumerate(lists or []):
        w = float(ws[li])
        for r, d in enumerate(docs or [], start=1):
            key = _doc_key_for_fusion(d, f"l{li}", r)
            if key in bank:
                merged = dict(bank[key])
                merged.update(d)
                bank[key] = merged
            else:
                bank[key] = d
            ranks[key] = ranks.get(key, 0.0) + (w / (k + r))

    merged_out = [{**bank[k2], 'score_rrf': v, 'doc_id': (bank[k2].get('doc_id') or k2)} for k2, v in ranks.items()]
    merged_out.sort(key=lambda x: float(x.get('score_rrf') or 0.0), reverse=True)
    return merged_out


def select_chunks_from_top_documents(
    items: List[Dict],
    top_docs: int = 6,
    per_doc: int = 3,
) -> List[Dict]:
    if not items:
        return []
    top_docs = max(1, int(top_docs))
    per_doc = max(1, int(per_doc))

    def _doc_key(d: Dict) -> str:
        # Prefer source+path, fallback doc_id.
        src = str(d.get('source') or d.get('path') or '').strip()
        if src:
            return _normalize_source_key(src)
        return str(d.get('doc_id') or '').strip()

    best_per_doc: Dict[str, float] = {}
    for d in items:
        k2 = _doc_key(d)
        if not k2:
            continue
        s = float(d.get('score_final') or d.get('score_rrf') or 0.0)
        best_per_doc[k2] = max(best_per_doc.get(k2, -1e9), s)

    doc_order = sorted(best_per_doc.keys(), key=lambda kk: best_per_doc.get(kk, 0.0), reverse=True)[:top_docs]
    doc_set = set(doc_order)

    buckets: Dict[str, List[Dict]] = {}
    for d in items:
        k2 = _doc_key(d)
        if not k2 or k2 not in doc_set:
            continue
        buckets.setdefault(k2, []).append(d)

    out: List[Dict] = []
    for dk in doc_order:
        docs = buckets.get(dk, [])
        docs.sort(key=lambda x: float(x.get('score_final') or x.get('score_rrf') or 0.0), reverse=True)
        out.extend(docs[:per_doc])

    out.sort(key=lambda x: float(x.get('score_final') or x.get('score_rrf') or 0.0), reverse=True)
    return out


def ensure_min_sources(
    items: List[Dict],
    min_sources: int = 2,
    max_per_source: int = 2,
    limit: int = MAX_CONTEXTS,
) -> List[Dict]:
    if not items:
        return []
    min_sources = max(1, int(min_sources))
    max_per_source = max(1, int(max_per_source))
    limit = max(1, int(limit))

    def _src(d: Dict) -> str:
        return _normalize_source_key(str(d.get('source') or d.get('path') or 'unknown')) or 'unknown'

    def _chunk_key(d: Dict) -> str:
        did = str(d.get('doc_id') or '')
        pg = str(d.get('page_start') or '') + '-' + str(d.get('page_end') or '')
        src = str(d.get('source') or d.get('path') or '')
        txt = re.sub(r"\s+", " ", str(d.get('text') or '').strip())
        if len(txt) > 140:
            txt = txt[:140]
        return did + '::' + pg + '::' + src + '::' + txt

    # 1) Seed at least N unique sources (best chunk per source in rank order).
    seeded: List[Dict] = []
    seen_src: set[str] = set()
    for d in items:
        s = _src(d)
        if s in seen_src:
            continue
        seeded.append(d)
        seen_src.add(s)
        if len(seeded) >= min_sources:
            break

    # 2) Fill remaining slots with per-source cap.
    merged = list(seeded)
    counts: Dict[str, int] = {}
    seen_keys: set[str] = set()
    for d in seeded:
        counts[_src(d)] = counts.get(_src(d), 0) + 1
        seen_keys.add(_chunk_key(d))

    for d in items:
        if len(merged) >= limit:
            break
        s = _src(d)
        if counts.get(s, 0) >= max_per_source:
            continue
        key = _chunk_key(d)
        if key in seen_keys:
            continue
        merged.append(d)
        seen_keys.add(key)
        counts[s] = counts.get(s, 0) + 1

    merged.sort(key=lambda x: float(x.get('score_final') or x.get('score_rrf') or 0.0), reverse=True)
    return merged[:limit]


def fuse_semantic_keyword(
    sem_docs: List[Dict],
    kw_docs: List[Dict],
    sem_weight: float = 1.0,
    kw_weight: float = 1.2,
    k: int = RRF_K,
) -> List[Dict]:
    """Weighted RRF fuse semantic + keyword lists."""
    bank: Dict[str, Dict] = {}
    ranks: Dict[str, float] = {}

    def _doc_key(d: Dict, fallback_prefix: str, i: int) -> str:
        did = d.get('doc_id')
        if isinstance(did, str) and did.strip():
            return did.strip()
        src = d.get('source')
        if isinstance(src, str) and src.strip():
            return src.strip()
        return f"{fallback_prefix}_{i}"

    for i, d in enumerate(sem_docs or [], start=1):
        key = _doc_key(d, 'sem', i)
        bank[key] = d
        ranks[key] = ranks.get(key, 0.0) + float(sem_weight) / (k + i)

    for i, d in enumerate(kw_docs or [], start=1):
        key = _doc_key(d, 'kw', i)
        if key in bank:
            merged = dict(bank[key])
            merged.update(d)
            bank[key] = merged
        else:
            bank[key] = d
        ranks[key] = ranks.get(key, 0.0) + float(kw_weight) / (k + i)

    merged = [{**bank[k2], 'score_rrf': v, 'doc_id': (bank[k2].get('doc_id') or k2)} for k2, v in ranks.items()]
    merged.sort(key=lambda x: float(x.get('score_rrf') or 0.0), reverse=True)
    return merged


def apply_domain_prior(
    items: List[Dict],
    inferred_domain: str | None,
    bonus: float = 0.15,
    penalty: float = 0.08,
) -> List[Dict]:
    if not items or not inferred_domain:
        return items
    dom0 = (inferred_domain or '').strip().lower()
    if not dom0:
        return items
    out: List[Dict] = []
    for d in items:
        u = dict(d)
        dom = str(u.get('domain') or '').strip().lower()
        base = float(u.get('score_final') or u.get('score_rrf') or 0.0)
        score = base
        if dom:
            if dom == dom0:
                score = base + float(bonus)
            elif float(penalty) > 0:
                score = base - float(penalty)
        u['score_final'] = score
        u['score_rrf'] = score
        out.append(u)
    out.sort(key=lambda x: float(x.get('score_rrf') or 0.0), reverse=True)
    return out


_DEFAULT_OVERBROAD_SOURCE_PENALTIES: Dict[str, float] = {
    # Files that frequently match too broadly (calendar/schedule/announcements)
    _normalize_source_key('ปฏิทินการศึกษา2568.txt'): 0.25,
    _normalize_source_key('ปฏิทินการศึกษา_2567.txt'): 0.22,
    _normalize_source_key('academiccalendar2025th.txt'): 0.22,
    _normalize_source_key('approved_exam2568.txt'): 0.22,
    _normalize_source_key('schedule2565.txt'): 0.16,
    _normalize_source_key('calculator2023.txt'): 0.10,
    _normalize_source_key('eng_b2568.txt'): 0.10,
}


def _load_overbroad_source_penalties() -> Dict[str, float]:
    """Load optional penalties from env.

    Supported formats:
    - RAG_OVERBROAD_SOURCE_PENALTIES_JSON='{"file.txt":0.12, ...}'
    - RAG_OVERBROAD_SOURCE_PENALTIES='file.txt:0.12,other.txt:0.08'
    """
    raw_json = (os.getenv('RAG_OVERBROAD_SOURCE_PENALTIES_JSON', '') or '').strip()
    raw_kv = (os.getenv('RAG_OVERBROAD_SOURCE_PENALTIES', '') or '').strip()

    out: Dict[str, float] = dict(_DEFAULT_OVERBROAD_SOURCE_PENALTIES)

    if raw_json:
        try:
            data = json.loads(raw_json)
            if isinstance(data, dict):
                for k, v in data.items():
                    kk = _normalize_source_key(str(k))
                    try:
                        vv = float(v)
                    except Exception:
                        continue
                    if kk:
                        out[kk] = vv
        except Exception:
            pass

    if raw_kv:
        for part in raw_kv.split(','):
            p = (part or '').strip()
            if not p:
                continue
            if ':' not in p:
                continue
            k, v = p.split(':', 1)
            kk = _normalize_source_key(k)
            try:
                vv = float((v or '').strip())
            except Exception:
                continue
            if kk:
                out[kk] = vv

    return out


_OVERBROAD_SOURCE_PENALTIES = _load_overbroad_source_penalties()


def apply_overbroad_source_penalty(
    items: List[Dict],
    inferred_domain: str | None,
    penalties: Dict[str, float] | None = None,
    question: str | None = None,
) -> List[Dict]:
    if not items:
        return items

    dom0 = (inferred_domain or '').strip().lower()
    # Apply penalties mainly when intent is curriculum/regulations, where broad calendar/announcement
    # docs frequently leak into the top ranks.
    if dom0 not in ('curriculum', 'regulations'):
        return items

    pen = penalties or _OVERBROAD_SOURCE_PENALTIES
    if not pen:
        return items

    ql = (question or '').strip().lower()
    is_calendar_intent = any(t in ql for t in (
        'ปฏิทิน', 'calendar', 'กำหนดการ', 'ตาราง', 'schedule', 'deadline', 'วันเปิด', 'วันปิด', 'ชำระ',
    ))
    has_course_code = re.search(r"\b[a-z]{2,6}\s*[- ]?\s*\d{3}\b", ql, flags=re.IGNORECASE) is not None
    is_course_info = (has_course_code or ('หน่วยกิต' in ql) or ('คืออะไร' in ql) or ('มีกี่หน่วยกิต' in ql))
    mult = 1.0
    if dom0 == 'curriculum' and (not is_calendar_intent) and is_course_info:
        mult = 2.0
    elif dom0 == 'regulations' and (not is_calendar_intent) and any(t in ql for t in ('ระเบียบ', 'ข้อบังคับ', 'ข้อ', 'มาตรา', 'อุทธรณ์', 'ทุจริต', 'วินัย')):
        mult = 1.5

    out: List[Dict] = []
    for d in items:
        u = dict(d)
        src = str(u.get('source') or u.get('path') or '')
        key = _normalize_source_key(src)
        p = float(pen.get(key, 0.0)) if key else 0.0
        if p and float(mult) != 1.0:
            p = float(p) * float(mult)
        base = float(u.get('score_final') or u.get('score_rrf') or 0.0)
        if p:
            base -= p
        u['score_final'] = base
        u['score_rrf'] = base
        out.append(u)
    out.sort(key=lambda x: float(x.get('score_rrf') or 0.0), reverse=True)
    return out


def majority_domain_rescue(
    items: List[Dict],
    topn: int = 5,
    margin: float = 0.08,
    require_majority: int = 3,
) -> List[Dict]:
    if not items or len(items) < 2:
        return items

    topn = max(2, int(topn))
    head = items[:topn]
    counts: Dict[str, int] = {}
    for d in head:
        dom = str(d.get('domain') or '').strip().lower()
        if not dom:
            continue
        counts[dom] = counts.get(dom, 0) + 1
    if not counts:
        return items

    maj_dom = max(counts, key=lambda k: counts[k])
    if counts.get(maj_dom, 0) < int(require_majority):
        return items

    top1_dom = str(items[0].get('domain') or '').strip().lower()
    if not maj_dom or maj_dom == top1_dom:
        return items

    def _score(d: Dict) -> float:
        return float(d.get('score_final') or d.get('score_rrf') or 0.0)

    # Items are already sorted desc, so the first matching domain item is its best candidate.
    best_idx = next(
        (i for i, d in enumerate(items) if str(d.get('domain') or '').strip().lower() == maj_dom),
        None,
    )
    if best_idx is None or best_idx == 0:
        return items

    top_score = _score(items[0])
    maj_score = _score(items[best_idx])

    # Rescue only when the majority-domain best item is not much worse than rank-1.
    if maj_score + float(margin) < top_score:
        return items

    out = list(items)
    rescued = out.pop(best_idx)
    out.insert(0, rescued)
    return out


def promote_exact_anchor_hits(items: List[Dict], anchors: List[str], bonus_per_hit: float = 0.18) -> List[Dict]:
    if not items or not anchors:
        return items
        
    course_code_anchors = {a.lower() for a in anchors if re.match(r"^[a-zA-Z]{2,6}\d{3}$", a.strip())}
    
    out: List[Dict] = []
    for d in items:
        blob = ' '.join([
            str(d.get('text') or ''),
            str(d.get('source') or ''),
            str(d.get('path') or ''),
            str(d.get('title') or ''),
        ]).lower()
        blob_norm = re.sub(r"[^0-9a-zก-๙]+", "", blob)
        bonus = 0.0
        for a in anchors:
            s = (a or '').strip().lower()
            if not s:
                continue
            
            is_course = s in course_code_anchors
            hit = False
            
            if s in blob:
                hit = True
            else:
                s2 = re.sub(r"[^0-9a-zก-๙]+", "", s)
                if s2 and s2 in blob_norm:
                    hit = True
                    
            if hit:
                # Add a substantial multiplier for exact course code matches to heavily boost to Top-1
                if is_course:
                    bonus += float(bonus_per_hit) * 6.0
                else:
                    bonus += float(bonus_per_hit)

        u = dict(d)
        base = float(u.get('score_rrf') or 0.0)
        u['score_final'] = base + bonus
        u['score_rrf'] = u['score_final']
        out.append(u)
    out.sort(key=lambda x: float(x.get('score_rrf') or 0.0), reverse=True)
    return out


def diversify_by_source(items: List[Dict], max_per_source: int = 2, limit: int = MAX_CONTEXTS) -> List[Dict]:
    if not items:
        return []
    max_per_source = max(1, int(max_per_source))
    limit = max(1, int(limit))

    out: List[Dict] = []
    seen_keys: set[str] = set()
    per_src: Dict[str, int] = {}

    def _k(d: Dict) -> str:
        did = str(d.get('doc_id') or '')
        pg = str(d.get('page_start') or '') + '-' + str(d.get('page_end') or '')
        src = str(d.get('source') or d.get('path') or '')
        txt = re.sub(r"\s+", " ", str(d.get('text') or '').strip())
        if len(txt) > 140:
            txt = txt[:140]
        return did + '::' + pg + '::' + src + '::' + txt

    def _src(d: Dict) -> str:
        s = d.get('source')
        if s:
            return str(s)
        p = d.get('path')
        return str(p) if p else 'unknown'

    # Pass 1: enforce per-source cap.
    for d in items:
        key = _k(d)
        if key in seen_keys:
            continue
        src = _src(d)
        if per_src.get(src, 0) >= max_per_source:
            continue
        out.append(d)
        seen_keys.add(key)
        per_src[src] = per_src.get(src, 0) + 1
        if len(out) >= limit:
            return out

    # Pass 2: fill remaining slots without cap.
    if len(out) < limit:
        for d in items:
            key = _k(d)
            if key in seen_keys:
                continue
            out.append(d)
            seen_keys.add(key)
            if len(out) >= limit:
                break
    return out
