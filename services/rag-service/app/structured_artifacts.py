from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any
import re

from .config import ROOT_DIR


def _artifact_candidates(domain: str, filename: str) -> list[Path]:
    dom = str(domain or '').strip().lower()
    if not dom:
        return []
    return [
        ROOT_DIR / 'indexes' / dom / 'structured' / filename,
        ROOT_DIR / 'data' / 'structured' / dom / filename,
        ROOT_DIR / 'data' / dom / 'structured' / filename,
    ]


def _load_json(paths: list[Path]) -> dict[str, Any]:
    for path in paths:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding='utf-8'))
                if isinstance(data, dict):
                    return data
        except Exception:
            continue
    return {}


@lru_cache(maxsize=1)
def load_announcement_calendar_artifact() -> dict[str, Any]:
    return _load_json(_artifact_candidates('announcements', 'announcement_calendar.json'))


@lru_cache(maxsize=1)
def load_course_prerequisites_artifact() -> dict[str, Any]:
    return _load_json(_artifact_candidates('curriculum', 'course_prerequisites.json'))


@lru_cache(maxsize=1)
def load_regulation_clauses_artifact() -> dict[str, Any]:
    return _load_json(_artifact_candidates('regulations', 'regulation_clauses.json'))


@lru_cache(maxsize=4)
def load_fact_index_artifact(domain: str) -> dict[str, Any]:
    dom = str(domain or '').strip().lower()
    if not dom:
        return {}
    return _load_json(_artifact_candidates(dom, 'fact_index.json'))


@lru_cache(maxsize=4)
def load_document_profiles_artifact(domain: str) -> dict[str, Any]:
    dom = str(domain or '').strip().lower()
    if not dom:
        return {}
    return _load_json(_artifact_candidates(dom, 'document_profiles.json'))


def summarize_document_profiles(domains: list[str] | None = None, limit_per_domain: int = 4) -> dict[str, list[dict[str, Any]]]:
    doms = [str(d or '').strip().lower() for d in (domains or []) if str(d or '').strip()]
    if not doms:
        doms = ['curriculum', 'regulations', 'announcements']
    out: dict[str, list[dict[str, Any]]] = {}
    for dom in doms:
        art = load_document_profiles_artifact(dom)
        profiles = art.get('profiles') if isinstance(art, dict) else None
        if not isinstance(profiles, list):
            continue
        rows: list[dict[str, Any]] = []
        for prof in profiles[: max(1, int(limit_per_domain or 4))]:
            if not isinstance(prof, dict):
                continue
            rows.append(
                {
                    'source_name': str(prof.get('source_name') or '').strip(),
                    'doc_type': str(prof.get('doc_type') or '').strip(),
                    'semantic_chunk_strategy': str(prof.get('semantic_chunk_strategy') or '').strip(),
                    'extractor_profile': str(prof.get('extractor_profile') or '').strip(),
                }
            )
        if rows:
            out[dom] = rows
    return out


def load_all_fact_index_artifacts() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for dom in ('curriculum', 'regulations', 'announcements'):
        art = load_fact_index_artifact(dom)
        if art:
            out[dom] = art
    return out


def _normalize_search_text(text: str) -> str:
    t = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return re.sub(r"[^a-z0-9\u0E00-\u0E7F ]+", " ", t)


def _tokenize_search_text(text: str) -> list[str]:
    t = _normalize_search_text(text)
    toks = [tok for tok in t.split(" ") if tok]
    seen: set[str] = set()
    out: list[str] = []
    for tok in toks:
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def _is_policy_graduation_query(question: str, intent: str | None) -> bool:
    q = _normalize_search_text(question)
    intent_key = str(intent or '').strip().lower()
    policy_terms = (
        'สำเร็จการศึกษา', 'สําเร็จการศึกษา', 'เกณฑ์', 'เงื่อนไข', 'ข้อกำหนด', 'ข้อกําหนด',
        'หน่วยกิต', 'gpax', 'เกรด', 'graduation', 'requirement', 'policy', 'regulation'
    )
    return intent_key in ('policy_lookup', 'academic_status_policy') or any(term in q for term in policy_terms)


