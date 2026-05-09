from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_COURSE_CODE_RE = re.compile(r"\b[A-Z]{2,6}\s*\d{3}\b", re.IGNORECASE)
_CLAUSE_RE = re.compile(r"^ข้อ\s*\d+(?:\.\d+)?", re.MULTILINE)
_URL_RE = re.compile(r"https?://\S+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(\b0\d{1,2}[- ]?\d{3}[- ]?\d{3,4}\b)")
_SEMESTER_RE = re.compile(r"(ภาคการศึกษาที่\s*[1-3]|เทอม\s*[1-3]|semester\s*[1-3])", re.IGNORECASE)
_DATE_RE = re.compile(r"(\b\d{1,2}\s*[/-]\s*\d{1,2}\s*[/-]\s*(?:\d{2}|\d{4})\b|\b\d{1,2}\s*(?:ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.)\s*(?:25\d{2}|26\d{2})\b)", re.IGNORECASE)
_PLO_RE = re.compile(r"\b(?:PLO\s*\d+|\d+[A-Z])\b", re.IGNORECASE)
_FACULTY_NAME_RE = re.compile(r"^(?:รศ\.ดร\.|ผศ\.ดร\.|ผศ\.|อ\.ดร\.|อ\.)\s+.+$")
_FACULTY_SECTION_RE = re.compile(r"(ประวัติการศึกษา|ภาระงานสอน|ผลงาน|education|teaching\s*load|publication)", re.IGNORECASE)
_TABLE_ROW_RE = re.compile(r"\s{2,}|\||,")
_HEADING_RE = re.compile(r"^(?:บท|หมวด|ภาคผนวก|ข้อ|[0-9]+(?:\.[0-9]+)*[\.)]?|[A-Za-zก-๙]+\s*:)")


def _top_lines(text: str, limit: int = 250) -> list[str]:
    out: list[str] = []
    for line in (text or '').splitlines():
        s = line.strip()
        if not s:
            continue
        out.append(s)
        if len(out) >= limit:
            break
    return out


def _split_cells(line: str) -> list[str]:
    s = (line or '').strip()
    if not s:
        return []
    if '|' in s:
        parts = [p.strip() for p in s.split('|')]
        if parts and parts[0] == '':
            parts = parts[1:]
        if parts and parts[-1] == '':
            parts = parts[:-1]
        return [p for p in parts if p]
    if ',' in s:
        parts = [p.strip() for p in s.split(',')]
        dense = [p for p in parts if p]
        if len(dense) >= 3:
            return dense
    parts = [p.strip() for p in re.split(r"\s{2,}", s) if p.strip()]
    return parts


def _table_like_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        cells = _split_cells(line)
        if len(cells) >= 3 or ('|' in line and len(cells) >= 2):
            out.append(line)
    return out


def _count_heading_lines(lines: list[str]) -> int:
    return sum(1 for line in lines if _HEADING_RE.search(line))


def _count_clause_lines(lines: list[str]) -> int:
    return sum(1 for line in lines if _CLAUSE_RE.search(line))


def _table_header_score(lines: list[str]) -> int:
    score = 0
    for line in lines[:40]:
        ll = line.lower()
        if any(tok in ll for tok in ('ชื่อ', 'รหัส', 'หน่วยกิต', 'course', 'credits', 'email', 'โทร', 'วันที่', 'กิจกรรม')):
            score += 1
    return score


def _mixed_layout_score(lines: list[str], table_lines: list[str]) -> int:
    if not lines:
        return 0
    heading_count = _count_heading_lines(lines)
    prose_lines = max(0, len(lines) - len(table_lines))
    score = 0
    if heading_count >= 2 and len(table_lines) >= 3:
        score += 2
    if prose_lines >= 8 and len(table_lines) >= 4:
        score += 1
    return score


