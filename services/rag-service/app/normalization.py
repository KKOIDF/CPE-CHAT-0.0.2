from __future__ import annotations

from typing import List
import re
import unicodedata


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
    ('อารัย', 'อะไร'),
    ('อะรัย', 'อะไร'),
    ('วิชาบังครับ', 'วิชาบังคับ'),
    ('คับ', 'ครับ'),
    ('คัฟ', 'ครับ'),
    ('ปะ', 'ไหม'),
    ('ป่าว', 'เปล่า'),
    ('มั้ย', 'ไหม'),
    ('มั๊ย', 'ไหม'),
    ('ได้ปะ', 'ได้ไหม'),
    ('ปรึกสา', 'ปรึกษา'),
    ('ถอดรายวิชา', 'ถอนรายวิชา'),
    ('ถอดวิชา', 'ถอนวิชา'),
    ('ดรอปรายวิชา', 'ถอนรายวิชา'),
    ('ดรอปวิชา', 'ถอนวิชา'),
    ('drop รายวิชา', 'ถอนรายวิชา'),
    ('withdraw รายวิชา', 'ถอนรายวิชา'),
    ('กำหนดส่งเอกสาร', 'กำหนดส่งเอกสาร'),
    # common Thai chat shorthand / colloquial phrasing
    ('เรียนไรบ้าง', 'เรียนอะไรบ้าง'),
    ('เรียนไร', 'เรียนอะไร'),
    ('วิชาไรบ้าง', 'วิชาอะไรบ้าง'),
    ('วิชาไร', 'วิชาอะไร'),
    ('มีไรบ้าง', 'มีอะไรบ้าง'),
    ('มีไร', 'มีอะไร'),
    ('คือไร', 'คืออะไร'),
    ('ทำไร', 'ทำอะไร'),
    ('เอาไร', 'เอาอะไร'),
    ('ต้องใช้ไร', 'ต้องใช้อะไร'),
    ('ได้ไร', 'ได้อะไร'),
]


_COURSE_NAME_SYNONYMS: list[tuple[str, str]] = [
    ('แคล1', 'Calculus I'),
    ('แคล 1', 'Calculus I'),
    ('แคล2', 'Calculus II'),
    ('แคล 2', 'Calculus II'),
    ('แคล', 'Calculus'),
    ('แคลคูลัส', 'Calculus'),
    ('ฟิสิกส์1', 'Physics I'),
    ('ฟิสิกส์ 1', 'Physics I'),
    ('ฟิสิกส์2', 'Physics II'),
    ('ฟิสิกส์ 2', 'Physics II'),
    ('ฟิสิกส์', 'Physics'),
    ('เคมี', 'Chemistry'),
    ('อิ้ง', 'English'),
    ('เจน', 'GEN'),
    ('คอมโปร', 'Computer Programming'),
    ('ซัมเมอร์', 'ภาคฤดูร้อน'),
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
    for src, dst in _COURSE_NAME_SYNONYMS:
        # replace standalone occurrences using word boundaries wouldn't work easily for Thai,
        # but simple string replace is safe enough for these specific abbreviations.
        q = q.replace(src, dst)

    # Normalize alphanumeric course codes without/with dash: CPE342 / CPE-342 -> CPE 342
    q = re.sub(r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b", r"\1 \2", q)
    # Handle OCR/typo ambiguity in numeric part: CPE 34O / CPE34O -> CPE 340
    q = re.sub(
        r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{2})[oO]\b",
        lambda m: f"{(m.group(1) or '').upper()} {(m.group(2) or '').strip()}0",
        q,
    )

    # Normalize credits
    q = re.sub(r"(\d+)\s*(กิต|นก\.|หน่วย)\b", r"\1 หน่วยกิต", q)
    # Normalize semester/year e.g. "เทอม 1" -> "ภาคการศึกษาที่ 1"
    q = re.sub(r"(เทอม|ภาค)\s*([123])", r"ภาคการศึกษาที่ \2", q)
    # Normalize year e.g. "ปี 1", "ปี1" -> "ชั้นปีที่ 1", except if it is followed by 4 digits (e.g. ปี 2568)
    q = re.sub(r"ปี\s*([12345])(\D|$)", r"ชั้นปีที่ \1\2", q)

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

    # OCR/typo variant where last digit uses O/o, e.g. CPE34O -> CPE340.
    for m in re.finditer(r"\b([A-Za-z]{2,6})\s*[-]?\s*([0-9]{2})[oO]\b", q2):
        pfx = (m.group(1) or '').upper()
        num2 = m.group(2) or ''
        if not pfx or not num2:
            continue
        num = f"{num2}0"
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

    # LNG questions are often asked in mixed formats (LNG120 / LNG 120) or by
    # intent words like "language course". Add a compact bilingual hint to improve recall.
    ql = q.lower()
    if re.search(r"\blng\s*[- ]?\s*\d{3}\b", q, flags=re.IGNORECASE) and ('language course' not in ql):
        q = f"{q} (language course รายวิชาภาษา)"
    if any(t in q for t in ('ถอนรายวิชา', 'ถอนวิชา', 'ลดรายวิชา')) and ('withdraw' not in ql):
        q = f"{q} (withdraw drop add/drop W เพิ่ม-ลด ถอนวิชา ลดรายวิชา)"

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
    normalized = normalize_question(raw)
    semantic_q = normalize_query_for_retrieval(search_query_from_question(normalized))
    keyword_q = normalize_query_for_keyword(normalized)
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
        # registrar / announcement-ish
        'ถอนรายวิชา', 'ถอนวิชา', 'ลดรายวิชา', 'เพิ่ม-ลด', 'ลงทะเบียน', 'w', 'withdrawn',
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
