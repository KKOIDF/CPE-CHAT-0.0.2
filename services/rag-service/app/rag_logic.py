from typing import List, Dict, Tuple, Sequence
from concurrent.futures import ThreadPoolExecutor
import re
import math
from pathlib import Path
import unicodedata
import os
import json
import logging

from .perf import time_block, add_metric

from .sqlite_client import keyword_search, fetch_docs_with_path, domain_sqlite_path
from .chroma_client import semantic_search_domain
from .config import TOKEN_BUDGET, RRF_K, MAX_CONTEXTS, KNOWN_DOMAINS, ROOT_DIR
from .neo4j_client import (
    extract_course_codes,
    graph_doc_ids_for_codes,
    graph_doc_ids_for_course_prefix,
    graph_expand_from_seed_chunks,
    graph_doc_ids_for_requisites,
)

from .structured_curriculum import (
    Course,
    extract_courses_from_text,
    format_required_cpe_answer,
    load_credit_totals_2564,
    load_all_courses_2564,
    load_cpe_curriculum_2564,
)
from . import normalization as _normalization
from . import routing as _routing
from . import retrieval as _retrieval
from . import rerank as _rerank
from . import context_packing as _context_packing
from . import prompting as _prompting


logger = logging.getLogger(__name__)

# Simple token counter heuristic (~4 chars/token Thai)
CHAR_PER_TOKEN = 4.0


_LANG_SYNONYMS: list[tuple[str, str]] = [
    ('อาจาร์ย', 'อาจารย์'),
    ('ภาษามาเล', 'ภาษามลายู'),
    ('ภาษา มาเล', 'ภาษามลายู'),
]

_LANG_AUGMENT: dict[str, str] = {
    'ภาษามลายู': 'Malay',
    'ภาษาฝรั่งเศส': 'French',
    'ภาษาจีน': 'Chinese',
    'ภาษาญี่ปุ่น': 'Japanese',
    'ภาษาเกาหลี': 'Korean',
    'ภาษาเยอรมัน': 'German',
    'ภาษาสเปน': 'Spanish',
    'ภาษารัสเซีย': 'Russian',
}


_THAI_TO_ARABIC = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')


_RETRIEVAL_PARALLEL = (os.getenv('RAG_RETRIEVAL_PARALLEL', '1') or '1').strip().lower() in (
    '1', 'true', 'yes', 'on'
)
_VECTOR_ONLY = (os.getenv('RAG_VECTOR_ONLY', '0') or '0').strip().lower() in (
    '1', 'true', 'yes', 'on'
)
_SEARCH_ALL_DOMAINS = (os.getenv('RAG_SEARCH_ALL_DOMAINS', '1') or '1').strip().lower() in (
    '1', 'true', 'yes', 'on'
)
try:
    _RETRIEVAL_PARALLEL_WORKERS = max(2, int(os.getenv('RAG_RETRIEVAL_PARALLEL_WORKERS', '2') or '2'))
except Exception:
    _RETRIEVAL_PARALLEL_WORKERS = 2

_DEBUG_RETRIEVAL = (os.getenv('RAG_DEBUG_RETRIEVAL', '0') or '0').strip().lower() in (
    '1', 'true', 'yes', 'on'
)

_MULTI_DOC_MODE = (os.getenv('RAG_MULTI_DOC_MODE', 'auto') or 'auto').strip().lower()
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


def is_multi_doc_question(q: str) -> bool:
    """Heuristic: detect questions that likely require combining multiple sources."""
    ql = (q or '').strip().lower()
    if not ql:
        return False

    # Strong explicit signals.
    if any(t in ql for t in ('เปรียบเทียบ', 'ต่างกัน', 'เหมือนกัน', 'ทั้ง', 'พร้อมกัน', 'conflict')):
        return True

    # Multiple clauses / intents.
    signals = (' แล้ว', ' และ', ' รวมถึง', ' พร้อม', ' กรณี', ',', ';')
    sig_hits = sum(1 for s in signals if s in ql)

    qmark_hits = ql.count('?')
    multi_intent = any(t in ql for t in ('ต้องทำยังไง', 'ทำอย่างไร', 'ขั้นตอน', 'เงื่อนไข', 'ต้องใช้', 'ต้องมี', 'ได้ไหม'))

    if qmark_hits >= 2:
        return True
    if sig_hits >= 2:
        return True
    if sig_hits >= 1 and multi_intent:
        return True
    return False


