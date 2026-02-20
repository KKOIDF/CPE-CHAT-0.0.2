import math, time, re
import hashlib
from pathlib import Path
from typing import List, Dict, Optional

from .config import CHUNK_MIN_TOKENS, CHUNK_MAX_TOKENS, CHUNK_OVERLAP_RATIO, CHAR_PER_TOKEN, CHUNK_STRATEGY, CURRICULUM_PROGRAM
from .utils import split_paragraphs_smart, segment_sentences_thai

_HEADING_PATTS = [r"^บท\s*ที่\s*\d+", r"^หมวด\s*ที่?\s*\d+", r"^ภาคผนวก", r"^บท\s*\d+", r"^(?:\d+\.)+\s+", r"^\d+\)\s+", r"^[A-Za-zก-๙]+\s*:\s+"]
_HEADING_RE = re.compile("|".join(_HEADING_PATTS))
_BULLET_PATTS = [r"^[\-\•\–]\s+", r"^[ก-ฮ]\)\s+", r"^\([ก-ฮ]\)\s+", r"^\([0-9]+\)\s+"]
_BULLET_RE = re.compile("|".join(_BULLET_PATTS))

_COURSE_CODE_RE = re.compile(r"^(?P<prefix>[A-Z]{2,4})\s*(?P<num>\d{3})\b")
_COURSE_CODE_ANYWHERE_RE = re.compile(r"(?P<prefix>[A-Z]{2,4})\s*(?P<num>\d{3})\b")
_SSC_COURSE_RE = re.compile(r"^SSC\s*(?P<num>\d{3})\s*:\s*(?P<title>.+)$")

_GE_GROUP_RE = re.compile(r"^(กลุ่มวิชา|กลุ่ม|หมวดวิชา).{0,80}$")
_LANG_FRAMEWORK_RE = re.compile(r"(CEFR|common\s+european\s+framework|ระดับภาษา|framework|ภาษาอังกฤษ\s*เพื่อ)", re.IGNORECASE)

_TABLE_CELL_SPLIT_RE = re.compile(r"\s{2,}|\|")
_X_MARK_RE = re.compile(r"\b[Xx✓✔]\b")

_DEGREE_RE = re.compile(
    r"\b(Ph\.?D\.|D\.?Phil\.|M\.?Sc\.|M\.?Eng\.|B\.?Eng\.|B\.?Sc\.|MBA|M\.?A\.|B\.?A\.|วศ\.บ\.|วท\.บ\.|ค\.บ\.|ศ\.บ\.|วศ\.ม\.|วท\.ม\.|ปร\.ด\.)\b",
    re.IGNORECASE,
)


def _sha1_32(s: str) -> str:
    return hashlib.sha1((s or '').encode('utf-8', 'ignore')).hexdigest()[:32]


def _split_table_cells(line: str) -> List[str]:
    s = (line or '').strip()
    if not s:
        return []
    if '|' in s:
        parts = [p.strip() for p in s.split('|')]
        # Trim at most one leading/trailing boundary cell caused by leading/trailing pipes.
        # Do NOT strip all trailing empties; empties can be meaningful cells in X-matrix tables.
        if parts and parts[0] == '':
            parts = parts[1:]
        if parts and parts[-1] == '':
            parts = parts[:-1]
        return parts
    parts = [p.strip() for p in _TABLE_CELL_SPLIT_RE.split(s) if p is not None]
    return [p for p in parts if p != '']


def _extract_degrees(block_lines: List[str]) -> List[Dict]:
    s = "\n".join([x for x in (block_lines or []) if x and x.strip()])
    if not s:
        return []
    out: List[Dict] = []
    for m in _DEGREE_RE.finditer(s):
        deg = (m.group(1) or '').strip()
        if not deg:
            continue
        out.append({'degree': deg})
        if len(out) >= 12:
            break
    # de-dup in order
    seen = set()
    uniq: List[Dict] = []
    for d in out:
        key = (d.get('degree') or '').lower()
        if not key or key in seen:
            continue
        seen.add(key)
        uniq.append(d)
    return uniq


def _year_to_ad(y: int) -> int:
    if y <= 0:
        return 0
    if y >= 2400:
        return y - 543
    return y


def _extract_learning_outcomes(lines: List[str], lo_start_idx: int) -> List[str]:
    if not lines or lo_start_idx is None or lo_start_idx < 0 or lo_start_idx >= len(lines):
        return []
    out: List[str] = []
    for ln in lines[lo_start_idx + 1 : lo_start_idx + 80]:
        s = (ln or '').strip()
        if not s:
            continue
        # stop if a new section starts (common in course blocks)
        if re.match(r"^(เนื้อหา|หัวข้อ|วิธีการสอน|การวัดผล|วิธีการวัด|การประเมิน)\b", s):
            break
        # bullets / numbering
        if _BULLET_RE.match(s) or re.match(r"^\d+[\.)]\s+", s) or re.match(r"^[A-Za-z]\)\s+", s):
            out.append(re.sub(r"^\s*(?:[\-\•\–]|\d+[\.)]|[A-Za-z]\))\s+", "", s).strip())
        elif out and len(s) <= 220:
            # continuation line
            out[-1] = (out[-1] + ' ' + s).strip()
        if len(out) >= 25:
            break
    # de-dup while preserving order
    seen = set()
    uniq: List[str] = []
    for x in out:
        key = (x or '').strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        uniq.append(x)
    return uniq

_PLO_RE = re.compile(r"^\s*PLO\s*(?P<num>\d+)\b", re.IGNORECASE)
_SUB_PLO_RE = re.compile(r"^\s*(?P<num>\d+)(?P<lemma>[A-Z])\b")
_PLO_ANYWHERE_RE = re.compile(r"\bPLO\s*(?P<num>\d+)\b", re.IGNORECASE)
_SUB_PLO_ANYWHERE_RE = re.compile(r"\b(?P<num>\d+)(?P<lemma>[A-Z])\b")
_PLO_SECTION_HINT_RE = re.compile(r"(ผลลัพธ์การเรียนรู้ของหลักสูตร|program\s*learning\s*outcomes|PLO\b)", re.IGNORECASE)
_PLO_MAP_HINT_RE = re.compile(r"(ตาราง\s*แมป|mapping|PLO\s*↔|PLO\s*\-\s*รายวิชา|PLO\s*กับ\s*รายวิชา)", re.IGNORECASE)

_COURSE_EQUIV_RE = re.compile(
    r"(?P<old>[A-Z]{3}\s*\d{3}).{0,40}?(?:→|->|แทน|เป็น|เปลี่ยนเป็น|ปรับรหัส).{0,40}?(?P<new>[A-Z]{3}\s*\d{3})"
)

_FACULTY_NAME_RE = re.compile(r"^(รศ\.ดร\.|ผศ\.ดร\.|ผศ\.|อ\.ดร\.|อ\.)\s+.+$")
# Faculty profile section headings are often numbered.
# Notes:
# - Accept both "2. หัวข้อ" and "2.1 หัวข้อ" (some sources omit the trailing dot).
# - Filter using heading-hint regex so we don't split on publication numbering lines like "1. Author, ...".
_FACULTY_SEC_RE = re.compile(r"^(?P<sec>\d+(?:\.\d+)*)(?:\.)?\s+(?P<title>.+)$")
_FACULTY_SEC_HEADING_HINT_RE = re.compile(
    r"(ประวัติการศึกษา|education|ภาระงานสอน|teaching\s*load|courses\s*taught|เหตุผล|รับผิดชอบหลักสูตร|ประจำหลักสูตร|คุณวุฒิ|ผลงาน|publication)",
    re.IGNORECASE,
)
_FACULTY_EDU_RE = re.compile(r"(ประวัติการศึกษา|education)", re.IGNORECASE)
_FACULTY_TEACH_RE = re.compile(r"(ภาระงานสอน|teaching\s*load|courses\s*taught)", re.IGNORECASE)
_FACULTY_PUB_RE = re.compile(r"(ผลงาน|publication)", re.IGNORECASE)

_CREDITS_HINT_RE = re.compile(r"\b(\d+)\s*\((\d+\s*[-–]\s*\d+\s*[-–]\s*\d+)\)\b")
_LO_RE = re.compile(
    r"(ผลลัพธ์การเรียนรู้|ผลการเรียนรู้|learning\s+outcomes?|course\s+learning\s+outcomes?|\bC?LO\b)",
    re.IGNORECASE,
)
_STRUCTURE_RE = re.compile(r"(โครงสร้างหลักสูตร|โครงสร้าง\s*GE|program\s*structure)", re.IGNORECASE)
_STUDY_PLAN_RE = re.compile(r"(แผนการศึกษา|แผนการเรียน|study\s*plan)", re.IGNORECASE)

_CLAUSE_RE = re.compile(r"^ข้อ\s*(?P<num>\d+)(?:\s*[\.:]\s*(?P<sub>\d+))?\b")
_SUBCLAUSE_RE = re.compile(r"^(?P<num>\d+)\.(?P<sub>\d+)\b")
_SEMESTER_RE = re.compile(r"(ภาคการศึกษาที่\s*\d+\s*/\s*(25\d{2}|26\d{2})|ภาค\s*\d\s*/\s*(25\d{2}|26\d{2})|ภาคพิเศษ\s*/\s*(25\d{2}|26\d{2})|semester\s*\d\s*/\s*\d{4})", re.IGNORECASE)
_DATE_LIKE_RE = re.compile(r"(\b\d{1,2}\s*[/-]\s*\d{1,2}\s*[/-]\s*(?:\d{2}|\d{4})\b|\b\d{1,2}\s*(ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.)\s*(25\d{2}|26\d{2})\b)")
_TABLE_HINT_RE = re.compile(r"(ตาราง|อัตรา|ค่าธรรมเนียม|คะแนน|เกณฑ์|บาท|THB|fee|score)", re.IGNORECASE)
_TABLE_ROWISH_RE = re.compile(r"\s{2,}|\|")
_DELTA_HINT_RE = re.compile(r"(แก้ไข|เพิ่มเติม|ยกเลิก|แทนฉบับ|ให้ใช้ข้อความต่อไปนี้แทน|ประกาศฉบับนี้ให้ใช้แทน|ยกเลิกประกาศ)")
_MEMO_HINT_RE = re.compile(r"(บันทึกข้อความ|หนังสือราชการ|^ที่\s*\S+|^เรียน\s|อ้างถึง)")
_EFFECTIVE_HINT_RE = re.compile(r"(มีผล|ให้มีผล|ตั้งแต่|ตั้งแต่ภาค|วันถัดจากวันประกาศ|effective\s+from)", re.IGNORECASE)
_AUDIENCE_HINTS = [
    ('international', re.compile(r"(international|ต่างชาติ|นักศึกษาต่างชาติ)", re.IGNORECASE)),
    ('phd', re.compile(r"(ป\.เอก|ดุษฎี|ph\.?d)", re.IGNORECASE)),
    ('master', re.compile(r"(ป\.โท|มหาบัณฑิต|master)", re.IGNORECASE)),
    ('undergrad', re.compile(r"(ป\.ตรี|ปริญญาตรี|undergrad)", re.IGNORECASE)),
    ('final_year', re.compile(r"(ชั้นปีสุดท้าย|ปีสุดท้าย|final\s+year)", re.IGNORECASE)),
]

_TOPIC_HINTS = [
    ('english', re.compile(r"(อังกฤษ|english|lng\s*\d{3}|tetet|toeic|ielts)", re.IGNORECASE)),
    ('fees', re.compile(r"(ค่าธรรมเนียม|fee|อัตรา|บาท|THB)", re.IGNORECASE)),
    ('insurance', re.compile(r"(ประกัน|insurance)", re.IGNORECASE)),
    ('internship', re.compile(r"(ฝึกงาน|intern)", re.IGNORECASE)),
    ('credit_transfer', re.compile(r"(เทียบโอน|credit\s*transfer)", re.IGNORECASE)),
    ('exam', re.compile(r"(สอบ|คุมสอบ|exam)", re.IGNORECASE)),
    ('calculator', re.compile(r"(เครื่องคิดเลข|calculator)", re.IGNORECASE)),
    ('prereq', re.compile(r"(pre[- ]?requisite|co[- ]?requisite|prereq)", re.IGNORECASE)),
    ('schedule', re.compile(r"(กำหนดการ|ปฏิทิน|calendar|ลงทะเบียน|เพิ่ม-ลด|ถอน|W)", re.IGNORECASE)),
]

# Regulations
_REG_CHAPTER_RE = re.compile(r"^หมวด\s*(?:ที่\s*)?(?P<num>\d+)\b")
_REG_CLAUSE_RE = re.compile(r"^ข้อ\s*(?P<num>\d+)(?P<rest>(?:\.\d+)*)\b")
_DELTA_DOC_HINT_RE = re.compile(r"(ฉบับที่\s*\d+|แก้ไขเพิ่มเติม|ให้ใช้ความต่อไปนี้แทน|ให้ใช้ข้อความต่อไปนี้แทน|ยกเลิกข้อความเดิม|ให้ยกเลิก)")
_COVID_HINT_RE = re.compile(r"(covid|โควิด|โรคติดเชื้อ|สถานการณ์ฉุกเฉิน)", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"(https?://\S+|www\.\S+)")
_PHONE_RE = re.compile(r"(\b0\d{1,2}[- ]?\d{3}[- ]?\d{4}\b|\b0\d{2}[- ]?\d{3}[- ]?\d{3,4}\b)")
_FEE_HINT_RE = re.compile(r"(ค่าธรรมเนียม|อัตรา|บาท|THB|fee)", re.IGNORECASE)
_AMENDS_HINT_RE = re.compile(r"(แก้ไขเพิ่มเติม|ให้ใช้แทน|แทนฉบับ|amend|replace)", re.IGNORECASE)
_SUPERSEDES_HINT_RE = re.compile(r"(ยกเลิก|ให้ยกเลิก|supersede|revoke)", re.IGNORECASE)
_DELTA_CHANGE_MARK_RE = re.compile(
    r"(ให้ยกเลิกข้อความในข้อ\s*\d+(?:\.\d+)*|ให้ใช้ข้อความต่อไปนี้แทน|ให้เพิ่มเติมข้อความ|ให้เพิ่มข้อ\s*\d+|ให้ยกเลิกระเบียบ|ให้ใช้ระเบียบฉบับนี้แทน)"
)


def est_tokens(text: str) -> int:
    return max(1, int(math.ceil(len(text) / CHAR_PER_TOKEN)))


def _infer_lang(text: str) -> str:
    s = text or ''
    has_th = bool(re.search(r"[ก-๙]", s))
    has_en = bool(re.search(r"[A-Za-z]", s))
    if has_th and has_en:
        return 'mixed'
    if has_th:
        return 'th'
    if has_en:
        return 'en'
    return ''


def _course_code_norm(code: str) -> str:
    m = _COURSE_CODE_ANYWHERE_RE.search((code or '').strip())
    if not m:
        return re.sub(r"\s+", "", (code or '').strip()).upper()
    return f"{m.group('prefix').upper()}{m.group('num')}"


