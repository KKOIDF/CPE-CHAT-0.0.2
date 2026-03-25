from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from .normalization import normalize_question
from .neo4j_client import extract_course_codes, graph_requisite_codes_for_course
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
    """Return (instructors, relation_hit, contact_hit) for a normalized course code."""
    code = (code or "").strip().upper()
    m = re.match(r"^([A-Z]{2,6})\s*(\d{3})$", code)
    if not m:
        return [], False, False

    pref = m.group(1)
    num = m.group(2)
    db_path = domain_sqlite_path("curriculum")

    dids: list[str] = []
    seen_ids: set[str] = set()
    needles = [f"{pref} {num}", f"{pref}{num}", f"รายวิชา: {pref}"]
    for needle in needles:
        for did in keyword_search(needle, limit=600, sqlite_path=db_path):
            if did and did not in seen_ids:
                dids.append(did)
                seen_ids.add(did)
        if len(dids) >= 500:
            break

    docs = fetch_docs_with_path(dids, sqlite_path=db_path)
    if not docs:
        return [], False, False

    code_re = re.compile(rf"\b{re.escape(pref)}\s*[- ]?\s*{re.escape(num)}\b", re.IGNORECASE)
    title_name_re = re.compile(r"((?:ศ\.ดร\.|รศ\.ดร\.|ผศ\.ดร\.|ดร\.|อ\.)\s*[^\n\[\]]{2,120})")
    stop_tokens = (
        'Assoc.', 'Assistant Professor', 'Professor', 'ภาระงานสอน',
        'ประวัติการศึกษา', 'รายวิชา', 'อนุมัติจากสภา', 'International'
    )
    rel_hint_re = re.compile(r"(ผู้สอน|อาจารย์|lecturer|instructor|teacher)", re.IGNORECASE)

    found: list[tuple[str, str]] = []
    relation_hit = False
    contact_hit = False
    for d in docs:
        txt = str(d.get("text") or "")
        if not txt:
            continue
        src = str(d.get("source") or "").strip() or "curriculum"
        src_l = src.lower()
        cite = f"{src}/1"

        if ('contact' in src_l) or ('faculty' in src_l):
            contact_hit = True

        match_positions = list(code_re.finditer(txt))
        if not match_positions:
            continue
        relation_hit = True

        for m_code in match_positions:
            s = max(0, m_code.start() - 260)
            e = min(len(txt), m_code.end() + 560)
            window = txt[s:e]
            if (not rel_hint_re.search(window)) and (not contact_hit):
                continue

            for m_name in title_name_re.finditer(window):
                raw = (m_name.group(1) or "").strip()
                if not raw:
                    continue
                cleaned = raw
                for tok in stop_tokens:
                    pos = cleaned.find(tok)
                    if pos > 0:
                        cleaned = cleaned[:pos].strip()
                cleaned = re.split(r"\s+-\s+|\s+\(|\s+Assoc\.|\s+Professor", cleaned, maxsplit=1)[0].strip()
                cleaned = cleaned.strip(' -,:;()[]')
                if len(cleaned) < 6:
                    continue
                if not re.search(r"[\u0E00-\u0E7F]", cleaned):
                    continue
                found.append((cleaned, cite))

    # Deduplicate while preserving order.
    uniq: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    for name, cite in found:
        norm = re.sub(r"\s+", "", name)
        if norm in seen_names:
            continue
        seen_names.add(norm)
        uniq.append((name, cite))

    return uniq[:8], relation_hit, contact_hit


