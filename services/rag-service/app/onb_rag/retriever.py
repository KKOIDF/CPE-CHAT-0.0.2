from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Sequence
import os
import re
import unicodedata

from .tokenizer import tokenize
from .vector_store import keyword_search, vector_search


_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_COURSE_CODE_RE = re.compile(r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b")
_THAI_WORD_RE = re.compile(r"[\u0E00-\u0E7F]{2,}")
_ASCII_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_NUM_RE = re.compile(r"\d{2,}")

_DOMAIN_HINTS: dict[str, tuple[str, ...]] = {
    "curriculum": ("หลักสูตร", "รายวิชา", "หน่วยกิต", "สำเร็จการศึกษา", "course", "curriculum", "credits"),
    "regulations": ("ข้อบังคับ", "ระเบียบ", "เงื่อนไข", "ข้อ", "หมวด", "regulation", "policy"),
    "announcements": ("ประกาศ", "กำหนดการ", "deadline", "calendar", "announcement", "date"),
    "test_domain": ("หลักสูตรทดสอบ", "จบหลักสูตร", "สำเร็จการศึกษา"),
}


def normalize_question_text(question: str) -> str:
    value = unicodedata.normalize("NFKC", (question or "").strip())
    value = value.translate(_THAI_DIGITS)
    value = value.replace("–", "-").replace("—", "-").replace("−", "-")
    value = re.sub(r"\s+", " ", value).strip()
    return re.sub(
        r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b",
        lambda m: f"{(m.group(1) or '').upper()} {m.group(2)}",
        value,
    )


def extract_course_codes(question: str) -> List[str]:
    seen: set[str] = set()
    out: list[str] = []
    for match in _COURSE_CODE_RE.finditer(question or ""):
        code = f"{(match.group(1) or '').upper()} {match.group(2) or ''}".strip()
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def extract_keywords(question: str) -> List[str]:
    q = normalize_question_text(question)
    token_items = tokenize(q)
    items = [*extract_course_codes(q), *token_items, *_ASCII_WORD_RE.findall(q), *_NUM_RE.findall(q)]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = str(item or "").strip()
        if len(key) < 2:
            continue
        if key in {"อะไร", "บ้าง", "เกี่ยว", "ไหม", "อย่างไร"}:
            continue
        low = key.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(key)
    return out[:12]


def infer_candidate_domains(question: str, requested_domain: str | None = None) -> List[Dict[str, Any]]:
    q = normalize_question_text(question).lower()
    scores = {domain: 0.0 for domain in _DOMAIN_HINTS}
    for domain, hints in _DOMAIN_HINTS.items():
        for hint in hints:
            if hint.lower() in q:
                scores[domain] += 1.0
    requested = str(requested_domain or "").strip().lower()
    if requested:
        scores[requested] = scores.get(requested, 0.0) + 2.5
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    total = sum(scores.values())
    if total <= 0:
        return [{"domain": d, "score": round(1.0 / 3.0, 3)} for d in ("curriculum", "regulations", "announcements")]
    return [{"domain": domain, "score": round(raw / total, 3)} for domain, raw in ranked if raw > 0][:4]


def generate_query_variants(question: str, max_variants: int | None = None) -> List[str]:
    normalized = normalize_question_text(question)
    max_n = max_variants or max(1, int(os.getenv("RAG_QUERY_VARIANTS_MAX", "4") or "4"))
    variants = [normalized]
    keywords = extract_keywords(normalized)
    if keywords:
        variants.append(" ".join(keywords[:8]))
    codes = extract_course_codes(normalized)
    if codes or keywords:
        variants.append(" ".join([*codes[:4], *keywords[:6]]).strip())
    out: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        key = re.sub(r"\s+", " ", (variant or "").strip().lower())
        if key and key not in seen:
            seen.add(key)
            out.append(variant.strip())
        if len(out) >= max_n:
            break
    return out


def rrf_merge(result_lists: Sequence[Sequence[Dict[str, Any]]], k: int = 60) -> List[Dict[str, Any]]:
    bank: dict[str, dict[str, Any]] = {}
    scores: dict[str, float] = defaultdict(float)
    for results in result_lists:
        for rank, item in enumerate(results, start=1):
            key = str(item.get("stable_chunk_id") or item.get("doc_id") or item.get("chunk_id") or rank)
            if key not in bank:
                bank[key] = dict(item)
            scores[key] += 1.0 / float(k + rank)
    merged: list[dict[str, Any]] = []
    for key, item in bank.items():
        row = dict(item)
        row["hybrid_score"] = float(row.get("hybrid_score") or 0.0) + scores[key]
        merged.append(row)
    merged.sort(key=lambda row: float(row.get("hybrid_score") or 0.0), reverse=True)
    return merged


def _junk_chunk_penalty(text: str, title: str, section: str) -> float:
    lower_text = (text or "").lower()
    lower_title = (title or "").lower()
    lower_section = (section or "").lower()
    penalty = 0.0
    course_markers = lower_text.count("course ")
    if course_markers >= 2 and "unknown" in lower_text:
        penalty -= 0.45
    if lower_text.count("unknown") >= 2:
        penalty -= 0.18
    if lower_text.count("0.95") >= 1 and course_markers >= 1:
        penalty -= 0.12
    if lower_title and lower_text.count(lower_title) >= 2:
        penalty -= 0.12
    if lower_section and lower_section == lower_title:
        penalty -= 0.06
    if 'teacher_profiles' in lower_text or 'ภาระงานสอนในปัจจุบัน' in lower_text:
        penalty -= 0.35
    return penalty


def _query_specific_penalty(
    question: str,
    text: str,
    title: str,
    section: str,
    source_name: str,
) -> float:
    q = normalize_question_text(question).lower()
    full = " ".join(part for part in (title, section, text) if part)
    penalty = 0.0
    if 'teacher_profiles' in source_name or 'teacher_profiles' in full:
        penalty -= 0.40
    overview_markers = (
        'สารบัญ',
        'บทสรุปผู้บริหาร',
        'อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา',
        'ความพร้อมเผยแพร่คุณภาพ',
    )
    requirement_question = any(token in q for token in ('เกณฑ์', 'เงื่อนไข', 'สำเร็จการศึกษา', 'จบหลักสูตร', 'graduate', 'requirement'))
    requirement_markers = (
        'หน่วยกิต',
        'เกรดเฉลี่ย',
        'gpax',
        'gpa',
        'ไม่ต่ำกว่า',
        'สำเร็จการศึกษา',
        'ต้องผ่าน',
        'ยื่นคำร้อง',
        'หนี้สิน',
        'กิจกรรมเสริมหลักสูตร',
    )
    if requirement_question:
        matched_requirements = sum(1 for marker in requirement_markers if marker in full)
        if any(marker in full for marker in overview_markers):
            penalty -= 0.28
        if not matched_requirements:
            penalty -= 0.16
        else:
            penalty += min(0.24, matched_requirements * 0.04)
    return penalty


def rerank_results(results: Sequence[Dict[str, Any]], question: str, candidate_domains: Sequence[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
    keywords = {k.lower() for k in extract_keywords(question)}
    codes = {c.lower() for c in extract_course_codes(question)}
    normalized_question = normalize_question_text(question).lower()
    domain_score_map = {str(item.get("domain") or ""): float(item.get("score") or 0.0) for item in (candidate_domains or [])}
    ranked: list[dict[str, Any]] = []
    for item in results:
        row = dict(item)
        text = str(row.get("text") or "").lower()
        title = str(row.get("title") or row.get("source_name") or "").lower()
        section = str(row.get("section_heading") or "").lower()
        full = " ".join(part for part in (title, section, text) if part).strip()
        exact_matches = sum(1 for kw in keywords if kw in text)
        field_matches = sum(1 for kw in keywords if kw in full)
        title_matches = sum(1 for kw in keywords if kw in title)
        section_matches = sum(1 for kw in keywords if kw in section)
        code_matches = sum(1 for code in codes if code in full)
        question_exact = 1 if normalized_question and normalized_question in full else 0
        overlap_ratio = (field_matches / max(len(keywords), 1)) if keywords else 0.0
        no_overlap_penalty = -0.18 if keywords and field_matches == 0 and code_matches == 0 else 0.0
        source_name = str(row.get("source_name") or row.get("source") or "").lower()
        junk_penalty = _junk_chunk_penalty(text, title, section)
        query_penalty = _query_specific_penalty(question, text, title, section, source_name)
        final_score = (
            float(row.get("hybrid_score") or 0.0)
            + float(row.get("vector_score") or 0.0)
            + float(row.get("keyword_score") or 0.0)
            + (exact_matches * 0.05)
            + (field_matches * 0.035)
            + (title_matches * 0.08)
            + (section_matches * 0.06)
            + (code_matches * 0.2)
            + (overlap_ratio * 0.25)
            + (question_exact * 0.35)
            + domain_score_map.get(str(row.get("domain") or ""), 0.0) * 0.15
            + no_overlap_penalty
            + junk_penalty
            + query_penalty
        )
        row["keyword_overlap"] = field_matches
        row["overlap_ratio"] = overlap_ratio
        row["junk_penalty"] = junk_penalty
        row["query_penalty"] = query_penalty
        row["rerank_score"] = final_score
        ranked.append(row)
    ranked.sort(key=lambda row: float(row.get("rerank_score") or 0.0), reverse=True)
    return ranked


def enforce_source_diversity(results: Sequence[Dict[str, Any]], limit: int = 8, max_per_source: int = 3) -> List[Dict[str, Any]]:
    by_source: dict[str, int] = defaultdict(int)
    seen: set[str] = set()
    seen_signatures: set[tuple[str, str, str]] = set()
    selected: list[dict[str, Any]] = []
    for item in results:
        row = dict(item)
        key = str(row.get("stable_chunk_id") or row.get("doc_id") or row.get("chunk_id") or "")
        source_id = str(row.get("source_id") or row.get("source_name") or row.get("source") or "unknown")
        text = str(row.get("text") or "")
        section = str(row.get("section_heading") or "")
        signature = (source_id.strip().lower(), section.strip().lower(), text[:180].strip().lower())
        if key and key in seen:
            continue
        if signature in seen_signatures:
            continue
        if by_source[source_id] >= max_per_source and len({r.get("source_id") or r.get("source_name") or r.get("source") for r in selected}) >= int(os.getenv("RAG_MIN_SOURCE_DIVERSITY", "2") or "2"):
            continue
        if key:
            seen.add(key)
        seen_signatures.add(signature)
        by_source[source_id] += 1
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def retrieve(question: str, requested_domain: str | None = None, strict_domain: bool = False, final_limit: int = 8) -> Dict[str, Any]:
    variants = generate_query_variants(question)
    candidate_domains = infer_candidate_domains(question, requested_domain=requested_domain)
    where = {"domain": requested_domain} if strict_domain and requested_domain else None
    vector_top_k = max(12, int(os.getenv("RAG_VECTOR_TOP_K", "40") or "40"))
    keyword_top_k = max(8, int(os.getenv("RAG_KEYWORD_TOP_K", "30") or "30"))

    vector_lists: list[list[dict[str, Any]]] = []
    keyword_lists: list[list[dict[str, Any]]] = []
    for variant in variants:
        hits = vector_search(variant, top_k=vector_top_k, where=where)
        if hits:
            for row in hits:
                row["query_variant_source"] = variant
            vector_lists.append(hits)
    for variant in variants[:2]:
        hits = keyword_search(variant, top_k=keyword_top_k, strict_domain=requested_domain if strict_domain else None)
        if hits:
            keyword_lists.append(hits)

    merged = rrf_merge([*vector_lists, *keyword_lists], k=max(1, int(os.getenv("RAG_HYBRID_RRF_K", "60") or "60")))
    reranked = rerank_results(merged, question=question, candidate_domains=candidate_domains)
    selected = enforce_source_diversity(
        reranked,
        limit=max(1, int(final_limit or int(os.getenv("RAG_FINAL_CONTEXT_K", "8") or "8"))),
        max_per_source=max(1, int(os.getenv("RAG_MAX_CHUNKS_PER_SOURCE", "3") or "3")),
    )
    return {
        "query_variants": variants,
        "candidate_domains": candidate_domains,
        "vector_candidates": [item for sub in vector_lists for item in sub],
        "keyword_candidates": [item for sub in keyword_lists for item in sub],
        "merged_candidates": merged,
        "selected_chunks": selected,
    }
