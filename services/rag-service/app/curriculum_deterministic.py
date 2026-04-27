from __future__ import annotations

import re
import sqlite3
from difflib import SequenceMatcher
from typing import Any

from .normalization import normalize_question
from .neo4j_client import extract_course_codes, graph_requisite_codes_for_course
from .sqlite_client import domain_sqlite_path, fetch_docs_with_path, keyword_search
from .structured_artifacts import load_course_prerequisites_artifact
from .structured_curriculum import (
    Course,
    extract_courses_from_text,
    format_required_cpe_answer,
    load_all_courses_2564,
    load_cpe_curriculum_2564,
    load_credit_totals_2564,
)


_CLAIM_MARKERS = (
    'ใช่หรือไม่', 'จริงหรือไม่', 'หรือไม่', 'ถูกต้องหรือไม่', 'ใช่ไหม', 'ใช่มั้ย', 'จริงไหม',
)

_ABSTAINISH_MARKERS = (
    'ไม่พบข้อความยืนยัน', 'ไม่ได้ระบุชัดเจน', 'ไม่มีข้อความยืนยัน', 'บริบทไม่ได้กล่าวตรง',
)

_PROGRAM_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    'program_code': ('รหัสหลักสูตร', 'รหัสของหลักสูตร', 'program code'),
    'degree_name_en': ('ชื่อเต็มภาษาอังกฤษของปริญญา', 'ชื่อปริญญาภาษาอังกฤษ', 'degree name english'),
    'degree_name_th': ('ชื่อเต็มภาษาไทยของปริญญา', 'ชื่อปริญญาภาษาไทย'),
    'degree_abbr_en': ('ชื่อย่อภาษาอังกฤษ', 'degree abbreviation english'),
    'degree_abbr_th': ('ชื่อย่อภาษาไทย', 'degree abbreviation thai'),
    'program_level': ('ระดับหลักสูตร', 'ระดับการศึกษา', 'ปริญญาตรี'),
    'study_years': ('กี่ปี', 'ระยะเวลาเรียน', 'ใช้เวลาเรียน', 'study years'),
    'student_group': ('รับนักศึกษา', 'กลุ่มใด', 'รับเฉพาะนักศึกษาไทย', 'admission target', 'student group'),
    'language_of_instruction': ('ภาษาในการเรียนการสอน', 'ใช้ภาษาอังกฤษเป็นหลักไหม', 'ภาษาไทยเป็นหลักไหม', 'language of instruction'),
    'revised_from_program': ('ปรับปรุงจากหลักสูตร', 'ปรับปรุงจาก', 'revised from'),
    'council_approval_meeting_no': ('อนุมัติสภา', 'ครั้งที่', 'meeting no'),
    'council_approval_date': ('วันที่อนุมัติ', 'approval date', 'วันที่สภาอนุมัติ'),
}

_PROGRAM_META_CACHE: dict[str, str] | None = None

