from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import ROOT_DIR


@dataclass(frozen=True)
class Course:
    prefix: str
    number: str
    title_th: str
    credits: int

    @property
    def code(self) -> str:
        return f"{self.prefix}{self.number}"


@dataclass(frozen=True)
class CurriculumCPE2564:
    source_path: Path
    # Required courses explicitly listed in the study plan.
    # Note: electives placeholders like CPE xxx / GEN xxx are intentionally excluded.
    required_cpe_common: tuple[Course, ...]
    required_cpe_normal_only: tuple[Course, ...]
    required_cpe_wil_only: tuple[Course, ...]


# Cache the parsed curriculum to avoid re-parsing per request.
_CACHED_2564: Optional[CurriculumCPE2564] = None
_CACHED_ALL_COURSES_2564: Optional[dict[str, Course]] = None


_COURSE_LINE_RE = re.compile(
    r"^\s*(?P<or>หรือ\s+)?(?P<prefix>[A-Z]{2,6})\s+(?P<num>\d{3}|[xX]{3}|\d[xX]{2})\s+(?P<title>.+?)\s+(?P<credits>\d+)\s*\(",
)

# Some chunks use a header form like: "รายวิชา: LNG 275 Chinese I ... 3 (3-0-6)"
_COURSE_HEADER_RE = re.compile(
    r"รายวิชา\s*[:：]\s*(?P<prefix>[A-Z]{2,6})\s*(?P<num>\d{3})\s+(?P<title>[^\n]+)",
)


def extract_courses_from_text(text: str, prefix_filter: str | None = None) -> list[Course]:
    """Extract course entries from a text chunk.

    Supports both study-plan lines and "รายวิชา: XXX NNN" header-style chunks.
    """
    out: dict[str, Course] = {}
    pref_f = (prefix_filter or '').strip().upper() if prefix_filter else None
    if not text:
        return []

    lines = (text or '').splitlines()

    # Pass 1: line-based pattern with credits.
    for ln in lines:
        m = _COURSE_LINE_RE.match(ln.rstrip())
        if not m:
            continue
        prefix = (m.group('prefix') or '').strip().upper()
        num = (m.group('num') or '').strip()
        if pref_f and prefix != pref_f:
            continue
        if re.search(r"[xX]", num):
            continue
        title_th = re.sub(r"\s+", " ", (m.group('title') or '').strip())
        try:
            credits = int(m.group('credits') or '0')
        except Exception:
            credits = 0
        c = Course(prefix=prefix, number=num, title_th=title_th, credits=credits)
        out[c.code] = c

    # Pass 2: header-based pattern; credits may be elsewhere.
    for m in _COURSE_HEADER_RE.finditer(text):
        prefix = (m.group('prefix') or '').strip().upper()
        num = (m.group('num') or '').strip()
        if pref_f and prefix != pref_f:
            continue
        title = (m.group('title') or '').strip()
        # Trim trailing English title in parentheses if present.
        title = re.sub(r"\(.*?\)", "", title).strip()
        title = re.sub(r"\s+", " ", title)

        # Try to find credits near the match (within a small window).
        window = text[m.end():m.end() + 200]
        cm = re.search(r"\b(\d)\s*\(\s*\d+\s*[-–]\s*\d+\s*[-–]\s*\d+\s*\)", window)
        credits = int(cm.group(1)) if cm else 0

        # OCR often yields: "... <title> 3" without a parsable (3-0-6) tuple in-window.
        # If we still have no credits but the title ends with a single digit, treat it as credits.
        if credits == 0:
            tm = re.search(r"\b([1-9])\b\s*$", title)
            if tm:
                credits = int(tm.group(1))
                title = re.sub(r"\s*\b[1-9]\b\s*$", "", title).strip()

        # If the title ends with the same credit number, drop it.
        if credits and re.search(rf"\b{credits}\b\s*$", title):
            title = re.sub(rf"\s*\b{credits}\b\s*$", "", title).strip()

        c = Course(prefix=prefix, number=num, title_th=title, credits=credits)
        out.setdefault(c.code, c)

    # Stable sort
    def _key(c: Course) -> tuple[str, int]:
        try:
            n = int(c.number)
        except Exception:
            n = 9999
        return (c.prefix, n)

    return sorted(out.values(), key=_key)


def _find_cpe_2564_source() -> Optional[Path]:
    # Prefer explicit env override.
    import os
    override = (os.getenv('CURRICULUM_CPE_2564_PATH') or '').strip()
    if override:
        try:
            p = Path(override).expanduser()
            if p.exists():
                return p
        except Exception:
            pass

    # Default location in this repo.
    p = ROOT_DIR / 'data' / 'curriculum' / 'FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt'
    if p.exists():
        return p

    # Best-effort: find a matching file name under data/curriculum.
    cur_dir = ROOT_DIR / 'data' / 'curriculum'
    try:
        for cand in cur_dir.glob('**/*2564*.txt'):
            name = cand.name
            if 'วิศวกรรมคอมพิวเตอร์' in name and 'FOE10' in name:
                return cand
    except Exception:
        return None

    return None


def _parse_required_courses_from_study_plan(text: str) -> dict[str, Course]:
    """Parse explicit course lines from the study plan section.

    Returns a mapping code -> Course. Excludes placeholder electives (xxx/3xx).
    """
    out: dict[str, Course] = {}
    for raw_ln in (text or '').splitlines():
        ln = raw_ln.rstrip()
        m = _COURSE_LINE_RE.match(ln)
        if not m:
            continue

        prefix = (m.group('prefix') or '').strip().upper()
        num = (m.group('num') or '').strip()

        # Skip placeholders like xxx / 3xx.
        if re.search(r"[xX]", num):
            continue

        title_th = re.sub(r"\s+", " ", (m.group('title') or '').strip())
        try:
            credits = int(m.group('credits') or '0')
        except Exception:
            credits = 0

        c = Course(prefix=prefix, number=num, title_th=title_th, credits=credits)
        out[c.code] = c

    return out