def infer_document_profile(source_path: str, text: str, domain_hint: str | None = None) -> dict[str, Any]:
    path = Path(source_path)
    name = path.name.lower()
    stem = path.stem.lower()
    ext = path.suffix.lower()
    domain = str(domain_hint or '').strip().lower()
    basis = f"{path.name}\n{text[:12000]}"
    lines = _top_lines(basis)
    table_lines = _table_like_lines(lines)
    heading_count = _count_heading_lines(lines)
    clause_count = _count_clause_lines(lines)
    course_codes = len(_COURSE_CODE_RE.findall(basis))
    plo_hits = len(_PLO_RE.findall(basis))
    semester_hits = len(_SEMESTER_RE.findall(basis))
    date_hits = len(_DATE_RE.findall(basis))
    email_hits = len(_EMAIL_RE.findall(basis))
    phone_hits = len(_PHONE_RE.findall(basis))
    table_header_hits = _table_header_score(lines)
    mixed_layout_score = _mixed_layout_score(lines, table_lines)

    doc_family = domain or 'general'
    doc_type = 'unknown'
    semantic_chunk_strategy = 'structure'
    extractor_profile = 'generic'
    confidence = 0.55

    if domain == 'curriculum':
        doc_family = 'curriculum'
        if 'teacher_profiles_by_course' in name or ('course_code' in basis.lower() and 'teaching_part' in basis.lower()):
            doc_type = 'teacher_profile_csv'
            semantic_chunk_strategy = 'table_aware'
            extractor_profile = 'teacher_profiles'
            confidence = 0.99
        elif _FACULTY_NAME_RE.search(basis) and _FACULTY_SECTION_RE.search(basis):
            doc_type = 'faculty_profile'
            semantic_chunk_strategy = 'mixed_layout'
            extractor_profile = 'faculty_sections'
            confidence = 0.94
        elif plo_hits >= 4 and course_codes >= 2 and len(table_lines) >= 3:
            doc_type = 'mapping_table'
            semantic_chunk_strategy = 'table_aware'
            extractor_profile = 'plo_mapping'
            confidence = 0.94
        elif semester_hits >= 2 and course_codes >= 4 and len(table_lines) >= 4:
            doc_type = 'study_plan_table'
            semantic_chunk_strategy = 'table_aware'
            extractor_profile = 'study_plan_table'
            confidence = 0.9
        elif course_codes >= 3:
            doc_type = 'course_catalog'
            semantic_chunk_strategy = 'curriculum_course'
            extractor_profile = 'course_blocks'
            confidence = 0.91
        elif len(table_lines) >= 5:
            doc_type = 'curriculum_table_general'
            semantic_chunk_strategy = 'table_aware'
            extractor_profile = 'curriculum_table'
            confidence = 0.82
        elif mixed_layout_score >= 2:
            doc_type = 'curriculum_mixed_layout'
            semantic_chunk_strategy = 'mixed_layout'
            extractor_profile = 'curriculum_mixed'
            confidence = 0.8
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
        elif name == 'contacts.txt' or ((email_hits or phone_hits) and re.search(r"(โทร|อีเมล|contact|ชื่อ:)", basis, re.IGNORECASE)):
            doc_type = 'contact_directory'
            semantic_chunk_strategy = 'regulation_template'
            extractor_profile = 'contact_blocks'
            confidence = 0.97
        elif re.search(r"(ค่าธรรมเนียม|fee|บาท|THB)", basis, re.IGNORECASE) and len(table_lines) >= 3:
            doc_type = 'fee_table'
            semantic_chunk_strategy = 'table_aware'
            extractor_profile = 'fee_rows'
            confidence = 0.95
        elif re.search(r"(แก้ไขเพิ่มเติม|ให้ใช้แทน|ยกเลิก|replace|supersede)", basis, re.IGNORECASE):
            doc_type = 'amendment'
            semantic_chunk_strategy = 'mixed_layout' if mixed_layout_score >= 2 else 'regulation_template'
            extractor_profile = 'amendment_blocks'
            confidence = 0.93
        elif clause_count >= 2:
            doc_type = 'regulation_clause'
            semantic_chunk_strategy = 'mixed_layout' if len(table_lines) >= 4 else 'regulation_template'
            extractor_profile = 'regulation_clauses'
            confidence = 0.9
        elif len(table_lines) >= 5:
            doc_type = 'regulation_table_general'
            semantic_chunk_strategy = 'table_aware'
            extractor_profile = 'regulation_table'
            confidence = 0.8
        else:
            doc_type = 'regulation_general'
            semantic_chunk_strategy = 'mixed_layout' if mixed_layout_score >= 2 else 'regulation_template'
            extractor_profile = 'regulation_general'
            confidence = 0.72

    elif domain == 'announcements':
        doc_family = 'announcements'
        if re.search(r"(ปฏิทินการศึกษา|calendar|กำหนดการ)", basis, re.IGNORECASE) and (semester_hits or date_hits):
            doc_type = 'academic_calendar'
            semantic_chunk_strategy = 'table_aware' if len(table_lines) >= 2 else 'announcement_template'
            extractor_profile = 'calendar_events'
            confidence = 0.97
        elif re.search(r"(ขั้นตอน|คำร้อง|download|ประกาศ)", basis, re.IGNORECASE) and heading_count >= 2:
            doc_type = 'announcement_procedure'
            semantic_chunk_strategy = 'mixed_layout' if mixed_layout_score >= 2 else 'announcement_template'
            extractor_profile = 'procedure_blocks'
            confidence = 0.86
        elif email_hits or phone_hits:
            doc_type = 'announcement_contact_list'
            semantic_chunk_strategy = 'mixed_layout'
            extractor_profile = 'contact_blocks'
            confidence = 0.84
        elif len(table_lines) >= 5 and table_header_hits >= 1:
            doc_type = 'announcement_table_general'
            semantic_chunk_strategy = 'table_aware'
            extractor_profile = 'announcement_table'
            confidence = 0.82
        else:
            doc_type = 'announcement_general'
            semantic_chunk_strategy = 'mixed_layout' if mixed_layout_score >= 2 else 'announcement_template'
            extractor_profile = 'announcement_general'
            confidence = 0.7

    else:
        if clause_count >= 2:
            doc_type = 'regulation_clause'
            semantic_chunk_strategy = 'regulation_template'
            extractor_profile = 'regulation_clauses'
            confidence = 0.8
            doc_family = 'regulations'
        elif course_codes >= 3:
            doc_type = 'course_catalog'
            semantic_chunk_strategy = 'curriculum_course'
            extractor_profile = 'course_blocks'
            confidence = 0.78
            doc_family = 'curriculum'
        elif len(table_lines) >= 5:
            doc_type = 'generic_table_document'
            semantic_chunk_strategy = 'table_aware'
            extractor_profile = 'generic_table'
            confidence = 0.72
        elif mixed_layout_score >= 2:
            doc_type = 'generic_mixed_layout'
            semantic_chunk_strategy = 'mixed_layout'
            extractor_profile = 'generic_mixed'
            confidence = 0.68

    return {
        'source_path': str(path),
        'source_name': path.name,
        'source_ext': ext,
        'domain': doc_family,
        'doc_type': doc_type,
        'semantic_chunk_strategy': semantic_chunk_strategy,
        'extractor_profile': extractor_profile,
        'confidence': confidence,
        'layout_signals': {
            'heading_count': heading_count,
            'clause_count': clause_count,
            'course_code_hits': course_codes,
            'plo_hits': plo_hits,
            'semester_hits': semester_hits,
            'date_hits': date_hits,
            'email_hits': email_hits,
            'phone_hits': phone_hits,
            'table_row_count': len(table_lines),
            'table_header_score': table_header_hits,
            'mixed_layout_score': mixed_layout_score,
        },
    }