def decompose_question(q: str, max_parts: int = _MULTI_DOC_MAX_SUBQS) -> List[str]:
    """Split multi-clause questions into a small set of sub-questions."""
    raw = (q or '').strip()
    if not raw:
        return []

    # Keep the original question first (important for global intent).
    parts: List[str] = [raw]

    # Split on common Thai connectors. Avoid exploding into too many sub-questions.
    segs = re.split(r"\s*(?:แล้ว|และ|รวมถึง|พร้อมกับ|พร้อม|กรณี|\/|\,|\;)+\s*", raw)
    for s in segs:
        ss = (s or '').strip()
        if not ss:
            continue
        if ss == raw:
            continue
        parts.append(ss)

    out: List[str] = []
    seen: set[str] = set()
    for p in parts:
        pp = (p or '').strip()
        if not pp:
            continue
        key = re.sub(r"\s+", " ", pp.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(pp)
        if len(out) >= max(1, int(max_parts)):
            break
    return out


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
    top_docs: int = _MULTI_DOC_DOC_TOPN,
    per_doc: int = _MULTI_DOC_CHUNKS_PER_DOC,
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
    min_sources: int = _MULTI_DOC_MIN_SOURCES,
    max_per_source: int = _MULTI_DOC_MAX_PER_SOURCE,
    limit: int = _MULTI_DOC_FINAL_LIMIT,
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
        # De-dup by doc_id/path-ish.
        key = _chunk_key(d)
        if key in seen_keys:
            continue
        merged.append(d)
        seen_keys.add(key)
        counts[s] = counts.get(s, 0) + 1

    merged.sort(key=lambda x: float(x.get('score_final') or x.get('score_rrf') or 0.0), reverse=True)
    return merged[:limit]


def pack_context_grouped(
    chunks: List[Dict],
    budget_tokens: int = TOKEN_BUDGET,
    truncate_chars: int | None = None,
) -> Tuple[str, Dict[int, str]]:
    if not chunks:
        return '', {}

    def _truncate_block_to_fit(prefix: str, text: str, remaining_tokens: int) -> str | None:
        """Return a possibly-truncated block that fits in remaining token budget.

        Uses a rough chars-per-token heuristic with a safety check via est_tokens.
        """
        if remaining_tokens <= 0:
            return None
        base = (prefix or '')
        base_tokens = est_tokens(base)
        if base_tokens >= remaining_tokens:
            return None
        txt = (text or '').strip()
        # If already fits, keep as-is.
        candidate = base + txt
        if est_tokens(candidate) <= remaining_tokens:
            return candidate

        # Otherwise, truncate to fit. Approx 4 chars/token is a common heuristic.
        avail_tokens = max(1, remaining_tokens - base_tokens)
        approx_chars = max(80, int(avail_tokens * 4))
        if approx_chars <= 0:
            return None
        clipped = txt[:approx_chars].rstrip()
        if clipped and clipped != txt:
            clipped = clipped + ' ...'
        candidate = base + clipped
        # Safety: if still too big, shrink once more.
        if est_tokens(candidate) > remaining_tokens:
            approx_chars = max(40, int(approx_chars * 0.6))
            clipped = txt[:approx_chars].rstrip()
            if clipped and clipped != txt:
                clipped = clipped + ' ...'
            candidate = base + clipped
        if est_tokens(candidate) <= remaining_tokens and candidate.strip() != base.strip():
            return candidate
        return None

    def _group_key(c: Dict) -> str:
        dom = str(c.get('domain') or '').strip()
        src = str(c.get('source') or c.get('path') or 'unknown').strip()
        if dom:
            return f"{dom}/{src}"
        return src

    groups: Dict[str, List[Dict]] = {}
    for c in chunks:
        groups.setdefault(_group_key(c), []).append(c)

    def _group_score(key: str) -> float:
        xs = groups.get(key, [])
        if not xs:
            return 0.0
        return max(float(x.get('score_final') or x.get('score_rrf') or 0.0) for x in xs)

    order = sorted(groups.keys(), key=_group_score, reverse=True)
    for k2 in order:
        groups[k2].sort(key=lambda x: float(x.get('score_final') or x.get('score_rrf') or 0.0), reverse=True)

    packed_blocks: List[str] = []
    used = 0
    cites: Dict[int, str] = {}
    i = 0

    for gk in order:
        remaining = budget_tokens - used
        if remaining <= 0:
            continue

        # Only emit a group header if we can include at least one chunk.
        group_blocks: List[str] = []
        group_cites: List[str] = []

        for c in groups.get(gk, []):
            cite = _cite_label(c)
            txt = (c.get('text', '') or '').strip()
            if truncate_chars is not None and truncate_chars > 0 and len(txt) > truncate_chars:
                txt = txt[:truncate_chars].rstrip() + ' ...'

            prefix = f"[{cite}] "
            remaining = budget_tokens - used - est_tokens(f"[Source: {gk}]")
            if remaining <= 0:
                break

            block = _truncate_block_to_fit(prefix, txt, remaining_tokens=remaining)
            if not block:
                continue
            group_blocks.append(block)
            group_cites.append(cite)

            # Stop early if we're close to budget; later groups can still contribute.
            if (budget_tokens - used) < 80:
                break

        if not group_blocks:
            continue

        header = f"[Source: {gk}]"
        ht = est_tokens(header)
        if used + ht > budget_tokens:
            continue
        packed_blocks.append(header)
        used += ht

        for block, cite in zip(group_blocks, group_cites):
            t = est_tokens(block)
            if used + t > budget_tokens:
                # Best-effort: should rarely happen due to _truncate_block_to_fit.
                continue
            packed_blocks.append(block)
            used += t
            i += 1
            cites[i] = cite

        packed_blocks.append('')

    return '\n'.join(packed_blocks).strip(), cites


def retrieve_multi_document(question: str) -> List[Dict]:
    """Multi-hop-ish retrieval: decompose -> wide retrieve per subq -> fuse -> doc→chunk -> diversify."""
    subqs = decompose_question(question, max_parts=_MULTI_DOC_MAX_SUBQS)
    if not subqs:
        return []

    lists: List[List[Dict]] = []
    weights: List[float] = []
    for i, sq in enumerate(subqs):
        # Retrieve wider than normal so we have enough breadth to combine evidence.
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
    fused = promote_exact_anchor_hits(fused, anchors)

    # Regulations-specific rerank for clause coverage. Multi-doc fusion is intentionally
    # generic and can over-favor chunks that appear in both semantic+keyword lists.
    # For questions asking about exam-room temporary leave, explicitly boost clause-16
    # chunks so they survive downstream per-source caps.
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

    # Doc stage: ensure we pull evidence from multiple documents, not only the single best chunk.
    doc_selected = select_chunks_from_top_documents(fused, top_docs=_MULTI_DOC_DOC_TOPN, per_doc=_MULTI_DOC_CHUNKS_PER_DOC)

    # If a critical clause chunk exists in the fused pool but is not within the
    # top `per_doc` chunks for its document, inject it here so downstream
    # per-source caps don't erase it entirely.
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

    # Diversity + min-sources for final contexts.
    final = ensure_min_sources(
        doc_selected,
        min_sources=_MULTI_DOC_MIN_SOURCES,
        max_per_source=_MULTI_DOC_MAX_PER_SOURCE,
        limit=_MULTI_DOC_FINAL_LIMIT,
    )

    # Regulations-specific: when the question includes multiple exam-room intents,
    # the per-source cap can drop a needed clause chunk (e.g., ข้อ 12 or ข้อ 16)
    # even though it exists in the fused pool. Force-include missing clause chunks
    # while keeping per-source limits.
    try:
        ql = (question or '').strip().lower()
        want_exam_late = (
            ('สอบ' in ql or 'ห้องสอบ' in ql)
            and ('มาสาย' in ql or 'สาย' in ql or 'เข้าห้องสอบ' in ql)
        )
        want_exam_temp_leave = (
            ('สอบ' in ql or 'ห้องสอบ' in ql)
            and (('ชั่วคราว' in ql) or ('ออกจากห้องสอบชั่วคราว' in ql) or ('ออกห้องสอบชั่วคราว' in ql))
        )

        if (want_exam_late or want_exam_temp_leave) and (final or []) and (fused or []):
            def _src_key(d: Dict) -> str:
                return _normalize_source_key(str(d.get('source') or d.get('path') or '')) or ''

            def _is_clause16(d: Dict) -> bool:
                t = str(d.get('text') or '')
                return ('ข้อ 16' in t) and (('ชั่วคราว' in t) or ('ออกจากห้องสอบ' in t) or ('กรรมการคุมสอบ' in t) or ('เครื่องมือสื่อสาร' in t))

            def _is_clause12(d: Dict) -> bool:
                t = str(d.get('text') or '')
                if 'ข้อ 12' not in t:
                    return False
                # Prefer the specific late-arrival policy chunk.
                return (
                    ('ห้องสอบ' in t)
                    and (('สิบห้านาที' in t) or ('15' in t))
                    and (('หกสิบนาที' in t) or ('60' in t))
                )

            # 1) Ensure clause 16 if asked.
            if want_exam_temp_leave and (not any(_is_clause16(d) for d in final)):
                cand16 = next((d for d in fused if _is_clause16(d)), None)
                if cand16 and (not any(str(x.get('doc_id') or '') == str(cand16.get('doc_id') or '') for x in final)):
                    add_metric('multi_doc_force_clause16', 1)
                    sk = _src_key(cand16)
                    swap_idx = None
                    if sk:
                        same_src = [
                            (i, d) for i, d in enumerate(final)
                            if _src_key(d) == sk
                        ]
                        if same_src:
                            same_src.sort(key=lambda p: float((p[1].get('score_final') or p[1].get('score_rrf') or 0.0)))
                            swap_idx = same_src[0][0]
                    if swap_idx is None:
                        swap_idx = min(
                            range(len(final)),
                            key=lambda i: float((final[i].get('score_final') or final[i].get('score_rrf') or 0.0)),
                        )
                    final[int(swap_idx)] = cand16
                    final.sort(key=lambda x: float(x.get('score_final') or x.get('score_rrf') or 0.0), reverse=True)

            # 2) Ensure clause 12 if asked (and avoid keeping two clause-16 chunks).
            if want_exam_late and (not any(_is_clause12(d) for d in final)):
                cand12 = next((d for d in fused if _is_clause12(d)), None)
                if cand12 and (not any(str(x.get('doc_id') or '') == str(cand12.get('doc_id') or '') for x in final)):
                    add_metric('multi_doc_force_clause12', 1)
                    sk = _src_key(cand12)
                    swap_idx = None

                    # Prefer swapping out a redundant clause-16 chunk from the same source.
                    c16_same = [
                        (i, d) for i, d in enumerate(final)
                        if (sk and _src_key(d) == sk and _is_clause16(d))
                    ]
                    if c16_same:
                        c16_same.sort(key=lambda p: float((p[1].get('score_final') or p[1].get('score_rrf') or 0.0)))
                        swap_idx = c16_same[0][0]

                    if swap_idx is None and sk:
                        same_src = [
                            (i, d) for i, d in enumerate(final)
                            if _src_key(d) == sk
                        ]
                        if same_src:
                            same_src.sort(key=lambda p: float((p[1].get('score_final') or p[1].get('score_rrf') or 0.0)))
                            swap_idx = same_src[0][0]

                    if swap_idx is None:
                        swap_idx = min(
                            range(len(final)),
                            key=lambda i: float((final[i].get('score_final') or final[i].get('score_rrf') or 0.0)),
                        )
                    final[int(swap_idx)] = cand12
                    final.sort(key=lambda x: float(x.get('score_final') or x.get('score_rrf') or 0.0), reverse=True)
    except Exception:
        pass

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


_COMMON_TYPO_FIXES: list[tuple[str, str]] = [
    # common Thai typos that frequently appear in chat inputs
    ('หนวยกิต', 'หน่วยกิต'),
    ('หน่วยกิจ', 'หน่วยกิต'),
    ('หนวยกิจ', 'หน่วยกิต'),
    ('หลกสตร', 'หลักสูตร'),
    ('หลักสุตร', 'หลักสูตร'),
    ('แผนการเรยน', 'แผนการเรียน'),
    ('ลงทะเบยน', 'ลงทะเบียน'),
    ('ลงทะเบีย', 'ลงทะเบียน'),
]


def normalize_question(question: str) -> str:
    """Normalize user input while keeping it readable for the prompt."""
    q = (question or '').strip()
    if not q:
        return ''

    # Unicode normalization helps with odd punctuation/fullwidth characters.
    q = unicodedata.normalize('NFKC', q)

    # Normalize Thai digits and common dash characters.
    q = q.translate(_THAI_TO_ARABIC)
    q = q.replace('–', '-').replace('—', '-').replace('−', '-')

    # Normalize whitespace
    q = re.sub(r"\s+", " ", q).strip()

    # Fix a few common typos / synonyms
    for src, dst in _LANG_SYNONYMS:
        q = q.replace(src, dst)
    for src, dst in _COMMON_TYPO_FIXES:
        q = q.replace(src, dst)

    # Light bilingual augmentation for better recall (vector/keyword).
    # Keep this readable (only appends a single English hint).
    for th, en in _LANG_AUGMENT.items():
        if th in q and en not in q:
            q = f"{q} ({en})"
    return q


def _expand_course_code_variants(q: str) -> list[str]:
    """Generate compact search variants for common course-code formats.

    Keeps output small; intended for retrieval/query-time only.
    """
    if not q:
        return []

    variants: list[str] = []

    # Normalize common digit typos in alphanum codes, e.g. CPE1O0 -> CPE100
    q2 = re.sub(r"(?<=\d)[oO](?=\d)", "0", q)

    # Alphanumeric course codes: CPE100 / CPE-100 / CPE 100
    for m in re.finditer(r"\b([A-Za-z]{2,6})\s*[-]?\s*([0-9]{3})\b", q2):
        pfx = (m.group(1) or '').upper()
        num = m.group(2) or ''
        if not pfx or not num:
            continue
        variants.extend([f"{pfx}{num}", f"{pfx} {num}", f"{pfx}-{num}"])

    # Placeholder family codes: LNGxxx / lngXX -> LNGxxx + LNG
    for m in re.finditer(r"\b([A-Za-z]{2,6})[xX]{2,}\b", q2):
        pfx = (m.group(1) or '').upper()
        if len(pfx) >= 2:
            variants.extend([f"{pfx}xxx", pfx])

    # Numeric Thai uni codes: 261-101 / 261 101 / 261.101 -> 261101 and friends
    for m in re.finditer(r"\b([0-9]{3})\s*[- .]\s*([0-9]{3})\b", q2):
        a = m.group(1) or ''
        b = m.group(2) or ''
        if a and b:
            variants.extend([f"{a}{b}", f"{a}-{b}", f"{a} {b}"])

    # De-dup, keep order, cap for prompt safety
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        v = (v or '').strip()
        if not v or v in seen:
            continue
        out.append(v)
        seen.add(v)
        if len(out) >= 8:
            break
    return out


def search_query_from_question(question: str) -> str:
    """Return a retrieval-optimized query string.

    Important: this may include additional normalized variants, but should not
    be used verbatim as the question shown to the model/user.
    """
    q = normalize_question(question)
    if not q:
        return ''
    variants = _expand_course_code_variants(q)
    if not variants:
        return q
    # Append compact hint block; keep it short.
    hint = ' / '.join(variants[:8])
    if hint and hint not in q:
        return f"{q} ({hint})"
    return q


def normalize_query_for_retrieval(q: str) -> str:
    """Normalize query for retrieval (search-time only).

    More aggressive than `normalize_question()`; aims to reduce formatting variance
    (Thai digits, separators, course-code spacing) before semantic/keyword search.
    """
    txt = (q or '').strip()
    if not txt:
        return ''
    txt = unicodedata.normalize('NFKC', txt)
    txt = txt.translate(_THAI_TO_ARABIC)
    txt = txt.replace('–', '-').replace('—', '-').replace('−', '-')
    txt = re.sub(r"[-_/]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    # CPE-101 / CPE 101 -> CPE101
    txt = re.sub(r"\b([A-Za-z]{2,6})\s+(\d{3})\b", r"\1\2", txt)
    txt = re.sub(r"\b([A-Za-z]{2,6})-(\d{3})\b", r"\1\2", txt)
    return txt


def normalize_query_for_keyword(q: str) -> str:
    """Normalize while preserving exact lexical anchors."""
    txt = (q or '').strip()
    if not txt:
        return ''
    txt = unicodedata.normalize('NFKC', txt)
    txt = txt.translate(_THAI_TO_ARABIC)
    txt = txt.replace('–', '-').replace('—', '-').replace('−', '-')
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def build_retrieval_queries(question: str) -> tuple[str, str]:
    raw = (question or '').strip()
    if not raw:
        return '', ''
    semantic_q = normalize_query_for_retrieval(search_query_from_question(raw))
    keyword_q = normalize_query_for_keyword(raw)
    return semantic_q, keyword_q


def extract_lexical_anchors(q: str) -> List[str]:
    """Extract high-signal tokens (course codes, clauses, numbers) for anti-drift."""
    txt = normalize_query_for_keyword(q)
    if not txt:
        return []

    anchors: List[str] = []

    course_anchors: List[str] = []
    clause_anchors: List[str] = []

    # Course code anchors: normalize to compact form (CPE123).
    for m in re.finditer(r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b", txt):
        pfx = (m.group(1) or '').upper()
        num = (m.group(2) or '').strip()
        if pfx and num:
            course_anchors.append(f"{pfx}{num}")

    anchors.extend(course_anchors)

    # Thai clause/article anchors.
    for m in re.finditer(r"(ข้อ|มาตรา)\s*(\d{1,4})", txt):
        kind = (m.group(1) or '').strip()
        num = (m.group(2) or '').strip()
        if kind and num:
            clause_anchors.append(f"{kind} {num}")

    anchors.extend(clause_anchors)

    # Time-unit anchors (e.g., '15 นาที')
    for m in re.finditer(r"\b(\d{1,3})\s*(นาที|ชม\.|ชั่วโมง|วัน|สัปดาห์)\b", txt):
        n = (m.group(1) or '').strip()
        u = (m.group(2) or '').strip()
        if n and u:
            anchors.append(f"{n} {u}")

    # Numeric anchors are useful when the question is *only* numeric (e.g., '15 นาที'),
    # but become noisy when a stronger anchor already exists (course code / clause).
    if (not course_anchors) and (not clause_anchors):
        for m in re.finditer(r"\b\d{1,4}\b", txt):
            anchors.append(m.group(0))

    # Domain-intent anchors: help curriculum/regulations beat broad announcements/calendar docs.
    ql = txt.lower()
    keyword_anchors = [
        # curriculum-ish
        'หน่วยกิต', 'หลักสูตร', 'วิชาศึกษาทั่วไป', 'หมวด', 'วิชาเลือก', 'วิชาบังคับ', 'ก่อนเรียน',
        'prerequisite', 'pre-requisite', 'gpa', 'เกรด',
        # regulations-ish
        'ระเบียบ', 'ข้อบังคับ', 'อุทธรณ์', 'ทุจริต', 'วินัย', 'มาสาย', 'หมดสิทธิ์',
    ]
    for t in keyword_anchors:
        if t and t.lower() in ql:
            anchors.append(t)

    # Add 'สอบ' only when the question is explicitly about rules/discipline,
    # otherwise it tends to drag in exam schedules for course-code queries.
    if 'สอบ' in ql:
        regs_cues = ('ระเบียบ', 'ข้อบังคับ', 'อุทธรณ์', 'ทุจริต', 'วินัย', 'มาสาย', 'หมดสิทธิ์')
        if any(c in ql for c in regs_cues):
            anchors.append('สอบ')

    out: List[str] = []
    seen: set[str] = set()
    for a in anchors:
        s = (a or '').strip()
        if not s:
            continue
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
        if len(out) >= 12:
            break
    return out


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
    bonus: float = _DOMAIN_PRIOR_BONUS,
    penalty: float = _DOMAIN_PRIOR_PENALTY,
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
    topn: int = _DOMAIN_RESCUE_TOPN,
    margin: float = _DOMAIN_RESCUE_MARGIN,
    require_majority: int = _DOMAIN_RESCUE_REQUIRE_MAJORITY,
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


def promote_exact_anchor_hits(items: List[Dict], anchors: List[str], bonus_per_hit: float = _ANCHOR_HIT_BONUS) -> List[Dict]:
    if not items or not anchors:
        return items
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
            if s in blob:
                bonus += float(bonus_per_hit)
                continue
            s2 = re.sub(r"[^0-9a-zก-๙]+", "", s)
            if s2 and s2 in blob_norm:
                bonus += float(bonus_per_hit)

        u = dict(d)
        base = float(u.get('score_rrf') or 0.0)
        u['score_final'] = base + bonus
        u['score_rrf'] = u['score_final']
        out.append(u)
    out.sort(key=lambda x: float(x.get('score_rrf') or 0.0), reverse=True)
    return out


def diversify_by_source(items: List[Dict], max_per_source: int = _MAX_PER_SOURCE, limit: int = MAX_CONTEXTS) -> List[Dict]:
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


def _extract_prefix_from_question(question: str) -> str | None:
    q = (question or '')
    # Prefer explicit patterns like LNGxxx / CPExxx
    m = re.search(r"\b([A-Za-z]{2,6})[xX]{2,}\b", q)
    if m:
        pref = re.sub(r"[xX]+$", "", m.group(1) or '')
        pref = pref.strip().upper()
        return pref or None
    # Or standalone prefix tokens
    toks = [t.upper() for t in re.findall(r"\b[A-Za-z]{2,6}\b", q)]
    if not toks:
        return None
    stop = {
        'AND', 'OR', 'NOT', 'THE', 'THIS', 'THAT', 'WITH', 'FROM', 'WHAT', 'HOW', 'WHY',
        'CAN', 'COULD', 'SHOULD', 'WANT', 'FIND', 'COURSE', 'COURSES', 'CODE'
    }
    toks = [t for t in toks if t not in stop]
    return toks[0] if toks else None


def _is_prefix_list_question(question: str) -> bool:
    q = (question or '')
    ql = q.lower()
    if 'xxx' in ql:
        return True
    return any(t in q for t in ('รหัสวิชา', 'มีวิชาอะไร', 'วิชาอะไรบ้าง', 'รายวิชา', 'ทั้งหมด', 'มีกี่วิชา'))


def structured_curriculum_answer(question: str) -> str | None:
    """Deterministic answers for curriculum domain (no top-k dependence)."""
    q = normalize_question(question)
    q_lower = q.lower()

    totals = load_credit_totals_2564()
    curriculum = load_cpe_curriculum_2564()
    source_name = curriculum.source_path.name if curriculum else 'FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt'

    # 0) Category totals lookup from the canonical 2564 curriculum source.
    if any(t in q for t in ('หมวดวิชาศึกษาทั่วไป', 'วิชาศึกษาทั่วไป', 'ศึกษาทั่วไป')) and 'หน่วยกิต' in q:
        ge = totals.get('general_education')
        if ge is not None:
            return f"- หมวดวิชาศึกษาทั่วไปต้องศึกษารวม {ge} หน่วยกิต [{source_name}/1]"

        sp = totals.get('specific')
        if sp is not None:
            return f"- หมวดวิชาเฉพาะต้องศึกษารวม {sp} หน่วยกิต [{source_name}/1]"

    # 0.5) Total-program-credit lookup from the canonical 2564 curriculum source.
    if 'หน่วยกิต' in q and (
        any(t in q for t in ('รวมกี่หน่วยกิต', 'หน่วยกิตรวมของหลักสูตร', 'จำนวนหน่วยกิตรวม', 'ตลอดหลักสูตร'))
        or ('หลักสูตร' in q and any(t in q for t in ('กี่', 'ทั้งหมด', 'รวม')))
    ):
        tot = totals.get('total')
        if tot is not None:
            return (
                f"- หลักสูตรวิศวกรรมคอมพิวเตอร์ต้องศึกษารวม {tot} หน่วยกิต [{source_name}/1]\n"
                f"- ข้อความอ้างอิงคือ จำนวนหน่วยกิตรวมตลอดหลักสูตร {tot} หน่วยกิต [{source_name}/1]"
            )

    # 0.1) Exact course-code lookup from the canonical 2564 curriculum source.
    # If the query asks about instructor/teacher, do not force a title+credit answer.
    instructor_intent = any(t in q for t in ('ใครสอน', 'ผู้สอน', 'อาจารย์', 'คนสอน'))

    # If the user asks about prerequisites or where the course appears in the study plan
    # (term/semester/year), do not shortcut to title+credits; prefer full RAG retrieval.
    prereq_intent = any(t in q for t in (
        'ต้องผ่าน', 'บังคับก่อน', 'วิชาบังคับก่อน', 'ผ่านอะไรก่อน', 'prereq', 'pre-req', 'prerequisite', 'เงื่อนไขก่อน'
    ))
    term_intent = any(t in q for t in (
        'เทอม', 'ภาค', 'ภาคการศึกษา', 'semester', 'ปีที่', 'ชั้นปี', 'อยู่ปี', 'เรียนปี'
    ))

    # When question is composed as:
    #   "<prev>\nคำถามต่อเนื่อง: <last>"
    # prioritize course codes from the follow-up segment to avoid stale-code bleed.
    def _codes_in_order(text: str) -> list[str]:
        vals: list[str] = []
        for m in re.finditer(r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b", text or ''):
            vals.append(f"{(m.group(1) or '').upper()} {(m.group(2) or '')}".strip())
        # Backward compatibility: merge parser-based extraction too.
        for c in list(extract_course_codes(text or '')):
            vals.append((c or '').strip())
        out: list[str] = []
        seen: set[str] = set()
        for c in vals:
            s = (c or '').strip()
            if not s:
                continue
            k = s.replace('-', '').replace(' ', '').upper()
            if k in seen:
                continue
            seen.add(k)
            out.append(s)
        return out

    followup_codes: list[str] = []
    explicit_followup = re.search(r"ค(?:ำ|ํา)ถามต่อเนื่อง\s*:", q) is not None
    if explicit_followup:
        parts = re.split(r"ค(?:ำ|ํา)ถามต่อเนื่อง\s*:", q, maxsplit=1)
        tail = (parts[1] if len(parts) > 1 else '').strip()
        if tail:
            followup_codes = _codes_in_order(tail)

    codes = followup_codes or _codes_in_order(q)
    if codes and not instructor_intent and not (prereq_intent or term_intent):
        all_courses = load_all_courses_2564()
        # Prefer the latest-mentioned code in the user message to avoid stale-code bleed.
        for code in reversed(codes):
            key = code.replace('-', '').replace(' ', '').upper()
            course = all_courses.get(key)
            if not course:
                continue
            curriculum = load_cpe_curriculum_2564()
            source_name = curriculum.source_path.name if curriculum else 'FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt'
            credit_text = f"{course.credits} หน่วยกิต" if course.credits else 'ไม่พบจำนวนหน่วยกิตในข้อความที่ parse ได้'
            return (
                f"- วิชา {course.prefix} {course.number} คือ {course.title_th} [{source_name}/1]\n"
                f"- วิชา {course.prefix} {course.number} มีจำนวน {credit_text} [{source_name}/1]"
            )
        # If user explicitly asked a follow-up code and that code isn't in canonical list,
        # do not fall back to an older code from previous turns.
        if explicit_followup and followup_codes:
            return None

    # 1) Full required CPE list (curriculum 2564 study plan)
    required = format_required_cpe_answer(q)
    if required:
        return required

    # 2) List courses under a prefix (e.g., LNGxxx / CPE มีรหัสวิชาอะไรบ้าง)
    pref = _extract_prefix_from_question(q)
    if pref and _is_prefix_list_question(q):
        # Prefer deterministic canonical curriculum list first.
        all_courses = load_all_courses_2564()
        from_canonical = [c for c in all_courses.values() if (c.prefix or '').upper() == pref.upper()]
        if from_canonical:
            items = sorted(from_canonical, key=lambda c: int(c.number))
            curriculum = load_cpe_curriculum_2564()
            source_name = curriculum.source_path.name if curriculum else 'FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt'
            lines: list[str] = []
            lines.append(f"รหัสวิชา {pref} ที่พบในโดเมนหลักสูตร (curriculum):")
            lines.append(f"- พบทั้งหมด {len(items)} วิชา [{source_name}/1]")
            for c in items:
                cred = f" ({c.credits} หน่วยกิต)" if c.credits else ""
                lines.append(f"- {c.prefix} {c.number} {c.title_th}{cred} [{source_name}/1]")
            return "\n".join(lines).strip()

        sqlite_path = domain_sqlite_path('curriculum')
        # Pull chunks that look like course descriptions first.
        ids = keyword_search(f"รายวิชา: {pref}", limit=600, sqlite_path=sqlite_path)
        if not ids:
            ids = keyword_search(pref, limit=600, sqlite_path=sqlite_path)
        docs = fetch_docs_with_path(ids, sqlite_path=sqlite_path)
        bank: dict[str, Course] = {}
        sources: list[str] = []
        for d in docs:
            if d.get('source') and d.get('source') not in sources:
                sources.append(str(d.get('source')))
            for c in extract_courses_from_text(d.get('text') or '', prefix_filter=pref):
                bank.setdefault(c.code, c)

        if not bank:
            return None

        items = sorted(bank.values(), key=lambda c: int(c.number))
        lines: list[str] = []
        lines.append(f"รหัสวิชา {pref} ที่พบในโดเมนหลักสูตร (curriculum):")
        lines.append(f"- พบทั้งหมด {len(items)} วิชา")
        for c in items:
            cred = f" ({c.credits} หน่วยกิต)" if c.credits else ""
            lines.append(f"- {c.prefix} {c.number} {c.title_th}{cred}")
        if sources:
            lines.append(f"\nแหล่งอ้างอิง (ตัวอย่าง): {', '.join(sources[:3])}")
        return "\n".join(lines).strip()

    return None


def infer_domain(question: str) -> str | None:
    """Best-effort domain inference to reduce cross-domain noise.

    Returns one of KNOWN_DOMAINS (e.g., 'curriculum', 'regulations', 'announcements')
    or None if unclear.
    """
    q = (question or '').strip()
    if not q:
        return None

    ql = q.lower()

    # Curriculum signals: course codes / prefixes / curriculum-specific keywords.
    # Strong signal: explicit course codes (e.g., CPE 342, LNG 220, GEN 121)
    if re.search(r"\b[A-Za-z]{2,6}\s*\d{3}\b", q):
        return 'curriculum'
    
    # Strong signal: common curriculum prefixes
    if re.search(r"\b(cpe|lng|ssc|gen|cpx|cen|csc)\b", ql):
        return 'curriculum'
    
    # Medium signals: curriculum-specific keywords and phrases
    curriculum_indicators = (
        'หลักสูตร',           # curriculum
        'แผนการเรียน',        # study plan
        'หน่วยกิต',           # credits
        'วิชาบังคับ',         # required courses
        'วิชาเลือก',          # elective courses
        'คำอธิบายรายวิชา',    # course description
        'รายวิชา',            # course (if not registrar op)
        'ต้องผ่าน',           # must pass / prerequisite
        'บังคับก่อน',         # prerequisite
        'วิชาบังคับก่อน',     # prerequisite courses
        'ก่อนเรียน',          # before studying
        'สาขาวิชา',           # major/branch
        'กลุ่มวิชา',           # course group
        'หมวดวิชา',           # course category
        'ปีที่',               # year level
        'ชั้นปี',              # academic year/level
        'ภาคการศึกษา',        # semester
        'ต้องมีพื้นฐาน',       # must have foundation
    )
    
    # Don't route registrar operations to curriculum  
    _registrar_ops = ('ถอนรายวิชา', 'เพิ่ม-ลด', 'เพิ่มลด', 'ลงทะเบียน', 'ปฏิทิน', 'กำหนดการ')
    
    if any(t in q for t in curriculum_indicators) and not any(op in q for op in _registrar_ops):
        return 'curriculum'
    
    # Strong signal: foreign language questions with specific languages (likely LNG courses)
    if 'ภาษา' in q and any(t in q for t in ('จีน', 'ญี่ปุ่น', 'เกาหลี', 'ฝรั่งเศส', 'สเปน', 'เยอรมัน', 'รัสเซีย', 'มลายู', 'มาเล', 'ญี่ปุ่น', 'พม่า')):
        return 'curriculum'

    # Regulations/registrar signals.
    # Exam-policy / discipline questions should go to regulations even if they contain time words.
    _exam_policy_terms = (
        'ห้องสอบ', 'เข้าห้องสอบ', 'ออกห้องสอบ', 'ออกจากห้องสอบ', 'ออกห้องสอบชั่วคราว',
        'กรรมการคุมสอบ', 'คุมสอบ', 'ข้อสอบ', 'กระดาษคำตอบ', 'สมุดคำตอบ',
        'ทุจริต', 'ส่อ', 'ลงโทษ', 'บทลงโทษ', 'อุทธรณ์', 'คำอุทธรณ์',
        'คณะกรรมการกลาง', 'คณะกรรมการสอบ',
    )
    if any(t in q for t in _exam_policy_terms):
        return 'regulations'

    # Schedule / calendar / registration timing: these usually live in announcements.
    if any(t in q for t in ('ปฏิทิน', 'กำหนดการ', 'ลงทะเบียน', 'เพิ่ม-ลด', 'เพิ่มลด', 'ช่วง', 'วัน', 'วันที่', 'เมื่อไหร่')):
        return 'announcements'
    
    # Withdraw/W questions often need the academic calendar (announcements) more than policy text.
    if ('ถอนรายวิชา' in q or re.search(r"\bW\b|\(W\)", q, re.IGNORECASE)):
        # If user asks for when/how, prefer announcements.
        if any(t in q for t in ('เมื่อไหร่', 'ทำได้เมื่อไหร่', 'ช่วงไหน', 'ทำอย่างไร', 'ขั้นตอน', 'กำหนด')):
            return 'announcements'
        return 'regulations'

    if any(t in q for t in ('คำร้อง', 'แบบฟอร์ม', 'RO-', 'ลาออก', 'ลาป่วย', 'ลากิจ', 'ทัณฑ์บน', 'วินัย', 'ตัดคะแนนความประพฤติ', 'สอบซ้อน', 'เข้าสอบ')):
        return 'regulations'

    # Announcements signals.
    if 'ประกาศ' in q or 'announcement' in ql:
        return 'announcements'

    return None


def infer_domain_bias(question: str) -> str | None:
    """Lightweight fallback domain bias when infer_domain() is inconclusive.

    Used only as a soft hint (never a hard gate) by all-domain fusion.
    """
    q = (question or '').strip().lower()
    if not q:
        return None

    # Strong hint: course-code questions are usually curriculum, unless explicitly about exam schedules.
    has_course_code = re.search(r"\b[a-z]{2,6}\s*[- ]?\s*\d{3}\b", q, flags=re.IGNORECASE) is not None
    examish = any(t in q for t in ('ตารางสอบ', 'สอบกลางภาค', 'สอบปลายภาค', 'วันสอบ', 'สอบ'))
    if has_course_code and not examish:
        return 'curriculum'

    curriculum_terms = [
        'หน่วยกิต', 'หลักสูตร', 'วิชาศึกษาทั่วไป', 'วิชาเลือก', 'วิชาบังคับ', 'ก่อนเรียน',
        'prerequisite', 'pre-requisite',
    ]
    regulations_terms = [
        'ระเบียบ', 'ข้อบังคับ', 'อุทธรณ์', 'ทุจริต', 'มาสาย', 'หมดสิทธิ์', 'วินัย',
    ]
    announcements_terms = [
        'ประกาศ', 'กำหนดการ', 'ปฏิทิน', 'เปิด', 'ปิด', 'ชำระ', 'ค่าธรรมเนียม',
    ]

    if any(t in q for t in curriculum_terms):
        return 'curriculum'
    if any(t in q for t in regulations_terms):
        return 'regulations'
    if any(t in q for t in announcements_terms):
        return 'announcements'
    return None


def fallback_domains_for_domain(primary: str | None) -> list[str] | None:
    """Prefer nearby domains before widening retrieval across everything."""
    p = (primary or '').strip().lower()
    if p == 'announcements':
        return ['announcements', 'regulations']
    if p == 'regulations':
        return ['regulations', 'announcements']
    if p == 'curriculum':
        return ['curriculum', 'announcements']
    return None


def fallback_min_results() -> int:
    """Minimum retrieval count before trying a wider domain fallback."""
    try:
        return max(1, int(os.getenv('RAG_DOMAIN_FALLBACK_MIN_RESULTS', '2') or '2'))
    except Exception:
        return 2

def est_tokens(text: str) -> int:
    return max(1, int(math.ceil(len(text) / CHAR_PER_TOKEN)))


def _cite_label(c: Dict) -> str:
    src = c.get('source') or c.get('path') or 'unknown'
    try:
        name = Path(str(src)).name
    except Exception:
        name = str(src)
    page = c.get('page_start')
    try:
        page_i = int(page) if page is not None else 0
    except Exception:
        page_i = 0
    return f"{name}/{page_i}"


def _extract_reference_filename(question: str) -> str | None:
    """Extract a hinted source filename from the question.

    Supports patterns used in evaluation CSV, e.g. "(อ้างอิง: t_fee.txt)".
    Returns only the basename (no directories).
    """
    q = (question or '')
    m = re.search(r"\(\s*อ้างอิง\s*:\s*([^\)]+)\)", q)
    if not m:
        return None
    raw = (m.group(1) or '').strip().strip('"').strip("'")
    if not raw:
        return None
    # If user wrote multiple, pick the first token.
    raw = raw.split(',')[0].strip()
    try:
        return Path(raw).name
    except Exception:
        return raw


def _reference_candidates(question: str) -> list[str]:
    """Return likely filename variants for an '(อ้างอิง: ...)' hint."""
    ref = _extract_reference_filename(question)
    if not ref:
        return []
    try:
        base = Path(ref).name
    except Exception:
        base = str(ref).strip()
    base = (base or '').strip()
    if not base:
        return []

    try:
        p = Path(base)
        stem = p.stem
        ext = p.suffix
    except Exception:
        stem, ext = base, ''

    variants = [
        base,
        base.replace('-', '_'),
        base.replace('_', '-'),
    ]

    # Add .txt if missing or different
    if ext.lower() != '.txt':
        variants.append(stem + '.txt')

    # Normalize stem dash/underscore
    variants.append(stem.replace('-', '_') + '.txt')
    variants.append(stem.replace('_', '-') + '.txt')

    out: list[str] = []
    seen: set[str] = set()
    for v in variants:
        v = (v or '').strip()
        if not v:
            continue
        k = v.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(v)
    return out


def _infer_domain_from_reference(question: str) -> str | None:
    """Infer domain by checking for the referenced file under repo data/<domain>/."""
    cands = _reference_candidates(question)
    if not cands:
        return None
    data_root = Path(ROOT_DIR) / 'data'
    for dom in KNOWN_DOMAINS:
        for c in cands:
            try:
                if (data_root / dom / c).exists():
                    return dom
            except Exception:
                continue
    return None


def _filter_chunks_by_reference(chunks: List[Dict], question: str, strict: bool = False) -> List[Dict]:
    """If question explicitly references a source file, keep only matching chunks.

    If strict=True and the reference doesn't match any chunk, return an empty list.
    Otherwise (default), behaves conservatively and keeps the original list.
    """
    cands = _reference_candidates(question)
    if not cands:
        return chunks
    cand_l = {c.lower() for c in cands}

    def _src_name(d: Dict) -> str:
        src = d.get('source') or d.get('path') or (d.get('metadata') or {}).get('source') or (d.get('metadata') or {}).get('path')
        try:
            return Path(str(src)).name.lower()
        except Exception:
            return str(src or '').lower()

    filtered = [c for c in (chunks or []) if _src_name(c) in cand_l]
    # If strict match fails, allow "contains" (handles slightly different stored names).
    if not filtered:
        filtered = [c for c in (chunks or []) if any(cl in _src_name(c) for cl in cand_l)]

    # Keep original if we'd lose essentially all context (unless strict).
    if strict:
        return filtered
    if len(filtered) >= 2 or (len(filtered) == 1 and len(chunks) <= 3):
        return filtered
    return chunks


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
    doms = [d.strip().lower() for d in (domains or list(KNOWN_DOMAINS)) if (d or '').strip()]
    if not doms:
        doms = list(KNOWN_DOMAINS)

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
            # Best-effort: if one domain is missing/corrupt, still answer from others.
            continue

        # retrieve_by_domain already returns a ranked list; fuse across domains via RRF.
        for r, d in enumerate(results, 1):
            doc_id = d.get('doc_id') or d.get('source') or f'unk_{r}'
            key = f"{dom}:{doc_id}"
            if key not in bank:
                bank[key] = {**d, 'doc_id': doc_id, 'domain': dom}
            else:
                bank[key].setdefault('domain', dom)
            ranks[key] = ranks.get(key, 0.0) + 1.0 / (RRF_K + r)

    merged = [{**bank[k], 'score_rrf': v} for k, v in ranks.items()]

    # Soft domain prior (boost), never a hard gate.
    inferred = infer_domain(normalize_question(question)) or infer_domain_bias(question)
    merged = apply_domain_prior(merged, inferred)

    # Exact-anchor promotion to avoid losing "ข้อ 12", course codes, etc.
    anchors = extract_lexical_anchors(question)
    merged = promote_exact_anchor_hits(merged, anchors)

    # Intent-aware boost: keep all-domain recall, but prioritize regulations
    # when the question clearly asks about exam rules/policies.
    ql = (question or '').strip().lower()
    exam_policy_intent = (
        any(t in ql for t in ('สอบ', 'ห้องสอบ', 'คุมสอบ', 'มาสาย', 'ทุจริต', 'อุทธรณ์'))
        and any(t in ql for t in ('ได้กี่', 'กี่นาที', 'กี่วัน', 'ระเบียบ', 'ข้อ', 'นโยบาย', 'อนุญาต'))
    )
    if exam_policy_intent:
        boosted: List[Dict] = []
        for d in merged:
            u = dict(d)
            dom = str(u.get('domain') or '').strip().lower()
            src = str(u.get('source') or '').strip().lower()
            score = float(u.get('score_final') or u.get('score_rrf') or 0.0)
            if dom == 'regulations':
                score += 0.25
            if ('rule_exam' in src) or ('สอบ' in src and 'ระเบียบ' in src):
                score += 0.55
            if src.endswith('forms.txt'):
                score -= 0.20
            if dom == 'curriculum':
                score -= 0.20
            if dom == 'announcements':
                score -= 0.12
            u['score_final'] = score
            u['score_rrf'] = score
            boosted.append(u)
        merged = boosted

    # Specific clause coverage: temporary leave from exam room (ข้อ 16).
    # In all-domain fusion, the correct clause chunk can rank low and get trimmed
    # before multi-doc has a chance to combine intents.
    want_exam_late = (
        ('สอบ' in ql or 'ห้องสอบ' in ql)
        and ('มาสาย' in ql or 'สาย' in ql or 'เข้าห้องสอบ' in ql)
    )
    want_exam_temp_leave = (
        ('สอบ' in ql or 'ห้องสอบ' in ql)
        and (('ชั่วคราว' in ql) or ('ออกจากห้องสอบชั่วคราว' in ql) or ('ออกห้องสอบชั่วคราว' in ql))
    )
    if (want_exam_late or want_exam_temp_leave) and merged:
        try:
            clause12_bonus = float(os.getenv('RAG_ALLDOM_REGULATIONS_CLAUSE12_BONUS', '0.75') or '0.75')
            clause16_bonus = float(os.getenv('RAG_ALLDOM_REGULATIONS_CLAUSE16_BONUS', '0.85') or '0.85')
        except Exception:
            clause12_bonus = 0.75
            clause16_bonus = 0.85

        boosted2: List[Dict] = []
        for d in merged:
            u = dict(d)
            dom = str(u.get('domain') or '').strip().lower()
            text = str(u.get('text') or '')
            score = float(u.get('score_final') or u.get('score_rrf') or 0.0)
            if dom == 'regulations':
                if want_exam_late:
                    if (
                        ('ข้อ 12' in text)
                        and ('ห้องสอบ' in text)
                        and (('สิบห้านาที' in text) or ('15' in text))
                        and (('หกสิบนาที' in text) or ('60' in text))
                    ):
                        score += clause12_bonus
                if ('ข้อ 16' in text) and (('ชั่วคราว' in text) or ('ออกจากห้องสอบ' in text) or ('กรรมการคุมสอบ' in text) or ('เครื่องมือสื่อสาร' in text)):
                    score += clause16_bonus
            u['score_final'] = score
            u['score_rrf'] = score
            boosted2.append(u)
        merged = boosted2

    # Penalize overbroad sources for curriculum/regulations intents (calendar/schedule leaks).
    merged = apply_overbroad_source_penalty(merged, inferred, question=question)

    merged.sort(key=lambda x: x.get('score_rrf', 0.0), reverse=True)
    merged = majority_domain_rescue(merged)
    final_limit = max(1, int(final_limit))
    max_per_source = max(1, int(max_per_source))

    candidates = merged[: max(final_limit * 4, final_limit)]
    final = diversify_by_source(candidates, max_per_source=max_per_source, limit=final_limit)
    final = majority_domain_rescue(final)
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

    def _augment_curriculum_query(original_question: str, base_query: str) -> str:
        """Domain-specific query expansion for curriculum questions.

        Curriculum data relies heavily on course code matching and structured data.
        We add hints for common question patterns to improve recall.
        """
        q = (original_question or '').strip()
        if not q:
            return base_query

        hints: list[str] = []

        # Course description/title queries
        if any(t in q for t in ('คือวิชาอะไร', 'คือ', 'ชื่อ', 'ชื่อวิชา', 'เรื่องอะไร')):
            hints.extend(['รายวิชา', 'คำอธิบายวิชา', 'course description', 'title'])

        # Credit/unit queries
        if any(t in q for t in ('หน่วยกิต', 'กี่หน่วย', 'หน่วยการศึกษา', 'หน่วยกิตรวม')):
            hints.extend(['หน่วยกิต', 'credit', 'units', 'ชั่วโมง'])

        # Year/semester queries
        if any(t in q for t in ('ปีไหน', 'ชั้นปี', 'ปีที่', 'เทอม', 'ภาค')):
            hints.extend(['ปีที่', 'ชั้นปี', 'ภาคการศึกษา', 'semester', 'year'])

        # Category/group queries
        if any(t in q for t in ('กลุ่มวิชา', 'หมวดวิชา', 'แผนกวิชา', 'สาขา')):
            hints.extend(['หมวดวิชา', 'กลุ่มวิชา', 'category', 'group'])

        # Prerequisite queries
        if any(t in q for t in ('ต้องผ่าน', 'บังคับก่อน', 'ก่อนเรียน', 'prerequisite')):
            hints.extend(['วิชาบังคับก่อน', 'prerequisite', 'requirement', 'ต้องมีพื้นฐาน'])

        # Lecturer queries
        if any(t in q for t in ('ใครสอน', 'อาจารย์', 'ผู้สอน', 'teacher')):
            hints.extend(['อาจารย์', 'ผู้สอน', 'lecturer', 'instructor', 'teacher'])

        # Course code patterns
        if re.search(r"\b[A-Za-z]{2,6}\s*\d{3}\b", q):
            hints.extend(['รายวิชา', 'course code', 'course number'])

        # De-dup while preserving order.
        seen: set[str] = set()
        compact: list[str] = []
        for h in hints:
            s = (h or '').strip()
            if not s:
                continue
            k = s.lower()
            if k in seen:
                continue
            seen.add(k)
            compact.append(s)

        if not compact:
            return base_query

        # Keep it short; keyword search benefits from a few clause anchors.
        compact = compact[:12]
        hint_block = ' '.join(compact)
        if hint_block and hint_block not in (base_query or ''):
            return f"{base_query} {hint_block}".strip()
        return base_query

    def _augment_regulations_query(original_question: str, base_query: str) -> str:
        """Domain-specific query expansion for regulations.

        SQLite FTS tokenization for Thai can be brittle (few spaces), and some
        regulation texts contain typos (e.g., 'ออกหากห้องสอบ'). We append a
        compact set of high-signal keywords/clauses to improve recall.
        """
        q = (original_question or '').strip()
        if not q:
            return base_query

        hints: list[str] = []

        # Exam room entry/late arrival
        if ('เข้าห้องสอบ' in q) or ('มาสาย' in q) or ('สาย' in q and 'สอบ' in q):
            hints.extend([
                'ห้องสอบ', 'การสอบ',
                'ข้อ 12',
                'สิบห้านาที', '15',
                'หกสิบนาที', '60',
                'ยื่นคำร้อง',
                'ประธานกรรมการจัดการสอบ',
            ])

        # Leaving exam room (permanent)
        if ('ออกห้องสอบ' in q) or ('ออกจากห้องสอบ' in q):
            hints.extend([
                'ห้องสอบ', 'การสอบ',
                'ข้อ 15',
                'ออกหากห้องสอบ',  # typo present in source
                'หกสิบนาที', '60',
            ])

        # Temporary leave
        if ('ชั่วคราว' in q) or ('ออกห้องสอบชั่วคราว' in q):
            hints.extend([
                'ห้องสอบ', 'ชั่วคราว',
                'ข้อ 16',
                'กรรมการคุมสอบ',
                'เครื่องมือสื่อสาร',
            ])

        # Central committee term / duties
        if 'คณะกรรมการ' in q and ('กลาง' in q or 'สอบกลาง' in q):
            hints.extend([
                'คณะกรรมการกลาง', 'การสอบ', 'ทุจริต',
                'ข้อ 19', 'วาระ', 'สี่ปี', '4 ปี',
                'ข้อ 20', 'อำนาจหน้าที่',
            ])

        # Appeal process
        if 'อุทธรณ์' in q or ('ลงโทษ' in q and 'อุทธรณ์' in q):
            hints.extend([
                'หมวดที่ 5', 'การอุทธรณ์',
                'ข้อ 26', 'ข้อ 27', 'ข้อ 28', 'ข้อ 29', 'ข้อ 30',
                'อธิการบดี',
                'สิบห้าวัน', '15 วัน',
            ])

        # De-dup while preserving order.
        seen: set[str] = set()
        compact: list[str] = []
        for h in hints:
            s = (h or '').strip()
            if not s:
                continue
            k = s.lower()
            if k in seen:
                continue
            seen.add(k)
            compact.append(s)

        if not compact:
            return base_query

        # Keep it short; keyword search benefits from a few clause anchors.
        compact = compact[:18]
        hint_block = ' '.join(compact)
        if hint_block and hint_block not in (base_query or ''):
            return f"{base_query} {hint_block}".strip()
        return base_query

    def _clip_long_regulations_text(item: Dict, original_question: str) -> Dict:
        """Clip very long regulation texts to a relevant excerpt.

        Some regulation sources are indexed as a single large text blob. When
        that happens, `pack_context()` may skip them entirely due to the token
        budget, even if retrieval selected the correct document. We keep the
        same metadata but replace `text` with a focused excerpt.
        """
        try:
            txt = str(item.get('text') or '')
        except Exception:
            return item
        if not txt:
            return item

        # Only clip when the block is huge.
        max_chars = int(os.getenv('RAG_REGULATIONS_CLIP_CHARS', '2200') or '2200')
        if len(txt) <= max_chars:
            return item

        q = (original_question or '').strip()
        anchors: list[str] = []

        # Exam rules
        if ('มาสาย' in q) or ('เข้าห้องสอบ' in q):
            anchors += ['ข้อ 12']
        if ('ออกห้องสอบชั่วคราว' in q) or ('ชั่วคราว' in q and 'ห้องสอบ' in q):
            anchors += ['ข้อ 16']
        if ('ออกห้องสอบ' in q) or ('ออกจากห้องสอบ' in q):
            anchors += ['ข้อ 15', 'ข้อ 17']

        # Committee
        if 'คณะกรรมการ' in q and ('กลาง' in q or 'สอบกลาง' in q):
            anchors += ['ข้อ 19', 'ข้อ 20', 'คณะกรรมการกลาง']

        # Appeal
        if 'อุทธรณ์' in q:
            anchors += ['หมวดที่ 5', 'การอุทธรณ์', 'ข้อ 26', 'ข้อ 27', 'ข้อ 28', 'ข้อ 29', 'ข้อ 30']

        # De-dup anchors
        seen: set[str] = set()
        dedup: list[str] = []
        for a in anchors:
            s = (a or '').strip()
            if not s:
                continue
            k = s.lower()
            if k in seen:
                continue
            seen.add(k)
            dedup.append(s)
        anchors = dedup

        # Find anchor positions.
        hits: list[tuple[int, str]] = []
        for a in anchors:
            p = txt.find(a)
            if p != -1:
                hits.append((p, a))

        # If no anchor found, fallback to the first part.
        if not hits:
            clipped = txt[:max_chars].rstrip()
        else:
            # Some questions include multiple intents (e.g., ข้อ 12 + ข้อ 16).
            # Prefer including multiple small excerpts rather than clipping to only
            # the first anchor, which can drop relevant clauses.
            try:
                max_anchor_snips = max(1, int(os.getenv('RAG_REGULATIONS_CLIP_MAX_ANCHORS', '2') or '2'))
            except Exception:
                max_anchor_snips = 2

            # Keep a window around each anchor; prefer expanding to newline boundaries.
            window = int(os.getenv('RAG_REGULATIONS_CLIP_WINDOW', '1600') or '1600')
            half = max(200, window // 2)

            hits.sort(key=lambda x: x[0])
            picked_hits = hits[:max_anchor_snips]

            parts: list[str] = []
            for pos, hit in picked_hits:
                start = max(0, pos - half)
                end = min(len(txt), pos + half)

                nl_left = txt.rfind('\n', 0, start)
                if nl_left != -1 and (start - nl_left) < 200:
                    start = nl_left + 1
                nl_right = txt.find('\n', end)
                if nl_right != -1 and (nl_right - end) < 200:
                    end = nl_right

                seg = txt[start:end].strip()
                if hit and hit not in seg:
                    seg = (hit + " ...\n" + seg).strip()
                if seg:
                    parts.append(seg)

            if not parts:
                clipped = txt[:max_chars].rstrip()
            else:
                clipped = "\n\n...\n\n".join(parts).strip()
                if len(clipped) > max_chars:
                    clipped = clipped[:max_chars].rstrip() + ' ...'

        out = dict(item)
        out['text'] = clipped
        return out

    def _question_terms_for_rerank(text: str) -> list[str]:
        q = (text or '').strip()
        if not q:
            return []
        stop_terms = {
            'อะไร', 'อย่างไร', 'หรือ', 'และ', 'ของ', 'ใน', 'ที่', 'ได้', 'ไหม', 'บ้าง', 'จาก', 'ให้', 'กับ',
            'เรื่อง', 'ข้อมูล', 'เอกสาร', 'ระบุ', 'ถาม', 'ตอบ', 'หน่อย', 'ครับ', 'ค่ะ', 'คะ', 'คือ', 'มี',
            'เท่าไร', 'เท่าไหร่', 'เมื่อไร', 'วันที่', 'วัน', 'หลักสูตร', 'วิชา', 'รายวิชา'
        }
        out: list[str] = []
        seen: set[str] = set()
        for token in re.findall(r"[\u0E00-\u0E7F]{3,}|[A-Za-z]{2,}|\d{2,4}", q):
            key = token.lower()
            if key in stop_terms or key in seen:
                continue
            seen.add(key)
            out.append(token)
        return out[:8]

    def _apply_lexical_rerank(items: List[Dict], original_question: str, active_domain: str) -> List[Dict]:
        dom = (active_domain or '').strip().lower()
        if dom not in ('announcements', 'regulations') or not items:
            return items
        terms = _question_terms_for_rerank(original_question)
        if not terms:
            return items
        boosted: List[Dict] = []
        for item in items:
            text = ' '.join(
                [
                    str(item.get('text') or ''),
                    str(item.get('source') or ''),
                    str(item.get('path') or ''),
                ]
            ).lower()
            matches = sum(1 for term in terms if term.lower() in text)
            updated = dict(item)
            updated['score_rrf'] = float(updated.get('score_rrf') or 0.0) + (matches * 0.08)
            boosted.append(updated)
        boosted.sort(key=lambda x: float(x.get('score_rrf') or 0.0), reverse=True)
        return boosted

    def _apply_curriculum_rerank(items: List[Dict], original_question: str, target_codes: set[str]) -> List[Dict]:
        """Curriculum-specific reranking to boost exact course code matches.

        Prioritizes documents that directly match extracted course codes.
        """
        if not items or not target_codes:
            return items
        
        boosted: List[Dict] = []
        for item in items:
            updated = dict(item)
            base_score = float(updated.get('score_rrf') or 0.0)
            
            # Check if item matches any target course code
            if _item_matches_course_codes(item, target_codes):
                # Boost score significantly for exact matches
                updated['score_rrf'] = base_score + 0.5
                updated['_curriculum_match'] = True
            
            boosted.append(updated)
        
        # Sort: exact matches first, then by original RRF score
        def sort_key(x):
            has_match = float(x.get('_curriculum_match', False))
            return (has_match, float(x.get('score_rrf', 0.0)))
        
        boosted.sort(key=sort_key, reverse=True)
        
        # Clean up temporary fields
        for item in boosted:
            item.pop('_curriculum_match', None)
        
        return boosted

    def _hydrate_from_sqlite(items: List[Dict], sqlite_path: str | None) -> List[Dict]:
        """Replace item text/metadata from SQLite when doc_id is known.

        Chroma collections can be stale or OCR-corrupted compared to the SQLite index.
        When both share doc_id, prefer SQLite as the canonical source of truth for
        context packing.
        """
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
            # Preserve semantic scores/fields on `it`, but prefer canonical metadata/text from SQLite.
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

    def _meta_get(item: Dict, key: str):
        if key in item:
            return item.get(key)
        md = item.get('metadata') or {}
        if isinstance(md, dict):
            return md.get(key)
        return None

    def _normalize_code_text(text: str) -> str:
        return re.sub(r"[^A-Za-z0-9]", "", (text or '').upper())

    def _item_section_path(item: Dict) -> list[str]:
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

    def _is_faculty_course_relation(item: Dict) -> bool:
        dt = str(_meta_get(item, 'doc_type') or '').strip().lower()
        if dt == 'faculty_course_relation':
            return True
        sec = str(_meta_get(item, 'section') or '').strip().lower()
        if sec == 'facultycourserelation':
            return True
        section_path = '/'.join(_item_section_path(item)).lower()
        return 'facultycourserelation' in section_path

    def _item_matches_course_codes(item: Dict, target_codes: set[str]) -> bool:
        if not target_codes:
            return False

        candidates: list[str] = []
        for k in ('course_code', 'course_code_norm', 'course', 'course_id', 'entity_key'):
            v = _meta_get(item, k)
            if v is not None:
                candidates.append(str(v))
        aliases = _meta_get(item, 'aliases')
        if isinstance(aliases, list):
            candidates.extend([str(x) for x in aliases if x is not None])
        links_to = _meta_get(item, 'links_to')
        if isinstance(links_to, list):
            candidates.extend([str(x) for x in links_to if x is not None])
        candidates.extend(_item_section_path(item))
        txt = item.get('text')
        if isinstance(txt, str) and txt:
            candidates.append(txt)

        for c in candidates:
            norm = _normalize_code_text(c)
            if not norm:
                continue
            for t in target_codes:
                if t and (t == norm or t in norm):
                    return True
        return False

    def _contains_target_code_in_visible_fields(item: Dict, target_codes: set[str]) -> bool:
        if not target_codes:
            return False
        blob = ' '.join(
            [
                str(item.get('text') or ''),
                str(item.get('source') or ''),
                str(item.get('path') or ''),
            ]
        )
        norm_blob = _normalize_code_text(blob)
        if not norm_blob:
            return False
        for t in target_codes:
            if t and t in norm_blob:
                return True
        return False

    dom = (domain or '').strip().lower()
    add_metric('retrieval_domain', dom or 'auto')

    # Some call sites (multi-doc wide retrieval) need a wider per-domain context
    # list than the default MAX_CONTEXTS.
    max_contexts_local = MAX_CONTEXTS
    if max_contexts_override is not None:
        try:
            max_contexts_local = max(1, int(max_contexts_override))
        except Exception:
            max_contexts_local = MAX_CONTEXTS

    semantic_q, keyword_q = build_retrieval_queries(question)
    if dom == 'regulations':
        semantic_q = _augment_regulations_query(question, semantic_q)
    elif dom == 'curriculum':
        semantic_q = _augment_curriculum_query(question, semantic_q)

    anchors = extract_lexical_anchors(keyword_q or question)

    ref_allow = _reference_candidates(question)
    source_allowlist: Sequence[str] | None = ref_allow if ref_allow else None
    strict_ref_hints = (os.getenv('STRICT_REFERENCE_HINTS', '1') or '1').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )
    strict_ref = bool(source_allowlist) and strict_ref_hints
    add_metric('retrieval_ref_hint_count', len(ref_allow or []))
    add_metric('retrieval_strict_ref', int(strict_ref))

    # Domain 1&2: vector + keyword/FTS
    if dom in ('announcements', 'regulations'):
        sqlite_path = domain_sqlite_path(dom)

        sem, kw_ids = _retrieve_semantic_and_keyword(
            semantic_q,
            keyword_q,
            k_vec,
            k_kw,
            dom,
            sqlite_path,
            source_allowlist,
        )
        with time_block('hydrate_sqlite'):
            if sem:
                sem = _hydrate_from_sqlite(sem, sqlite_path)
        with time_block('fetch_kw_docs'):
            kw_docs = fetch_docs_with_path(kw_ids, sqlite_path=sqlite_path) if kw_ids else []

        # Hard anchor for exam-room policy queries via vector index only.
        if dom == 'regulations':
            ql = (question or '').strip().lower()
            exam_late_intent = (
                ('สอบ' in ql or 'ห้องสอบ' in ql)
                and ('มาสาย' in ql or 'สาย' in ql or 'เข้าห้องสอบ' in ql)
            )
            if exam_late_intent:
                add_metric('retrieval_exam_late_anchor', 1)
                with time_block('vector_search_exam_anchor'):
                    sem_extra = semantic_search_domain(
                        'ข้อ 12 ห้องสอบ มาสาย สิบห้านาที 15 หกสิบนาที 60',
                        top_k=max(20, k_vec * 2),
                        domain='regulations',
                        source_allowlist=None,
                    )
                with time_block('hydrate_sqlite_exam_anchor'):
                    sem_extra = _hydrate_from_sqlite(sem_extra, sqlite_path)
                if sem_extra:
                    clause12_docs: List[Dict] = []
                    other_docs: List[Dict] = []
                    for d in sem_extra:
                        txt = str(d.get('text') or '')
                        if ('ข้อ 12' in txt and 'ห้องสอบ' in txt and (('สิบห้านาที' in txt) or ('15' in txt)) and (('หกสิบนาที' in txt) or ('60' in txt))):
                            clause12_docs.append(d)
                        else:
                            other_docs.append(d)
                    prioritized = [*clause12_docs, *other_docs]
                    seen_doc_ids: set[str] = {
                        str(d.get('doc_id'))
                        for d in sem
                        if d.get('doc_id') is not None
                    }
                    injected: List[Dict] = []
                    for d in prioritized:
                        did = d.get('doc_id')
                        key = str(did) if did is not None else ''
                        if key and key in seen_doc_ids:
                            continue
                        injected.append(d)
                        if key:
                            seen_doc_ids.add(key)
                        if len(injected) >= 10:
                            break
                    if injected:
                        sem = [*injected, *sem]

            exam_temp_leave_intent = (
                ('สอบ' in ql or 'ห้องสอบ' in ql)
                and (
                    ('ชั่วคราว' in ql)
                    or ('ออกจากห้องสอบชั่วคราว' in ql)
                    or ('ออกห้องสอบชั่วคราว' in ql)
                )
            )
            if exam_temp_leave_intent:
                add_metric('retrieval_exam_temp_leave_anchor', 1)
                with time_block('vector_search_exam_temp_leave_anchor'):
                    sem_extra = semantic_search_domain(
                        'ข้อ 16 ห้องสอบ ออกจากห้องสอบชั่วคราว กรรมการคุมสอบ เครื่องมือสื่อสาร',
                        top_k=max(20, k_vec * 2),
                        domain='regulations',
                        source_allowlist=None,
                    )
                with time_block('hydrate_sqlite_exam_temp_leave_anchor'):
                    sem_extra = _hydrate_from_sqlite(sem_extra, sqlite_path)
                if sem_extra:
                    clause16_docs: List[Dict] = []
                    other_docs: List[Dict] = []
                    for d in sem_extra:
                        txt = str(d.get('text') or '')
                        if ('ข้อ 16' in txt) and (('ชั่วคราว' in txt) or ('ออกจากห้องสอบ' in txt) or ('กรรมการคุมสอบ' in txt)):
                            clause16_docs.append(d)
                        else:
                            other_docs.append(d)
                    prioritized = [*clause16_docs, *other_docs]
                    seen_doc_ids: set[str] = {
                        str(d.get('doc_id'))
                        for d in sem
                        if d.get('doc_id') is not None
                    }
                    injected: List[Dict] = []
                    for d in prioritized:
                        did = d.get('doc_id')
                        key = str(did) if did is not None else ''
                        if key and key in seen_doc_ids:
                            continue
                        injected.append(d)
                        if key:
                            seen_doc_ids.add(key)
                        if len(injected) >= 8:
                            break
                    if injected:
                        sem = [*injected, *sem]
        add_metric('retrieval_sem_n', len(sem))
        add_metric('retrieval_kw_n', len(kw_docs))

        # If the user explicitly referenced a source, stay within it (avoid cross-doc hallucinations).
        if (not strict_ref) and source_allowlist and (len(sem) + len(kw_docs) < 2):
            add_metric('retrieval_source_fallback_used', 1)
            sem, kw_ids = _retrieve_semantic_and_keyword(
                semantic_q,
                keyword_q,
                k_vec,
                k_kw,
                dom,
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
        merged = _apply_lexical_rerank(merged, question, dom)
        merged = promote_exact_anchor_hits(merged, anchors)
        add_metric('retrieval_merged_n', len(merged))
        candidates = merged[: max(max_contexts_local * 4, max_contexts_local)]
        picked = diversify_by_source(candidates, max_per_source=_MAX_PER_SOURCE, limit=max_contexts_local)

        # Regulations: ensure the final set covers key clauses when the question
        # clearly asks about them (helps when per-source caps would otherwise keep
        # only multiple chunks about the same clause).
        if dom == 'regulations':
            try:
                ql = (question or '').strip().lower()
                want_exam_temp_leave = (
                    ('สอบ' in ql or 'ห้องสอบ' in ql)
                    and (('ชั่วคราว' in ql) or ('ออกจากห้องสอบชั่วคราว' in ql) or ('ออกห้องสอบชั่วคราว' in ql))
                )
                if want_exam_temp_leave and candidates and picked:
                    def _is_clause16(d: Dict) -> bool:
                        t = str(d.get('text') or '')
                        return ('ข้อ 16' in t) and (('ชั่วคราว' in t) or ('ออกจากห้องสอบ' in t) or ('กรรมการคุมสอบ' in t) or ('เครื่องมือสื่อสาร' in t))

                    has16 = any(_is_clause16(d) for d in picked)
                    if not has16:
                        cand16 = None
                        for d in candidates:
                            if _is_clause16(d):
                                cand16 = d
                                break
                        # Fallback: force a clause-16 hit via targeted vector search.
                        if cand16 is None:
                            try:
                                with time_block('vector_search_exam_temp_leave_fallback'):
                                    sem_extra2 = semantic_search_domain(
                                        'ข้อ 16 ห้องสอบ ออกจากห้องสอบชั่วคราว กรรมการคุมสอบ เครื่องมือสื่อสาร',
                                        top_k=max(30, k_vec * 2),
                                        domain='regulations',
                                        source_allowlist=None,
                                    )
                                sem_extra2 = _hydrate_from_sqlite(sem_extra2, sqlite_path)
                                for d in (sem_extra2 or []):
                                    if _is_clause16(d):
                                        cand16 = d
                                        break
                            except Exception:
                                cand16 = None
                        if cand16 and (not any(str(x.get('doc_id') or '') == str(cand16.get('doc_id') or '') for x in picked)):
                            add_metric('retrieval_force_clause16', 1)
                            src_key = _normalize_source_key(str(cand16.get('source') or cand16.get('path') or ''))
                            swap_idx = None
                            if src_key:
                                same_src = [
                                    (i, d) for i, d in enumerate(picked)
                                    if _normalize_source_key(str(d.get('source') or d.get('path') or '')) == src_key
                                ]
                                if same_src:
                                    same_src.sort(key=lambda p: float((p[1].get('score_final') or p[1].get('score_rrf') or 0.0)))
                                    swap_idx = same_src[0][0]
                            if swap_idx is None:
                                swap_idx = min(
                                    range(len(picked)),
                                    key=lambda i: float((picked[i].get('score_final') or picked[i].get('score_rrf') or 0.0)),
                                )
                            picked[int(swap_idx)] = cand16
                            picked.sort(key=lambda x: float(x.get('score_final') or x.get('score_rrf') or 0.0), reverse=True)
            except Exception:
                pass
        add_metric('retrieval_final_n', len(picked))
        if dom == 'regulations':
            picked = [_clip_long_regulations_text(it, question) for it in picked]
        _log_retrieval(
            'retrieve_by_domain',
            {
                'domain': dom,
                'question': question,
                'semantic_q': semantic_q,
                'keyword_q': keyword_q,
                'anchors': anchors,
                'sem_n': len(sem or []),
                'kw_n': len(kw_docs or []),
                'picked_n': len(picked or []),
                'top': [
                    {
                        'doc_id': d.get('doc_id'),
                        'source': d.get('source'),
                        'score': d.get('score_rrf'),
                    }
                    for d in (picked[:6] if picked else [])
                ],
            },
        )
        return picked

    # Domain 3: curriculum = vector + keyword + graph expansion
    # If no domain was provided, keep legacy behavior (vector+keyword on default env paths)
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

    # Heuristic: users often ask "LNGxxx มีวิชาอะไรให้เลือกเรียนบ้าง" without naming languages.
    # Pull in curriculum chunks anchored by the "รายวิชา: LNG" header to increase recall.
    lng_docs: List[Dict] = []
    lng_diverse_docs: List[Dict] = []
    wants_lng_list = False
    q = (question or '')
    q_lower = q.lower()
    codes = sorted(extract_course_codes(question))
    target_codes = {_normalize_code_text(c) for c in codes if _normalize_code_text(c)}

    exact_code_docs: List[Dict] = []
    exact_code_doc_ids: set[str] = set()
    exact_first_enabled = (os.getenv('RAG_CURRICULUM_EXACT_CODE_FIRST', '1') or '1').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )
    add_metric('retrieval_exact_code_route_enabled', int(exact_first_enabled))
    if dom == 'curriculum' and target_codes and exact_first_enabled:
        # Exact-first retrieval path for course-code questions.
        candidate_docs = [*sem, *kw_docs]
        for d in candidate_docs:
            did = d.get('doc_id')
            if not isinstance(did, str) or did in exact_code_doc_ids:
                continue
            if _item_matches_course_codes(d, target_codes):
                exact_code_docs.append(d)
                exact_code_doc_ids.add(did)

        # If merged candidates still miss exact hits, query SQLite by normalized code variants.
        if not exact_code_docs:
            exact_ids: List[str] = []
            seen_ids: set[str] = set()
            for code in sorted(target_codes):
                if len(code) < 4:
                    continue
                needles = [code]
                mcode = re.match(r"^([A-Z]{2,6})(\d{3})$", code)
                if mcode:
                    needles = [f"{mcode.group(1)} {mcode.group(2)}", code, f"รายวิชา: {mcode.group(1)}"]
                for needle in needles:
                    for did in keyword_search(needle, limit=max(40, k_kw), sqlite_path=sqlite_path):
                        if did and did not in seen_ids:
                            exact_ids.append(did)
                            seen_ids.add(did)
                    if len(exact_ids) >= max(80, k_kw * 2):
                        break
                if len(exact_ids) >= max(80, k_kw * 2):
                    break
            if exact_ids:
                exact_fetched = fetch_docs_with_path(exact_ids, sqlite_path=sqlite_path)
                # Keep only chunks that truly contain the target course code and have usable text.
                exact_code_docs = [
                    d
                    for d in exact_fetched
                    if _item_matches_course_codes(d, target_codes)
                    and _contains_target_code_in_visible_fields(d, target_codes)
                    and str(d.get('text') or '').strip()
                ]
                exact_code_doc_ids = {
                    str(d.get('doc_id'))
                    for d in exact_code_docs
                    if isinstance(d.get('doc_id'), str)
                }

    add_metric('retrieval_exact_code_hits_n', len(exact_code_docs))
    if dom == 'curriculum':
        wants_lng_list = (
            re.search(r"LNG", q, re.IGNORECASE) is not None
            and any(t in q for t in ('เลือกเรียน', 'มีวิชา', 'วิชาอะไร', 'เลือกได้', 'ตัวเลือก'))
        )
        if wants_lng_list:
            add_metric('retrieval_lng_query', 1)
            with time_block('lng_keyword_search'):
                lng_ids = keyword_search('รายวิชา: LNG', limit=max(80, k_kw * 2), sqlite_path=sqlite_path)
            with time_block('lng_fetch_docs'):
                lng_docs = fetch_docs_with_path(lng_ids, sqlite_path=sqlite_path)

            # If Neo4j is configured, also fetch LNG* chunks via graph to improve recall.
            with time_block('neo4j_course_prefix'):
                graph_lng_ids = graph_doc_ids_for_course_prefix('LNG', domain=dom, limit=160)
            if graph_lng_ids:
                with time_block('neo4j_fetch_docs'):
                    lng_docs.extend(fetch_docs_with_path(graph_lng_ids, sqlite_path=sqlite_path))

            # Prefer diversity across *non-English* languages rather than many English-only chunks.
            # Many curriculum chunks start with "รายวิชา: LNG ... ภาษาอังกฤษ..." and can crowd out
            # Japanese/Chinese/Burmese/etc. So we pick non-English first.
            def _lang_name(txt: str) -> str | None:
                m = re.search(r"ภาษา([\u0E00-\u0E7F]{2,20})", txt or '')
                return m.group(1) if m else None

            non_en: dict[str, Dict] = {}
            en: dict[str, Dict] = {}
            other: list[Dict] = []
            for d in lng_docs:
                txt = (d.get('text') or '')
                name = _lang_name(txt)
                if not name:
                    other.append(d)
                    continue
                if name.startswith('อังกฤษ') or name.startswith('ไทย'):
                    en.setdefault(name, d)
                else:
                    non_en.setdefault(name, d)

            # Seed some specific languages if present (helps when OCR variations exist).
            priority_markers = ['ญี่ปุ่น', 'จีน', 'พม่า', 'เกาหลี', 'ฝรั่งเศส', 'สเปน', 'เยอรมัน', 'รัสเซีย']
            picked_ids: set[str] = set()
            for mkr in priority_markers:
                for d in lng_docs:
                    did = d.get('doc_id')
                    if not isinstance(did, str) or did in picked_ids:
                        continue
                    if mkr in (d.get('text') or ''):
                        lng_diverse_docs.append(d)
                        picked_ids.add(did)
                        break

            for _name, d in non_en.items():
                did = d.get('doc_id')
                if isinstance(did, str) and did not in picked_ids:
                    lng_diverse_docs.append(d)
                    picked_ids.add(did)
                if len(lng_diverse_docs) >= 14:
                    break

            # Keep a couple of English chunks too (often required in answers).
            for _name, d in en.items():
                did = d.get('doc_id')
                if isinstance(did, str) and did not in picked_ids:
                    lng_diverse_docs.append(d)
                    picked_ids.add(did)
                if len(lng_diverse_docs) >= 18:
                    break
            add_metric('retrieval_lng_docs_n', len(lng_diverse_docs or lng_docs))

    # Default context cap; expand for list-style LNG questions.
    max_contexts = max(MAX_CONTEXTS, 20) if wants_lng_list else MAX_CONTEXTS
    if max_contexts_override is not None:
        try:
            max_contexts = max(1, int(max_contexts_override))
        except Exception:
            pass

    wants_prereq = False
    if dom == 'curriculum':
        ql = q.lower()
        wants_prereq = any(
            t in ql
            for t in (
                'ต้องผ่าน',
                'บังคับก่อน',
                'วิชาบังคับก่อน',
                'ก่อนเรียน',
                'prerequisite',
                'pre-requisite',
                'pre requisite',
            )
        )

    simple_curriculum_lookup = False
    if dom == 'curriculum':
        simple_curriculum_lookup = bool(codes) or any(
            t in q_lower for t in ('รวมกี่หน่วยกิต', 'หน่วยกิตรวมของหลักสูตร', 'จำนวนหน่วยกิตรวม', 'ตลอดหลักสูตร')
        )

    # Heuristic: short course-prefix queries like "SSC" often get drowned out by generic
    # curriculum chunks containing the word "วิชา". If users are clearly asking for courses
    # under a prefix, force-boost prefix-matching chunks.
    prefix_docs: List[Dict] = []
    wants_prefix_list = False
    if dom == 'curriculum':
        # Capture standalone ASCII prefixes (2-6 letters) like SSC, LNG, GEN.
        prefixes = [m.upper() for m in re.findall(r"\b[A-Za-z]{2,6}\b", q or '')]
        # Drop overly-generic/common English words that can appear in questions.
        stop = {
            'AND', 'OR', 'NOT', 'THE', 'THIS', 'THAT', 'WITH', 'FROM', 'WHAT', 'HOW', 'WHY',
            'CAN', 'COULD', 'SHOULD', 'WANT', 'FIND', 'COURSE', 'COURSES', 'CODE'
        }
        prefixes = [p for p in prefixes if p not in stop]

        wants_prefix_list = bool(prefixes) and any(
            t in (q or '')
            for t in (
                'หาวิชา', 'หา', 'วิชา', 'รายวิชา', 'มีวิชา', 'รหัสวิชา', 'เลือกเรียน', 'ตัวเลือก'
            )
        )

        if wants_prefix_list:
            add_metric('retrieval_prefix_query', 1)
            pref_ids: List[str] = []
            seen: set[str] = set()
            # Pull a wider candidate pool then let ranking/packing decide.
            for pref in prefixes:
                # Prefer exact prefix hits (e.g., "SSC 162")
                for needle in (f"{pref} ", pref):
                    ids = keyword_search(needle, limit=max(80, k_kw * 3), sqlite_path=sqlite_path)
                    for did in ids:
                        if did and did not in seen:
                            pref_ids.append(did)
                            seen.add(did)
                if len(pref_ids) >= 200:
                    break
            prefix_docs = fetch_docs_with_path(pref_ids, sqlite_path=sqlite_path)
            add_metric('retrieval_prefix_docs_n', len(prefix_docs))

    # Graph expansion (best-effort; requires Neo4j + graph ingested)
    add_metric('course_codes', len(codes))
    graph_docs: List[Dict] = []
    if dom == 'curriculum' and codes and not simple_curriculum_lookup:
        with time_block('neo4j_codes'):
            graph_ids = graph_doc_ids_for_codes(codes=codes, domain=dom, limit=max(30, MAX_CONTEXTS * 8))
        with time_block('neo4j_fetch_docs'):
            graph_docs = fetch_docs_with_path(graph_ids, sqlite_path=sqlite_path)
        add_metric('retrieval_graph_docs_n', len(graph_docs))

    prereq_docs: List[Dict] = []
    if dom == 'curriculum' and wants_prereq and codes and not simple_curriculum_lookup:
        with time_block('neo4j_prereq'):
            prereq_ids = graph_doc_ids_for_requisites(codes=codes, domain=dom, kind='prereq', limit=max(60, MAX_CONTEXTS * 10))
        if prereq_ids:
            with time_block('neo4j_fetch_docs'):
                prereq_docs = fetch_docs_with_path(prereq_ids, sqlite_path=sqlite_path)
        add_metric('retrieval_prereq_docs_n', len(prereq_docs))

    # Graph neighborhood expansion from retrieved chunks (works even without course codes)
    graph_neighbor_docs: List[Dict] = []
    if dom == 'curriculum' and not simple_curriculum_lookup:
        seed_ids: List[str] = []
        for d in (sem[:8] + kw_docs[:8]):
            did = d.get('doc_id')
            if did and did not in seed_ids:
                seed_ids.append(did)
        if seed_ids:
            with time_block('neo4j_neighbors'):
                neighbor_ids = graph_expand_from_seed_chunks(seed_ids, domain=dom, window=2, limit=max(60, MAX_CONTEXTS * 8))
            with time_block('neo4j_fetch_docs'):
                graph_neighbor_docs = fetch_docs_with_path(neighbor_ids, sqlite_path=sqlite_path)
        add_metric('retrieval_neighbor_docs_n', len(graph_neighbor_docs))

    bank: Dict[str, Dict] = {}
    ranks: Dict[str, float] = {}

    # vector ranks
    for r, d in enumerate(sem, 1):
        doc_id = d.get('doc_id') or d.get('source') or f'vec_{r}'
        bank[doc_id] = d
        ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + r)
    # keyword ranks
    credit_total_re = None
    if dom == 'curriculum' and ('หน่วยกิต' in (question or '')):
        credit_total_re = re.compile(r"จ\s*า\s*น\s*ว\s*น\s*หน่วยกิต\s*ที่\s*เรียน\s*ตลอด\s*หลักสูตร[^\d]{0,60}(\d{2,3})\s*หน่วยกิต")

    for r, d in enumerate(kw_docs, 1):
        doc_id = d.get('doc_id') or f'kw_{r}'
        bank.setdefault(doc_id, d)
        ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + r)

        # Extra boost when the chunk clearly contains the total-credits statement.
        if credit_total_re is not None:
            txt = (d.get('text') or '')
            if txt and credit_total_re.search(txt):
                ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0

    # LNG anchor ranks (boost diverse languages to surface options beyond EN/TH)
    if wants_lng_list and lng_diverse_docs:
        for r, d in enumerate(lng_diverse_docs, 1):
            doc_id = d.get('doc_id') or f'lng_{r}'
            bank.setdefault(doc_id, d)
            # Stronger boost for list-style questions so multiple languages appear in context.
            ranks[doc_id] = ranks.get(doc_id, 0.0) + 6.0 / (RRF_K + r)

    # Course-prefix anchor ranks (e.g., SSC/GEN/LNG*)
    if dom == 'curriculum' and wants_prefix_list and prefix_docs:
        for r, d in enumerate(prefix_docs, 1):
            doc_id = d.get('doc_id') or f'pref_{r}'
            bank.setdefault(doc_id, d)
            # Strong boost so prefix-relevant chunks survive the top-k cutoff.
            ranks[doc_id] = ranks.get(doc_id, 0.0) + 8.0 / (RRF_K + r)

    # graph ranks
    for r, d in enumerate(graph_docs, 1):
        doc_id = d.get('doc_id') or f'graph_{r}'
        bank.setdefault(doc_id, d)
        ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + r)

    # neighborhood ranks (slightly down-weight by shifting rank)
    for r, d in enumerate(graph_neighbor_docs, 1):
        doc_id = d.get('doc_id') or f'graphn_{r}'
        bank.setdefault(doc_id, d)
        ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + (r + 10))

    # prereq ranks (boost when question is explicitly about prerequisites)
    if dom == 'curriculum' and wants_prereq and prereq_docs:
        for r, d in enumerate(prereq_docs, 1):
            doc_id = d.get('doc_id') or f'prereq_{r}'
            bank.setdefault(doc_id, d)
            ranks[doc_id] = ranks.get(doc_id, 0.0) + 2.5 / (RRF_K + r)

    if dom == 'curriculum':
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
        wants_teacher_for_course = bool(codes) and any(m in q_lower for m in teacher_markers)
        if wants_teacher_for_course:
            try:
                relation_boost = float(os.getenv('RAG_FACULTY_RELATION_BOOST', '1.2') or '1.2')
            except Exception:
                relation_boost = 1.2

            boosted = 0
            for doc_id, d in bank.items():
                if not _is_faculty_course_relation(d):
                    continue
                if not _item_matches_course_codes(d, target_codes):
                    continue
                ranks[doc_id] = ranks.get(doc_id, 0.0) + relation_boost
                boosted += 1

            add_metric('retrieval_teacher_course_intent', 1)
            add_metric('retrieval_fac_rel_boosted_n', boosted)

    merged = [{**bank[k], 'score_rrf': v, 'doc_id': k} for k, v in ranks.items()]
    merged.sort(key=lambda x: x['score_rrf'], reverse=True)
    
    # Apply curriculum-specific reranking to boost exact course code matches
    if dom == 'curriculum' and target_codes:
        merged = _apply_curriculum_rerank(merged, question, target_codes)

    merged = promote_exact_anchor_hits(merged, anchors)

    if dom == 'curriculum' and exact_code_docs:
        # Force-include a few exact course-code hits before generic ranking.
        must_include = min(5, max_contexts)
        picked: List[Dict] = []
        seen: set[str] = set()

        # Prioritize exact chunks that visibly include the target code and non-empty text.
        exact_sorted = sorted(
            exact_code_docs,
            key=lambda d: (
                0 if _contains_target_code_in_visible_fields(d, target_codes) else 1,
                0 if str(d.get('text') or '').strip() else 1,
                len((d.get('text') or '').strip()) if isinstance(d.get('text'), str) else 10**9,
            ),
        )
        for d in exact_sorted:
            did = d.get('doc_id')
            if isinstance(did, str) and did not in seen:
                picked.append(d)
                seen.add(did)
                if len(picked) >= must_include:
                    break

        for m in merged:
            did = m.get('doc_id')
            if isinstance(did, str) and did not in seen:
                picked.append(m)
                seen.add(did)
                if len(picked) >= max_contexts:
                    break
        add_metric('retrieval_merged_n', len(merged))
        add_metric('retrieval_final_n', len(picked))
        picked = diversify_by_source(picked, max_per_source=_MAX_PER_SOURCE, limit=max_contexts)
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

    if dom == 'curriculum' and wants_prefix_list and prefix_docs:
        pref_set = {d.get('doc_id') for d in prefix_docs if d.get('doc_id')}
        must_include = min(2, max_contexts)
        picked: List[Dict] = []
        seen: set[str] = set()
        # Force-include a couple prefix chunks first.
        for m in merged:
            did = m.get('doc_id')
            if isinstance(did, str) and did in pref_set and did not in seen:
                picked.append(m)
                seen.add(did)
                if len(picked) >= must_include:
                    break
        # Then fill as usual.
        for m in merged:
            did = m.get('doc_id')
            if isinstance(did, str) and did not in seen:
                picked.append(m)
                seen.add(did)
                if len(picked) >= max_contexts:
                    break
            add_metric('retrieval_merged_n', len(merged))
            add_metric('retrieval_final_n', len(picked))
        picked = diversify_by_source(picked, max_per_source=_MAX_PER_SOURCE, limit=max_contexts)
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

    if dom == 'curriculum' and graph_neighbor_docs:
        neighbor_set = {d.get('doc_id') for d in graph_neighbor_docs if d.get('doc_id')}
        # Force-include up to 2 neighbor chunks to make graph expansion observable/useful.
        must_include = min(2, max_contexts)
        picked: List[Dict] = []
        seen: set[str] = set()
        for m in merged:
            did = m.get('doc_id')
            if isinstance(did, str) and did in neighbor_set and did not in seen:
                picked.append(m)
                seen.add(did)
                if len(picked) >= must_include:
                    break
        for m in merged:
            did = m.get('doc_id')
            if isinstance(did, str) and did not in seen:
                picked.append(m)
                seen.add(did)
                if len(picked) >= max_contexts:
                    break
        add_metric('retrieval_merged_n', len(merged))
        add_metric('retrieval_final_n', len(picked))
        picked = diversify_by_source(picked, max_per_source=_MAX_PER_SOURCE, limit=max_contexts)
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

    add_metric('retrieval_merged_n', len(merged))
    candidates = merged[: max(max_contexts * 4, max_contexts)]
    picked = diversify_by_source(candidates, max_per_source=_MAX_PER_SOURCE, limit=max_contexts)
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


