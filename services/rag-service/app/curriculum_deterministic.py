from __future__ import annotations

import re

from .normalization import normalize_question
from .neo4j_client import extract_course_codes
from .sqlite_client import domain_sqlite_path, fetch_docs_with_path, keyword_search
from .structured_curriculum import (
    Course,
    extract_courses_from_text,
    format_required_cpe_answer,
    load_all_courses_2564,
    load_cpe_curriculum_2564,
    load_credit_totals_2564,
)

_COURSE_ALIASES = {
    "introduction to computer engineering": "CPE100",
    "computer engineering mathematics": "CPE111",
    "computer programming": "CPE101",
    "data structure": "CPE112",
    "data structures": "CPE112",
    "discrete mathematics": "CPE211",
    "algorithm": "CPE213",
    "algorithms": "CPE213",
    "operating system": "CPE214",
    "operating systems": "CPE214",
    "digital logic": "CPE121",
    "software engineering": "CPE241",
    "database system": "CPE231",
    "database systems": "CPE231",
    "artificial intelligence": "CPE324",
    "computer architecture": "CPE223",
    "computer networks": "CPE314",
    "computer network": "CPE314",
}


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

    # English aliases parsing
    if not codes and not instructor_intent and not (prereq_intent or term_intent):
        ql_en = re.sub(r"[^a-z0-9\s]", " ", q.lower()).strip()
        for alias, alias_code in _COURSE_ALIASES.items():
            if alias in ql_en:
                codes.append(alias_code)
                break

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