def search_fact_index(
    question: str,
    domains: list[str] | None = None,
    limit: int = 8,
    intent: str | None = None,
    needed_evidence: list[str] | None = None,
) -> list[dict[str, Any]]:
    q = str(question or "").strip()
    if not q:
        return []
    doms = [str(d or "").strip().lower() for d in (domains or []) if str(d or "").strip()]
    if not doms:
        doms = ['curriculum', 'regulations', 'announcements']
    q_norm = _normalize_search_text(q)
    q_tokens = _tokenize_search_text(q)
    if not q_tokens:
        return []

    rows: list[dict[str, Any]] = []
    for dom in doms:
        artifact = load_fact_index_artifact(dom)
        facts = artifact.get('facts') if isinstance(artifact, dict) else None
        if not isinstance(facts, list):
            continue
        for idx, fact in enumerate(facts):
            if not isinstance(fact, dict):
                continue
            blob = str(fact.get('blob') or fact.get('evidence_text') or '').strip()
            if not blob:
                continue
            blob_norm = _normalize_search_text(blob)
            blob_compact = blob_norm.replace(' ', '')
            hits = 0
            exact_hits = 0
            for tok in q_tokens:
                tok_compact = tok.replace(' ', '')
                if tok and (tok in blob_norm or (tok_compact and tok_compact in blob_compact)):
                    hits += 1
                    if re.search(rf"(?<![a-z0-9\u0E00-\u0E7F]){re.escape(tok)}(?![a-z0-9\u0E00-\u0E7F])", blob_norm):
                        exact_hits += 1
            if hits <= 0:
                continue
            coverage = hits / max(1, len(q_tokens))
            exact_bonus = exact_hits / max(1, len(q_tokens))
            confidence = float(fact.get('confidence') or 0.0)
            entity_type = str(fact.get('entity_type') or '').strip().lower()
            score = round((coverage * 0.7) + (exact_bonus * 0.2) + (confidence * 0.1), 4)
            intent_key = str(intent or '').strip().lower()
            needed = [str(v or '').strip().lower() for v in (needed_evidence or []) if str(v or '').strip()]
            if dom == 'curriculum' and _is_policy_graduation_query(q, intent_key):
                if entity_type in {'course_instructor', 'person_contact'}:
                    continue
                if 'ภาระงานสอนในปัจจุบัน' in blob or 'teacher_profiles_by_course.csv' in str(fact.get('source') or ''):
                    continue
                if entity_type == 'course':
                    needed_course_fields = any(v in needed for v in ('course_code', 'course_name', 'credits'))
                    if not needed_course_fields:
                        continue
            if intent_key in ('contact_lookup', 'person_contact', 'instructor_lookup'):
                if entity_type == 'person_contact':
                    score += 0.35
                elif entity_type == 'course_instructor':
                    score += 0.28
                elif entity_type == 'course':
                    score -= 0.08
            elif intent_key in ('course_lookup', 'credit_lookup', 'prerequisite_lookup'):
                if entity_type == 'course':
                    score += 0.28
                elif entity_type == 'course_instructor':
                    score += 0.08
            elif intent_key == 'form_lookup' and entity_type == 'form':
                score += 0.3
            elif intent_key in ('procedure_lookup', 'registration_policy') and entity_type == 'procedure':
                score += 0.3
            elif intent_key in ('calendar_lookup', 'calendar_deadline') and entity_type == 'calendar_event':
                score += 0.3
            if needed:
                if entity_type == 'person_contact' and any(v in needed for v in ('email', 'phone', 'contact')):
                    score += 0.08
                if entity_type == 'course' and any(v in needed for v in ('course_code', 'course_name', 'credits')):
                    score += 0.08
            rows.append(
                {
                    'doc_id': f"fact:{dom}:{idx}",
                    'domain': dom,
                    'source': str(fact.get('source') or 'fact_index.json').strip() or 'fact_index.json',
                    'path': str(fact.get('source_doc') or fact.get('source') or 'fact_index.json').strip() or 'fact_index.json',
                    'page_start': int(fact.get('page') or 1),
                    'page_end': int(fact.get('page') or 1),
                    'score_rrf': score,
                    'score_final': score,
                    'text': blob,
                    'metadata': fact,
                }
            )
    rows.sort(key=lambda row: float(row.get('score_final') or 0.0), reverse=True)
    return rows[: max(1, int(limit or 8))]