def pack_context(
    chunks: List[Dict],
    budget_tokens: int = TOKEN_BUDGET,
    truncate_chars: int | None = None,
) -> Tuple[str, Dict[int, str]]:
    def _truncate_block_to_fit(prefix: str, text: str, remaining_tokens: int) -> str | None:
        if remaining_tokens <= 0:
            return None
        base = (prefix or '')
        base_tokens = est_tokens(base)
        if base_tokens >= remaining_tokens:
            return None
        txt = (text or '').strip()
        candidate = base + txt
        if est_tokens(candidate) <= remaining_tokens:
            return candidate
        avail_tokens = max(1, remaining_tokens - base_tokens)
        approx_chars = max(80, int(avail_tokens * 4))
        clipped = txt[:approx_chars].rstrip()
        if clipped and clipped != txt:
            clipped = clipped + ' ...'
        candidate = base + clipped
        if est_tokens(candidate) > remaining_tokens:
            approx_chars = max(40, int(approx_chars * 0.6))
            clipped = txt[:approx_chars].rstrip()
            if clipped and clipped != txt:
                clipped = clipped + ' ...'
            candidate = base + clipped
        if est_tokens(candidate) <= remaining_tokens and candidate.strip() != base.strip():
            return candidate
        return None

    packed_blocks = []
    used = 0
    cites = {}
    for i, c in enumerate(chunks, 1):
        cite = _cite_label(c)
        txt = (c.get('text', '') or '').strip()
        if truncate_chars is not None and truncate_chars > 0 and len(txt) > truncate_chars:
            txt = txt[:truncate_chars].rstrip() + ' ...'
        prefix = f"[{cite}] "
        remaining = budget_tokens - used
        block = _truncate_block_to_fit(prefix, txt, remaining_tokens=remaining)
        if not block:
            # Don't stop entirely; later chunks may be smaller and still fit.
            continue
        t = est_tokens(block)
        if used + t > budget_tokens:
            continue
        packed_blocks.append(block)
        used += t
        cites[i] = cite
    return '\n\n'.join(packed_blocks), cites


