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

_COURSE_CODE_RE = re.compile(r"^(?P<prefix>[A-Z]{3})\s*(?P<num>\d{3})\b")
_COURSE_CODE_ANYWHERE_RE = re.compile(r"(?P<prefix>[A-Z]{3})\s*(?P<num>\d{3})\b")
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

    Uses 25xx/26xx matches from filename; returns '' if not found.
    """
    name = Path(source_path).name
    # Avoid \b here because '_' is a word char and breaks boundaries.
    m = re.search(r"(25\d{2}|26\d{2})", name)
    return m.group(1) if m else ''


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
    year: str,
) -> Dict:
    pages_int = [int(p) for p in pages if isinstance(p, int) or str(p).isdigit()]
    page_start = min(pages_int) if pages_int else 0
    page_end = max(pages_int) if pages_int else 0
    source_file = Path(source_path).name
    chunk_uid_basis = f"{source_file}|{year}|{course_code}|{section}|course"
    chunk_uid = hashlib.sha1(chunk_uid_basis.encode('utf-8', 'ignore')).hexdigest()[:32]
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
        'doc_type': 'course',
        'program': CURRICULUM_PROGRAM,
        'course_code': course_code,
        'course_th': course_th,
        'course_en': course_en,
        'category': category,
        'section': section,
        'section_heading': section_heading,
        'source_file': source_file,
        'year': year,
        'chunk_uid': chunk_uid,
        'source_priority': _source_priority(source_path),
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

    prelude_lines: List[str] = []
    prelude_pages: List[int] = []

    active_heading = ''
    current_heading = ''
    current_code = ''
    current_header_line = ''
    current_lines: List[str] = []
    current_pages: List[int] = []

    def _flush_course(out: List[Dict]):
        nonlocal current_code, current_header_line, current_lines, current_pages, current_heading
        if not current_code or not current_lines:
            current_code = ''
            current_header_line = ''
            current_lines = []
            current_pages = []
            current_heading = ''
            return

        course_code = _normalize_course_code(current_code)
        category = course_code.split(' ', 1)[0] if course_code else ''
        course_th, course_en = _parse_course_names(current_header_line or current_lines[0])

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

        if est_tokens(full_text) <= CHUNK_MAX_TOKENS or lo_idx is None:
            section = 'CourseDescription+LearningOutcomes' if lo_idx is not None else 'CourseDescription'
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
                year=year,
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
                    year=year,
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
                    year=year,
                ))

        current_code = ''
        current_header_line = ''
        current_lines = []
        current_pages = []
        current_heading = ''

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
            if m:
                # New course block begins
                _flush_course(chunks)
                current_code = f"{m.group('prefix')} {m.group('num')}"
                current_header_line = ln
                current_heading = active_heading
                current_lines = [ln]
                current_pages = [page]
                continue

            if current_code:
                current_lines.append(ln)
                current_pages.append(page)
            else:
                prelude_lines.append(ln)
                prelude_pages.append(page)

    _flush_course(chunks)

    # Prelude/non-course content: keep as a single chunk if meaningful.
    prelude_text = "\n".join([x for x in prelude_lines if x and x.strip()]).strip()
    if prelude_text and est_tokens(prelude_text) >= 10:
        doc_type = 'program_structure' if _STRUCTURE_RE.search(prelude_text) else ('study_plan' if _STUDY_PLAN_RE.search(prelude_text) else 'program_structure')
        pages_int = [int(p) for p in prelude_pages if isinstance(p, int) or str(p).isdigit()]
        page_start = min(pages_int) if pages_int else 0
        page_end = max(pages_int) if pages_int else 0
        source_file = Path(source_path).name
        section = 'ProgramStructure' if doc_type == 'program_structure' else 'StudyPlan'
        chunk_uid_basis = f"{source_file}|{year}|{doc_type}|{section}"
        chunk_uid = hashlib.sha1(chunk_uid_basis.encode('utf-8', 'ignore')).hexdigest()[:32]
        chunks.insert(0, {
            'source': resolved_source,
            'path': resolved_path,
            'page': page_start,
            'page_start': page_start,
            'page_end': page_end,
            'owner': 'owner:unknown',
            'sensitivity': 'internal',
            'updated_at': int(time.time()),
            'text': prelude_text,
            'tokens_est': est_tokens(prelude_text),
            'doc_type': doc_type,
            'program': CURRICULUM_PROGRAM,
            'course_code': '',
            'course_th': '',
            'course_en': '',
            'category': '',
            'section': section,
            'section_heading': '',
            'source_file': source_file,
            'year': year,
            'chunk_uid': chunk_uid,
            'source_priority': _source_priority(source_path),
        })

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
    if strat == 'sentence_window':
        return _make_chunks_sentence_window(paragraphs, source_path)
    if strat in ('announcement_template', 'announcements'):
        return _make_chunks_announcement_template(paragraphs, source_path)
    if strat in ('curriculum_course', 'course_centric', 'course'):
        return _make_chunks_curriculum_course(paragraphs, source_path)
    if strat in ('regulation_template', 'regulations'):
        return _make_chunks_regulation_template(paragraphs, source_path)
    return _make_chunks_structure(paragraphs, source_path)