def _split_tracks(text: str) -> tuple[str, str, str]:
    """Return (common_part, normal_part, wil_part) for study plan.

    Common part includes everything up to the point where the doc introduces
    the normal plan section.
    """
    t = text or ''

    # Everything before the explicit split is common.
    normal_marker = 'แผนการศึกษาปกติ'
    wil_marker = 'แผนการศึกษาการเรียนรู้ร่วมกับการทำงาน'

    if normal_marker not in t and wil_marker not in t:
        return t, '', ''

    common = t
    normal = ''
    wil = ''

    if normal_marker in t:
        common, rest = t.split(normal_marker, 1)
        normal = rest
    else:
        rest = t

    if wil_marker in rest:
        before_wil, wil_rest = rest.split(wil_marker, 1)
        # If we have a normal section, keep only the portion before WIL as normal.
        if normal:
            normal = before_wil
        else:
            common = before_wil
        wil = wil_rest

    return common, normal, wil


def load_cpe_curriculum_2564() -> Optional[CurriculumCPE2564]:
    global _CACHED_2564
    if _CACHED_2564 is not None:
        return _CACHED_2564

    src = _find_cpe_2564_source()
    if not src:
        return None

    try:
        text = src.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None

    # Focus on the study plan section to avoid pulling prerequisite lists etc.
    study_marker = 'แผนการศึกษา'
    if study_marker in text:
        text = text.split(study_marker, 1)[1]

    common_txt, normal_txt, wil_txt = _split_tracks(text)

    common = _parse_required_courses_from_study_plan(common_txt)
    normal = _parse_required_courses_from_study_plan(normal_txt)
    wil = _parse_required_courses_from_study_plan(wil_txt)

    # Compute track differences, focusing on CPE prefix as requested.
    def _only_cpe(m: dict[str, Course]) -> dict[str, Course]:
        return {k: v for k, v in m.items() if v.prefix == 'CPE'}

    c_common = _only_cpe(common)
    c_normal = _only_cpe(normal)
    c_wil = _only_cpe(wil)

    # Some CPE courses (e.g., 401/402/403) appear only in specific track sections.
    normal_only = {k: v for k, v in c_normal.items() if k not in c_common}
    wil_only = {k: v for k, v in c_wil.items() if k not in c_common}

    # Stable ordering by numeric code.
    def _sorted(vals: dict[str, Course]) -> tuple[Course, ...]:
        return tuple(sorted(vals.values(), key=lambda c: (c.prefix, int(c.number))))

    _CACHED_2564 = CurriculumCPE2564(
        source_path=src,
        required_cpe_common=_sorted(c_common),
        required_cpe_normal_only=_sorted(normal_only),
        required_cpe_wil_only=_sorted(wil_only),
    )
    return _CACHED_2564


def load_all_courses_2564() -> dict[str, Course]:
    global _CACHED_ALL_COURSES_2564
    if _CACHED_ALL_COURSES_2564 is not None:
        return _CACHED_ALL_COURSES_2564

    src = _find_cpe_2564_source()
    if not src:
        _CACHED_ALL_COURSES_2564 = {}
        return _CACHED_ALL_COURSES_2564

    try:
        text = src.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        _CACHED_ALL_COURSES_2564 = {}
        return _CACHED_ALL_COURSES_2564

    bank: dict[str, Course] = {}
    for course in extract_courses_from_text(text):
        bank.setdefault(course.code.upper(), course)

    _CACHED_ALL_COURSES_2564 = bank
    return _CACHED_ALL_COURSES_2564


def is_required_cpe_question(question: str) -> bool:
    q = (question or '').strip()
    if not q:
        return False
    ql = q.lower()
    if 'วิชาบังคับ' not in q and 'วิชาแกน' not in q:
        return False
    return ('cpe' in ql) or ('วิศวกรรมคอมพิวเตอร์' in q)


def format_required_cpe_answer(question: str) -> Optional[str]:
    """Return a full list answer for required CPE courses (curriculum 2564) if applicable."""
    if not is_required_cpe_question(question):
        return None

    cur = load_cpe_curriculum_2564()
    if not cur:
        return None

    if not cur.required_cpe_common and not cur.required_cpe_normal_only and not cur.required_cpe_wil_only:
        return None

    lines: list[str] = []
    lines.append("วิชาบังคับ (รายวิชา CPE) ตามแผนการศึกษา หลักสูตรวิศวกรรมคอมพิวเตอร์ (ปรับปรุง พ.ศ. 2564):")

    for c in cur.required_cpe_common:
        lines.append(f"- {c.prefix} {c.number} {c.title_th} ({c.credits} หน่วยกิต)")

    if cur.required_cpe_normal_only:
        lines.append("\nเฉพาะแผนการศึกษาปกติ:")
        for c in cur.required_cpe_normal_only:
            lines.append(f"- {c.prefix} {c.number} {c.title_th} ({c.credits} หน่วยกิต)")

    if cur.required_cpe_wil_only:
        lines.append("\nเฉพาะแผนการศึกษาการเรียนรู้ร่วมกับการทำงาน (WIL):")
        for c in cur.required_cpe_wil_only:
            lines.append(f"- {c.prefix} {c.number} {c.title_th} ({c.credits} หน่วยกิต)")

    # Make the source explicit to the user.
    lines.append(f"\nแหล่งอ้างอิง: {cur.source_path.name}")
    return "\n".join(lines).strip()