def build_prompt(question: str, ctx: str, cites: Dict[int, str]) -> str:
    require_citations = (os.getenv('RAG_REQUIRE_CITATIONS', '0') or '0').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )

    allowed_cites: list[str] = []
    seen: set[str] = set()
    for c in (cites or {}).values():
        s = (c or '').strip()
        if not s or s in seen:
            continue
        seen.add(s)
        allowed_cites.append(s)

    allowed_block = "\n".join([f"- [{c}]" for c in allowed_cites])

    multi_doc_hint = (os.getenv('RAG_MULTI_DOC_HINTS', '1') or '1').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )

    multi_doc_guidance = ""
    if multi_doc_hint and any(line.startswith('[Source:') for line in (ctx or '').splitlines()):
        multi_doc_guidance = (
            "8) หากคำตอบต้องอาศัยหลายเอกสาร ให้แยกเป็นประเด็น ๆ และระบุว่าแต่ละประเด็นอ้างอิงจากเอกสารใด.\n"
            "9) หากมีข้อมูลขัดแย้งกัน ให้ชี้ให้เห็นความขัดแย้งและอ้างอิงแยกตามเอกสาร.\n"
            "10) หากหลักฐานไม่ครบทุกเงื่อนไข ให้ระบุชัดเจนว่ายังขาดข้อมูลส่วนใด.\n"
        )

    if require_citations:
        instruction = (
            "คุณคือผู้ช่วยของภาควิชาวิศวกรรมคอมพิวเตอร์ ณ มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี ตอบเป็นภาษาไทย.\n"
            "หลักการตอบ:\n"
            "1) ใช้เฉพาะข้อมูลในบริบทที่ให้ หากไม่พบคำตอบแบบชัดเจน ให้ตอบสิ่งที่สรุปได้จากบริบทเท่านั้น และระบุชัดเจนว่าเอกสารไม่ได้กล่าวตรง ๆ หรือไม่มีข้อความยืนยันโดยตรง.\n"
            "2) ให้ตอบเป็น bullet เป็นหลัก (ขึ้นต้นด้วย '- ') และแต่ละ bullet ต้องลงท้ายด้วยการอ้างอิงอย่างน้อย 1 รายการต่อบรรทัด โดยใส่ท้ายบรรทัดในรูปแบบ [source/page].\n"
            "3) หากคำถามมีหลายประเด็น/หลายคำถามย่อย ให้ตอบให้ครบทุกประเด็น โดยแยก 1 bullet ต่อ 1 ประเด็น.\n"
            "4) ห้ามเดาข้อมูลนอกรายการที่มี ใช้เฉพาะข้อมูลที่มีในบริบทเท่านั้น.\n"
            "5) หากคำถามขอ 'สรุป' หรือ 'โครงสร้าง' ให้จัดลำดับหัวข้อก่อนรายละเอียด.\n"
            "6) หากคำถามกำกวม/สั้นมาก (เช่น พิมพ์แค่ชื่อภาษา หรือ xxx) ให้ถามกลับ 1 คำถามสั้น ๆ เพื่อขอรายละเอียดที่จำเป็นก่อน.\n"
            "7) ห้ามให้ URL/ลิงก์ภายนอก เว้นแต่ URL นั้นปรากฏอยู่ในบริบท.\n"
            "8) เรื่องวัน/วันที่/เดดไลน์: ให้ระบุเฉพาะวันที่ที่มีข้อความยืนยันตรง ๆ ในบริบทเท่านั้น ห้ามอนุมานเดดไลน์จากคำว่า 'ประกาศ ณ วันที่ ...' หรือวันที่ที่ไม่ได้ระบุว่าเป็นกำหนดการ/เส้นตาย.\n"
            f"{multi_doc_guidance}"
            
        )
    else:
        instruction = (
            "คุณคือผู้ช่วยของภาควิชาวิศวกรรมคอมพิวเตอร์ ณ มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี ตอบเป็นภาษาไทย.\n"
            "หลักการตอบ:\n"
            "1) ใช้เฉพาะข้อมูลในบริบทที่ให้ หากไม่พบคำตอบแบบชัดเจน ให้ตอบสิ่งที่สรุปได้จากบริบทเท่านั้น และระบุชัดเจนว่าเอกสารไม่ได้กล่าวตรง ๆ หรือไม่มีข้อความยืนยันโดยตรง.\n"
            "2) ให้ตอบเป็น bullet เป็นหลัก (ขึ้นต้นด้วย '- ') และตอบให้ตรงคำถาม กระชับ ชัดเจน.\n"
            "3) หากคำถามมีหลายประเด็น/หลายคำถามย่อย ให้ตอบให้ครบทุกประเด็น โดยแยก 1 bullet ต่อ 1 ประเด็น.\n"
            "4) ห้ามเดาข้อมูลนอกรายการที่มี ใช้เฉพาะข้อมูลที่มีในบริบทเท่านั้น.\n"
            "5) หากคำถามขอ 'สรุป' หรือ 'โครงสร้าง' ให้จัดลำดับหัวข้อก่อนรายละเอียด.\n"
            "6) หากคำถามกำกวม/สั้นมาก (เช่น พิมพ์แค่ชื่อภาษา หรือ xxx) ให้ถามกลับ 1 คำถามสั้น ๆ เพื่อขอรายละเอียดที่จำเป็นก่อน.\n"
            "7) ห้ามให้ URL/ลิงก์ภายนอก เว้นแต่ URL นั้นปรากฏอยู่ในบริบท.\n"
            "8) เรื่องวัน/วันที่/เดดไลน์: ให้ระบุเฉพาะวันที่ที่มีข้อความยืนยันตรง ๆ ในบริบทเท่านั้น ห้ามอนุมานเดดไลน์จากคำว่า 'ประกาศ ณ วันที่ ...' หรือวันที่ที่ไม่ได้ระบุว่าเป็นกำหนดการ/เส้นตาย.\n"
            f"{multi_doc_guidance}"
        )

    if require_citations:
        return (
            f"{instruction}\n"
            f"คำถาม:\n{question}\n\n"
            f"บริบท:\n{ctx}\n\n"
            f"รายชื่ออ้างอิงที่อนุญาต (ใช้ได้เฉพาะรายการนี้เท่านั้น):\n{allowed_block}\n\n"
            f"คำตอบ:\n"
        )
    return (
        f"{instruction}\n"
        f"คำถาม:\n{question}\n\n"
        f"บริบท:\n{ctx}\n\n"
        f"คำตอบ:\n"
    )