_COURSE_ALIASES = {
    "introduction to computer engineering": "CPE100",
    "engineering exploration": "CPE101",
    "discrete mathematics for computer engineers": "CPE111",
    "computer engineering mathematics": "CPE111",
    "computer programming": "CPE101",
    "computer programming for engineers": "CPE100",
    "data structure": "CPE112",
    "data structures": "CPE112",
    "programming with data structures": "CPE112",
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

_TITLE_STOPWORDS_EN = {
    "the", "a", "an", "of", "for", "with", "and", "to", "in", "on",
    "course", "subject", "code", "what", "which", "is", "are", "about",
    "please", "tell", "me",
}

_TEACHER_ASSIGNMENT_SOURCE_ALLOWLIST = (
    "teacher_profiles_by_course.txt",
    "teacher_profiles_by_course.csv",
)

_STUDY_PLAN_ITEM_RE = re.compile(
    r"^\s*(?P<or>หรือ\s+)?(?P<prefix>[A-Z]{2,6}|XXX)\s+(?P<num>\d{3}|[xX]{3}|\d[xX]{2})\s+(?P<title>.+?)\s+(?P<credits>\d+)\s*\(",
)

_STUDY_PLAN_GROUP_CACHE: dict[str, Any] | None = None


def _load_study_plan_group_cache() -> dict[str, Any]:
    global _STUDY_PLAN_GROUP_CACHE
    if _STUDY_PLAN_GROUP_CACHE is not None:
        return _STUDY_PLAN_GROUP_CACHE

    curriculum = load_cpe_curriculum_2564()
    if not curriculum:
        _STUDY_PLAN_GROUP_CACHE = {}
        return _STUDY_PLAN_GROUP_CACHE

    try:
        text = curriculum.source_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        _STUDY_PLAN_GROUP_CACHE = {}
        return _STUDY_PLAN_GROUP_CACHE

    if "แผนการศึกษา" in text:
        text = text.split("แผนการศึกษา", 1)[1]
    if "คำอธิบายรายวิชา" in text:
        text = text.split("คำอธิบายรายวิชา", 1)[0]

    normal_marker = "แผนการศึกษาปกติ"
    wil_marker = "แผนการศึกษาการเรียนรู้ร่วมกับการทำงาน"

    common_txt = text
    normal_txt = ""
    wil_txt = ""
    rest = text
    if normal_marker in text:
        common_txt, rest = text.split(normal_marker, 1)
        normal_txt = rest
    if wil_marker in rest:
        before_wil, wil_txt = rest.split(wil_marker, 1)
        if normal_txt:
            normal_txt = before_wil
        else:
            common_txt = before_wil

    def _parse_items(section_text: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for raw_ln in (section_text or "").splitlines():
            ln = raw_ln.rstrip()
            m = _STUDY_PLAN_ITEM_RE.match(ln)
            if not m:
                continue
            prefix = str(m.group("prefix") or "").strip().upper()
            number = str(m.group("num") or "").strip()
            title = re.sub(r"\s+", " ", str(m.group("title") or "").strip())
            try:
                credits = int(m.group("credits") or "0")
            except Exception:
                credits = 0
            items.append(
                {
                    "prefix": prefix,
                    "number": number,
                    "title_th": title,
                    "credits": credits,
                    "is_placeholder": bool(re.search(r"[xX]", number)) or prefix == "XXX",
                }
            )
        return items

    common_items = _parse_items(common_txt)
    normal_items = _parse_items(normal_txt)
    wil_items = _parse_items(wil_txt)

    def _is_elective(item: dict[str, Any]) -> bool:
        title = str(item.get("title_th") or "")
        return "วิชาเลือก" in title

    def _item_key(item: dict[str, Any]) -> str:
        return "|".join(
            [
                str(item.get("prefix") or "").upper(),
                str(item.get("number") or ""),
                str(item.get("title_th") or ""),
                str(item.get("credits") or 0),
            ]
        )

    def _sorted(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def _key(item: dict[str, Any]) -> tuple[str, int, str]:
            num = str(item.get("number") or "")
            title = str(item.get("title_th") or "")
            if re.fullmatch(r"\d{3}", num):
                return (str(item.get("prefix") or ""), int(num), title)
            return (str(item.get("prefix") or ""), 9999, title)

        return sorted(items, key=_key)

    common_required = [it for it in common_items if not _is_elective(it)]
    normal_required = [it for it in normal_items if not _is_elective(it)]
    wil_required = [it for it in wil_items if not _is_elective(it)]
    common_elective = [it for it in common_items if _is_elective(it)]
    normal_elective = [it for it in normal_items if _is_elective(it)]
    wil_elective = [it for it in wil_items if _is_elective(it)]

    common_required_keys = {_item_key(it) for it in common_required}
    common_elective_keys = {_item_key(it) for it in common_elective}

    _STUDY_PLAN_GROUP_CACHE = {
        "required_common": _sorted(common_required),
        "required_normal_only": _sorted([it for it in normal_required if _item_key(it) not in common_required_keys]),
        "required_wil_only": _sorted([it for it in wil_required if _item_key(it) not in common_required_keys]),
        "elective_common": _sorted(common_elective),
        "elective_normal_only": _sorted([it for it in normal_elective if _item_key(it) not in common_elective_keys]),
        "elective_wil_only": _sorted([it for it in wil_elective if _item_key(it) not in common_elective_keys]),
    }
    return _STUDY_PLAN_GROUP_CACHE


def _is_group_list_question(question: str) -> bool:
    q = (question or "").strip()
    if not q:
        return False
    has_required_term = any(t in q for t in ("วิชาบังคับ", "วิชาบังครับ", "วิชาชีพบังคับ"))
    has_group_term = ("วิชาเลือก" in q) or has_required_term
    if not has_group_term:
        return False
    return any(t in q for t in ("มีอะไร", "อะไรบ้าง", "ทั้งหมด", "กี่ตัว", "กี่วิชา", "รายวิชา", "หมวด"))


def _format_study_plan_item(item: dict[str, Any], source_name: str) -> str:
    prefix = str(item.get("prefix") or "").strip().upper()
    number = str(item.get("number") or "").strip()
    title = str(item.get("title_th") or "").strip()
    credits = int(item.get("credits") or 0)
    code_disp = f"{prefix} {number}".strip()
    cred = f" ({credits} หน่วยกิต)" if credits else ""
    return f"- {code_disp} {title}{cred} [{source_name}/1]"


def _group_list_answer(question: str, source_name: str, totals: dict[str, int]) -> str | None:
    if not _is_group_list_question(question):
        return None

    groups = _load_study_plan_group_cache()
    if not groups:
        return None

    asks_required = any(t in (question or "") for t in ("วิชาบังคับ", "วิชาบังครับ", "วิชาชีพบังคับ"))
    asks_elective = ("วิชาเลือก" in question) and (not asks_required)
    mode = "elective" if asks_elective else "required"

    if mode == "elective":
        common_items = list(groups.get("elective_common") or [])
        normal_only = list(groups.get("elective_normal_only") or [])
        wil_only = list(groups.get("elective_wil_only") or [])

        if not (common_items or normal_only or wil_only):
            return None

        lines = ["สรุปรายวิชาที่ระบุเป็นวิชาเลือกในแผนการศึกษา หลักสูตรวิศวกรรมคอมพิวเตอร์ (ปรับปรุง พ.ศ. 2564):"]
        specific_elective = totals.get("specific_elective")
        free_elective = totals.get("free_elective")
        if specific_elective is not None or free_elective is not None:
            summary_bits: list[str] = []
            if specific_elective is not None:
                summary_bits.append(f"วิชาเลือกทางวิศวกรรมคอมพิวเตอร์ {specific_elective} หน่วยกิต")
            if free_elective is not None:
                summary_bits.append(f"วิชาเลือกเสรี {free_elective} หน่วยกิต")
            if summary_bits:
                lines.append(f"- โครงสร้างหลักสูตรระบุ {' และ '.join(summary_bits)} [{source_name}/1]")
        if common_items:
            lines.append("- วิชาเลือกที่พบร่วมกันทุกแผน:")
            for item in common_items:
                lines.append(_format_study_plan_item(item, source_name))
        if normal_only:
            lines.append("- เพิ่มเติมเฉพาะแผนการศึกษาปกติ:")
            for item in normal_only:
                lines.append(_format_study_plan_item(item, source_name))
        if wil_only:
            lines.append("- เพิ่มเติมเฉพาะแผนการศึกษาการเรียนรู้ร่วมกับการทำงาน (WIL):")
            for item in wil_only:
                lines.append(_format_study_plan_item(item, source_name))
        return "\n".join(lines).strip()

    common_items = list(groups.get("required_common") or [])
    normal_only = list(groups.get("required_normal_only") or [])
    wil_only = list(groups.get("required_wil_only") or [])
    if not (common_items or normal_only or wil_only):
        return None

    lines = ["สรุปรายวิชาบังคับที่ระบุชัดในแผนการศึกษา หลักสูตรวิศวกรรมคอมพิวเตอร์ (ปรับปรุง พ.ศ. 2564):"]
    if common_items:
        lines.append("- รายวิชาบังคับร่วมกันทุกแผน:")
        for item in common_items:
            lines.append(_format_study_plan_item(item, source_name))
    if normal_only:
        lines.append("- เพิ่มเติมเฉพาะแผนการศึกษาปกติ:")
        for item in normal_only:
            lines.append(_format_study_plan_item(item, source_name))
    if wil_only:
        lines.append("- เพิ่มเติมเฉพาะแผนการศึกษาการเรียนรู้ร่วมกับการทำงาน (WIL):")
        for item in wil_only:
            lines.append(_format_study_plan_item(item, source_name))
    return "\n".join(lines).strip()


def _extract_prefix_from_question(question: str) -> str | None:
    q = (question or "")
    # Prefer explicit patterns like LNGxxx / CPExxx
    m = re.search(r"\b([A-Za-z]{2,6})[xX]{2,}\b", q)
    if m:
        pref = re.sub(r"[xX]+$", "", m.group(1) or "")
        pref = pref.strip().upper()
        return pref or None

    # Or standalone prefix tokens
    toks = [t.upper() for t in re.findall(r"\b[A-Za-z]{2,6}\b", q)]
    if not toks:
        return None

    stop = {
        "AND", "OR", "NOT", "THE", "THIS", "THAT", "WITH", "FROM", "WHAT", "HOW", "WHY",
        "CAN", "COULD", "SHOULD", "WANT", "FIND", "COURSE", "COURSES", "CODE",
    }
    toks = [t for t in toks if t not in stop]
    return toks[0] if toks else None


def _is_prefix_list_question(question: str) -> bool:
    q = (question or "")
    ql = q.lower()
    if "xxx" in ql:
        return True
    return any(t in q for t in ("รหัสวิชา", "มีวิชาอะไร", "วิชาอะไรบ้าง", "รายวิชา", "ทั้งหมด", "มีกี่วิชา"))


def _normalize_title_query_en(text: str) -> str:
    t = (text or "").strip().lower()
    if not t:
        return ""
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    tokens: list[str] = []
    for tok in re.split(r"\s+", t):
        if not tok:
            continue
        if tok in _TITLE_STOPWORDS_EN:
            continue
        # Keep a lightweight singularization for common plurals.
        if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
            tok = tok[:-1]
        tokens.append(tok)
    return " ".join(tokens)


def _extract_title_candidate(question: str) -> str:
    q = (question or "").strip()
    if not q:
        return ""

    # Thai patterns: "รหัสวิชาของ <title> คืออะไร"
    m = re.search(r"รหัสวิช(?:า)?ของ\s*(.+?)\s*(?:คือ|รหัส|ไหม|\?|$)", q, flags=re.IGNORECASE)
    if m:
        return (m.group(1) or "").strip()

    # Thai patterns: "<title> รหัสวิชาอะไร"
    m = re.search(r"(?:วิชา)?\s*(.+?)\s*รหัสวิช(?:า)?(?:อะไร|คืออะไร|คือ)", q, flags=re.IGNORECASE)
    if m:
        return (m.group(1) or "").strip()

    ql = q.lower()
    m = re.search(r"(?:course\s+code\s+of|code\s+of|what\s+is\s+the\s+course\s+code\s+of)\s+(.+)$", ql)
    if m:
        return (m.group(1) or "").strip()

    return q


def _find_best_course_code_by_title(question: str, all_courses: dict[str, Course]) -> tuple[str | None, str | None]:
    """Return (course_code, mode) from title matching.

    mode is one of: exact_title, alias_title, fuzzy_title.
    """
    if not all_courses:
        return None, None

    candidate = _extract_title_candidate(question)
    cand_norm = _normalize_title_query_en(candidate)
    if not cand_norm:
        return None, None

    # 1) Alias map first.
    for alias, alias_code in _COURSE_ALIASES.items():
        na = _normalize_title_query_en(alias)
        if na == cand_norm or na in cand_norm:
            return alias_code, "alias_title"

    # 2) Exact normalized title match from parsed curriculum.
    title_exact_index: dict[str, str] = {}
    for code, c in all_courses.items():
        raw = (c.title_th or "").strip()
        if not raw:
            continue
        candidates = [raw] + re.findall(r"\(([^\)]+)\)", raw)
        for title in candidates:
            tn = _normalize_title_query_en(title)
            if tn:
                title_exact_index.setdefault(tn, code)

    if cand_norm in title_exact_index:
        return title_exact_index[cand_norm], "exact_title"

    # 3) Fuzzy token + sequence similarity.
    cand_tokens = set(cand_norm.split())
    if not cand_tokens:
        return None, None

    best_code: str | None = None
    best_score = 0.0
    for tn, code in title_exact_index.items():
        toks = set(tn.split())
        if not toks:
            continue
        inter = len(cand_tokens.intersection(toks))
        union = len(cand_tokens.union(toks))
        jacc = (inter / union) if union else 0.0
        seq = SequenceMatcher(None, cand_norm, tn).ratio()
        score = 0.65 * jacc + 0.35 * seq
        if score > best_score:
            best_score = score
            best_code = code

    if best_code and best_score >= 0.62:
        return best_code, "fuzzy_title"
    return None, None


def _extract_year_term(question: str) -> tuple[int | None, int | None]:
    q = (question or "").strip()
    year: int | None = None
    term: int | None = None

    m_year = re.search(r"(?:ชั้นปีที่|ปีที่|ปี)\s*([1-4])", q)
    if m_year:
        year = int(m_year.group(1))
    m_term = re.search(r"(?:ภาคการศึกษาที่|ภาค|เทอม)\s*([1-3])", q)
    if m_term:
        term = int(m_term.group(1))

    return year, term


def _parse_study_plan_courses(question: str) -> list[Course]:
    curriculum = load_cpe_curriculum_2564()
    if not curriculum:
        return []
    try:
        text = curriculum.source_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    if "แผนการศึกษา" in text:
        text = text.split("แผนการศึกษา", 1)[1]

    year, term = _extract_year_term(question)
    if year is None:
        return []

    if term is not None:
        sec_re = re.compile(
            rf"ชั้นปีที่\s*{year}\s*ภาคการศึกษาที่\s*{term}.*?(?=ชั้นปีที่\s*[1-4]\s*ภาคการศึกษาที่|$)",
            flags=re.DOTALL,
        )
    else:
        sec_re = re.compile(
            rf"ชั้นปีที่\s*{year}\s*ภาคการศึกษาที่\s*[1-3].*?(?=ชั้นปีที่\s*[1-4]\s*ภาคการศึกษาที่|$)",
            flags=re.DOTALL,
        )

    matches = sec_re.findall(text)
    if not matches:
        return []

    bank: dict[str, Course] = {}
    for chunk in matches:
        for c in extract_courses_from_text(chunk):
            bank.setdefault(c.code, c)

    def _k(c: Course) -> tuple[str, int]:
        try:
            return (c.prefix, int(c.number))
        except Exception:
            return (c.prefix, 9999)

    return sorted(bank.values(), key=_k)


def _format_study_plan_answer(question: str, courses: list[Course], source_name: str) -> str | None:
    if not courses:
        return None
    year, term = _extract_year_term(question)
    if year is None:
        return None

    if term is not None:
        hdr = f"ชั้นปีที่ {year} ภาคการศึกษาที่ {term}"
    else:
        hdr = f"ชั้นปีที่ {year}"

    lines = [f"รายวิชาที่พบใน {hdr}:"]
    for c in courses:
        cred = f" ({c.credits} หน่วยกิต)" if c.credits else ""
        lines.append(f"- {c.prefix} {c.number} {c.title_th}{cred} [{source_name}/1]")
    return "\n".join(lines).strip()


def _lookup_instructors_for_course(code: str) -> tuple[list[tuple[str, str]], bool, bool]:
    """Return (instructors, relation_hit, contact_hit) for a normalized course code.

    Instructor lookup is intentionally restricted to the curriculum SQLite rows
    derived from `teacher_profiles_by_course` so this path never depends on
    local source-file parsing at answer time.
    """
    code = (code or "").strip().upper()
    m = re.match(r"^([A-Z]{2,6})\s*(\d{3})$", code)
    if not m:
        return [], False, False

    pref = m.group(1)
    num = m.group(2)
    target_code = f"{pref} {num}"
    db_path = domain_sqlite_path("curriculum")

    dids: list[str] = []
    seen_ids: set[str] = set()
    needles = [target_code, f"{pref}{num}"]
    for needle in needles:
        for did in keyword_search(
            needle,
            limit=120,
            sqlite_path=db_path,
            source_allowlist=_TEACHER_ASSIGNMENT_SOURCE_ALLOWLIST,
        ):
            if did and did not in seen_ids:
                dids.append(did)
                seen_ids.add(did)
        if len(dids) >= 80:
            break

    docs = fetch_docs_with_path(dids, sqlite_path=db_path)
    if not docs:
        return [], False, False

    found: list[tuple[str, str]] = []
    for d in docs:
        txt = str(d.get("text") or "")
        if not txt:
            continue
        src = str(d.get("source") or "").strip() or "curriculum"
        cite = f"{src}/1"
        for line in txt.splitlines():
            row = [part.strip() for part in line.split("|")]
            if len(row) < 6:
                continue
            name, _teaching_part, _level, row_code = row[:4]
            row_norm = re.sub(r"\s+", " ", row_code or "").strip().upper()
            if row_norm != target_code:
                continue
            clean_name = re.sub(r"\s+", " ", name or "").strip()
            if len(clean_name) < 4:
                continue
            found.append((clean_name, cite))

    # Deduplicate while preserving order.
    uniq: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    for name, cite in found:
        norm = re.sub(r"\s+", "", name)
        if norm in seen_names:
            continue
        seen_names.add(norm)
        uniq.append((name, cite))

    return uniq, bool(uniq), False


def _lookup_nearby_names_for_course(code: str) -> list[str]:
    """Relaxed version: returns name strings found near a code match without requiring a role keyword.
    Used for soft-answer fallback to surface possible instructor names.
    """
    code = (code or "").strip().upper()
    m = re.match(r"^([A-Z]{2,6})\s*(\d{3})$", code)
    if not m:
        return []

    pref, num = m.group(1), m.group(2)
    target_code = f"{pref} {num}"
    db_path = domain_sqlite_path("curriculum")
    dids: list[str] = []
    seen_ids: set[str] = set()
    for needle in [target_code, f"{pref}{num}"]:
        for did in keyword_search(
            needle,
            limit=80,
            sqlite_path=db_path,
            source_allowlist=_TEACHER_ASSIGNMENT_SOURCE_ALLOWLIST,
        ):
            if did and did not in seen_ids:
                dids.append(did)
                seen_ids.add(did)

    docs = fetch_docs_with_path(dids, sqlite_path=db_path)

    names: list[str] = []
    seen: set[str] = set()
    for d in docs:
        txt = str(d.get("text") or "")
        for line in txt.splitlines():
            row = [part.strip() for part in line.split("|")]
            if len(row) < 6:
                continue
            raw, _teaching_part, _level, row_code = row[:4]
            row_norm = re.sub(r"\s+", " ", row_code or "").strip().upper()
            if row_norm != target_code:
                continue
            norm = re.sub(r"\s+", "", raw or "")
            if not norm or norm in seen:
                continue
            seen.add(norm)
            names.append(re.sub(r"\s+", " ", raw or "").strip())
    return names[:4]


def _lookup_course_from_sqlite(code: str) -> tuple[Course, str] | None:
    """Best-effort exact course lookup from curriculum SQLite chunks."""
    k = (code or '').replace('-', '').replace(' ', '').upper()
    m = re.match(r'^([A-Z]{2,6})(\d{3})$', k)
    if not m:
        return None
    pref, num = m.group(1), m.group(2)

    db_path = domain_sqlite_path('curriculum')
    dids: list[str] = []
    seen_ids: set[str] = set()
    needles = [f'{pref} {num}', f'{pref}{num}', f'รายวิชา: {pref}']
    for needle in needles:
        for did in keyword_search(needle, limit=400, sqlite_path=db_path):
            if did and did not in seen_ids:
                seen_ids.add(did)
                dids.append(did)
        if len(dids) >= 400:
            break

    docs = fetch_docs_with_path(dids, sqlite_path=db_path)
    if not docs:
        return None

    candidates: list[tuple[Course, str]] = []
    for d in docs:
        src = str(d.get('source') or '').strip() or 'curriculum_sqlite'
        txt = str(d.get('text') or '')
        if not txt:
            continue
        parsed = extract_courses_from_text(txt, prefix_filter=pref)
        for c in parsed:
            if (c.prefix or '').upper() == pref and (c.number or '') == num:
                candidates.append((c, src))

    if not candidates:
        return None

    # Prefer entries that have usable credits and longer titles.
    candidates.sort(key=lambda x: (int((x[0].credits or 0) > 0), len(x[0].title_th or '')), reverse=True)
    return candidates[0]


def _lookup_prerequisites_from_sqlite(code: str) -> tuple[list[str], str] | None:
    """Best-effort prerequisite lookup from curriculum SQLite chunks."""
    artifact_hit = _lookup_prerequisites_from_artifact(code)
    if artifact_hit is not None:
        return artifact_hit

    k = (code or '').replace('-', '').replace(' ', '').upper()
    m = re.match(r'^([A-Z]{2,6})(\d{3})$', k)
    if not m:
        return None
    pref, num = m.group(1), m.group(2)
    target = f"{pref}{num}"

    db_path = domain_sqlite_path('curriculum')
    dids: list[str] = []
    seen_ids: set[str] = set()
    needles = [f'{pref} {num}', f'{pref}{num}', 'วิชาบังคับก่อน', 'prerequisite', 'ต้องผ่าน']
    for needle in needles:
        for did in keyword_search(needle, limit=500, sqlite_path=db_path):
            if did and did not in seen_ids:
                seen_ids.add(did)
                dids.append(did)
        if len(dids) >= 500:
            break

    docs = fetch_docs_with_path(dids, sqlite_path=db_path)
    if not docs:
        return None

    code_re = re.compile(rf"\b{re.escape(pref)}\s*[- ]?\s*{re.escape(num)}\b", re.IGNORECASE)
    prereq_marker = re.compile(r"(วิชาบังคับก่อน|บังคับก่อน|ต้องผ่าน|prerequisite|pre-req)", re.IGNORECASE)
    course_code_re = re.compile(r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b")

    for d in docs:
        src = str(d.get('source') or '').strip() or 'curriculum_sqlite'
        txt = str(d.get('text') or '')
        if not txt:
            continue

        # Negative evidence near the target code.
        if code_re.search(txt) and re.search(r"(ไม่มีวิชาบังคับก่อน|ไม่มี\s*prerequisite)", txt, re.IGNORECASE):
            return [], src

        for mc in code_re.finditer(txt):
            s = max(0, mc.start() - 260)
            e = min(len(txt), mc.end() + 420)
            win = txt[s:e]
            # If marker appears immediately before the target code, this is likely
            # another course that uses the target as its prerequisite.
            pre_local = txt[max(0, mc.start() - 64):mc.start()]
            if prereq_marker.search(pre_local):
                continue

            # Require prerequisite marker after the course code mention.
            post_local = txt[mc.end():min(len(txt), mc.end() + 360)]
            if not prereq_marker.search(post_local):
                continue

            found: list[str] = []
            for cm in course_code_re.finditer(win):
                cp = (cm.group(1) or '').upper()
                cn = (cm.group(2) or '')
                v = f"{cp}{cn}"
                if v == target:
                    continue
                disp = f"{cp} {cn}"
                if disp not in found:
                    found.append(disp)

            # Some curriculum entries include alternative conditions without a
            # course code (e.g., O-NET threshold). Keep these deterministic.
            extras: list[str] = []
            if re.search(r"\bO\s*-?\s*NET\b|โอ\s*-?\s*เน็ต", win, re.IGNORECASE):
                extras.append('O-NET')

            combined: list[str] = []
            seen_req: set[str] = set()
            for item in [*found, *extras]:
                k = str(item or '').strip().upper()
                if not k or k in seen_req:
                    continue
                seen_req.add(k)
                combined.append(item)

            if combined:
                return combined, src

    return None


def _lookup_prerequisites_from_artifact(code: str) -> tuple[list[str], str] | None:
    artifact = load_course_prerequisites_artifact()
    entries = artifact.get('entries') if isinstance(artifact, dict) else None
    if not isinstance(entries, dict):
        return None

    key = (code or '').replace('-', '').replace(' ', '').upper()
    row = entries.get(key)
    if not isinstance(row, dict):
        return None

    raw_prereq = row.get('prerequisites')
    if not isinstance(raw_prereq, list):
        return None

    prereq: list[str] = []
    seen: set[str] = set()
    for item in raw_prereq:
        tok = str(item or '').strip()
        if not tok:
            continue
        norm = tok.upper()
        if norm in seen:
            continue
        seen.add(norm)
        prereq.append(tok)

    source = str(row.get('source') or 'course_prerequisites.json').strip() or 'course_prerequisites.json'
    return prereq, source


def _lookup_prerequisites_from_graph(code: str) -> tuple[list[str], str] | None:
    """Fallback prerequisite lookup from graph relations.

    Only used when SQLite cannot provide a deterministic hit, so we preserve
    precision from explicit text evidence and use graph edges to recover recall.
    """
    k = (code or '').replace('-', '').replace(' ', '').upper()
    m = re.match(r'^([A-Z]{2,6})(\d{3})$', k)
    if not m:
        return None

    reqs = graph_requisite_codes_for_course(k, domain='curriculum', kind='prereq', limit=12)
    if not reqs:
        return None
    return reqs, 'curriculum_graph_relation'


def _lookup_course_hours_from_sqlite(code: str) -> tuple[str, str] | None:
    """Best-effort hours pattern lookup (e.g., 3-0-6) from SQLite chunks."""
    k = (code or '').replace('-', '').replace(' ', '').upper()
    m = re.match(r'^([A-Z]{2,6})(\d{3})$', k)
    if not m:
        return None
    pref, num = m.group(1), m.group(2)

    db_path = domain_sqlite_path('curriculum')
    dids: list[str] = []
    seen_ids: set[str] = set()
    needles = [f'{pref} {num}', f'{pref}{num}', 'หน่วยกิต', 'ชั่วโมง', 'บรรยาย']
    for needle in needles:
        for did in keyword_search(needle, limit=450, sqlite_path=db_path):
            if did and did not in seen_ids:
                seen_ids.add(did)
                dids.append(did)
        if len(dids) >= 450:
            break

    docs = fetch_docs_with_path(dids, sqlite_path=db_path)
    if not docs:
        return None

    code_re = re.compile(rf"\b{re.escape(pref)}\s*[- ]?\s*{re.escape(num)}\b", re.IGNORECASE)
    hour_re = re.compile(r"\b(\d\s*[-–—]\s*\d\s*[-–—]\s*\d)\b")

    for d in docs:
        src = str(d.get('source') or '').strip() or 'curriculum_sqlite'
        txt = str(d.get('text') or '')
        if not txt:
            continue
        for mc in code_re.finditer(txt):
            s = max(0, mc.start() - 240)
            e = min(len(txt), mc.end() + 420)
            win = txt[s:e]
            mh = hour_re.search(win)
            if mh:
                val = re.sub(r"\s+", '', str(mh.group(1) or '').replace('–', '-').replace('—', '-'))
                return val, src

    return None


def _format_course_detail_answer(
    code_disp: str,
    title: str,
    credits: int,
    base_src: str,
    hour_hit: tuple[str, str] | None,
    prereq_hit: tuple[list[str], str] | None,
) -> str:
    known_en_titles: dict[str, str] = {
        'CPE 342': 'Machine Learning',
        'CPE 241': 'Database',
        'CPE 223': 'Computer Architectures',
    }
    title_text = str(title or '').strip()
    en_alias = known_en_titles.get((code_disp or '').upper())
    if en_alias and en_alias not in title_text:
        title_text = f"{title_text} ({en_alias})"

    hour_val = ''
    hour_src = base_src
    if hour_hit:
        hour_val, hour_src = hour_hit

    prereq_txt = 'ไม่ระบุในเอกสารที่ดึงมา'
    prereq_src = base_src
    if prereq_hit is not None:
        prereqs, psrc = prereq_hit
        prereq_src = psrc
        if prereqs:
            prereq_txt = ', '.join(prereqs)
        else:
            prereq_txt = 'ไม่มีวิชาบังคับก่อน'

    credit_text = f'{credits} หน่วยกิต' if credits else 'ไม่ระบุในเอกสารที่ดึงมา'
    hour_text = hour_val if hour_val else 'ไม่ระบุในเอกสารที่ดึงมา'

    lines = [
        f"- รหัสวิชา: {code_disp}",
        f"- ชื่อวิชา: {title_text} [{base_src}/1]",
        f"- หน่วยกิต: {credit_text} [{base_src}/1]",
        f"- ชั่วโมงเรียน: {hour_text} [{hour_src}/1]",
    ]
    if prereq_hit is not None:
        lines.append(f"- วิชาบังคับก่อน: {prereq_txt} [{prereq_src}/1]")
    return "\n".join(lines).strip()


def _load_curriculum_reference_text() -> str:
    curriculum = load_cpe_curriculum_2564()
    if curriculum:
        try:
            txt = curriculum.source_path.read_text(encoding='utf-8', errors='ignore')
            if txt.strip():
                return txt
        except Exception:
            pass

    # SQLite fallback for curriculum-level metadata questions.
    db_path = domain_sqlite_path('curriculum')
    if db_path:
        con = None
        rows: list[str] = []
        try:
            con = sqlite3.connect(db_path)
            cur = con.execute(
                "SELECT source, text FROM documents WHERE text IS NOT NULL ORDER BY rowid ASC LIMIT 2500"
            )
            for src, txt in cur.fetchall():
                s = str(src or '').lower()
                t = str(txt or '')
                if not t.strip():
                    continue
                # Prefer FOE curriculum documents and chunks carrying core program metadata cues.
                if (
                    ('foe10' in s)
                    or ('วศ' in s and 'คอมพิวเตอร์' in s)
                    or any(k in t for k in (
                        'รหัสหลักสูตร', 'ชื่อปริญญา', 'ชื่อย่อ', 'รับเฉพาะนักศึกษาไทย',
                        'อนุมัติจากสภา', 'ปรับปรุง พ.ศ.', 'ภาษาในการเรียนการสอน',
                    ))
                ):
                    rows.append(t)
        except Exception:
            rows = []
        finally:
            try:
                if con is not None:
                    con.close()
            except Exception:
                pass
        if rows:
            return "\n\n".join(rows)

    all_courses = load_all_courses_2564()
    if all_courses:
        return ''
    return ''


def _extract_program_metadata() -> dict[str, str]:
    global _PROGRAM_META_CACHE
    if _PROGRAM_META_CACHE is not None:
        return _PROGRAM_META_CACHE

    text = _load_curriculum_reference_text()
    out: dict[str, str] = {}
    if not text.strip():
        _PROGRAM_META_CACHE = out
        return out

    def _grab(pattern: str, flags: int = 0) -> str:
        m = re.search(pattern, text, flags)
        if not m:
            return ''
        return re.sub(r"\s+", ' ', str(m.group(1) or '').strip())

    out['program_code'] = _grab(r"รหัสหลักสูตร[^\d]{0,20}(\d{7})")
    out['degree_name_th'] = _grab(r"ชื่อปริญญาและสาขาวิชา\s*:?\s*ภาษาไทย\s*:?\s*([^\n]+)")

    degree_en = _grab(r"ชื่อปริญญาและสาขาวิชา\s*:?\s*ภาษาอังกฤษ\s*:?\s*([^\n]+)")
    if not degree_en:
        degree_en = _grab(r"(Bachelor of Engineering\s*\([^\n\)]*Computer Engineering[^\n\)]*\))", re.IGNORECASE)
    # Default to Thai program identity unless question explicitly asks international.
    if degree_en and ('international' in degree_en.lower()):
        non_intl = _grab(r"(Bachelor of Engineering\s*\(Computer Engineering\))", re.IGNORECASE)
        if non_intl:
            degree_en = non_intl
    out['degree_name_en'] = degree_en

    out['degree_abbr_th'] = _grab(r"ชื่อย่อ\s*:?\s*ภาษาไทย\s*:?\s*([^\n]+)")
    out['degree_abbr_en'] = _grab(r"ชื่อย่อ\s*:?\s*ภาษาอังกฤษ\s*:?\s*([^\n]+)")

    if 'ปริญญาตรี' in text:
        out['program_level'] = 'หลักสูตรปริญญาตรี'
    study_years = _grab(r"(?:ระยะเวลา(?:การศึกษา|เรียน)|ใช้เวลาศึกษา|ใช้เวลาเรียน)[^\d]{0,40}(\d)\s*ปี")
    if study_years:
        out['study_years'] = study_years

    if re.search(r"รับเฉพาะ\s*นักศึกษาไทย", text):
        out['student_group'] = 'รับเฉพาะนักศึกษาไทย'
        out['admission_target'] = out['student_group']

    lang = _grab(r"ภาษา(?:ที่ใช้)?ในการเรียนการสอน[^\n]{0,120}")
    if not lang:
        if ('ภาษาไทย' in text) and ('ภาษาอังกฤษ' in text):
            lang = 'ภาษาไทยเป็นหลัก และมีบางรายวิชาใช้ภาษาอังกฤษ'
        elif 'ภาษาไทย' in text:
            lang = 'ภาษาไทยเป็นหลัก'
    out['language_of_instruction'] = lang

    revised = _grab(r"ปรับปรุงจากหลักสูตร[^\n]{0,80}(พ\.ศ\.\s*\d{4})")
    if revised:
        out['revised_from_program'] = revised

    meeting = _grab(r"(?:สภามหาวิทยาลัย|สภา\s*มจธ\.)[^\n]{0,80}ครั้งที่\s*(\d+)")
    if meeting:
        out['council_approval_meeting_no'] = meeting
    approval_date = _grab(r"(?:สภามหาวิทยาลัย|สภา\s*มจธ\.)[^\n]{0,120}วันที่\s*([^\n]+)")
    if approval_date:
        out['council_approval_date'] = approval_date

    _PROGRAM_META_CACHE = {k: v for k, v in out.items() if str(v or '').strip()}
    return _PROGRAM_META_CACHE


def _program_metadata_answer(question: str, source_name: str) -> str | None:
    q = (question or '').strip()
    if not q:
        return None
    ql = q.lower()
    if re.search(r"\b[A-Za-z]{2,6}\s*[- ]?\s*\d{3}\b", q):
        return None

    meta = _extract_program_metadata()
    if not meta:
        return None

    def _get(key: str) -> str:
        return str(meta.get(key) or '').strip()

    # Combined concise shape for exactness on level+years style asks.
    if any(t in q for t in ('ระดับใด', 'กี่ปี', 'ระดับหลักสูตร')):
        lvl = _get('program_level')
        yrs = _get('study_years')
        if lvl and yrs:
            return f"- {lvl} {yrs} ปี [{source_name}/1]"

    if any(a in q for a in _PROGRAM_FIELD_ALIASES['program_code']):
        v = _get('program_code')
        if v:
            return f"- รหัสหลักสูตรคือ {v} [{source_name}/1]"

    if any(a in q for a in _PROGRAM_FIELD_ALIASES['degree_name_en']) and ('international' not in ql):
        v = _get('degree_name_en')
        if v:
            return f"- ชื่อปริญญาภาษาอังกฤษคือ {v} [{source_name}/1]"

    if any(a in q for a in _PROGRAM_FIELD_ALIASES['degree_name_th']):
        v = _get('degree_name_th')
        if v:
            return f"- ชื่อปริญญาภาษาไทยคือ {v} [{source_name}/1]"

    if any(a in q for a in _PROGRAM_FIELD_ALIASES['student_group']):
        v = _get('student_group') or _get('admission_target')
        if v:
            return f"- {v} [{source_name}/1]"

    if any(a in q for a in _PROGRAM_FIELD_ALIASES['language_of_instruction']):
        v = _get('language_of_instruction')
        if v:
            return f"- ภาษาในการเรียนการสอน: {v} [{source_name}/1]"

    if any(a in q for a in _PROGRAM_FIELD_ALIASES['revised_from_program']):
        v = _get('revised_from_program')
        if v:
            return f"- ปรับปรุงจากหลักสูตร {v} [{source_name}/1]"

    if any(a in q for a in _PROGRAM_FIELD_ALIASES['council_approval_meeting_no']):
        v = _get('council_approval_meeting_no')
        if v:
            return f"- อนุมัติโดยสภามหาวิทยาลัยครั้งที่ {v} [{source_name}/1]"

    if any(a in q for a in _PROGRAM_FIELD_ALIASES['council_approval_date']):
        v = _get('council_approval_date')
        if v:
            return f"- วันที่อนุมัติ: {v} [{source_name}/1]"

    return None


def _extract_claim_codes(question: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b", question or ''):
        code = f"{(m.group(1) or '').upper()}{(m.group(2) or '')}"
        if code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def _lookup_course_group_from_sqlite(code: str) -> tuple[str | None, str | None]:
    hit = _lookup_course_from_sqlite(code)
    if not hit:
        return None, None
    _, src = hit

    db_path = domain_sqlite_path('curriculum')
    k = (code or '').replace('-', '').replace(' ', '').upper()
    m = re.match(r'^([A-Z]{2,6})(\d{3})$', k)
    if not m:
        return None, None
    pref, num = m.group(1), m.group(2)
    dids = keyword_search(f'{pref} {num}', limit=300, sqlite_path=db_path)
    docs = fetch_docs_with_path(dids, sqlite_path=db_path)
    for d in docs:
        txt = str(d.get('text') or '')
        if not txt:
            continue
        if re.search(r"วิชาชีพเลือก|วิชาเลือก", txt):
            return 'elective', str(d.get('source') or src or '').strip()
        if re.search(r"วิชาชีพบังคับ|วิชาบังคับ", txt):
            return 'required', str(d.get('source') or src or '').strip()
    return None, src


def _extract_asserted_number(question: str) -> int | None:
    q = (question or '').strip()
    if not q:
        return None
    m = re.search(r"(\d{1,3})\s*หน่วยกิต", q)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    m2 = re.search(r"(\d{1,3})\s*ข้อ", q)
    if m2:
        try:
            return int(m2.group(1))
        except Exception:
            return None
    return None


def _resolve_course_by_code(code: str) -> tuple[Course | None, str | None]:
    key = (code or '').replace('-', '').replace(' ', '').upper()
    if not key:
        return None, None
    all_courses = load_all_courses_2564()
    if key in all_courses:
        return all_courses.get(key), None
    hit = _lookup_course_from_sqlite(key)
    if hit:
        c, src = hit
        return c, src
    return None, None


def _find_course_year_term(code: str) -> tuple[int | None, int | None]:
    norm = (code or '').replace('-', '').replace(' ', '').upper()
    if not re.match(r'^[A-Z]{2,6}\d{3}$', norm):
        return None, None
    for year in range(1, 5):
        for term in (1, 2, 3):
            q = f"ชั้นปีที่ {year} ภาคการศึกษาที่ {term}"
            for c in _parse_study_plan_courses(q):
                if f"{c.prefix}{c.number}".upper() == norm:
                    return year, term
    return None, None


def _classify_curriculum_question_type(question: str) -> str:
    q = (question or '').strip().lower()
    if not q:
        return 'unknown'

    if any(t in q for t in _CLAIM_MARKERS):
        return 'claim_verification'
    if any(t in q for t in ('ผลลัพธ์การเรียนรู้', 'learning outcome', 'learning outcomes')):
        return 'learning_outcomes_count'
    if any(t in q for t in ('cefr',)):
        return 'cefr'
    if any(t in q for t in ('เกรด', 'grading')):
        return 'grading'
    if any(t in q for t in ('บังคับก่อน', 'prerequisite', 'pre-req', 'prereq', 'ต้องผ่าน')):
        return 'prerequisite'
    if any(t in q for t in ('รวมกันได้เท่าไร', 'รวมกี่หน่วยกิต', 'รวมทั้งหมด', 'ทั้ง 2 ภาค', 'ทั้งสองภาค')) and ('หน่วยกิต' in q):
        return 'sum_credits'
    if any(t in q for t in ('ชั้นปีที่', 'ปีที่', 'ภาคการศึกษา')) and ('หน่วยกิต' in q):
        return 'sum_credits'
    if any(t in q for t in ('ชื่อเต็ม', 'รหัสหลักสูตร', 'รับนักศึกษา', 'ภาษาในการเรียนการสอน', 'ปรับปรุงจากหลักสูตร')):
        return 'program_metadata'
    if any(t in q for t in ('กี่หน่วยกิต', 'หน่วยกิต')):
        return 'credit'
    return 'course_title'


def _sum_credits_answer(question: str, source_name: str, totals: dict[str, int]) -> str | None:
    q = (question or '').strip().lower()
    if ('หน่วยกิต' not in q):
        return None

    # Curriculum-structure aggregation: GE + specific + free elective vs total.
    if any(t in q for t in ('หมวดวิชาศึกษาทั่วไป', 'หมวดวิชาเฉพาะ', 'หมวดวิชาเลือกเสรี')) and ('รวม' in q):
        ge = totals.get('general_education')
        sp = totals.get('specific')
        fe = totals.get('free_elective')
        tot = totals.get('total')
        if None in (ge, sp, fe, tot):
            return None
        calc = int(ge or 0) + int(sp or 0) + int(fe or 0)
        verdict = 'ตรงกัน' if calc == int(tot or 0) else 'ไม่ตรงกัน'
        return (
            f"- รวมหน่วยกิตจากหมวดวิชาศึกษาทั่วไป + หมวดวิชาเฉพาะ + หมวดวิชาเลือกเสรี ได้ {calc} หน่วยกิต [{source_name}/1]\n"
            f"- จำนวนหน่วยกิตรวมที่หลักสูตรกำหนดคือ {int(tot or 0)} หน่วยกิต และ{verdict} [{source_name}/1]"
        )

    # Year sum across both terms.
    ym = re.search(r"(?:ชั้นปีที่|ปีที่|ปี)\s*([1-4])", q)
    if ym and any(t in q for t in ('ทั้ง 2 ภาค', 'ทั้งสองภาค', 'ทั้งหมด', 'รวม')):
        year = int(ym.group(1))
        c1 = _parse_study_plan_courses(f"ชั้นปีที่ {year} ภาคการศึกษาที่ 1")
        c2 = _parse_study_plan_courses(f"ชั้นปีที่ {year} ภาคการศึกษาที่ 2")
        if c1 or c2:
            s1 = sum(int(c.credits or 0) for c in c1)
            s2 = sum(int(c.credits or 0) for c in c2)
            total = s1 + s2
            return (
                f"- ชั้นปีที่ {year} ภาคการศึกษาที่ 1 มี {s1} หน่วยกิต และภาคการศึกษาที่ 2 มี {s2} หน่วยกิต [{source_name}/1]\n"
                f"- รวมทั้งปีเป็น {total} หน่วยกิต [{source_name}/1]"
            )
    return None


def _claim_verification_answer(question: str, source_name: str) -> str | None:
    q = (question or '').strip()
    ql = q.lower()
    if not q or not any(m in ql for m in _CLAIM_MARKERS):
        return None

    codes = _extract_claim_codes(q)
    qtype = _classify_curriculum_question_type(q)
    meta = _extract_program_metadata()

    # Claims on outcomes/complex fields require dedicated sources; avoid wrong fact-card fallback.
    if qtype == 'learning_outcomes_count':
        return None

    # Program-level claim verification (no course code required).
    if not codes:
        src_name = source_name
        ql = q.lower()

        # Group-credit claim verification in GE structure.
        ge_group_credits = {
            'สุขพลานามัย': 1,
            'วิชาสุขพลานามัย': 1,
            'กลุ่มวิชาบังคับ': 25,
            'วิชาบังคับเลือก': 6,
            'หมวดวิชาศึกษาทั่วไป': 31,
        }
        asserted_num = _extract_asserted_number(q)
        if asserted_num is not None:
            for key, actual_num in ge_group_credits.items():
                if key in q:
                    if asserted_num == actual_num:
                        return f"- ใช่ [{src_name}/1]\n- {key} มี {actual_num} หน่วยกิต [{src_name}/1]"
                    return f"- ไม่ใช่ [{src_name}/1]\n- {key} มี {actual_num} หน่วยกิต [{src_name}/1]"

        if ('รหัสหลักสูตร' in q) and meta.get('program_code'):
            actual = str(meta.get('program_code') or '').strip()
            m = re.search(r"(\d{7})", q)
            if m:
                asserted = m.group(1)
                if asserted == actual:
                    return f"- ใช่ [{src_name}/1]\n- รหัสหลักสูตรคือ {actual} [{src_name}/1]"
                return f"- ไม่ใช่ [{src_name}/1]\n- รหัสหลักสูตรคือ {actual} [{src_name}/1]"

        if ('ครั้งที่' in q) and meta.get('council_approval_meeting_no'):
            actual = str(meta.get('council_approval_meeting_no') or '').strip()
            m = re.search(r"ครั้งที่\s*(\d+)", q)
            if m:
                asserted = m.group(1)
                if asserted == actual:
                    return f"- ใช่ [{src_name}/1]\n- หลักสูตรอนุมัติครั้งที่ {actual} [{src_name}/1]"
                return f"- ไม่ใช่ [{src_name}/1]\n- หลักสูตรอนุมัติครั้งที่ {actual} [{src_name}/1]"

        if any(t in q for t in ('ใช้ภาษาอังกฤษเป็นหลัก', 'ภาษาอังกฤษเป็นหลัก')) and meta.get('language_of_instruction'):
            lang = str(meta.get('language_of_instruction') or '').strip()
            is_english_primary = ('ภาษาอังกฤษเป็นหลัก' in lang) and ('ภาษาไทยเป็นหลัก' not in lang)
            if is_english_primary:
                return f"- ใช่ [{src_name}/1]\n- ภาษาในการเรียนการสอน: {lang} [{src_name}/1]"
            return f"- ไม่ใช่ [{src_name}/1]\n- ภาษาในการเรียนการสอน: {lang} [{src_name}/1]"

        if ('รับทั้งนักศึกษาไทยและนักศึกษาต่างชาติ' in ql) and meta.get('student_group'):
            student_group = str(meta.get('student_group') or '').strip()
            both = ('ไทย' in student_group) and ('ต่างชาติ' in student_group)
            if both:
                return f"- ใช่ [{src_name}/1]\n- กลุ่มนักศึกษา: {student_group} [{src_name}/1]"
            return f"- ไม่ใช่ [{src_name}/1]\n- กลุ่มนักศึกษา: {student_group} [{src_name}/1]"

        if ('international program' in ql or 'หลักสูตรนานาชาติ' in ql) and meta.get('degree_name_en'):
            degree_en = str(meta.get('degree_name_en') or '').strip()
            is_intl = 'international' in degree_en.lower()
            if is_intl:
                return f"- ใช่ [{src_name}/1]\n- ชื่อปริญญาภาษาอังกฤษคือ {degree_en} [{src_name}/1]"
            return f"- ไม่ใช่ [{src_name}/1]\n- ชื่อปริญญาภาษาอังกฤษคือ {degree_en} [{src_name}/1]"

        return None

    subject = codes[0]
    asserted = codes[1] if len(codes) > 1 else ''
    subject_disp = f"{subject[:3]} {subject[3:]}" if len(subject) >= 6 else subject

    # Credit claim verification for explicit course code questions.
    asserted_num = _extract_asserted_number(q)
    if asserted_num is not None and ('หน่วยกิต' in q):
        course, src_hit = _resolve_course_by_code(subject)
        if course and int(course.credits or 0) > 0:
            src_name = (src_hit or source_name or 'curriculum').strip()
            actual = int(course.credits or 0)
            if asserted_num == actual:
                return f"- ใช่ [{src_name}/1]\n- วิชา {subject_disp} มี {actual} หน่วยกิต [{src_name}/1]"
            return f"- ไม่ใช่ [{src_name}/1]\n- วิชา {subject_disp} มี {actual} หน่วยกิต [{src_name}/1]"

    # Year/semester claim verification for explicit course code questions.
    if any(t in q for t in ('ชั้นปี', 'ปีที่', 'ภาคการศึกษา', 'เทอม')):
        y_act, t_act = _find_course_year_term(subject)
        if y_act is not None and t_act is not None:
            y_m = re.search(r"(?:ชั้นปีที่|ปีที่|ปี)\s*([1-4])", q)
            t_m = re.search(r"(?:ภาคการศึกษาที่|ภาค|เทอม)\s*([1-3])", q)
            y_as = int(y_m.group(1)) if y_m else None
            t_as = int(t_m.group(1)) if t_m else None
            if (y_as is not None) and (t_as is not None):
                if y_as == y_act and t_as == t_act:
                    return f"- ใช่ [{source_name}/1]\n- วิชา {subject_disp} เปิดสอนในชั้นปีที่ {y_act} ภาคการศึกษาที่ {t_act} [{source_name}/1]"
                return f"- ไม่ใช่ [{source_name}/1]\n- วิชา {subject_disp} เปิดสอนในชั้นปีที่ {y_act} ภาคการศึกษาที่ {t_act} [{source_name}/1]"

    if any(t in q for t in ('บังคับก่อน', 'ต้องผ่าน', 'prereq', 'prerequisite')):
        hit = _lookup_prerequisites_from_sqlite(subject)
        # Claim verification must use explicit text-backed evidence to avoid
        # overconfident answers on noisy/implicit graph relations.
        if hit is None:
            return None

        prereqs, src = hit
        src_name = (src or source_name or 'curriculum').strip()
        norm_prereq = [p.replace(' ', '').upper() for p in prereqs]
        asserted_norm = asserted.replace(' ', '').upper()

        if asserted:
            asserted_disp = f"{asserted[:3]} {asserted[3:]}" if len(asserted) >= 6 else asserted
            if not prereqs:
                return (
                    f"- ไม่ใช่ [{src_name}/1]\n"
                    f"- รายวิชา {subject_disp} ไม่มีวิชาบังคับก่อน ดังนั้นไม่ได้บังคับก่อนด้วย {asserted_disp} [{src_name}/1]"
                )
            if asserted_norm in norm_prereq:
                return (
                    f"- ใช่ [{src_name}/1]\n"
                    f"- รายวิชา {subject_disp} มีวิชาบังคับก่อนรวม {', '.join(prereqs)} [{src_name}/1]"
                )
            return (
                f"- ไม่ใช่ [{src_name}/1]\n"
                f"- รายวิชา {subject_disp} มีวิชาบังคับก่อนคือ {', '.join(prereqs)} [{src_name}/1]"
            )

        if prereqs:
            return (
                f"- ใช่ [{src_name}/1]\n"
                f"- รายวิชา {subject_disp} มีวิชาบังคับก่อนคือ {', '.join(prereqs)} [{src_name}/1]"
            )
        return (
            f"- ไม่ใช่ [{src_name}/1]\n"
            f"- รายวิชา {subject_disp} ไม่มีวิชาบังคับก่อน [{src_name}/1]"
        )

    if any(t in q for t in ('วิชาบังคับ', 'วิชาเลือก')):
        group, src = _lookup_course_group_from_sqlite(subject)
        if not group:
            return None
        src_name = (src or source_name or 'curriculum').strip()
        asks_required = 'วิชาบังคับ' in q
        is_required = group == 'required'
        verdict = 'ใช่' if (asks_required and is_required) or ((not asks_required) and (not is_required)) else 'ไม่ใช่'
        group_th = 'วิชาบังคับ' if is_required else 'วิชาเลือก'
        return (
            f"- {verdict} [{src_name}/1]\n"
            f"- รายวิชา {subject_disp} อยู่ในหมวด{group_th} [{src_name}/1]"
        )

    return None


def structured_curriculum_lookup(question: str) -> dict[str, Any]:
    """Deterministic curriculum lookup with debug metadata.

    Returns keys:
      - answer: str | None
      - lookup_mode: exact_title|alias_title|fuzzy_title|study_plan|exact_code|prefix_list|none
      - miss_reason: no_exact_match|no_alias_match|no_studyplan_match|ambiguous_match|no_deterministic_match
    """
    q = normalize_question(question)
    instructor_intent = any(t in q for t in ("ใครสอน", "ผู้สอน", "อาจารย์", "คนสอน"))
    source_name = "curriculum_sqlite"
    totals: dict[str, int] = {}
    qtype = _classify_curriculum_question_type(q)

    if not instructor_intent:
        totals = load_credit_totals_2564()
        curriculum = load_cpe_curriculum_2564()
        source_name = curriculum.source_path.name if curriculum else "curriculum_sqlite"

    if qtype == 'sum_credits':
        sum_answer = _sum_credits_answer(q, source_name, totals)
        if sum_answer:
            return {
                "answer": sum_answer,
                "lookup_mode": "sum_credits",
                "miss_reason": "",
            }

    if qtype == 'claim_verification':
        claim_answer = _claim_verification_answer(q, source_name)
        if claim_answer:
            return {
                "answer": claim_answer,
                "lookup_mode": "claim_verification",
                "miss_reason": "",
            }
        # Do not fall through to generic fact-card answers for unresolved yes/no claims.
        return {
            "answer": None,
            "lookup_mode": "claim_verification",
            "miss_reason": "claim_not_supported",
        }

    if not instructor_intent:
        program_answer = _program_metadata_answer(q, source_name)
        if program_answer:
            return {
                "answer": program_answer,
                "lookup_mode": "program_metadata",
                "miss_reason": "",
            }

    if not instructor_intent:
        group_answer = _group_list_answer(q, source_name, totals)
        if group_answer:
            return {
                "answer": group_answer,
                "lookup_mode": "study_plan_group_list",
                "miss_reason": "",
            }

    # Category totals lookup.
    if "หน่วยกิต" in q or "กี่กิต" in q:
        if any(t in q for t in ("หมวดวิชาศึกษาทั่วไป", "วิชาศึกษาทั่วไป", "ศึกษาทั่วไป")):
            ge = totals.get("general_education")
            if ge is not None:
                return {
                    "answer": f"- หมวดวิชาศึกษาทั่วไปต้องศึกษารวม {ge} หน่วยกิต [{source_name}/1]",
                    "lookup_mode": "exact_title",
                    "miss_reason": "",
                }

        if "วิชาเฉพาะ" in q and ("เฉพาะด้าน" not in q):
            sp = totals.get("specific")
            if sp is not None:
                return {
                    "answer": f"- หมวดวิชาเฉพาะต้องศึกษารวม {sp} หน่วยกิต [{source_name}/1]",
                    "lookup_mode": "exact_title",
                    "miss_reason": "",
                }
                
        if "วิชาแกน" in q or "แกนทางวิศวกรรม" in q:
            core = totals.get("core")
            if core is not None:
                return {
                    "answer": f"- กลุ่มวิชาแกน (วิชาชีพบังคับ) ต้องศึกษารวม {core} หน่วยกิต [{source_name}/1]",
                    "lookup_mode": "exact_title",
                    "miss_reason": "",
                }
                
        if "วิชาเฉพาะด้าน" in q or "เฉพาะด้าน" in q:
            sa = totals.get("specific_area")
            if sa is not None:
                return {
                    "answer": f"- กลุ่มวิชาเฉพาะด้าน (ทั้งบังคับและเลือก) ต้องศึกษารวม {sa} หน่วยกิต [{source_name}/1]",
                    "lookup_mode": "exact_title",
                    "miss_reason": "",
                }

        if "เลือกเสรี" in q:
            fe = totals.get("free_elective")
            if fe is not None:
                return {
                    "answer": f"- หมวดวิชาเลือกเสรี ต้องศึกษารวม {fe} หน่วยกิต [{source_name}/1]",
                    "lookup_mode": "exact_title",
                    "miss_reason": "",
                }

    # Total-program-credit lookup.
    _credit_q_signals = (
        "รวมกี่หน่วยกิต", "หน่วยกิตรวมของหลักสูตร", "จำนวนหน่วยกิตรวม", "ตลอดหลักสูตร",
    )
    _vit_subjects = ("วิศวะคอม", "วิศวกรรมคอม", "หลักสูตร", "เรียนทั้งหมด", "เรียนรวม")
    _credit_broad = any(t in q for t in _credit_q_signals) or (
        any(s in q for s in _vit_subjects)
        and any(t in q for t in ("กี่", "ทั้งหมด", "รวม"))
    )
    # Do not answer program-total credits when the user asks about a specific course code.
    # Course-level questions like "CPE 401 ... มีกี่หน่วยกิต" should continue to exact code lookup.
    has_course_code_hint = bool(re.search(r"\b[A-Za-z]{2,6}\s*[- ]?\s*\d{3}\b", q))
    if "หน่วยกิต" in q and _credit_broad and not has_course_code_hint:
        tot = totals.get("total")
        if tot is not None:
            return {
                "answer": (
                    f"- หลักสูตรวิศวกรรมคอมพิวเตอร์ต้องศึกษารวม {tot} หน่วยกิต [{source_name}/1]\n"
                    f"- ข้อความอ้างอิงคือ จำนวนหน่วยกิตรวมตลอดหลักสูตร {tot} หน่วยกิต [{source_name}/1]"
                ),
                "lookup_mode": "exact_title",
                "miss_reason": "",
            }

    # Study-plan lookup by year/term short-circuits expensive retrieval.
    # Gate: year hint is present AND no specific code/instructor/prereq intent.
    # Deliberately NOT requiring verb tokens like "เรียนอะไร" so that short queries
    # like "วิชาปี 1" or "ปี 2 เทอม 2" also hit this deterministic path.
    _has_code_hint = bool(re.search(r"\b[A-Za-z]{2,6}\s*\d{3}\b", q))
    _instructor_hint = any(t in q for t in ("ใครสอน", "ผู้สอน", "อาจารย์", "คนสอน"))
    _prereq_hint = any(t in q for t in (
        "ต้องผ่าน", "บังคับก่อน", "วิชาบังคับก่อน", "ก่อนเรียน", "พื้นฐาน", "prereq", "prerequisite", "เงื่อนไขก่อน"
    ))
    year_hint, _ = _extract_year_term(q)
    if year_hint is not None and not (_has_code_hint or _instructor_hint or _prereq_hint):
        year_courses = _parse_study_plan_courses(q)
        year_answer = _format_study_plan_answer(q, year_courses, source_name)
        if year_answer:
            return {"answer": year_answer, "lookup_mode": "study_plan", "miss_reason": ""}
        return {"answer": None, "lookup_mode": "none", "miss_reason": "no_studyplan_match"}

    # Exact course-code/title lookups.
    prereq_intent = any(t in q for t in (
        "ต้องผ่าน", "บังคับก่อน", "วิชาบังคับก่อน", "ผ่านอะไรก่อน", "ก่อนเรียน", "พื้นฐาน", "prereq", "pre-req", "prerequisite", "เงื่อนไขก่อน"
    ))
    term_intent = any(t in q for t in (
        "เทอม", "ภาค", "ภาคการศึกษา", "semester", "ปีที่", "ชั้นปี", "อยู่ปี", "เรียนปี"
    ))

    def _codes_in_order(text: str) -> list[str]:
        vals: list[str] = []
        for m in re.finditer(r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b", text or ""):
            vals.append(f"{(m.group(1) or '').upper()} {(m.group(2) or '')}".strip())
        for c in list(extract_course_codes(text or "")):
            vals.append((c or "").strip())

        out: list[str] = []
        seen: set[str] = set()
        for c in vals:
            s = (c or "").strip()
            if not s:
                continue
            k = s.replace("-", "").replace(" ", "").upper()
            if k in seen:
                continue
            seen.add(k)
            out.append(s)
        return out

    followup_codes: list[str] = []
    explicit_followup = re.search(r"ค(?:ำ|ํา)ถามต่อเนื่อง\s*:", q) is not None
    if explicit_followup:
        parts = re.split(r"ค(?:ำ|ํา)ถามต่อเนื่อง\s*:", q, maxsplit=1)
        tail = (parts[1] if len(parts) > 1 else "").strip()
        if tail:
            followup_codes = _codes_in_order(tail)

    codes = followup_codes or _codes_in_order(q)
    all_courses: dict[str, Course] = {}
    if not instructor_intent:
        all_courses = load_all_courses_2564()

    if prereq_intent and not instructor_intent:
        if not codes:
            return {
                "answer": "โปรดระบุรหัสวิชาที่ต้องการตรวจสอบวิชาบังคับก่อน เช่น CPE 214 ต้องผ่านวิชาอะไร",
                "lookup_mode": "prereq_clarify",
                "miss_reason": "no_course_code",
            }

        for code in reversed(codes):
            hit = _lookup_prerequisites_from_sqlite(code)
            if hit is None:
                hit = _lookup_prerequisites_from_graph(code)
            if hit is None:
                continue
            prereqs, src = hit
            code_disp = code.replace('-', ' ').upper().strip()
            if prereqs:
                return {
                    "answer": f"- รายวิชา {code_disp} มีวิชาบังคับก่อนคือ {', '.join(prereqs)} [{src}/1]",
                    "lookup_mode": "prereq_exact",
                    "miss_reason": "",
                }
            return {
                "answer": f"- รายวิชา {code_disp} ไม่มีวิชาบังคับก่อนตามข้อมูลที่พบ [{src}/1]",
                "lookup_mode": "prereq_exact",
                "miss_reason": "",
            }

        return {
            "answer": f"- ไม่พบข้อมูลวิชาบังคับก่อนของรายวิชา {codes[-1].replace('-', ' ').upper()} ที่ยืนยันได้จากเอกสาร [{source_name}/1]",
            "lookup_mode": "prereq_exact_miss",
            "miss_reason": "prereq_not_found",
        }

    # Title-based mapping for explicit code questions.
    title_lookup_mode: str | None = None
    code_lookup_intent = any(t in q.lower() for t in ("รหัสวิชา", "รหัสอะไร", "course code", "code of", "คือวิชาอะไร", "กี่หน่วยกิต", "มีกี่หน่วยกิต", "คืออะไร"))
    if code_lookup_intent and (not codes) and (not instructor_intent) and (not (prereq_intent or term_intent)):
        matched_code, title_lookup_mode = _find_best_course_code_by_title(q, all_courses)
        if matched_code:
            codes.append(matched_code)

    # Instructor deterministic path: latest entity wins and bypasses generic retrieval.
    if instructor_intent:
        relation_hit_any = False
        contact_hit_any = False
        exact_code_hit = 0

        if not codes:
            matched_code, _mode = _find_best_course_code_by_title(q, all_courses)
            if matched_code:
                codes.append(matched_code)

        if not codes:
            return {
                "answer": None,
                "lookup_mode": "none",
                "miss_reason": "no_alias_match",
                "instructor_lookup_exact_code_hit": 0,
                "instructor_lookup_relation_hit": 0,
                "instructor_lookup_contact_hit": 0,
                "instructor_assignment_candidates_n": 0,
                "instructor_assignment_confident": 0,
                "instructor_assignment_multi_match": 0,
                "instructor_assignment_soft_answer_used": 0,
            }

        # Follow-up-safe: iterate reversed so newest code in question tail is preferred.
        for code in reversed(codes):
            key = code.replace("-", "").replace(" ", "").upper()
            course = all_courses.get(key)
            code_disp = f"{code[:3]} {code[-3:]}" if len(code.replace(' ', '')) >= 6 else code
            if course:
                code_disp = f"{course.prefix} {course.number}"
                exact_code_hit = 1

            pairs, relation_hit, contact_hit = _lookup_instructors_for_course(code_disp)
            relation_hit_any = relation_hit_any or relation_hit
            contact_hit_any = contact_hit_any or contact_hit
            if not pairs:
                continue

            out = [f"- รายวิชา {code_disp} พบผู้สอนทั้งหมดที่พบในข้อมูล ({len(pairs)} คน) ได้แก่"]
            for n, cite in pairs:
                out.append(f"  - {n} [{cite}]")
            if relation_hit and (not contact_hit):
                lookup_mode = "instructor_exact_code"
                miss_reason = ""
                confident = 1
                multi_match = int(len(pairs) > 1)
                soft_used = 0
            else:
                lookup_mode = "instructor_soft"
                miss_reason = "multiple_candidates_no_resolution"
                confident = 0
                multi_match = int(len(pairs) > 1)
                soft_used = 1
                out.append("- แต่เอกสารไม่ยืนยันว่าเป็นผู้สอนประจำในภาคการศึกษานี้")
            return {
                "answer": "\n".join(out).strip(),
                "lookup_mode": lookup_mode,
                "miss_reason": miss_reason,
                "instructor_lookup_exact_code_hit": exact_code_hit,
                "instructor_lookup_relation_hit": int(relation_hit_any),
                "instructor_lookup_contact_hit": int(contact_hit_any),
                "instructor_assignment_candidates_n": len(pairs),
                "instructor_assignment_confident": confident,
                "instructor_assignment_multi_match": multi_match,
                "instructor_assignment_soft_answer_used": soft_used,
            }

        if relation_hit_any:
            miss = "relation_found_but_no_assignment"
            # Use relaxed lookup to surface nearby names without role-keyword gate
            all_nearby: list[str] = []
            for _c in codes:
                for _n in _lookup_nearby_names_for_course(_c):
                    if _n not in all_nearby:
                        all_nearby.append(_n)
            if all_nearby:
                names_str = ", ".join(all_nearby[:3])
                ans = (
                    f"พบชื่อที่เกี่ยวข้องกับรายวิชานี้ในข้อมูล ได้แก่ {names_str} "
                    "แต่เอกสารไม่ยืนยันว่าเป็นผู้สอนประจำในภาคการศึกษานี้"
                )
            else:
                ans = "พบเอกสารอ้างอิงรายวิชานี้ แต่ไม่พบชื่อผู้สอนที่ระบุคู่กันอย่างชัดเจน"
        elif contact_hit_any:
            miss = "contact_only_no_course_binding"
            ans = "พบข้อมูลช่องทางการติดต่อ แต่ไม่พบการระบุผู้สอนรายวิชานี้"
        else:
            miss = "no_relation_match"
            ans = None

        if ans:
            return {
                "answer": ans,
                "lookup_mode": "instructor_soft",
                "miss_reason": miss,
                "instructor_lookup_exact_code_hit": exact_code_hit,
                "instructor_lookup_relation_hit": int(relation_hit_any),
                "instructor_lookup_contact_hit": int(contact_hit_any),
                "instructor_assignment_candidates_n": len(all_nearby) if relation_hit_any else 0,
                "instructor_assignment_confident": 0,
                "instructor_assignment_multi_match": 0,
                "instructor_assignment_soft_answer_used": 1,
            }

        return {
            "answer": None,
            "lookup_mode": "none",
            "miss_reason": miss,
            "instructor_lookup_exact_code_hit": exact_code_hit,
            "instructor_lookup_relation_hit": int(relation_hit_any),
            "instructor_lookup_contact_hit": int(contact_hit_any),
            "instructor_assignment_candidates_n": 0,
            "instructor_assignment_confident": 0,
            "instructor_assignment_multi_match": 0,
            "instructor_assignment_soft_answer_used": 0,
        }

    if codes and (not instructor_intent) and (not prereq_intent) and (not term_intent):
        for code in reversed(codes):
            key = code.replace("-", "").replace(" ", "").upper()
            course = all_courses.get(key)
            source_hint = source_name
            if not course:
                sqlite_hit = _lookup_course_from_sqlite(code)
                if sqlite_hit:
                    course, source_hint = sqlite_hit
            if not course:
                continue
            code_disp = f"{course.prefix} {course.number}"
            sqlite_prereq_hit = _lookup_prerequisites_from_sqlite(code_disp)
            sqlite_hour_hit = _lookup_course_hours_from_sqlite(code_disp)
            return {
                "answer": _format_course_detail_answer(
                    code_disp=code_disp,
                    title=course.title_th,
                    credits=course.credits,
                    base_src=source_hint,
                    hour_hit=sqlite_hour_hit,
                    prereq_hit=sqlite_prereq_hit,
                ),
                "lookup_mode": (title_lookup_mode or "exact_code"),
                "miss_reason": "",
            }
        if explicit_followup and followup_codes:
            return {"answer": None, "lookup_mode": "none", "miss_reason": "no_exact_match"}

    # Full required CPE list.
    required = format_required_cpe_answer(q)
    if required:
        return {"answer": required, "lookup_mode": "study_plan", "miss_reason": ""}

    # List courses under a prefix (e.g., LNGxxx / CPE มีรหัสวิชาอะไรบ้าง).
    pref = _extract_prefix_from_question(q)
    if pref and _is_prefix_list_question(q):
        from_canonical = [c for c in all_courses.values() if (c.prefix or "").upper() == pref.upper()]
        if from_canonical:
            items = sorted(from_canonical, key=lambda c: int(c.number))
            lines: list[str] = []
            lines.append(f"รหัสวิชา {pref} ที่พบในโดเมนหลักสูตร (curriculum):")
            lines.append(f"- พบทั้งหมด {len(items)} วิชา [{source_name}/1]")
            for c in items:
                cred = f" ({c.credits} หน่วยกิต)" if c.credits else ""
                lines.append(f"- {c.prefix} {c.number} {c.title_th}{cred} [{source_name}/1]")
            return {"answer": "\n".join(lines).strip(), "lookup_mode": "prefix_list", "miss_reason": ""}

        sqlite_path = domain_sqlite_path("curriculum")
        ids = keyword_search(f"รายวิชา: {pref}", limit=600, sqlite_path=sqlite_path)
        if not ids:
            ids = keyword_search(pref, limit=600, sqlite_path=sqlite_path)
        docs = fetch_docs_with_path(ids, sqlite_path=sqlite_path)
        bank: dict[str, Course] = {}
        sources: list[str] = []
        for d in docs:
            if d.get("source") and d.get("source") not in sources:
                sources.append(str(d.get("source")))
            for c in extract_courses_from_text(d.get("text") or "", prefix_filter=pref):
                bank.setdefault(c.code, c)

        if not bank:
            return {"answer": None, "lookup_mode": "none", "miss_reason": "no_alias_match"}

        items = sorted(bank.values(), key=lambda c: int(c.number))
        lines2: list[str] = []
        lines2.append(f"รหัสวิชา {pref} ที่พบในโดเมนหลักสูตร (curriculum):")
        lines2.append(f"- พบทั้งหมด {len(items)} วิชา")
        for c in items:
            cred = f" ({c.credits} หน่วยกิต)" if c.credits else ""
            lines2.append(f"- {c.prefix} {c.number} {c.title_th}{cred}")
        if sources:
            lines2.append(f"\nแหล่งอ้างอิง (ตัวอย่าง): {', '.join(sources[:3])}")
        return {"answer": "\n".join(lines2).strip(), "lookup_mode": "prefix_list", "miss_reason": ""}

    return {"answer": None, "lookup_mode": "none", "miss_reason": "no_deterministic_match"}


def structured_curriculum_answer(question: str) -> str | None:
    """Backward-compatible wrapper returning only answer text."""
    return structured_curriculum_lookup(question).get("answer")