def _lookup_nearby_names_for_course(code: str) -> list[str]:
    """Relaxed version: returns name strings found near a code match without requiring a role keyword.
    Used for soft-answer fallback to surface possible instructor names.
    """
    code = (code or "").strip().upper()
    m = re.match(r"^([A-Z]{2,6})\s*(\d{3})$", code)
    if not m:
        return []

    pref, num = m.group(1), m.group(2)
    db_path = domain_sqlite_path("curriculum")
    dids: list[str] = []
    seen_ids: set[str] = set()
    for needle in [f"{pref} {num}", f"{pref}{num}"]:
        for did in keyword_search(needle, limit=300, sqlite_path=db_path):
            if did and did not in seen_ids:
                dids.append(did)
                seen_ids.add(did)

    docs = fetch_docs_with_path(dids, sqlite_path=db_path)
    code_re = re.compile(rf"\b{re.escape(pref)}\s*[- ]?\s*{re.escape(num)}\b", re.IGNORECASE)
    title_name_re = re.compile(r"((?:ศ\.ดร\.|รศ\.ดร\.|ผศ\.ดร\.|ดร\.|อ\.)\s*[^\n\[\]]{2,80})")
    stop_tokens = ("Assoc.", "Assistant Professor", "Professor", "ภาระงานสอน", "ประวัติการศึกษา", "รายวิชา")

    names: list[str] = []
    seen: set[str] = set()
    for d in docs:
        txt = str(d.get("text") or "")
        for mc in code_re.finditer(txt):
            s, e = max(0, mc.start() - 200), min(len(txt), mc.end() + 400)
            for mn in title_name_re.finditer(txt[s:e]):
                raw = (mn.group(1) or "").strip()
                for tok in stop_tokens:
                    pos = raw.find(tok)
                    if pos > 0:
                        raw = raw[:pos].strip()
                raw = re.split(r"\s+-\s+|\s+\(|\s+Assoc\.", raw, maxsplit=1)[0].strip(' -,:;()[]')
                if len(raw) < 6 or not re.search(r"[\u0E00-\u0E7F]", raw):
                    continue
                norm = re.sub(r"\s+", "", raw)
                if norm not in seen:
                    seen.add(norm)
                    names.append(raw)
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
            if found:
                return found, src

    return None


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


def structured_curriculum_lookup(question: str) -> dict[str, Any]:
    """Deterministic curriculum lookup with debug metadata.

    Returns keys:
      - answer: str | None
      - lookup_mode: exact_title|alias_title|fuzzy_title|study_plan|exact_code|prefix_list|none
      - miss_reason: no_exact_match|no_alias_match|no_studyplan_match|ambiguous_match|no_deterministic_match
    """
    q = normalize_question(question)
    totals = load_credit_totals_2564()
    curriculum = load_cpe_curriculum_2564()
    source_name = curriculum.source_path.name if curriculum else "curriculum_sqlite"

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
    if "หน่วยกิต" in q and _credit_broad:
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
    instructor_intent = any(t in q for t in ("ใครสอน", "ผู้สอน", "อาจารย์", "คนสอน"))
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

            if len(pairs) == 1:
                n, cite = pairs[0]
                return {
                    "answer": f"- รายวิชา {code_disp} ระบุผู้สอนเป็น {n} [{cite}]",
                    "lookup_mode": "instructor_exact_code",
                    "miss_reason": "",
                    "instructor_lookup_exact_code_hit": exact_code_hit,
                    "instructor_lookup_relation_hit": int(relation_hit_any),
                    "instructor_lookup_contact_hit": int(contact_hit_any),
                    "instructor_assignment_candidates_n": 1,
                    "instructor_assignment_confident": 1,
                    "instructor_assignment_multi_match": 0,
                    "instructor_assignment_soft_answer_used": 0,
                }

            out = [f"- พบผู้สอนที่เกี่ยวข้องกับรายวิชา {code_disp} ในข้อมูล ได้แก่"]
            for n, cite in pairs[:6]:
                out.append(f"  - {n} [{cite}]")
            out.append("- แต่เอกสารไม่ยืนยันว่าเป็นผู้สอนประจำในภาคการศึกษานี้")
            return {
                "answer": "\n".join(out).strip(),
                "lookup_mode": "instructor_soft",
                "miss_reason": "multiple_candidates_no_resolution",
                "instructor_lookup_exact_code_hit": exact_code_hit,
                "instructor_lookup_relation_hit": int(relation_hit_any),
                "instructor_lookup_contact_hit": int(contact_hit_any),
                "instructor_assignment_candidates_n": len(pairs),
                "instructor_assignment_confident": 0,
                "instructor_assignment_multi_match": 1,
                "instructor_assignment_soft_answer_used": 1,
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
            credit_text = f"{course.credits} หน่วยกิต" if course.credits else "ไม่พบจำนวนหน่วยกิตในข้อความที่ parse ได้"
            return {
                "answer": (
                    f"- วิชา {course.prefix} {course.number} คือ {course.title_th} [{source_hint}/1]\n"
                    f"- วิชา {course.prefix} {course.number} มีจำนวน {credit_text} [{source_hint}/1]"
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