def rag_query(question: str) -> Dict:
    q_display = normalize_question(question)
    q_search = search_query_from_question(question)
    ref_allow = _reference_candidates(question)
    strict_ref_hints = (os.getenv('STRICT_REFERENCE_HINTS', '1') or '1').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )
    has_ref = bool(ref_allow) and strict_ref_hints
    # Some intents (e.g., intermission leave) require both policy/calendar and forms.
    multi_doc_triggered = is_multi_doc_question(q_display)
    multi_doc_used = False
    multi_doc_reason: str | None = None
    multi_doc_subqs: List[str] = []
    if 'ลาพัก' in q_display:
        dom = None
        add_metric('inferred_domain', 'multi:announcements+regulations')
        retrieved = retrieve_all_domains(q_search, domains=['announcements', 'regulations'])
    else:
        # Multi-document mode (auto/on/off) for multi-clause questions.
        multi_doc_on = False
        if _MULTI_DOC_MODE in ('1', 'true', 'yes', 'on'):
            multi_doc_on = True
        elif _MULTI_DOC_MODE == 'auto':
            multi_doc_on = multi_doc_triggered

        if multi_doc_on:
            add_metric('retrieval_multi_doc_mode', 1)
            dom = None
            multi_doc_used = True
            multi_doc_reason = 'forced' if _MULTI_DOC_MODE in ('1', 'true', 'yes', 'on') else 'auto'
            multi_doc_subqs = decompose_question(question, max_parts=_MULTI_DOC_MAX_SUBQS)
            retrieved = retrieve_multi_document(question)
        else:
            dom = infer_domain(q_display) or _infer_domain_from_reference(question)
            add_metric('inferred_domain', dom or 'auto')
            if dom and not _SEARCH_ALL_DOMAINS:
                retrieved = retrieve_by_domain(question, domain=dom)
                # If too few results, widen cautiously to nearby domains first.
                if (not has_ref) and len(retrieved) < fallback_min_results():
                    add_metric('retrieval_domain_fallback_used', 1)
                    retrieved = retrieve_all_domains(q_search, domains=fallback_domains_for_domain(dom))
            else:
                # Search all domains to avoid wrong-domain misses from router/inference.
                add_metric('retrieval_all_domains_forced', 1)
                retrieved = retrieve_all_domains(question)

    retrieved = _filter_chunks_by_reference(retrieved, question, strict=has_ref)
    # Group contexts by source in multi-doc mode to help evidence stitching.
    if _MULTI_DOC_MODE == 'auto' and is_multi_doc_question(q_display):
        ctx, cites = pack_context_grouped(retrieved)
    elif _MULTI_DOC_MODE in ('1', 'true', 'yes', 'on'):
        ctx, cites = pack_context_grouped(retrieved)
    else:
        ctx, cites = pack_context(retrieved)
    prompt = build_prompt(q_display, ctx, cites)

    # Basic multi-doc observability for API consumers.
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
            } for r in retrieved
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
    q_search = search_query_from_question(question)
    add_metric('inferred_domain', (domain or '').strip().lower() or 'auto')
    retrieved = retrieve_by_domain(question, domain=domain)

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
            } for r in retrieved
        ],
        'token_est': est_tokens(ctx)
    }