def _safe_int(x, default=0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _make_curriculum_chunk(
    *,
    source_path: str,
    resolved_source: str,
    resolved_path: str,
    pages: List[int],
    text: str,
    doc_type: str,
    year: str,
    section: str,
    section_heading: str = '',
    section_path: Optional[List[str]] = None,
    clause_id: str = '',
    extra_meta: Optional[Dict] = None,
) -> Dict:
    pages_int = [int(p) for p in pages if isinstance(p, int) or str(p).isdigit()]
    page_start = min(pages_int) if pages_int else 0
    page_end = max(pages_int) if pages_int else 0
    source_file = Path(source_path).name
    program_year = _safe_int(year, 0)
    priority = _source_priority(source_path)
    scope = f"p{page_start}-p{page_end}" if page_start or page_end else ''
    spath = section_path or ([section_heading] if section_heading else [])

    # Important: keep chunk IDs stable even if we improve year parsing.
    # Only use a strict 25xx/26xx year (from filename or content) in the UID basis.
    year_uid = ''
    m = re.search(r"(25\d{2}|26\d{2})", source_file)
    if m:
        year_uid = m.group(1)
    else:
        m = re.search(r"(25\d{2}|26\d{2})", text or '')
        if m:
            year_uid = m.group(1)

    chunk_uid_basis = f"{source_file}|{year_uid}|{doc_type}|{section}|{clause_id}|{'/'.join(spath)}"
    chunk_uid = _sha1_32(chunk_uid_basis)
    chunk_key = f"sha1:{chunk_uid}"
    canonical_key = f"{year}|{doc_type}|{clause_id or section}|{chunk_uid[:8]}"

    out: Dict = {
        'source': resolved_source,
        'path': resolved_path,
        'page': page_start,
        'page_start': page_start,
        'page_end': page_end,
        'owner': 'owner:unknown',
        'sensitivity': 'internal',
        'updated_at': int(time.time()),
        'text': (text or '').strip(),
        'tokens_est': est_tokens(text or ''),
        # Metadata
        'doc_type': doc_type,
        'program': CURRICULUM_PROGRAM,
        'program_year': program_year or (year if year else ''),
        'source_file': source_file,
        'source_scope': scope,
        'section': section,
        'section_heading': section_heading,
        'section_path': spath,
        'lang': _infer_lang(text or ''),
        'year': year,
        'priority': priority,
        'chunk_uid': chunk_uid,
        'chunk_key': chunk_key,
        'canonical_key': canonical_key,
        'source_priority': priority,
        'clause_id': clause_id,
    }
    if extra_meta:
        out.update(extra_meta)
    return out


def is_heading(text: str) -> bool:
    return bool(_HEADING_RE.search(text.strip()))


def is_bullet(text: str) -> bool:
    return bool(_BULLET_RE.search(text.strip()))


def group_bullets(paragraphs: List[Dict]) -> List[Dict]:
    grouped = []
    buf = []
    for p in paragraphs:
        if is_bullet(p['text']):
            buf.append(p)
        else:
            if buf:
                merged = {**buf[0]}
                merged['text'] = '\n'.join(x['text'] for x in buf)
                grouped.append(merged)
                buf = []
            grouped.append(p)
    if buf:
        merged = {**buf[0]}
        merged['text'] = '\n'.join(x['text'] for x in buf)
        grouped.append(merged)
    return grouped


def paragraphs_from_records(records: List[Dict]) -> List[Dict]:
    out = []
    for r in records:
        page_raw = r.get('page_no')
        try:
            page = int(page_raw) if page_raw is not None else 0
        except (ValueError, TypeError):
            page = 0
        paras = r.get('paragraphs') or [r.get('text', '')]
        for t in paras:
            if not t or not t.strip():
                continue
            out.append({'page': page, 'text': t.strip(), 'is_heading': is_heading(t), 'src': r.get('source')})
    return group_bullets(out)


def normalize_doc_name(src_path: str) -> str:
    name = Path(src_path).stem.lower()
    name = re.sub(r"[^0-9A-Za-z\u0E00-\u0E7F]+", "_", name).strip("_")
    if not name:
        name = 'document'
    if not name.endswith('.txt'):
        name = f'{name}.txt'
    return name


def _extract_year_from_source(source_path: str) -> str:
    """Best-effort year extraction for curriculum versions.

    Uses 25xx/26xx matches from filename; also supports common short forms like
    "_64" meaning BE 2564, and AD years like 2021 (converted to BE 2564).
    Returns '' if not found.
    """
    name = Path(source_path).name
    # Avoid \b here because '_' is a word char and breaks boundaries.
    m = re.search(r"(25\d{2}|26\d{2})", name)
    if m:
        return m.group(1)

    # AD year (e.g., 2021 -> 2564)
    m = re.search(r"(19\d{2}|20\d{2})", name)
    if m:
        try:
            ad = int(m.group(1))
            if 1900 <= ad <= 2099:
                return str(ad + 543)
        except ValueError:
            pass

    # Two-digit BE short year in filenames (common: _64, -64, .64)
    # Be conservative: only accept 40-99 to avoid misclassifying random numbers.
    m = re.search(r"(?:\.|_|-)(\d{2})(?:[^0-9]|$)", name)
    if m:
        try:
            yy = int(m.group(1))
            if 40 <= yy <= 99:
                return f"25{yy:02d}"
        except ValueError:
            pass

    return ''


def _source_priority(source_path: str) -> int:
    """Heuristic priority for dedupe/canonicalization.

    Higher = more canonical/detailed.
    """
    n = Path(source_path).name.lower()
    score = 10
    if 'มคอ' in n or 'tqf' in n or 'tqf2' in n or 'tqf_2' in n:
        score = 100
    elif 'foe10' in n or 'foe' in n:
        score = 90
    elif 'คำอธิบายรายวิชา' in n or 'course' in n:
        score = 80
    elif 'learning outcomes' in n or 'outcome' in n:
        score = 75
    elif 'โครงสร้าง' in n or 'structure' in n:
        score = 60
    elif 'แผนการศึกษา' in n or 'study_plan' in n or 'plan' in n:
        score = 55
    return score


def _extract_year_be_from_text_or_source(text: str, source_path: str) -> str:
    year = _extract_year_from_source(source_path)
    if year:
        return year
    m = re.search(r"(25\d{2}|26\d{2})", text)
    return m.group(1) if m else ''


def _infer_doc_title(text_lines: List[str], source_path: str) -> str:
    for ln in text_lines[:12]:
        s = (ln or '').strip()
        if not s:
            continue
        if _CLAUSE_RE.match(s) or _COURSE_CODE_RE.match(s):
            continue
        if len(s) >= 6:
            return s[:180]
    return Path(source_path).stem


def _infer_audience(text: str) -> str:
    for label, patt in _AUDIENCE_HINTS:
        if patt.search(text):
            return label
    return ''


def _infer_topic(text: str, source_path: str) -> str:
    basis = f"{Path(source_path).name}\n{text}"
    for label, patt in _TOPIC_HINTS:
        if patt.search(basis):
            return label
    return ''


def _infer_effective_from(text: str) -> str:
    # Return a short snippet around the first effective marker.
    m = _EFFECTIVE_HINT_RE.search(text)
    if not m:
        return ''
    start = max(0, m.start() - 40)
    end = min(len(text), m.end() + 80)
    snip = " ".join(text[start:end].split())
    return snip[:200]


def _infer_effective_to(text: str) -> str:
    # Avoid false positives from "หมายถึง" by not matching a bare "ถึง".
    m = re.search(r"(จนถึง|ถึง\s*วันที่|สิ้นสุด|effective\s+to)\s*([^\n]{0,80})", text, re.IGNORECASE)
    if not m:
        return ''
    snip = " ".join((m.group(0) or '').split())
    return snip[:200]


def _infer_delta_info(text: str) -> tuple[str, str]:
    # (delta_type, targets)
    if re.search(r"(ยกเลิก|revoke)", text):
        delta_type = 'revoke'
    elif re.search(r"(แก้ไข|เพิ่มเติม|amend)", text):
        delta_type = 'amend'
    elif re.search(r"(ใช้แทน|แทนฉบับ|replace)", text):
        delta_type = 'replace'
    else:
        delta_type = ''
    targets = []
    for m in re.finditer(r"ข้อ\s*\d+(?:\s*[\.:]\s*\d+)?", text):
        targets.append(m.group(0).replace(' ', ''))
        if len(targets) >= 6:
            break
    if not targets:
        # Try year targets
        yrs = re.findall(r"(25\d{2}|26\d{2})", text)
        if yrs:
            targets = [f"ประกาศปี{yrs[0]}"]
    return delta_type, ", ".join(targets)


def _reg_doc_type_from_text(text: str, source_path: str) -> str:
    basis = f"{Path(source_path).name}\n{text}"
    if _COVID_HINT_RE.search(basis):
        return 'covid'
    if re.search(r"(academic\s*calendar|ปฏิทินการศึกษา|ปฏิทิน|กำหนดการ|calendar)", basis, re.IGNORECASE) and len(_DATE_LIKE_RE.findall(basis)) >= 2:
        return 'calendar'
    if re.search(r"(แบบฟอร์ม|form)", basis, re.IGNORECASE) and _URL_RE.search(basis):
        return 'form'
    if _EMAIL_RE.search(basis) and (_PHONE_RE.search(basis) or re.search(r"(โทร|ติดต่อ)", basis)):
        return 'contact'
    if _DELTA_DOC_HINT_RE.search(basis) or _DELTA_HINT_RE.search(basis):
        return 'amendment'
    amount_hits = len(re.findall(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b\s*บาท", basis))
    if _FEE_HINT_RE.search(basis) and (amount_hits >= 2 or re.search(r"(อัตราค่าธรรมเนียม|ตาราง)", basis)):
        return 'fee'
    if re.search(r"(ข้อบังคับ)", basis):
        return 'bylaw'
    return 'regulation'


def _infer_reg_topic(text: str, source_path: str) -> str:
    basis = f"{Path(source_path).name}\n{text}"
    mapping = [
        ('grad_study', re.compile(r"(บัณฑิตศึกษา|ป\.เอก|ป\.โท|graduate)", re.IGNORECASE)),
        ('undergrad_study', re.compile(r"(ป\.ตรี|ปริญญาตรี|undergraduate)", re.IGNORECASE)),
        ('exam', re.compile(r"(สอบ|exam)", re.IGNORECASE)),
        ('discipline', re.compile(r"(วินัย|discipline)", re.IGNORECASE)),
        ('privacy', re.compile(r"(ข้อมูลส่วนบุคคล|PDPA|privacy)", re.IGNORECASE)),
        ('covid', _COVID_HINT_RE),
        ('obem', re.compile(r"(OBEM|โมดูล|module|buffer\s*class)", re.IGNORECASE)),
        ('fees', re.compile(r"(ค่าธรรมเนียม|fee|อัตรา|บาท)", re.IGNORECASE)),
        ('external_learner', re.compile(r"(ผู้เรียนรู้|external\s*learner)", re.IGNORECASE)),
    ]
    for label, patt in mapping:
        if patt.search(basis):
            return label
    # fallback to shared hints
    return _infer_topic(text, source_path)


def _split_definition_terms(block_lines: List[str]) -> List[tuple[str, List[str]]]:
    """Return list of (term, definition_lines)."""
    out: List[tuple[str, List[str]]] = []
    buf_term = ''
    buf_lines: List[str] = []

    def _flush():
        nonlocal buf_term, buf_lines
        if buf_term and buf_lines:
            out.append((buf_term.strip('“”"\''), buf_lines[:]))
        buf_term = ''
        buf_lines = []

    term_re = re.compile(r"^(?:[\-\•\–]\s*)?[“\"]?(?P<term>[^\"”]{2,60})[”\"]?\s*(?:หมายถึง|หมายความว่า|ให้หมายความว่า)\b")
    for ln in block_lines:
        s = (ln or '').strip()
        if not s:
            continue
        m = term_re.match(s)
        if m:
            _flush()
            buf_term = (m.group('term') or '').strip()
            buf_lines = [s]
        else:
            if buf_lines:
                buf_lines.append(s)
    _flush()
    return out


def _announcement_doc_type_from_text(text: str, source_path: str) -> str:
    name = Path(source_path).name
    basis = f"{name}\n{text}"
    # Calendar: require explicit calendar keyword or multiple date-like lines.
    if re.search(r"(academic\s*calendar|ปฏิทินการศึกษา)", basis, re.IGNORECASE):
        return 'calendar'
    date_hits = len(_DATE_LIKE_RE.findall(basis))
    if _SEMESTER_RE.search(basis) and date_hits >= 3:
        return 'calendar'

    # Memo: require explicit memo keywords or formal letter structure.
    if re.search(r"(บันทึกข้อความ|หนังสือราชการ)", basis):
        return 'memo'
    # Common formal letter lines
    if re.search(r"(^ที่\s*\S+\s*$|^เรียน\s+|^อ้างถึง\s+)", basis, re.MULTILINE):
        return 'memo'

    # Regulation/guideline vs announcement
    if re.search(r"ระเบียบ", basis):
        return 'regulation'
    if re.search(r"แนวปฏิบัติ|คู่มือ|guideline", basis, re.IGNORECASE):
        return 'guideline'

    return 'announcement'


def _pack_lines_to_chunks(
    *,
    source_path: str,
    resolved_source: str,
    resolved_path: str,
    pages: List[int],
    lines: List[str],
    base_meta: Dict,
    section: str,
    clause_id: str = '',
    extra_meta: Optional[Dict] = None,
) -> List[Dict]:
    out: List[Dict] = []
    cur_lines: List[str] = []
    cur_pages: List[int] = []
    cur_tokens = 0
    overlap_prefix: Optional[str] = None

    def _sent_tail(text: str, want_tokens: int) -> Optional[str]:
        if not text or want_tokens <= 0:
            return None
        flat = " ".join(text.split())
        if not flat:
            return None
        sents = segment_sentences_thai(flat) or [flat]
        sents = [s.strip() for s in sents if s and s.strip()]
        if not sents:
            return None
        buf: List[str] = []
        for s in reversed(sents):
            buf.insert(0, s)
            if est_tokens(" ".join(buf)) >= want_tokens:
                break
        tail = " ".join(buf).strip()
        if est_tokens(tail) >= max(1, int(0.8 * est_tokens(flat))):
            return None
        return tail

    def _emit(final_lines: List[str], final_pages: List[int], allow_overlap: bool):
        nonlocal overlap_prefix
        text = "\n".join([ln for ln in final_lines if ln and ln.strip()]).strip()
        if not text:
            return
        pages_int = [int(p) for p in final_pages if isinstance(p, int) or str(p).isdigit()]
        page_start = min(pages_int) if pages_int else 0
        page_end = max(pages_int) if pages_int else 0
        source_file = Path(source_path).name
        clause_part = clause_id or section
        chunk_uid_basis = f"{source_file}|{base_meta.get('year_be','')}|{base_meta.get('doc_type','')}|{clause_part}|{len(out)}"
        chunk_uid = hashlib.sha1(chunk_uid_basis.encode('utf-8', 'ignore')).hexdigest()[:32]
        meta = {
            **base_meta,
            'source': resolved_source,
            'path': resolved_path,
            'page': page_start,
            'page_start': page_start,
            'page_end': page_end,
            'owner': 'owner:unknown',
            'sensitivity': 'internal',
            'updated_at': int(time.time()),
            'text': text,
            'tokens_est': est_tokens(text),
            'section': section,
            'clause_id': clause_id,
            'source_file': source_file,
            'chunk_uid': chunk_uid,
            'source_priority': _source_priority(source_path),
        }
        if extra_meta:
            meta.update(extra_meta)
        out.append(meta)
        if allow_overlap and CHUNK_OVERLAP_RATIO > 0:
            want = int(max(1, round(CHUNK_OVERLAP_RATIO * est_tokens(text))))
            overlap_prefix = _sent_tail(text, want)
        else:
            overlap_prefix = None

    def _flush(allow_overlap: bool):
        nonlocal cur_lines, cur_pages, cur_tokens
        if not cur_lines:
            return
        if overlap_prefix:
            final = [overlap_prefix] + cur_lines
        else:
            final = cur_lines
        _emit(final, cur_pages, allow_overlap=allow_overlap)
        cur_lines = []
        cur_pages = []
        cur_tokens = 0

    for ln, pg in zip(lines, pages or [0] * len(lines)):
        s = (ln or '').strip()
        if not s:
            continue
        t = est_tokens(s)
        if cur_lines and (cur_tokens + t > CHUNK_MAX_TOKENS):
            _flush(allow_overlap=(cur_tokens >= CHUNK_MIN_TOKENS))
        cur_lines.append(s)
        cur_pages.append(int(pg) if isinstance(pg, int) or str(pg).isdigit() else 0)
        cur_tokens += t
    _flush(allow_overlap=False)
    return out


def _make_chunks_announcement_template(paragraphs: List[Dict], source_path: str) -> List[Dict]:
    resolved_source = normalize_doc_name(source_path)
    resolved_path = str(Path(source_path).resolve())

    # Flatten into lines with page association
    lines: List[str] = []
    pages: List[int] = []
    for p in paragraphs:
        page_raw = p.get('page', 0)
        try:
            page = int(page_raw) if page_raw is not None else 0
        except (ValueError, TypeError):
            page = 0
        txt = (p.get('text') or '').strip()
        if not txt:
            continue
        for ln in txt.splitlines():
            s = (ln or '').strip()
            if not s:
                continue
            lines.append(s)
            pages.append(page)

    full_text = "\n".join(lines)
    doc_title = _infer_doc_title(lines, source_path)
    year_be = _extract_year_be_from_text_or_source(full_text, source_path)
    doc_type = _announcement_doc_type_from_text(full_text, source_path)
    topic = _infer_topic(full_text, source_path)
    audience = _infer_audience(full_text)
    effective_from = _infer_effective_from(full_text)

    base_meta: Dict = {
        'doc_title': doc_title,
        'doc_type': doc_type,
        'topic': topic,
        'year_be': year_be,
        'effective_from': effective_from,
        'audience': audience,
    }

    chunks: List[Dict] = []

    # Detect clause starts
    clause_starts = []
    for i, ln in enumerate(lines):
        if _CLAUSE_RE.match(ln):
            clause_starts.append(i)
    has_clauses = len(clause_starts) >= 2

    # Header: before first clause / before first dense table / before first semester
    header_end = len(lines)
    candidates = []
    if clause_starts:
        candidates.append(clause_starts[0])
    for i, ln in enumerate(lines[:120]):
        if _SEMESTER_RE.search(ln):
            candidates.append(i)
            break
        if (i > 8 and _TABLE_HINT_RE.search(ln) and _TABLE_ROWISH_RE.search(ln)):
            candidates.append(i)
            break
    if candidates:
        header_end = min(candidates)
    header_lines = lines[:header_end]
    header_pages = pages[:header_end]
    if header_lines:
        chunks.extend(_pack_lines_to_chunks(
            source_path=source_path,
            resolved_source=resolved_source,
            resolved_path=resolved_path,
            pages=header_pages,
            lines=header_lines,
            base_meta=base_meta,
            section='header',
            clause_id='header',
        ))

    # Definitions: look for "ในประกาศนี้" or "หมายถึง"
    def_idx = None
    for i, ln in enumerate(lines[:500]):
        if re.search(r"(ในประกาศนี้|คำจำกัดความ|นิยาม|หมายถึง)", ln):
            def_idx = i
            break
    if def_idx is not None:
        # collect until next clause start or 30 lines
        end = min(len(lines), def_idx + 40)
        for j in range(def_idx + 1, end):
            if _CLAUSE_RE.match(lines[j]):
                end = j
                break
        defs_lines = lines[def_idx:end]
        defs_pages = pages[def_idx:end]
        chunks.extend(_pack_lines_to_chunks(
            source_path=source_path,
            resolved_source=resolved_source,
            resolved_path=resolved_path,
            pages=defs_pages,
            lines=defs_lines,
            base_meta=base_meta,
            section='definitions',
            clause_id='definitions',
        ))

    # Calendar: chunk by semester + activity
    if doc_type == 'calendar':
        cur_sem = ''
        cur_act_lines: List[str] = []
        cur_act_pages: List[int] = []

        def _flush_activity(clause_id: str):
            nonlocal cur_act_lines, cur_act_pages
            if not cur_act_lines:
                return
            chunks.extend(_pack_lines_to_chunks(
                source_path=source_path,
                resolved_source=resolved_source,
                resolved_path=resolved_path,
                pages=cur_act_pages,
                lines=cur_act_lines,
                base_meta={**base_meta, 'doc_type': 'calendar'},
                section='calendar',
                clause_id=clause_id,
            ))
            cur_act_lines = []
            cur_act_pages = []

        for ln, pg in zip(lines, pages):
            m = _SEMESTER_RE.search(ln)
            if m:
                _flush_activity(f"{cur_sem}:activity" if cur_sem else 'calendar:activity')
                cur_sem = " ".join(m.group(0).split())
                # start new with semester header
                cur_act_lines = [cur_sem]
                cur_act_pages = [pg]
                continue
            # Start a new activity on date-like lines if already have enough content
            if _DATE_LIKE_RE.search(ln) and cur_act_lines and est_tokens("\n".join(cur_act_lines)) >= CHUNK_MIN_TOKENS:
                _flush_activity(f"{cur_sem}:activity" if cur_sem else 'calendar:activity')
            if cur_sem:
                cur_act_lines.append(ln)
                cur_act_pages.append(pg)
        _flush_activity(f"{cur_sem}:activity" if cur_sem else 'calendar:activity')

        for idx, ch in enumerate(chunks):
            ch.setdefault('chunk_id', idx)
        return chunks

    # Memo: context/actions/effective
    if _MEMO_HINT_RE.search(full_text):
        # naive split: context until first "ขอให้/ให้/โปรด"; actions after
        ctx_end = None
        for i, ln in enumerate(lines):
            if re.search(r"(ขอให้|ให้|โปรด|จึงเรียนมาเพื่อ)", ln):
                ctx_end = i
                break
        if ctx_end is None:
            ctx_end = min(len(lines), 40)
        ctx_lines = lines[:ctx_end]
        ctx_pages = pages[:ctx_end]
        chunks.extend(_pack_lines_to_chunks(
            source_path=source_path,
            resolved_source=resolved_source,
            resolved_path=resolved_path,
            pages=ctx_pages,
            lines=ctx_lines,
            base_meta={**base_meta, 'doc_type': 'memo'},
            section='context',
            clause_id='context',
        ))
        act_lines = lines[ctx_end:]
        act_pages = pages[ctx_end:]
        chunks.extend(_pack_lines_to_chunks(
            source_path=source_path,
            resolved_source=resolved_source,
            resolved_path=resolved_path,
            pages=act_pages,
            lines=act_lines,
            base_meta={**base_meta, 'doc_type': 'memo'},
            section='action',
            clause_id='action',
        ))
        # Effective chunk if any effective marker exists
        if _EFFECTIVE_HINT_RE.search(full_text):
            eff_lines = [ln for ln in lines if _EFFECTIVE_HINT_RE.search(ln)]
            eff_pages = [pages[i] for i, ln in enumerate(lines) if _EFFECTIVE_HINT_RE.search(ln)]
            chunks.extend(_pack_lines_to_chunks(
                source_path=source_path,
                resolved_source=resolved_source,
                resolved_path=resolved_path,
                pages=eff_pages,
                lines=eff_lines,
                base_meta={**base_meta, 'doc_type': 'memo'},
                section='effective',
                clause_id='effective',
            ))

        for idx, ch in enumerate(chunks):
            ch.setdefault('chunk_id', idx)
        return chunks

    # Delta amendments
    if _DELTA_HINT_RE.search(full_text):
        delta_type, targets = _infer_delta_info(full_text)
        extra = {
            'delta_type': delta_type,
            'targets': targets,
            'amends': targets,
            'supersedes': targets,
        }
        chunks.extend(_pack_lines_to_chunks(
            source_path=source_path,
            resolved_source=resolved_source,
            resolved_path=resolved_path,
            pages=pages,
            lines=lines,
            base_meta=base_meta,
            section='delta',
            clause_id='delta',
            extra_meta=extra,
        ))
        for idx, ch in enumerate(chunks):
            ch.setdefault('chunk_id', idx)
        return chunks

    # Clause-based docs (A)
    if has_clauses:
        for ci, start in enumerate(clause_starts):
            end = clause_starts[ci + 1] if ci + 1 < len(clause_starts) else len(lines)
            block_lines = lines[start:end]
            block_pages = pages[start:end]
            head = block_lines[0] if block_lines else ''
            m = _CLAUSE_RE.match(head)
            clause_id = ''
            parent_num = None
            if m:
                clause_id = f"ข้อ {m.group('num')}" + (f".{m.group('sub')}" if m.group('sub') else '')
                parent_num = m.group('num')

            # Subclause split (5.1, 5.2)
            sub_starts = []
            if parent_num and parent_num.isdigit():
                parent_sub_re = re.compile(rf"^{re.escape(parent_num)}\\.(\\d+)\\b")
                for i2, ln in enumerate(block_lines[1:], start=1):
                    if parent_sub_re.match(ln.strip()):
                        sub_starts.append(i2)
            if sub_starts:
                # emit pre-sub content as parent clause
                pre = block_lines[: sub_starts[0]]
                pre_p = block_pages[: sub_starts[0]]
                if len(pre) > 1:
                    chunks.extend(_pack_lines_to_chunks(
                        source_path=source_path,
                        resolved_source=resolved_source,
                        resolved_path=resolved_path,
                        pages=pre_p,
                        lines=pre,
                        base_meta=base_meta,
                        section='clause',
                        clause_id=clause_id or head,
                    ))
                for si, ss in enumerate(sub_starts):
                    ee = sub_starts[si + 1] if si + 1 < len(sub_starts) else len(block_lines)
                    sub_lines = [block_lines[0]] + block_lines[ss:ee]
                    sub_pages = [block_pages[0]] + block_pages[ss:ee]
                    sub_id = clause_id
                    if parent_num:
                        sm = re.match(rf"^{re.escape(parent_num)}\\.(\\d+)\\b", block_lines[ss].strip())
                        if sm:
                            sub_id = f"ข้อ {parent_num}.{sm.group(1)}"
                    chunks.extend(_pack_lines_to_chunks(
                        source_path=source_path,
                        resolved_source=resolved_source,
                        resolved_path=resolved_path,
                        pages=sub_pages,
                        lines=sub_lines,
                        base_meta=base_meta,
                        section='clause',
                        clause_id=sub_id or (clause_id + ':sub'),
                    ))
            else:
                # If this clause contains a table, split table rows into a dedicated table chunk.
                table_start = None
                for i2, ln in enumerate(block_lines):
                    if i2 == 0:
                        continue
                    if 'ตาราง' in ln or (_TABLE_HINT_RE.search(ln) and _TABLE_ROWISH_RE.search(ln)):
                        table_start = i2
                        break
                if table_start is not None and table_start >= 1:
                    pre_lines = block_lines[:table_start]
                    pre_pages = block_pages[:table_start]
                    tbl_lines = block_lines[table_start:]
                    tbl_pages = block_pages[table_start:]
                    if pre_lines:
                        chunks.extend(_pack_lines_to_chunks(
                            source_path=source_path,
                            resolved_source=resolved_source,
                            resolved_path=resolved_path,
                            pages=pre_pages,
                            lines=pre_lines,
                            base_meta=base_meta,
                            section='clause',
                            clause_id=clause_id or head,
                        ))
                    # Extract simple table keys (ranges/amounts) for rerank/filtering
                    keys = []
                    for ln in tbl_lines:
                        for m2 in re.finditer(r"(<\s*\d+(?:\.\d+)?|>=\s*\d+(?:\.\d+)?|>\s*\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*[-–]\s*\d+(?:\.\d+)?|\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*บาท)", ln):
                            k = " ".join(m2.group(0).split())
                            if k not in keys:
                                keys.append(k)
                            if len(keys) >= 12:
                                break
                        if len(keys) >= 12:
                            break
                    extra_meta = {'table_keys': "; ".join(keys)} if keys else None
                    chunks.extend(_pack_lines_to_chunks(
                        source_path=source_path,
                        resolved_source=resolved_source,
                        resolved_path=resolved_path,
                        pages=tbl_pages,
                        lines=tbl_lines,
                        base_meta=base_meta,
                        section='table',
                        clause_id=f"{clause_id}:table" if clause_id else 'table',
                        extra_meta=extra_meta,
                    ))
                else:
                    chunks.extend(_pack_lines_to_chunks(
                        source_path=source_path,
                        resolved_source=resolved_source,
                        resolved_path=resolved_path,
                        pages=block_pages,
                        lines=block_lines,
                        base_meta=base_meta,
                        section='clause',
                        clause_id=clause_id or head,
                    ))

        for idx, ch in enumerate(chunks):
            ch.setdefault('chunk_id', idx)
        return chunks

    # Fallback: sentence window
    fallback = _make_chunks_sentence_window(paragraphs, source_path)
    for f in fallback:
        # attach basic announcement metadata
        f.setdefault('doc_title', doc_title)
        f.setdefault('doc_type', 'announcement')
        f.setdefault('topic', topic)
        f.setdefault('year_be', year_be)
        f.setdefault('effective_from', effective_from)
        f.setdefault('audience', audience)
        f.setdefault('clause_id', '')
    return fallback


def _make_chunks_regulation_template(paragraphs: List[Dict], source_path: str) -> List[Dict]:
    resolved_source = normalize_doc_name(source_path)
    resolved_path = str(Path(source_path).resolve())

    lines: List[str] = []
    pages: List[int] = []
    for p in paragraphs:
        page_raw = p.get('page', 0)
        try:
            page = int(page_raw) if page_raw is not None else 0
        except (ValueError, TypeError):
            page = 0
        txt = (p.get('text') or '').strip()
        if not txt:
            continue
        for ln in txt.splitlines():
            s = (ln or '').strip()
            if not s:
                continue
            lines.append(s)
            pages.append(page)

    full_text = "\n".join(lines)
    doc_title = _infer_doc_title(lines, source_path)
    year_be = _extract_year_be_from_text_or_source(full_text, source_path)
    doc_type = _reg_doc_type_from_text(full_text, source_path)
    topic = _infer_reg_topic(full_text, source_path)
    effective_from = _infer_effective_from(full_text)
    effective_to = _infer_effective_to(full_text)
    delta_type, targets = _infer_delta_info(full_text)
    base_meta: Dict = {
        'doc_title': doc_title,
        'doc_type': doc_type,
        'topic': topic,
        'year_be': year_be,
        'effective_from': effective_from,
        'effective_to': effective_to,
        'amends': targets if _AMENDS_HINT_RE.search(full_text) else '',
        'supersedes': targets if _SUPERSEDES_HINT_RE.search(full_text) else '',
    }

    chunks: List[Dict] = []

    if doc_type == 'contact':
        cur: List[str] = []
        cur_pages: List[int] = []
        cur_has_email = False

        def flush():
            nonlocal cur, cur_pages, cur_has_email
            if not cur:
                return
            text = "\n".join(cur).strip()
            email = _EMAIL_RE.search(text)
            phone = _PHONE_RE.search(text)
            person = ''
            for ln in cur[:6]:
                if _EMAIL_RE.search(ln) or _PHONE_RE.search(ln):
                    continue
                if len(ln.strip()) >= 2:
                    person = ln.strip()[:80]
                    break
            extra = {
                'section_path': 'Directory > Contacts',
                'person_name': person,
                'email': email.group(0) if email else '',
                'phone': phone.group(0) if phone else '',
            }
            chunks.extend(_pack_lines_to_chunks(
                source_path=source_path,
                resolved_source=resolved_source,
                resolved_path=resolved_path,
                pages=cur_pages,
                lines=cur,
                base_meta={**base_meta, 'doc_type': 'contact'},
                section='contact',
                clause_id=person or 'contact',
                extra_meta=extra,
            ))
            cur = []
            cur_pages = []
            cur_has_email = False

        for ln, pg in zip(lines, pages):
            if cur_has_email and _EMAIL_RE.search(ln):
                flush()
            cur.append(ln)
            cur_pages.append(pg)
            if _EMAIL_RE.search(ln):
                cur_has_email = True
            if est_tokens("\n".join(cur)) >= min(CHUNK_MAX_TOKENS, 220):
                flush()
        flush()
        for idx, ch in enumerate(chunks):
            ch.setdefault('chunk_id', idx)
        return chunks

    if doc_type == 'form':
        cur: List[str] = []
        cur_pages: List[int] = []

        def flush():
            nonlocal cur, cur_pages
            if not cur:
                return
            text = "\n".join(cur).strip()
            urlm = _URL_RE.search(text)
            form_name = (cur[0] if cur else '')[:120]
            purpose = (cur[1] if len(cur) > 1 else '')[:200]
            extra = {
                'section_path': 'Directory > Forms',
                'form_name_th': form_name,
                'purpose': purpose,
                'url': urlm.group(0) if urlm else '',
            }
            chunks.extend(_pack_lines_to_chunks(
                source_path=source_path,
                resolved_source=resolved_source,
                resolved_path=resolved_path,
                pages=cur_pages,
                lines=cur,
                base_meta={**base_meta, 'doc_type': 'form'},
                section='form',
                clause_id=form_name or 'form',
                extra_meta=extra,
            ))
            cur = []
            cur_pages = []

        for ln, pg in zip(lines, pages):
            cur.append(ln)
            cur_pages.append(pg)
            if _URL_RE.search(ln):
                flush()
            elif len(cur) >= 6 and est_tokens("\n".join(cur)) >= 180:
                flush()
        flush()
        for idx, ch in enumerate(chunks):
            ch.setdefault('chunk_id', idx)
        return chunks

    if doc_type == 'fee':
        header_lines = lines[: min(len(lines), 40)]
        header_pages = pages[: min(len(pages), 40)]
        chunks.extend(_pack_lines_to_chunks(
            source_path=source_path,
            resolved_source=resolved_source,
            resolved_path=resolved_path,
            pages=header_pages,
            lines=header_lines,
            base_meta={**base_meta, 'doc_type': 'fee'},
            section='header',
            clause_id='fee:header',
            extra_meta={'section_path': 'Fee > Header'},
        ))
        for ln, pg in zip(lines, pages):
            if re.search(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b\s*บาท", ln):
                keys = []
                for m2 in re.finditer(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*บาท", ln):
                    keys.append(m2.group(0))
                    if len(keys) >= 8:
                        break
                extra = {
                    'section_path': 'Fee > Item',
                    'table_keys': "; ".join(keys) if keys else '',
                }
                chunks.extend(_pack_lines_to_chunks(
                    source_path=source_path,
                    resolved_source=resolved_source,
                    resolved_path=resolved_path,
                    pages=[pg],
                    lines=[ln],
                    base_meta={**base_meta, 'doc_type': 'fee'},
                    section='fee_item',
                    clause_id=ln[:60],
                    extra_meta=extra,
                ))
        for idx, ch in enumerate(chunks):
            ch.setdefault('chunk_id', idx)
        return chunks

    if doc_type == 'amendment':
        marks = [i for i, ln in enumerate(lines) if _DELTA_CHANGE_MARK_RE.search(ln)]
        if not marks:
            marks = [0]
        blocks: List[tuple[List[str], List[int]]] = []
        for bi, start in enumerate(marks):
            end = marks[bi + 1] if bi + 1 < len(marks) else len(lines)
            if start == end:
                continue
            blocks.append((lines[start:end], pages[start:end]))
        if not blocks:
            blocks = [(lines, pages)]

        for bi, (b_lines, b_pages) in enumerate(blocks):
            txt = "\n".join(b_lines)
            d_type, targs = _infer_delta_info(txt)
            tcl = ''
            m = re.search(r"ข้อ\s*\d+(?:\.\d+)*", txt)
            if m:
                tcl = m.group(0).replace(' ', '')
                tcl = tcl.replace('ข้อ', 'ข้อ ')
            extra = {
                'section_path': 'Delta',
                'delta_type': d_type or delta_type,
                'targets': targs or targets,
                'target_clause': tcl,
                'amends': targs or targets,
                'supersedes': targs or targets,
            }
            chunks.extend(_pack_lines_to_chunks(
                source_path=source_path,
                resolved_source=resolved_source,
                resolved_path=resolved_path,
                pages=b_pages,
                lines=b_lines,
                base_meta={**base_meta, 'doc_type': 'amendment'},
                section='delta',
                clause_id=tcl or f"delta:{bi+1}",
                extra_meta=extra,
            ))

        for idx, ch in enumerate(chunks):
            ch.setdefault('chunk_id', idx)
        return chunks

    if doc_type == 'calendar':
        cur_sem = ''
        cur_lines: List[str] = []
        cur_pages: List[int] = []

        def flush():
            nonlocal cur_lines, cur_pages
            if not cur_lines:
                return
            sem = cur_sem or 'calendar'
            chunks.extend(_pack_lines_to_chunks(
                source_path=source_path,
                resolved_source=resolved_source,
                resolved_path=resolved_path,
                pages=cur_pages,
                lines=cur_lines,
                base_meta={**base_meta, 'doc_type': 'calendar'},
                section='calendar',
                clause_id=sem,
                extra_meta={'section_path': f"Calendar > {sem}"},
            ))
            cur_lines = []
            cur_pages = []

        for ln, pg in zip(lines, pages):
            m = _SEMESTER_RE.search(ln)
            if m:
                flush()
                cur_sem = " ".join(m.group(0).split())
                cur_lines = [cur_sem]
                cur_pages = [pg]
                continue
            if _DATE_LIKE_RE.search(ln) and cur_lines and est_tokens("\n".join(cur_lines)) >= CHUNK_MAX_TOKENS:
                flush()
            cur_lines.append(ln)
            cur_pages.append(pg)
        flush()
        for idx, ch in enumerate(chunks):
            ch.setdefault('chunk_id', idx)
        return chunks

    if doc_type == 'covid':
        semester_scope = ''
        for ln in lines[:200]:
            m = _SEMESTER_RE.search(ln)
            if m:
                semester_scope = " ".join(m.group(0).split())
                break
        cur: List[str] = []
        cur_pages: List[int] = []
        cur_head = ''

        def flush():
            nonlocal cur, cur_pages, cur_head
            if not cur:
                return
            sec = cur_head or 'covid'
            chunks.extend(_pack_lines_to_chunks(
                source_path=source_path,
                resolved_source=resolved_source,
                resolved_path=resolved_path,
                pages=cur_pages,
                lines=cur,
                base_meta={**base_meta, 'doc_type': 'covid'},
                section='covid',
                clause_id=sec,
                extra_meta={'section_path': f"COVID > {sec}", 'semester_scope': semester_scope},
            ))
            cur = []
            cur_pages = []

        for ln, pg in zip(lines, pages):
            if is_heading(ln):
                if cur and est_tokens("\n".join(cur)) >= CHUNK_MIN_TOKENS:
                    flush()
                cur_head = ln[:80]
            cur.append(ln)
            cur_pages.append(pg)
            if est_tokens("\n".join(cur)) >= CHUNK_MAX_TOKENS:
                flush()
        flush()
        for idx, ch in enumerate(chunks):
            ch.setdefault('chunk_id', idx)
        return chunks

    # regulation/bylaw main (T1)
    clause_starts: List[int] = []
    chapter = ''
    chapter_at: Dict[int, str] = {}
    for i, ln in enumerate(lines):
        cm = _REG_CHAPTER_RE.match(ln)
        if cm:
            chapter = " ".join(ln.split())
        if _REG_CLAUSE_RE.match(ln):
            clause_starts.append(i)
            chapter_at[i] = chapter

    fm_end = clause_starts[0] if clause_starts else min(len(lines), 80)
    if clause_starts:
        for ci, st in enumerate(clause_starts[:6]):
            m = _REG_CLAUSE_RE.match(lines[st])
            if m and int(m.group('num')) <= 3:
                nxt = clause_starts[ci + 1] if ci + 1 < len(clause_starts) else len(lines)
                fm_end = max(fm_end, nxt)
            else:
                break
    fm_lines = lines[:fm_end]
    fm_pages = pages[:fm_end]
    if fm_lines:
        chunks.extend(_pack_lines_to_chunks(
            source_path=source_path,
            resolved_source=resolved_source,
            resolved_path=resolved_path,
            pages=fm_pages,
            lines=fm_lines,
            base_meta=base_meta,
            section='front_matter',
            clause_id='front_matter',
            extra_meta={'section_path': 'FrontMatter'},
        ))

    for ci, start in enumerate(clause_starts):
        end = clause_starts[ci + 1] if ci + 1 < len(clause_starts) else len(lines)
        block_lines = lines[start:end]
        block_pages = pages[start:end]
        head = block_lines[0] if block_lines else ''
        m = _REG_CLAUSE_RE.match(head)
        if not m:
            continue
        num = m.group('num')
        rest = (m.group('rest') or '').strip()
        clause_id = f"ข้อ {num}{rest}".strip()
        chp = (chapter_at.get(start) or '').strip()
        section_path = f"{chp} > {clause_id}" if chp else clause_id

        def_signals = re.search(r"(ในระเบียบนี้|คำจำกัดความ|นิยาม|หมายถึง|ให้หมายความว่า)", "\n".join(block_lines))
        if def_signals:
            terms = _split_definition_terms(block_lines[1:])
            if terms:
                for term, t_lines in terms:
                    chunks.extend(_pack_lines_to_chunks(
                        source_path=source_path,
                        resolved_source=resolved_source,
                        resolved_path=resolved_path,
                        pages=block_pages,
                        lines=[head] + t_lines,
                        base_meta=base_meta,
                        section='definition',
                        clause_id=clause_id,
                        extra_meta={'section_path': f"{section_path} > {term}", 'term': term},
                    ))
                continue

        sub_starts: List[int] = []
        sub_re = re.compile(rf"^{re.escape(num)}\\.(\\d+(?:\\.\\d+)*)\\b")
        for i2, ln in enumerate(block_lines[1:], start=1):
            if sub_re.match(ln.strip()):
                sub_starts.append(i2)

        if sub_starts:
            pre = block_lines[: sub_starts[0]]
            pre_p = block_pages[: sub_starts[0]]
            if len(pre) >= 2:
                chunks.extend(_pack_lines_to_chunks(
                    source_path=source_path,
                    resolved_source=resolved_source,
                    resolved_path=resolved_path,
                    pages=pre_p,
                    lines=pre,
                    base_meta=base_meta,
                    section='clause',
                    clause_id=clause_id,
                    extra_meta={'section_path': section_path},
                ))
            for si, ss in enumerate(sub_starts):
                ee = sub_starts[si + 1] if si + 1 < len(sub_starts) else len(block_lines)
                sm = sub_re.match(block_lines[ss].strip())
                sub_id = clause_id
                if sm:
                    sub_id = f"ข้อ {num}.{sm.group(1)}"
                sub_lines = [head] + block_lines[ss:ee]
                sub_pages = [block_pages[0]] + block_pages[ss:ee]
                chunks.extend(_pack_lines_to_chunks(
                    source_path=source_path,
                    resolved_source=resolved_source,
                    resolved_path=resolved_path,
                    pages=sub_pages,
                    lines=sub_lines,
                    base_meta=base_meta,
                    section='clause',
                    clause_id=sub_id,
                    extra_meta={'section_path': f"{section_path} > {sub_id}"},
                ))
            continue

        table_start = None
        for i2, ln in enumerate(block_lines):
            if i2 == 0:
                continue
            if 'ตาราง' in ln or 'ภาคผนวก' in ln or (_TABLE_HINT_RE.search(ln) and _TABLE_ROWISH_RE.search(ln)):
                table_start = i2
                break
        if table_start is not None and table_start >= 1:
            pre_lines = block_lines[:table_start]
            pre_pages = block_pages[:table_start]
            tbl_lines = block_lines[table_start:]
            tbl_pages = block_pages[table_start:]
            if pre_lines:
                chunks.extend(_pack_lines_to_chunks(
                    source_path=source_path,
                    resolved_source=resolved_source,
                    resolved_path=resolved_path,
                    pages=pre_pages,
                    lines=pre_lines,
                    base_meta=base_meta,
                    section='clause',
                    clause_id=clause_id,
                    extra_meta={'section_path': section_path},
                ))
            keys = []
            for ln in tbl_lines:
                for m2 in re.finditer(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*บาท", ln):
                    k = m2.group(0)
                    if k not in keys:
                        keys.append(k)
                    if len(keys) >= 12:
                        break
                if len(keys) >= 12:
                    break
            extra = {
                'section_path': f"{section_path} > Annex/Table",
                'table_keys': "; ".join(keys) if keys else '',
            }
            chunks.extend(_pack_lines_to_chunks(
                source_path=source_path,
                resolved_source=resolved_source,
                resolved_path=resolved_path,
                pages=tbl_pages,
                lines=tbl_lines,
                base_meta=base_meta,
                section='table',
                clause_id=f"{clause_id}:table",
                extra_meta=extra,
            ))
        else:
            chunks.extend(_pack_lines_to_chunks(
                source_path=source_path,
                resolved_source=resolved_source,
                resolved_path=resolved_path,
                pages=block_pages,
                lines=block_lines,
                base_meta=base_meta,
                section='clause',
                clause_id=clause_id,
                extra_meta={'section_path': section_path},
            ))

    for idx, ch in enumerate(chunks):
        ch.setdefault('chunk_id', idx)
    return chunks


def _normalize_course_code(raw: str) -> str:
    m = _COURSE_CODE_ANYWHERE_RE.search(raw.strip())
    if not m:
        return raw.strip()
    return f"{m.group('prefix').upper()} {m.group('num')}"


def _parse_course_names(header_line: str) -> tuple[str, str]:
    """Return (course_th, course_en) best-effort from a header line."""
    s = header_line.strip()
    s = _COURSE_CODE_RE.sub('', s, count=1).strip()
    if not s:
        return '', ''
    # Pattern: Thai (English)
    m = re.search(r"\(([^\)]*)\)", s)
    if m:
        inside = (m.group(1) or '').strip()
        before = s[: m.start()].strip(' -–—:\t')
        if re.search(r"[A-Za-z]", inside):
            return before, inside
    # Split by common separators: "-" or ":" to find English tail
    parts = re.split(r"\s[-–—:]\s", s, maxsplit=1)
    if len(parts) == 2 and re.search(r"[A-Za-z]", parts[1]):
        return parts[0].strip(), parts[1].strip()
    # If line is mostly English
    if re.search(r"[A-Za-z]", s) and not re.search(r"[ก-๙]", s):
        return '', s
    return s, ''


def _make_curriculum_course_chunk(
    *,
    source_path: str,
    resolved_source: str,
    resolved_path: str,
    pages: List[int],
    text: str,
    course_code: str,
    course_th: str,
    course_en: str,
    category: str,
    section: str,
    section_heading: str,
    doc_type: str,
    year: str,
    section_path: Optional[List[str]] = None,
    credits_breakdown: str = '',
    source_scope: str = '',
    learning_outcomes: Optional[List[str]] = None,
) -> Dict:
    pages_int = [int(p) for p in pages if isinstance(p, int) or str(p).isdigit()]
    page_start = min(pages_int) if pages_int else 0
    page_end = max(pages_int) if pages_int else 0
    source_file = Path(source_path).name

    # Keep IDs stable even if we improve year parsing.
    year_uid = ''
    m = re.search(r"(25\d{2}|26\d{2})", source_file)
    if m:
        year_uid = m.group(1)
    else:
        m = re.search(r"(25\d{2}|26\d{2})", text or '')
        if m:
            year_uid = m.group(1)

    chunk_uid_basis = f"{source_file}|{year_uid}|{course_code}|{doc_type}|{section}"
    chunk_uid = _sha1_32(chunk_uid_basis)
    course_code_norm = _course_code_norm(course_code)
    chunk_key = f"sha1:{chunk_uid}"
    canonical_key = f"{year}|{course_code_norm}|{doc_type}"

    credits_total = 0
    mct = re.match(r"\s*(\d+)", credits_breakdown or '')
    if mct:
        credits_total = _safe_int(mct.group(1), 0)
    return {
        'source': resolved_source,
        'path': resolved_path,
        'page': page_start,
        'page_start': page_start,
        'page_end': page_end,
        'owner': 'owner:unknown',
        'sensitivity': 'internal',
        'updated_at': int(time.time()),
        'text': text.strip(),
        'tokens_est': est_tokens(text),
        # Metadata for retrieval
        'doc_type': doc_type,
        'program': CURRICULUM_PROGRAM,
        'program_year': _safe_int(year, 0) or (year if year else ''),
        'course_code': course_code,
        'course_code_norm': course_code_norm,
        'course_code_raw': (course_code or '').strip(),
        'course_th': course_th,
        'course_en': course_en,
        'category': category,
        'credits_total': credits_total,
        'credits_breakdown': credits_breakdown,
        'section': section,
        'section_heading': section_heading,
        'section_path': section_path or ([section_heading] if section_heading else []),
        'lang': _infer_lang(text),
        'source_file': source_file,
        'source_scope': source_scope or (f"p{page_start}-p{page_end}" if page_start or page_end else ''),
        'year': year,
        'chunk_uid': chunk_uid,
        'chunk_key': chunk_key,
        'canonical_key': canonical_key,
        'priority': _source_priority(source_path),
        'source_priority': _source_priority(source_path),
        'learning_outcomes': learning_outcomes or [],
    }


def _make_chunks_curriculum_course(paragraphs: List[Dict], source_path: str) -> List[Dict]:
    """Course-centric chunking for curriculum domain.

        - Splits by course code lines: ^[A-Z]{3} + 3 digits
    - Within each course: keep description+LO in one chunk unless too long,
      then split into two chunks: CourseDescription and LearningOutcomes.
    - Adds rich metadata required for disambiguation and retrieval.
    """
    resolved_source = normalize_doc_name(source_path)
    resolved_path = str(Path(source_path).resolve())
    year = _extract_year_from_source(source_path)

    term_head_re = re.compile(r"(ชั้นปีที่\s*\d+|ปีที่\s*\d+).{0,30}(ภาค\s*\d|ภาคการศึกษาที่\s*\d|ภาคฤดูร้อน|ภาคพิเศษ)")

    # File-specific parsing: SSC.txt style: "SSC 241 : ..."
    name_lower = Path(source_path).name.lower()
    if 'ssc' in name_lower:
        lines: List[str] = []
        pages: List[int] = []
        for p in paragraphs:
            page = _safe_int(p.get('page', 0), 0)
            txt = (p.get('text') or '').strip()
            if not txt:
                continue
            for raw_ln in txt.splitlines():
                ln = (raw_ln or '').strip()
                if not ln:
                    continue
                lines.append(ln)
                pages.append(page)

        out: List[Dict] = []
        cur_code = ''
        cur_title = ''
        cur_lines: List[str] = []
        cur_pages: List[int] = []

        def flush():
            nonlocal cur_code, cur_title, cur_lines, cur_pages
            if not cur_code or not cur_lines:
                cur_code = ''
                cur_title = ''
                cur_lines = []
                cur_pages = []
                return
            code = f"SSC {cur_code}".strip()
            course_th, course_en = _parse_course_names(cur_title)
            text = "\n".join(cur_lines).strip()
            out.append(_make_curriculum_course_chunk(
                source_path=source_path,
                resolved_source=resolved_source,
                resolved_path=resolved_path,
                pages=cur_pages,
                text=text,
                course_code=code,
                course_th=course_th,
                course_en=course_en,
                category='SSC',
                section='CourseFull',
                section_heading='SSC',
                doc_type='course_full',
                year=year,
                section_path=['SSC', code],
            ))
            cur_code = ''
            cur_title = ''
            cur_lines = []
            cur_pages = []

        for ln, pg in zip(lines, pages):
            m = _SSC_COURSE_RE.match(ln)
            if m:
                flush()
                cur_code = m.group('num')
                cur_title = f"SSC {cur_code} : {m.group('title')}"
                cur_lines = [cur_title]
                cur_pages = [pg]
                continue
            if cur_code:
                cur_lines.append(ln)
                cur_pages.append(pg)
        flush()
        for idx, ch in enumerate(out):
            ch.setdefault('chunk_id', idx)
        return out

    # File-specific parsing: GE structure / GEN-LNG grouped lists
    if 'ge' in name_lower or 'gen' in name_lower or 'lng' in name_lower or 'ศึกษาทั่วไป' in name_lower:
        lines: List[str] = []
        pages: List[int] = []
        for p in paragraphs:
            page = _safe_int(p.get('page', 0), 0)
            txt = (p.get('text') or '').strip()
            if not txt:
                continue
            for raw_ln in txt.splitlines():
                ln = (raw_ln or '').strip()
                if not ln:
                    continue
                lines.append(ln)
                pages.append(page)

        out: List[Dict] = []
        joined = "\n".join(lines)

        # language framework chunk (optional)
        if _LANG_FRAMEWORK_RE.search(joined):
            fw_lines = []
            fw_pages = []
            for ln, pg in zip(lines, pages):
                if _LANG_FRAMEWORK_RE.search(ln):
                    fw_lines.append(ln)
                    fw_pages.append(pg)
                    if len(fw_lines) >= 60:
                        break
            if fw_lines:
                out.append(_make_curriculum_chunk(
                    source_path=source_path,
                    resolved_source=resolved_source,
                    resolved_path=resolved_path,
                    pages=fw_pages,
                    text="\n".join(fw_lines),
                    doc_type='language_framework',
                    year=year,
                    section='LanguageFramework',
                    section_heading='Language framework',
                    section_path=['LNG', 'Framework'],
                    clause_id='language_framework',
                ))

        # ge_structure: look for a dense credit-summary region
        struct_idx = None
        for i, ln in enumerate(lines[:2000]):
            if re.search(r"(ตารางที่\s*1|โครงสร้าง|รวม\s*31\s*หน่วยกิต|หมวดวิชาศึกษาทั่วไป)", ln):
                struct_idx = i
                break
        if struct_idx is not None:
            end = min(len(lines), struct_idx + 220)
            block = [x for x in lines[struct_idx:end] if x and x.strip()]
            if block:
                out.append(_make_curriculum_chunk(
                    source_path=source_path,
                    resolved_source=resolved_source,
                    resolved_path=resolved_path,
                    pages=pages[struct_idx:end],
                    text="\n".join(block),
                    doc_type='ge_structure',
                    year=year,
                    section='GEStructure',
                    section_heading='GE structure',
                    section_path=['GE', 'Structure'],
                    clause_id='ge_structure',
                ))

        # ge_group blocks + course_full per GEN/LNG row
        group_starts = [i for i, ln in enumerate(lines) if _GE_GROUP_RE.match(ln)]
        if group_starts:
            for gi, st in enumerate(group_starts[:120]):
                en = group_starts[gi + 1] if gi + 1 < len(group_starts) else min(len(lines), st + 500)
                ghead = lines[st][:160]
                block = [x for x in lines[st:en] if x and x.strip()]
                if not block:
                    continue
                out.append(_make_curriculum_chunk(
                    source_path=source_path,
                    resolved_source=resolved_source,
                    resolved_path=resolved_path,
                    pages=pages[st:en],
                    text="\n".join(block),
                    doc_type='ge_group',
                    year=year,
                    section='GEGroup',
                    section_heading=ghead,
                    section_path=['GE', ghead],
                    clause_id=ghead,
                ))

                # course rows inside group
                cur_code = ''
                cur_lines: List[str] = []
                cur_pages: List[int] = []

                def flush_course():
                    nonlocal cur_code, cur_lines, cur_pages
                    if not cur_code or not cur_lines:
                        cur_code = ''
                        cur_lines = []
                        cur_pages = []
                        return
                    course_code = _normalize_course_code(cur_code)
                    category = course_code.split(' ', 1)[0] if course_code else ''
                    course_th, course_en = _parse_course_names(cur_lines[0])
                    credits_breakdown = ''
                    cm = _CREDITS_HINT_RE.search(" ".join(cur_lines[:4]))
                    if cm:
                        credits_breakdown = f"{cm.group(1)} ({cm.group(2)})"
                    out.append(_make_curriculum_course_chunk(
                        source_path=source_path,
                        resolved_source=resolved_source,
                        resolved_path=resolved_path,
                        pages=cur_pages,
                        text="\n".join(cur_lines),
                        course_code=course_code,
                        course_th=course_th,
                        course_en=course_en,
                        category=category,
                        section='CourseFull',
                        section_heading=ghead,
                        doc_type='course_full',
                        year=year,
                        section_path=['GE', ghead, course_code],
                        credits_breakdown=credits_breakdown,
                    ))
                    cur_code = ''
                    cur_lines = []
                    cur_pages = []

                def _ge_looks_like_course_header(line: str) -> bool:
                    m = _COURSE_CODE_RE.match((line or '').strip())
                    if not m:
                        return False
                    rest = (line[m.end():] or '').strip()
                    if not rest:
                        return False
                    if _CREDITS_HINT_RE.search(line) or 'หน่วยกิต' in rest:
                        return True
                    if re.search(r"[ก-๙]", rest):
                        return True
                    if re.search(r"[A-Za-z]", rest) and len(rest) >= 6:
                        return True
                    return False

                for ln, pg in zip(lines[st:en], pages[st:en]):
                    m = _COURSE_CODE_RE.match(ln)
                    if m and _ge_looks_like_course_header(ln):
                        flush_course()
                        cur_code = f"{m.group('prefix')} {m.group('num')}"
                        cur_lines = [ln]
                        cur_pages = [pg]
                        continue
                    if cur_code:
                        cur_lines.append(ln)
                        cur_pages.append(pg)
                flush_course()

        for idx, ch in enumerate(out):
            ch.setdefault('chunk_id', idx)
        if out:
            return out

    prelude_lines: List[str] = []
    prelude_pages: List[int] = []
    prelude_line_nos: List[int] = []

    active_heading = ''
    current_heading = ''
    current_code = ''
    current_header_line = ''
    current_lines: List[str] = []
    current_pages: List[int] = []
    current_line_start = 0
    current_line_end = 0

    line_no = 0
    study_plan_hold = 0

    def _looks_like_course_header(line: str) -> bool:
        m = _COURSE_CODE_RE.match(line.strip())
        if not m:
            return False
        rest = (line[m.end():] or '').strip()
        if not rest:
            return False
        # Strong signals
        if _CREDITS_HINT_RE.search(line) or 'หน่วยกิต' in rest:
            return True
        if re.search(r"[ก-๙]", rest):
            return True
        if '(' in rest or ')' in rest or ':' in rest or '-' in rest or '–' in rest or '—' in rest:
            return True
        # English-only titles are possible; avoid mapping rows like "PLO1 1A 1B".
        if re.search(r"[A-Za-z]", rest) and not re.match(r"^PLO\s*\d+\b", rest, re.IGNORECASE) and len(rest) >= 8:
            return True
        return False

    def _flush_course(out: List[Dict]):
        nonlocal current_code, current_header_line, current_lines, current_pages, current_heading, current_line_start, current_line_end
        if not current_code or not current_lines:
            current_code = ''
            current_header_line = ''
            current_lines = []
            current_pages = []
            current_heading = ''
            current_line_start = 0
            current_line_end = 0
            return

        course_code = _normalize_course_code(current_code)
        category = course_code.split(' ', 1)[0] if course_code else ''
        course_th, course_en = _parse_course_names(current_header_line or current_lines[0])

        # Best-effort credits breakdown from header or nearby lines
        credits_breakdown = ''
        for probe in (current_header_line, " ".join(current_lines[:6])):
            if not probe:
                continue
            cm = _CREDITS_HINT_RE.search(probe)
            if cm:
                credits_breakdown = f"{cm.group(1)} ({cm.group(2)})"
                break

        section_path = []
        if current_heading:
            section_path.append(current_heading)
        if course_code:
            section_path.append(course_code)

        lines = [ln for ln in current_lines if ln and ln.strip()]
        full_text = "\n".join(lines).strip()
        if not full_text:
            current_code = ''
            current_header_line = ''
            current_lines = []
            current_pages = []
            current_heading = ''
            return

        # Split LO if present and long
        lo_idx = None
        for i, ln in enumerate(lines):
            if _LO_RE.search(ln):
                lo_idx = i
                break

        learning_outcomes = _extract_learning_outcomes(lines, lo_idx) if lo_idx is not None else []

        scope = ''
        if current_line_start and current_line_end:
            scope = f"p{min(current_pages) if current_pages else 0}-p{max(current_pages) if current_pages else 0}:l{current_line_start}-l{current_line_end}"

        if est_tokens(full_text) <= CHUNK_MAX_TOKENS or lo_idx is None:
            section = 'CourseFull'
            doc_type = 'course_full'
            out.append(_make_curriculum_course_chunk(
                source_path=source_path,
                resolved_source=resolved_source,
                resolved_path=resolved_path,
                pages=current_pages,
                text=full_text,
                course_code=course_code,
                course_th=course_th,
                course_en=course_en,
                category=category,
                section=section,
                section_heading=current_heading,
                doc_type=doc_type,
                year=year,
                section_path=section_path,
                credits_breakdown=credits_breakdown,
                source_scope=scope,
                learning_outcomes=learning_outcomes,
            ))
        else:
            desc_lines = lines[:lo_idx]
            lo_lines = lines[lo_idx:]
            desc_text = "\n".join(desc_lines).strip()
            lo_text = "\n".join(lo_lines).strip()
            if desc_text:
                out.append(_make_curriculum_course_chunk(
                    source_path=source_path,
                    resolved_source=resolved_source,
                    resolved_path=resolved_path,
                    pages=current_pages,
                    text=desc_text,
                    course_code=course_code,
                    course_th=course_th,
                    course_en=course_en,
                    category=category,
                    section='CourseDescription',
                    section_heading=current_heading,
                    doc_type='course_description',
                    year=year,
                    section_path=section_path + ['CourseDescription'],
                    credits_breakdown=credits_breakdown,
                    source_scope=scope,
                ))
            if lo_text:
                out.append(_make_curriculum_course_chunk(
                    source_path=source_path,
                    resolved_source=resolved_source,
                    resolved_path=resolved_path,
                    pages=current_pages,
                    text=lo_text,
                    course_code=course_code,
                    course_th=course_th,
                    course_en=course_en,
                    category=category,
                    section='LearningOutcomes',
                    section_heading=current_heading,
                    doc_type='course_learning_outcomes',
                    year=year,
                    section_path=section_path + ['LearningOutcomes'],
                    credits_breakdown=credits_breakdown,
                    source_scope=scope,
                    learning_outcomes=learning_outcomes,
                ))

        current_code = ''
        current_header_line = ''
        current_lines = []
        current_pages = []
        current_heading = ''
        current_line_start = 0
        current_line_end = 0

    chunks: List[Dict] = []

    # Scan line-by-line to handle table-like PDFs where multiple courses appear in one paragraph.
    for p in paragraphs:
        page_raw = p.get('page', 0)
        try:
            page = int(page_raw) if page_raw is not None else 0
        except (ValueError, TypeError):
            page = 0
        text = (p.get('text') or '').strip()
        if not text:
            continue
        if p.get('is_heading'):
            active_heading = text.strip()

        for raw_ln in text.splitlines():
            ln = (raw_ln or '').strip()
            if not ln:
                continue
            line_no += 1

            # Heuristic: when inside a study-plan table/list, keep course-code lines as part of plan
            # (do not start course chunks), because users ask by year/term and the plan table
            # should be chunked at the plan level.
            if not current_code:
                if re.search(r"(คำอธิบายรายวิชา|ภาคผนวก\s*ก|course\s+description)", ln, re.IGNORECASE):
                    study_plan_hold = 0
                if term_head_re.search(ln) or _STUDY_PLAN_RE.search(ln) or ln.startswith('แผน'):
                    study_plan_hold = max(study_plan_hold, 180)

            if not current_code and study_plan_hold > 0:
                prelude_lines.append(ln)
                prelude_pages.append(page)
                prelude_line_nos.append(line_no)
                study_plan_hold -= 1
                continue

            # Curriculum docs often have headings without punctuation; treat key markers as headings.
            if (
                _STRUCTURE_RE.search(ln)
                or _STUDY_PLAN_RE.search(ln)
                or ln.startswith('หมวด')
                or ln.startswith('โครงสร้าง')
                or ln.startswith('แผนการศึกษา')
                or ln.startswith('แผนการเรียน')
            ) and len(ln) <= 120:
                active_heading = ln

            m = _COURSE_CODE_RE.match(ln)
            if m and _looks_like_course_header(ln):
                # New course block begins
                _flush_course(chunks)
                current_code = f"{m.group('prefix')} {m.group('num')}"
                current_header_line = ln
                current_heading = active_heading
                current_lines = [ln]
                current_pages = [page]
                current_line_start = line_no
                current_line_end = line_no
                continue

            if current_code:
                current_lines.append(ln)
                current_pages.append(page)
                current_line_end = line_no
            else:
                prelude_lines.append(ln)
                prelude_pages.append(page)
                prelude_line_nos.append(line_no)

    _flush_course(chunks)

    # --- Extractions from non-course content (multi-granularity) ---
    prelude_text = "\n".join([x for x in prelude_lines if x and x.strip()]).strip()
    prelude_pages_int = [int(p) for p in prelude_pages if isinstance(p, int) or str(p).isdigit()]
    prelude_page_start = min(prelude_pages_int) if prelude_pages_int else 0
    prelude_page_end = max(prelude_pages_int) if prelude_pages_int else 0

    # Program profile (title/year/degree lines)
    prof_lines = []
    for ln in prelude_lines[:120]:
        if re.search(r"(หลักสูตร|ปริญญา|Bachelor|B\.Eng|วิศวกรรมคอมพิวเตอร์|Computer\s+Engineering)", ln, re.IGNORECASE):
            prof_lines.append(ln)
        if len(prof_lines) >= 18:
            break
    if prof_lines:
        chunks.insert(0, _make_curriculum_chunk(
            source_path=source_path,
            resolved_source=resolved_source,
            resolved_path=resolved_path,
            pages=[prelude_page_start, prelude_page_end],
            text="\n".join(prof_lines),
            doc_type='program_profile',
            year=year,
            section='ProgramProfile',
            section_heading='',
            section_path=['Program Profile'],
            clause_id='program_profile',
        ))

    # Program structure / study plan as before, but add a clearer doc_type
    if prelude_text and est_tokens(prelude_text) >= 10:
        doc_type = 'program_structure' if _STRUCTURE_RE.search(prelude_text) else ('study_plan' if _STUDY_PLAN_RE.search(prelude_text) else 'program_structure')
        section = 'ProgramStructure' if doc_type == 'program_structure' else 'StudyPlan'

        credits = None
        if doc_type == 'program_structure':
            # best-effort extract totals (common in FOE10 and มคอ.2 summary)
            credits = {}
            m_total = re.search(r"รวม\s*(\d{2,3})\s*หน่วยกิต", prelude_text)
            if m_total:
                credits['total'] = _safe_int(m_total.group(1), 0)
            m_ge = re.search(r"ศึกษาทั่วไป\s*(\d{1,3})", prelude_text)
            if m_ge:
                credits['general'] = _safe_int(m_ge.group(1), 0)
            m_major = re.search(r"วิชาเฉพาะ\s*(\d{1,3})", prelude_text)
            if m_major:
                credits['major'] = _safe_int(m_major.group(1), 0)
            m_free = re.search(r"เลือกเสรี\s*(\d{1,3})", prelude_text)
            if m_free:
                credits['free_elective'] = _safe_int(m_free.group(1), 0)
            if not credits:
                credits = None

        chunks.insert(1 if prof_lines else 0, _make_curriculum_chunk(
            source_path=source_path,
            resolved_source=resolved_source,
            resolved_path=resolved_path,
            pages=[prelude_page_start, prelude_page_end],
            text=prelude_text,
            doc_type=doc_type,
            year=year,
            section=section,
            section_heading='',
            section_path=[section],
            clause_id=section,
            extra_meta={'credits': credits, 'credits_total': (credits or {}).get('total') if credits else None},
        ))

    # Study plan term chunks (best-effort): split on year/term headers
    term_starts = [i for i, ln in enumerate(prelude_lines) if term_head_re.search(ln)]
    for ti, st in enumerate(term_starts[:80]):
        en = term_starts[ti + 1] if ti + 1 < len(term_starts) else min(len(prelude_lines), st + 80)
        block = [x for x in prelude_lines[st:en] if x and x.strip()]
        if not block:
            continue
        head = block[0][:160]
        block_pages = prelude_pages[st:en] if st < len(prelude_pages) else []
        block_lines = prelude_line_nos[st:en] if st < len(prelude_line_nos) else []
        scope = ''
        if block_lines:
            scope = f"p{min(block_pages) if block_pages else 0}-p{max(block_pages) if block_pages else 0}:l{min(block_lines)}-l{max(block_lines)}"
        chunks.append(_make_curriculum_chunk(
            source_path=source_path,
            resolved_source=resolved_source,
            resolved_path=resolved_path,
            pages=block_pages,
            text="\n".join(block),
            doc_type='study_plan_term',
            year=year,
            section='StudyPlanTerm',
            section_heading=head,
            section_path=['Study Plan', head],
            clause_id=head,
            extra_meta={'term_label': head, 'plan_label': head if 'แผน' in head else '', 'source_scope': scope},
        ))

        # Optional row-level chunks inside the term block (1 row ~= 1 course line)
        for ri, (ln, pg) in enumerate(zip(prelude_lines[st:en], prelude_pages[st:en])):
            if '|' in (ln or ''):
                continue
            cm = _COURSE_CODE_RE.match((ln or '').strip())
            if not cm:
                continue
            code = _course_code_norm(f"{cm.group('prefix')} {cm.group('num')}")
            credits_breakdown = ''
            ccm = _CREDITS_HINT_RE.search(ln)
            if ccm:
                credits_breakdown = f"{ccm.group(1)} ({ccm.group(2)})"
            chunks.append(_make_curriculum_chunk(
                source_path=source_path,
                resolved_source=resolved_source,
                resolved_path=resolved_path,
                pages=[pg],
                text=ln,
                doc_type='study_plan_term_row',
                year=year,
                section='StudyPlanTermRow',
                section_heading=head,
                section_path=['Study Plan', head, code],
                clause_id=f"{head}|{code}|{ri}",
                extra_meta={
                    'term_label': head,
                    'plan_label': head if 'แผน' in head else '',
                    'course_code_norm': code,
                    'credits_breakdown': credits_breakdown,
                    'canonical_key': f"{year}|{head}|{code}|study_plan_term_row",
                },
            ))

    # PLO/Sub-PLO chunks
    if _PLO_SECTION_HINT_RE.search(prelude_text):
        plo_starts = []
        for i, ln in enumerate(prelude_lines):
            if _PLO_RE.match(ln) or re.match(r"^ผลลัพธ์การเรียนรู้ของหลักสูตร", ln):
                plo_starts.append(i)
        for pi, st in enumerate(plo_starts[:200]):
            en = plo_starts[pi + 1] if pi + 1 < len(plo_starts) else min(len(prelude_lines), st + 120)
            block = [x for x in prelude_lines[st:en] if x and x.strip()]
            if not block:
                continue
            head = block[0]
            m = _PLO_RE.search(head)
            plo_num = m.group('num') if m else ''
            clause = f"PLO{plo_num}" if plo_num else 'PLO'
            chunks.append(_make_curriculum_chunk(
                source_path=source_path,
                resolved_source=resolved_source,
                resolved_path=resolved_path,
                pages=prelude_pages[st:en],
                text="\n".join(block),
                doc_type='plo',
                year=year,
                section='PLO',
                section_heading='PLO',
                section_path=['PLO', clause],
                clause_id=clause,
                extra_meta={'plo_id': clause},
            ))
            # Sub-PLO within the block
            sub_idxs = [j for j, ln in enumerate(block[1:], start=1) if _SUB_PLO_RE.match(ln)]
            for si, ss in enumerate(sub_idxs[:200]):
                ee = sub_idxs[si + 1] if si + 1 < len(sub_idxs) else len(block)
                sub_block = [head] + block[ss:ee]
                sm = _SUB_PLO_RE.match(block[ss])
                sub_id = f"{sm.group('num')}{sm.group('lemma')}" if sm else ''
                if not sub_id:
                    continue
                chunks.append(_make_curriculum_chunk(
                    source_path=source_path,
                    resolved_source=resolved_source,
                    resolved_path=resolved_path,
                    pages=prelude_pages[st:en],
                    text="\n".join(sub_block),
                    doc_type='sub_plo',
                    year=year,
                    section='SubPLO',
                    section_heading='PLO',
                    section_path=['PLO', clause, sub_id],
                    clause_id=sub_id,
                    extra_meta={'plo_id': clause, 'sub_plo_id': sub_id},
                ))

    # Course equivalence / change log chunks
    for i, ln in enumerate(prelude_lines[:5000]):
        m = _COURSE_EQUIV_RE.search(ln)
        if not m:
            continue
        old_code = _normalize_course_code(m.group('old'))
        new_code = _normalize_course_code(m.group('new'))
        chunks.append(_make_curriculum_chunk(
            source_path=source_path,
            resolved_source=resolved_source,
            resolved_path=resolved_path,
            pages=[prelude_pages[i] if i < len(prelude_pages) else 0],
            text=ln,
            doc_type='course_equivalence',
            year=year,
            section='CourseEquivalence',
            section_heading='Course change',
            section_path=['Course Equivalence', f"{old_code}->{new_code}"],
            clause_id=f"{old_code}->{new_code}",
            extra_meta={'old_code': old_code, 'new_code': new_code},
        ))

    # Faculty roster (best-effort): capture consecutive faculty lines
    roster_idxs = [i for i, ln in enumerate(prelude_lines[:4000]) if _FACULTY_NAME_RE.match(ln)]
    if roster_idxs:
        start = roster_idxs[0]
        end = min(len(prelude_lines), start + 160)
        roster_block = [x for x in prelude_lines[start:end] if x and x.strip()]
        degrees = _extract_degrees(roster_block)
        chunks.append(_make_curriculum_chunk(
            source_path=source_path,
            resolved_source=resolved_source,
            resolved_path=resolved_path,
            pages=prelude_pages[start:end],
            text="\n".join(roster_block),
            doc_type='faculty_roster',
            year=year,
            section='FacultyRoster',
            section_heading='Faculty roster',
            section_path=['Faculty', 'Roster'],
            clause_id='faculty_roster',
            extra_meta={'degrees': degrees},
        ))

    # Faculty biography appendix (ภาคผนวก ง.) — parse per-person, then split sections 1/2/3
    all_lines: List[str] = []
    all_pages: List[int] = []
    all_line_nos: List[int] = []
    for p in paragraphs:
        page = _safe_int(p.get('page', 0), 0)
        txt = (p.get('text') or '').strip()
        if not txt:
            continue
        for raw_ln in txt.splitlines():
            ln = (raw_ln or '').strip()
            if not ln:
                continue
            all_lines.append(ln)
            all_pages.append(page)
            all_line_nos.append(len(all_line_nos) + 1)

    app_idx = None
    for i, ln in enumerate(all_lines[:8000]):
        if re.search(r"ภาคผนวก\s*ง", ln):
            app_idx = i
            break
    if app_idx is not None:
        bio_lines = all_lines[app_idx:]
        bio_pages = all_pages[app_idx:]
        bio_line_nos = all_line_nos[app_idx:]
        starts = [i for i, ln in enumerate(bio_lines) if _FACULTY_NAME_RE.match(ln)]

        def _pack_lines_with_prefix(
            *,
            prefix_lines: List[str],
            lines: List[str],
            pages: List[int],
            max_tokens: int,
        ) -> List[Dict]:
            """Pack (line,page) pairs into <= max_tokens chunks, repeating prefix per chunk."""
            prefix = [x for x in (prefix_lines or []) if x and x.strip()]
            prefix_text = "\n".join(prefix).strip()
            prefix_tok = est_tokens(prefix_text) if prefix_text else 0

            budget = max(40, int(max_tokens) - prefix_tok)
            out_parts: List[Dict] = []

            cur_lines: List[str] = []
            cur_pages: List[int] = []
            cur_tok = 0

            for ln, pg in zip(lines or [], pages or []):
                s = (ln or '').strip()
                if not s:
                    continue
                t = est_tokens(s)
                if cur_lines and (cur_tok + t > budget):
                    out_parts.append({'lines': cur_lines, 'pages': cur_pages})
                    cur_lines = []
                    cur_pages = []
                    cur_tok = 0
                cur_lines.append(s)
                cur_pages.append(pg)
                cur_tok += t

            if cur_lines:
                out_parts.append({'lines': cur_lines, 'pages': cur_pages})

            return out_parts

        def _person_id(name_th: str) -> str:
            basis = f"{year}|{name_th.strip()}"
            return f"kmuttt:{hashlib.sha1(basis.encode('utf-8','ignore')).hexdigest()[:16]}"

        for pi, st in enumerate(starts[:300]):
            en = starts[pi + 1] if pi + 1 < len(starts) else min(len(bio_lines), st + 400)
            block = [x for x in bio_lines[st:en] if x and x.strip()]
            if not block:
                continue
            name_th = block[0][:120]
            name_en = block[1][:120] if len(block) > 1 and re.search(r"[A-Za-z]", block[1]) else ''
            pid = _person_id(name_th)
            rank_th = ''
            rm = re.match(r"^(รศ\.ดร\.|ผศ\.ดร\.|ผศ\.|อ\.ดร\.|อ\.)", name_th)
            if rm:
                rank_th = rm.group(1)
            degrees = _extract_degrees(block[:80])

            scope = ''
            if st < len(bio_line_nos) and (en - 1) < len(bio_line_nos):
                scope = f"p{min(bio_pages[st:en]) if bio_pages[st:en] else 0}-p{max(bio_pages[st:en]) if bio_pages[st:en] else 0}:l{bio_line_nos[st]}-l{bio_line_nos[en-1]}"
            # full profile
            chunks.append(_make_curriculum_chunk(
                source_path=source_path,
                resolved_source=resolved_source,
                resolved_path=resolved_path,
                pages=bio_pages[st:en],
                text="\n".join(block),
                doc_type='faculty_profile_full',
                year=year,
                section='FacultyProfile',
                section_heading=name_th,
                section_path=['Faculty', name_th],
                clause_id=pid,
                extra_meta={
                    'person_id': pid,
                    'person_name_th': name_th,
                    'person_name_en': name_en,
                    'academic_rank_th': rank_th,
                    'degrees': degrees,
                    'source_scope': scope,
                },
            ))
            # section splits
            sec_starts: List[int] = []
            for j, ln in enumerate(block[:800]):
                m = _FACULTY_SEC_RE.match((ln or '').strip())
                if not m:
                    continue
                # Avoid splitting on publication numbering like "1. Author, ...".
                if not _FACULTY_SEC_HEADING_HINT_RE.search(ln):
                    continue
                # Keep headings reasonably short (helps avoid false positives).
                if len((ln or '').strip()) > 180:
                    continue
                sec_starts.append(j)

            for si, ss in enumerate(sec_starts[:60]):
                ee = sec_starts[si + 1] if si + 1 < len(sec_starts) else len(block)
                sec_block = [x for x in block[ss:ee] if x and x.strip()]
                if not sec_block:
                    continue
                head_ln = (sec_block[0] or '').strip()
                if est_tokens("\n".join(sec_block)) < 12:
                    continue

                sm = _FACULTY_SEC_RE.match(head_ln)
                sec_id = (sm.group('sec') if sm else '').strip()
                dtype = 'faculty_section'
                probe = "\n".join(sec_block[:5])
                if _FACULTY_EDU_RE.search(probe):
                    dtype = 'faculty_education'
                elif _FACULTY_TEACH_RE.search(probe):
                    dtype = 'faculty_teaching_load'
                elif _FACULTY_PUB_RE.search(probe):
                    dtype = 'faculty_publications'
                # extract taught courses
                taught = []
                if dtype == 'faculty_teaching_load':
                    for ln2 in sec_block:
                        for mm in _COURSE_CODE_ANYWHERE_RE.finditer(ln2):
                            taught.append(_course_code_norm(f"{mm.group('prefix')} {mm.group('num')}"))
                            if len(taught) >= 40:
                                break
                        if len(taught) >= 40:
                            break
                    taught = sorted(set(taught))

                pubs_5y = []
                pub_years = []
                if dtype == 'faculty_publications':
                    now_year = time.gmtime().tm_year
                    for ln2 in sec_block:
                        for ym in re.finditer(r"\b(20\d{2}|25\d{2}|26\d{2})\b", ln2):
                            yy = _safe_int(ym.group(1), 0)
                            ad = _year_to_ad(yy)
                            if ad:
                                pub_years.append(ad)
                                if ad >= now_year - 5:
                                    pubs_5y.append(ln2.strip())
                        if len(pubs_5y) >= 40:
                            break
                    # de-dup
                    pubs_5y = [x for i, x in enumerate(pubs_5y) if x and x not in pubs_5y[:i]]
                    pub_years = sorted(set(pub_years))

                # Add person-name prefix to help name-specific retrieval.
                prefix_lines = [name_th]
                if name_en:
                    prefix_lines.append(name_en)

                # NOTE: block lines are filtered for empties; keep page/scope coarse to avoid misalignment.
                sec_pages = bio_pages[st:en]
                sec_scope = scope

                sec_text_full = "\n".join(prefix_lines + sec_block).strip()
                if est_tokens(sec_text_full) <= CHUNK_MAX_TOKENS:
                    chunks.append(_make_curriculum_chunk(
                        source_path=source_path,
                        resolved_source=resolved_source,
                        resolved_path=resolved_path,
                        pages=sec_pages,
                        text=sec_text_full,
                        doc_type=dtype,
                        year=year,
                        section='FacultySection',
                        section_heading=head_ln[:120],
                        section_path=['Faculty', name_th, head_ln[:120]],
                        clause_id=f"{pid}:{sec_id or head_ln[:16]}:{dtype}",
                        extra_meta={
                            'person_id': pid,
                            'person_name_th': name_th,
                            'person_name_en': name_en,
                            'academic_rank_th': rank_th,
                            'degrees': degrees,
                            'teaching_current': taught,
                            'teaching_in_program': taught,
                            'publications_5y': pubs_5y,
                            'publications_years': pub_years,
                            'source_scope': sec_scope,
                            'section_id': sec_id,
                        },
                    ))
                else:
                    # Split long sections to avoid embedding truncation.
                    packed = _pack_lines_with_prefix(
                        prefix_lines=prefix_lines,
                        lines=sec_block,
                        pages=sec_pages,
                        max_tokens=CHUNK_MAX_TOKENS,
                    )
                    for part_i, part in enumerate(packed[:50]):
                        part_lines = part.get('lines') or []
                        part_pages = part.get('pages') or []
                        part_text = "\n".join(prefix_lines + part_lines).strip()
                        if not part_text:
                            continue
                        chunks.append(_make_curriculum_chunk(
                            source_path=source_path,
                            resolved_source=resolved_source,
                            resolved_path=resolved_path,
                            pages=part_pages,
                            text=part_text,
                            doc_type=dtype,
                            year=year,
                            section='FacultySection',
                            section_heading=(head_ln[:110] + f" (part {part_i+1})")[:120],
                            section_path=['Faculty', name_th, head_ln[:120]],
                            clause_id=f"{pid}:{sec_id or head_ln[:16]}:{dtype}:{part_i}",
                            extra_meta={
                                'person_id': pid,
                                'person_name_th': name_th,
                                'person_name_en': name_en,
                                'academic_rank_th': rank_th,
                                'degrees': degrees,
                                'teaching_current': taught,
                                'teaching_in_program': taught,
                                'publications_5y': pubs_5y,
                                'publications_years': pub_years,
                                'source_scope': sec_scope,
                                'section_id': sec_id,
                                'chunk_part': part_i,
                            },
                        ))

    # PLO↔Course mapping derived chunks (best-effort)
    if _PLO_MAP_HINT_RE.search(prelude_text):
        # Collect candidate lines
        map_lines: List[str] = []
        map_pages: List[int] = []
        for ln, pg in zip(prelude_lines, prelude_pages or [0] * len(prelude_lines)):
            if _COURSE_CODE_ANYWHERE_RE.search(ln) or _SUB_PLO_ANYWHERE_RE.search(ln) or '|' in ln or 'X' in ln or term_head_re.search(ln):
                if _PLO_MAP_HINT_RE.search(ln) or _COURSE_CODE_ANYWHERE_RE.search(ln) or _SUB_PLO_ANYWHERE_RE.search(ln) or _X_MARK_RE.search(ln) or term_head_re.search(ln):
                    map_lines.append(ln)
                    map_pages.append(pg)
                    if len(map_lines) >= 400:
                        break

        if map_lines:
            chunks.append(_make_curriculum_chunk(
                source_path=source_path,
                resolved_source=resolved_source,
                resolved_path=resolved_path,
                pages=map_pages,
                text="\n".join(map_lines),
                doc_type='plo_course_map_table',
                year=year,
                section='PLOMapTable',
                section_heading='PLO↔Course map',
                section_path=['PLO Mapping', 'Table'],
                clause_id='plo_course_map_table',
            ))

            # 1) Try column-based extraction using a header row of PLO/SubPLO labels
            header_idx = None
            header_cols: List[str] = []
            for i, ln in enumerate(map_lines[:200]):
                cols = _split_table_cells(ln)
                labels = [c for c in cols if re.fullmatch(r"(?:PLO\d+|\d+[A-Z])", c, flags=re.IGNORECASE)]
                if len(labels) >= 5:
                    header_idx = i
                    header_cols = [lab.upper().replace(' ', '') for lab in labels]
                    break

            derived: Dict[str, set] = {}
            term_by_course: Dict[str, str] = {}
            current_term = ''
            if header_idx is not None and header_cols:
                for ln in map_lines[header_idx + 1 : header_idx + 260]:
                    if term_head_re.search(ln):
                        if '|' in ln:
                            cols = _split_table_cells(ln)
                            current_term = (cols[0] if cols else ln).strip()[:160]
                        else:
                            current_term = ln.strip()[:160]
                        continue
                    cm = _COURSE_CODE_ANYWHERE_RE.search(ln)
                    if not cm:
                        continue
                    code = _course_code_norm(f"{cm.group('prefix')} {cm.group('num')}")
                    if current_term:
                        term_by_course.setdefault(code, current_term)
                    cols = _split_table_cells(ln)
                    if len(cols) < len(header_cols):
                        continue
                    # Map using the rightmost N cells (handles variable left columns)
                    right = cols[-len(header_cols):]
                    plos = set()
                    for lab, cell in zip(header_cols, right):
                        if _X_MARK_RE.search(cell) or cell.strip() in {'X', 'x', '✓', '✔'}:
                            plos.add(lab if lab.startswith('PLO') else lab)
                    if plos:
                        derived.setdefault(code, set()).update(plos)

            # 2) Fallback: same-line labels
            if not derived:
                for ln in map_lines:
                    cm = _COURSE_CODE_ANYWHERE_RE.search(ln)
                    if not cm:
                        continue
                    code = _course_code_norm(f"{cm.group('prefix')} {cm.group('num')}")
                    plos = set()
                    for pm in _PLO_ANYWHERE_RE.finditer(ln):
                        plos.add(f"PLO{pm.group('num')}")
                    for sm in _SUB_PLO_ANYWHERE_RE.finditer(ln):
                        if len(sm.group('num')) <= 2:
                            plos.add(f"{sm.group('num')}{sm.group('lemma').upper()}")
                    if plos:
                        derived.setdefault(code, set()).update(plos)

            for code, plos in sorted(derived.items())[:800]:
                plos_list = sorted(plos)
                chunks.append(_make_curriculum_chunk(
                    source_path=source_path,
                    resolved_source=resolved_source,
                    resolved_path=resolved_path,
                    pages=map_pages,
                    text=f"Course {code} covers: {', '.join(plos_list)}",
                    doc_type='course_plo_map',
                    year=year,
                    section='CoursePLOMap',
                    section_heading=code,
                    section_path=['PLO Mapping', code],
                    clause_id=code,
                    extra_meta={'course_code_norm': code, 'plos_covered': plos_list, 'canonical_key': f"{year}|{code}|course_plo_map"},
                ))

            # Term-level derived summary (if term headings were detected)
            if term_by_course and derived:
                term_agg: Dict[str, Dict[str, set]] = {}
                for code, term in term_by_course.items():
                    if code not in derived:
                        continue
                    rec = term_agg.setdefault(term, {'courses': set(), 'plos': set()})
                    rec['courses'].add(code)
                    rec['plos'].update(derived[code])
                for term, rec in list(term_agg.items())[:80]:
                    courses = sorted(rec['courses'])
                    plos = sorted(rec['plos'])
                    chunks.append(_make_curriculum_chunk(
                        source_path=source_path,
                        resolved_source=resolved_source,
                        resolved_path=resolved_path,
                        pages=map_pages,
                        text=f"{term}\nCourses: {', '.join(courses)}\nPLOs covered: {', '.join(plos)}",
                        doc_type='term_plo_map',
                        year=year,
                        section='TermPLOMap',
                        section_heading=term,
                        section_path=['PLO Mapping', 'By Term', term],
                        clause_id=term,
                        extra_meta={
                            'term_label': term,
                            'term_courses': courses,
                            'plos_covered': plos,
                            'canonical_key': f"{year}|{term}|term_plo_map",
                        },
                    ))

    # Deterministic ordering id within a source file
    for idx, ch in enumerate(chunks):
        ch.setdefault('chunk_id', idx)
    return chunks


def _make_chunks_structure(paragraphs: List[Dict], source_path: str) -> List[Dict]:
    chunks: List[Dict] = []
    resolved_source = normalize_doc_name(source_path)
    resolved_path = str(Path(source_path).resolve())

    cur_texts: List[str] = []
    cur_pages: List[int] = []
    cur_tokens = 0
    overlap_prefix: Optional[str] = None

    # Keep a short heading context to prefix chunks created by max-length splits.
    active_headings: List[str] = []

    def _valid_pages(pages: List[int]) -> List[int]:
        out: List[int] = []
        for pg in pages:
            try:
                if pg is not None:
                    out.append(int(pg))
            except (ValueError, TypeError):
                pass
        return out

    def _sent_tail_for_overlap(text: str, want_tokens: int) -> Optional[str]:
        if not text or want_tokens <= 0:
            return None
        flat = " ".join((text or "").split())
        if not flat:
            return None
        sents = segment_sentences_thai(flat) or [flat]
        sents = [s.strip() for s in sents if s and s.strip()]
        if not sents:
            return None
        buf: List[str] = []
        tok = 0
        for s in reversed(sents):
            buf.insert(0, s)
            tok = est_tokens(" ".join(buf))
            if tok >= want_tokens:
                break
        tail = " ".join(buf).strip()
        # Guard: don't let overlap become the whole chunk.
        if est_tokens(tail) >= max(1, int(0.8 * est_tokens(flat))):
            return None
        return tail

    def _maybe_add_section_prefix():
        nonlocal cur_tokens
        if cur_texts:
            return
        prefix_lines: List[str] = []
        if overlap_prefix:
            prefix_lines.append(overlap_prefix.strip())
        # Only prefix headings when the next chunk isn't starting with a heading paragraph.
        if active_headings:
            prefix_lines.extend(active_headings[-2:])
        if not prefix_lines:
            return
        prefix = "\n".join([ln for ln in prefix_lines if ln and ln.strip()]).strip()
        if prefix:
            cur_texts.append(prefix)
            cur_tokens += est_tokens(prefix)

    def _add_paragraph_text(text: str, page: int):
        nonlocal cur_tokens
        if not text or not text.strip():
            return
        _maybe_add_section_prefix()
        cur_texts.append(text.strip())
        cur_pages.append(page)
        cur_tokens += est_tokens(text)

    def _finalize_current(allow_overlap: bool) -> None:
        nonlocal cur_texts, cur_pages, cur_tokens, overlap_prefix
        if not cur_texts:
            overlap_prefix = None
            return
        text = "\n\n".join(cur_texts).strip()
        if not text:
            cur_texts = []
            cur_pages = []
            cur_tokens = 0
            overlap_prefix = None
            return
        pages = _valid_pages(cur_pages)
        page_start = min(pages) if pages else 0
        page_end = max(pages) if pages else 0
        chunks.append({
            'source': resolved_source,
            'path': resolved_path,
            'page': page_start,
            'page_start': page_start,
            'page_end': page_end,
            'owner': 'owner:unknown',
            'sensitivity': 'internal',
            'updated_at': int(time.time()),
            'text': text,
            'tokens_est': est_tokens(text),
        })

        if allow_overlap and CHUNK_OVERLAP_RATIO > 0:
            want = int(max(1, round(CHUNK_OVERLAP_RATIO * est_tokens(text))))
            overlap_prefix = _sent_tail_for_overlap(text, want)
        else:
            overlap_prefix = None

        cur_texts = []
        cur_pages = []
        cur_tokens = 0

    def _emit_long_text_as_chunks(text: str, page: int) -> None:
        """Split a single long paragraph into chunks using sentence packing + overlap."""
        nonlocal overlap_prefix
        sents = segment_sentences_thai(text) or [text]
        sents = [s.strip() for s in sents if s and s.strip()]
        if not sents:
            return
        buf: List[str] = []
        for s in sents:
            tentative = (" ".join(buf + [s])).strip()
            if buf and est_tokens(tentative) > CHUNK_MAX_TOKENS:
                part = " ".join(buf).strip()
                if part:
                    # Write as its own chunk
                    local_texts: List[str] = []
                    if overlap_prefix:
                        local_texts.append(overlap_prefix)
                    if active_headings:
                        local_texts.extend(active_headings[-2:])
                    local_texts.append(part)
                    final = "\n".join([x for x in local_texts if x and x.strip()]).strip()
                    chunks.append({
                        'source': resolved_source,
                        'path': resolved_path,
                        'page': page,
                        'page_start': page,
                        'page_end': page,
                        'owner': 'owner:unknown',
                        'sensitivity': 'internal',
                        'updated_at': int(time.time()),
                        'text': final,
                        'tokens_est': est_tokens(final),
                    })
                    want = int(max(1, round(CHUNK_OVERLAP_RATIO * est_tokens(final))))
                    overlap_prefix = _sent_tail_for_overlap(final, want)
                buf = [s]
            else:
                buf.append(s)

        if buf:
            part = " ".join(buf).strip()
            if part:
                local_texts = []
                if overlap_prefix:
                    local_texts.append(overlap_prefix)
                if active_headings:
                    local_texts.extend(active_headings[-2:])
                local_texts.append(part)
                final = "\n".join([x for x in local_texts if x and x.strip()]).strip()
                chunks.append({
                    'source': resolved_source,
                    'path': resolved_path,
                    'page': page,
                    'page_start': page,
                    'page_end': page,
                    'owner': 'owner:unknown',
                    'sensitivity': 'internal',
                    'updated_at': int(time.time()),
                    'text': final,
                    'tokens_est': est_tokens(final),
                })
                want = int(max(1, round(CHUNK_OVERLAP_RATIO * est_tokens(final))))
                overlap_prefix = _sent_tail_for_overlap(final, want)

    for p in paragraphs:
        page_raw = p.get('page', 0)
        try:
            page = int(page_raw) if page_raw is not None else 0
        except (ValueError, TypeError):
            page = 0
        text = (p.get('text') or '').strip()
        if not text:
            continue

        # Heading handling: treat as a strong boundary *only* if we already have a decent chunk.
        if p.get('is_heading'):
            # Update heading context.
            active_headings.append(text)
            active_headings = active_headings[-3:]

            if cur_texts and cur_tokens >= CHUNK_MIN_TOKENS:
                # New section: do not carry overlap across headings.
                _finalize_current(allow_overlap=False)
                overlap_prefix = None
            # Always include the heading in the next content chunk.
            _add_paragraph_text(text, page)
            continue

        p_tokens = est_tokens(text)

        # Very long paragraph: flush current then emit sentence-packed chunks.
        if p_tokens > CHUNK_MAX_TOKENS:
            if cur_texts:
                _finalize_current(allow_overlap=True)
            _emit_long_text_as_chunks(text, page)
            continue

        # Need to start a new chunk due to max size.
        # Always respect CHUNK_MAX_TOKENS; if the current chunk is still small,
        # finalize without overlap rather than exceeding the max budget.
        if cur_texts and (cur_tokens + p_tokens > CHUNK_MAX_TOKENS):
            _finalize_current(allow_overlap=(cur_tokens >= CHUNK_MIN_TOKENS))

        _add_paragraph_text(text, page)

    # Final chunk: no need to compute overlap.
    _finalize_current(allow_overlap=False)
    return chunks


def _make_chunks_sentence_window(paragraphs: List[Dict], source_path: str) -> List[Dict]:
    """Sentence-window chunking.

    Intended for domains where paragraph boundaries are noisy (e.g., announcements).
    Preserves heading boundaries and uses overlap based on CHUNK_OVERLAP_RATIO.
    """
    chunks: List[Dict] = []
    resolved_source = normalize_doc_name(source_path)
    resolved_path = str(Path(source_path).resolve())

    cur_texts: List[str] = []
    cur_pages: List[int] = []
    cur_tokens = 0
    overlap_prefix: Optional[str] = None
    active_headings: List[str] = []

    def _valid_pages(pages: List[int]) -> List[int]:
        out: List[int] = []
        for pg in pages:
            try:
                if pg is not None:
                    out.append(int(pg))
            except (ValueError, TypeError):
                pass
        return out

    def _sent_tail_for_overlap(text: str, want_tokens: int) -> Optional[str]:
        if not text or want_tokens <= 0:
            return None
        flat = " ".join((text or "").split())
        if not flat:
            return None
        sents = segment_sentences_thai(flat) or [flat]
        sents = [s.strip() for s in sents if s and s.strip()]
        if not sents:
            return None
        buf: List[str] = []
        tok = 0
        for s in reversed(sents):
            buf.insert(0, s)
            tok = est_tokens(" ".join(buf))
            if tok >= want_tokens:
                break
        tail = " ".join(buf).strip()
        if est_tokens(tail) >= max(1, int(0.8 * est_tokens(flat))):
            return None
        return tail

    def _maybe_add_section_prefix():
        nonlocal cur_tokens
        if cur_texts:
            return
        prefix_lines: List[str] = []
        if overlap_prefix:
            prefix_lines.append(overlap_prefix.strip())
        if active_headings:
            prefix_lines.extend(active_headings[-2:])
        prefix = "\n".join([ln for ln in prefix_lines if ln and ln.strip()]).strip()
        if prefix:
            cur_texts.append(prefix)
            cur_tokens += est_tokens(prefix)

    def _add_text(text: str, page: int):
        nonlocal cur_tokens
        if not text or not text.strip():
            return
        _maybe_add_section_prefix()
        cur_texts.append(text.strip())
        cur_pages.append(page)
        cur_tokens += est_tokens(text)

    def _finalize_current(allow_overlap: bool) -> None:
        nonlocal cur_texts, cur_pages, cur_tokens, overlap_prefix
        if not cur_texts:
            overlap_prefix = None
            return
        text = " ".join([t for t in cur_texts if t and t.strip()]).strip()
        if not text:
            cur_texts = []
            cur_pages = []
            cur_tokens = 0
            overlap_prefix = None
            return
        pages = _valid_pages(cur_pages)
        page_start = min(pages) if pages else 0
        page_end = max(pages) if pages else 0
        chunks.append({
            'source': resolved_source,
            'path': resolved_path,
            'page': page_start,
            'page_start': page_start,
            'page_end': page_end,
            'owner': 'owner:unknown',
            'sensitivity': 'internal',
            'updated_at': int(time.time()),
            'text': text,
            'tokens_est': est_tokens(text),
        })
        if allow_overlap and CHUNK_OVERLAP_RATIO > 0:
            want = int(max(1, round(CHUNK_OVERLAP_RATIO * est_tokens(text))))
            overlap_prefix = _sent_tail_for_overlap(text, want)
        else:
            overlap_prefix = None
        cur_texts = []
        cur_pages = []
        cur_tokens = 0

    for p in paragraphs:
        page_raw = p.get('page', 0)
        try:
            page = int(page_raw) if page_raw is not None else 0
        except (ValueError, TypeError):
            page = 0
        text = (p.get('text') or '').strip()
        if not text:
            continue

        if p.get('is_heading'):
            active_headings.append(text)
            active_headings = active_headings[-3:]
            if cur_texts and cur_tokens >= CHUNK_MIN_TOKENS:
                _finalize_current(allow_overlap=False)
                overlap_prefix = None
            # Do not emit heading alone; keep it as prefix context.
            continue

        # Keep bullet groups intact (avoid sentence tokenizers mangling lists)
        if is_bullet(text):
            t_tokens = est_tokens(text)
            if cur_texts and (cur_tokens + t_tokens > CHUNK_MAX_TOKENS):
                _finalize_current(allow_overlap=(cur_tokens >= CHUNK_MIN_TOKENS))
            _add_text(text, page)
            continue

        sents = segment_sentences_thai(text) or [text]
        sents = [s.strip() for s in sents if s and s.strip()]
        for s in sents:
            s_tokens = est_tokens(s)
            if cur_texts and (cur_tokens + s_tokens > CHUNK_MAX_TOKENS):
                _finalize_current(allow_overlap=(cur_tokens >= CHUNK_MIN_TOKENS))
            _add_text(s, page)

    _finalize_current(allow_overlap=False)
    return chunks


def make_chunks(paragraphs: List[Dict], source_path: str) -> List[Dict]:
    strat = (CHUNK_STRATEGY or 'structure').strip().lower()
    if strat in ('langchain_recursive', 'langchain'):
        return _make_chunks_langchain_recursive(paragraphs, source_path)
    if strat == 'sentence_window':
        return _make_chunks_sentence_window(paragraphs, source_path)
    if strat in ('announcement_template', 'announcements'):
        return _make_chunks_announcement_template(paragraphs, source_path)
    if strat in ('curriculum_course', 'course_centric', 'course'):
        return _make_chunks_curriculum_course(paragraphs, source_path)
    if strat in ('regulation_template', 'regulations'):
        return _make_chunks_regulation_template(paragraphs, source_path)
    return _make_chunks_structure(paragraphs, source_path)


def _make_chunks_langchain_recursive(paragraphs: List[Dict], source_path: str) -> List[Dict]:
    """Simple, generic LangChain splitter strategy.

    Notes:
    - Intended as an optional baseline/fallback. Domain-tuned strategies in this
      repo often outperform generic splitters.
    - Preserves page ranges approximately using paragraph boundary mapping.
    """
    try:
        from bisect import bisect_right
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except Exception:
        # LangChain not installed; fall back to existing default.
        return _make_chunks_structure(paragraphs, source_path)

    resolved_source = normalize_doc_name(source_path)
    resolved_path = str(Path(source_path).resolve())

    paras = [p for p in (paragraphs or []) if (p.get('text') or '').strip()]
    if not paras:
        return []

    texts: list[str] = []
    pages: list[int] = []
    starts: list[int] = []
    cur = 0
    for p in paras:
        t = (p.get('text') or '').strip()
        try:
            pg = int(p.get('page') or 0)
        except Exception:
            pg = 0
        if texts:
            # separator between paragraphs
            cur += 2
        starts.append(cur)
        texts.append(t)
        pages.append(pg)
        cur += len(t)

    full_text = "\n\n".join(texts)

    # Best-effort shared metadata inference (kept lightweight/robust).
    # Domain-specific strategies still exist and may outperform this baseline.
    doc_title = _infer_doc_title((full_text.splitlines() if full_text else []), source_path)
    year_be = _extract_year_be_from_text_or_source(full_text, source_path)
    topic = _infer_topic(full_text, source_path)
    audience = _infer_audience(full_text)
    effective_from = _infer_effective_from(full_text)
    base_meta: Dict = {
        'doc_title': doc_title,
        'doc_type': '',
        'topic': topic,
        'year_be': year_be,
        'effective_from': effective_from,
        'audience': audience,
    }
    # Approximate token->char conversion using configured heuristics.
    chunk_size = max(200, int(CHUNK_MAX_TOKENS * CHAR_PER_TOKEN))
    overlap = max(0, int(chunk_size * float(CHUNK_OVERLAP_RATIO or 0.0)))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", " ", ""],
        add_start_index=True,
    )

    docs = splitter.create_documents([full_text], metadatas=[{'source_path': source_path}])
    out: list[Dict] = []
    for i, d in enumerate(docs):
        content = (getattr(d, 'page_content', '') or '').strip()
        if not content:
            continue
        md = getattr(d, 'metadata', {}) or {}
        try:
            start_idx = int(md.get('start_index') or 0)
        except Exception:
            start_idx = 0
        end_idx = start_idx + len(content)

        # Map char positions back to approximate paragraph pages.
        # starts[] stores the start char index of each paragraph.
        pi_start = max(0, bisect_right(starts, start_idx) - 1)
        pi_end = max(0, bisect_right(starts, max(start_idx, end_idx - 1)) - 1)
        pg_start = pages[pi_start] if pi_start < len(pages) else 0
        pg_end = pages[pi_end] if pi_end < len(pages) else pg_start

        chunk_uid = hashlib.sha1(f"{source_path}|{start_idx}|{end_idx}".encode('utf-8', 'ignore')).hexdigest()[:16]
        source_file = Path(source_path).name
        out.append({
            **base_meta,
            'source': resolved_source,
            'path': resolved_path,
            'page': int(pg_start),
            'page_start': int(pg_start),
            'page_end': int(pg_end),
            'owner': 'owner:unknown',
            'sensitivity': 'internal',
            'updated_at': int(time.time()),
            'text': content,
            'tokens_est': est_tokens(content),
            'section': 'body',
            'clause_id': '',
            'source_file': source_file,
            'chunk_uid': chunk_uid,
            'source_priority': _source_priority(source_path),
            'chunk_id': i,
        })
    return out
