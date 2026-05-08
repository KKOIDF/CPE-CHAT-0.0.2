from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_COURSE_CODE_RE = re.compile(r"\b[A-Z]{2,6}\s*\d{3}\b", re.IGNORECASE)
_CLAUSE_RE = re.compile(r"^ข้อ\s*\d+(?:\.\d+)?", re.MULTILINE)
_URL_RE = re.compile(r"https?://\S+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def infer_document_profile(source_path: str, text: str, domain_hint: str | None = None) -> dict[str, Any]:
    path = Path(source_path)
    name = path.name.lower()
    stem = path.stem.lower()
    domain = str(domain_hint or '').strip().lower()
    basis = f"{path.name}\n{text[:8000]}"

    doc_family = domain or 'general'
    doc_type = 'unknown'
    semantic_chunk_strategy = 'structure'
    extractor_profile = 'generic'
    confidence = 0.55

    if domain == 'curriculum':
        doc_family = 'curriculum'
        if 'teacher_profiles_by_course' in name:
            doc_type = 'teacher_profile_csv'
            semantic_chunk_strategy = 'curriculum_course'
            extractor_profile = 'teacher_profiles'
            confidence = 0.98
        elif _COURSE_CODE_RE.search(basis):
            doc_type = 'course_catalog'
            semantic_chunk_strategy = 'curriculum_course'
            extractor_profile = 'course_blocks'
            confidence = 0.9
        else:
            doc_type = 'curriculum_general'
            semantic_chunk_strategy = 'curriculum_course'
            extractor_profile = 'curriculum_general'
            confidence = 0.72

    elif domain == 'regulations':
        doc_family = 'regulations'
        if name == 'forms.txt' or ('form' in stem and _URL_RE.search(basis)):
            doc_type = 'form_directory'
            semantic_chunk_strategy = 'regulation_template'
            extractor_profile = 'form_blocks'
            confidence = 0.98
        elif name == 'contacts.txt' or (_EMAIL_RE.search(basis) and re.search(r"(โทร|อีเมล|contact|ชื่อ:)", basis, re.IGNORECASE)):
            doc_type = 'contact_directory'
            semantic_chunk_strategy = 'regulation_template'
            extractor_profile = 'contact_blocks'
            confidence = 0.96
        elif _CLAUSE_RE.search(basis):
            doc_type = 'regulation_clause'
            semantic_chunk_strategy = 'regulation_template'
            extractor_profile = 'regulation_clauses'
            confidence = 0.9
        else:
            doc_type = 'regulation_general'
            semantic_chunk_strategy = 'regulation_template'
            extractor_profile = 'regulation_general'
            confidence = 0.72

    elif domain == 'announcements':
        doc_family = 'announcements'
        if re.search(r"(ปฏิทินการศึกษา|calendar|กำหนดการ)", basis, re.IGNORECASE):
            doc_type = 'academic_calendar'
            semantic_chunk_strategy = 'announcement_template'
            extractor_profile = 'calendar_events'
            confidence = 0.96
        elif re.search(r"(ขั้นตอน|คำร้อง|download|ประกาศ)", basis, re.IGNORECASE):
            doc_type = 'announcement_procedure'
            semantic_chunk_strategy = 'announcement_template'
            extractor_profile = 'procedure_blocks'
            confidence = 0.82
        else:
            doc_type = 'announcement_general'
            semantic_chunk_strategy = 'announcement_template'
            extractor_profile = 'announcement_general'
            confidence = 0.7

    return {
        'source_path': str(path),
        'source_name': path.name,
        'domain': doc_family,
        'doc_type': doc_type,
        'semantic_chunk_strategy': semantic_chunk_strategy,
        'extractor_profile': extractor_profile,
        'confidence': confidence,
    }