# Modularized function bindings (kept here for backward compatibility imports).
normalize_question = _normalization.normalize_question
search_query_from_question = _normalization.search_query_from_question
build_retrieval_queries = _normalization.build_retrieval_queries
normalize_query_for_retrieval = _normalization.normalize_query_for_retrieval
normalize_query_for_keyword = _normalization.normalize_query_for_keyword
extract_lexical_anchors = _normalization.extract_lexical_anchors

is_multi_doc_question = _routing.is_multi_doc_question
decompose_question = _routing.decompose_question
infer_domain = _routing.infer_domain
infer_domain_bias = _routing.infer_domain_bias
fallback_domains_for_domain = _routing.fallback_domains_for_domain
fallback_min_results = _routing.fallback_min_results
_reference_candidates = _routing._reference_candidates
_infer_domain_from_reference = _routing._infer_domain_from_reference
_filter_chunks_by_reference = _routing._filter_chunks_by_reference

_normalize_source_key = _rerank._normalize_source_key
fuse_rrf_lists = _rerank.fuse_rrf_lists
select_chunks_from_top_documents = _rerank.select_chunks_from_top_documents
ensure_min_sources = _rerank.ensure_min_sources
fuse_semantic_keyword = _rerank.fuse_semantic_keyword
apply_domain_prior = _rerank.apply_domain_prior
apply_overbroad_source_penalty = _rerank.apply_overbroad_source_penalty
majority_domain_rescue = _rerank.majority_domain_rescue
promote_exact_anchor_hits = _rerank.promote_exact_anchor_hits
diversify_by_source = _rerank.diversify_by_source

# Keep legacy retrieval execution path active for now to avoid behavior regressions.
# Retrieval logic has been extracted to `retrieval.py` for incremental migration.

est_tokens = _context_packing.est_tokens
pack_context = _context_packing.pack_context
pack_context_grouped = _context_packing.pack_context_grouped

build_prompt = _prompting.build_prompt
