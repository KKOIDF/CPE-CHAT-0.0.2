from typing import List, Dict, Tuple, Sequence
import re
import math
from pathlib import Path
import unicodedata
import os
import json

from .perf import time_block, add_metric

from .sqlite_client import keyword_search, fetch_docs_with_path, domain_sqlite_path
from .chroma_client import semantic_search_domain
from .config import TOKEN_BUDGET, RRF_K, MAX_CONTEXTS, KNOWN_DOMAINS, ROOT_DIR
from .neo4j_client import (
    extract_course_codes,
    graph_doc_ids_for_codes,
    graph_doc_ids_for_course_prefix,
    graph_expand_from_seed_chunks,
    graph_doc_ids_for_requisites,
)

from .structured_curriculum import (
    Course,
    extract_courses_from_text,
    format_required_cpe_answer,
    load_credit_totals_2564,
    load_all_courses_2564,
    load_cpe_curriculum_2564,
)

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
    variants = _expand_course_code_variants(q)
    if not variants:
        return q
    # Append compact hint block; keep it short.
    hint = ' / '.join(variants[:8])
    if hint and hint not in q:
        return f"{q} ({hint})"
    return q


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
    q_lower = q.lower()

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
    if codes and not instructor_intent:
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


def infer_domain(question: str) -> str | None:
    """Best-effort domain inference to reduce cross-domain noise.

    Returns one of KNOWN_DOMAINS (e.g., 'curriculum', 'regulations', 'announcements')
    or None if unclear.
    """
    q = (question or '').strip()
    if not q:
        return None

    ql = q.lower()

    # Curriculum signals: course codes / prefixes / curriculum-specific keywords.
    # Strong signal: explicit course codes (e.g., CPE 342, LNG 220, GEN 121)
    if re.search(r"\b[A-Za-z]{2,6}\s*\d{3}\b", q):
        return 'curriculum'
    
    # Strong signal: common curriculum prefixes
    if re.search(r"\b(cpe|lng|ssc|gen|cpx|cen|csc)\b", ql):
        return 'curriculum'
    
    # Medium signals: curriculum-specific keywords and phrases
    curriculum_indicators = (
        'หลักสูตร',           # curriculum
        'แผนการเรียน',        # study plan
        'หน่วยกิต',           # credits
        'วิชาบังคับ',         # required courses
        'วิชาเลือก',          # elective courses
        'คำอธิบายรายวิชา',    # course description
        'รายวิชา',            # course (if not registrar op)
        'ต้องผ่าน',           # must pass / prerequisite
        'บังคับก่อน',         # prerequisite
        'วิชาบังคับก่อน',     # prerequisite courses
        'ก่อนเรียน',          # before studying
        'สาขาวิชา',           # major/branch
        'กลุ่มวิชา',           # course group
        'หมวดวิชา',           # course category
        'ปีที่',               # year level
        'ชั้นปี',              # academic year/level
        'ภาคการศึกษา',        # semester
        'ต้องมีพื้นฐาน',       # must have foundation
    )
    
    # Don't route registrar operations to curriculum  
    _registrar_ops = ('ถอนรายวิชา', 'เพิ่ม-ลด', 'เพิ่มลด', 'ลงทะเบียน', 'ปฏิทิน', 'กำหนดการ')
    
    if any(t in q for t in curriculum_indicators) and not any(op in q for op in _registrar_ops):
        return 'curriculum'
    
    # Strong signal: foreign language questions with specific languages (likely LNG courses)
    if 'ภาษา' in q and any(t in q for t in ('จีน', 'ญี่ปุ่น', 'เกาหลี', 'ฝรั่งเศส', 'สเปน', 'เยอรมัน', 'รัสเซีย', 'มลายู', 'มาเล', 'ญี่ปุ่น', 'พม่า')):
        return 'curriculum'

    # Regulations/registrar signals.
    # Exam-policy / discipline questions should go to regulations even if they contain time words.
    _exam_policy_terms = (
        'ห้องสอบ', 'เข้าห้องสอบ', 'ออกห้องสอบ', 'ออกจากห้องสอบ', 'ออกห้องสอบชั่วคราว',
        'กรรมการคุมสอบ', 'คุมสอบ', 'ข้อสอบ', 'กระดาษคำตอบ', 'สมุดคำตอบ',
        'ทุจริต', 'ส่อ', 'ลงโทษ', 'บทลงโทษ', 'อุทธรณ์', 'คำอุทธรณ์',
        'คณะกรรมการกลาง', 'คณะกรรมการสอบ',
    )
    if any(t in q for t in _exam_policy_terms):
        return 'regulations'

    # Schedule / calendar / registration timing: these usually live in announcements.
    if any(t in q for t in ('ปฏิทิน', 'กำหนดการ', 'ลงทะเบียน', 'เพิ่ม-ลด', 'เพิ่มลด', 'ช่วง', 'วัน', 'วันที่', 'เมื่อไหร่')):
        return 'announcements'
    
    # Withdraw/W questions often need the academic calendar (announcements) more than policy text.
    if ('ถอนรายวิชา' in q or re.search(r"\bW\b|\(W\)", q, re.IGNORECASE)):
        # If user asks for when/how, prefer announcements.
        if any(t in q for t in ('เมื่อไหร่', 'ทำได้เมื่อไหร่', 'ช่วงไหน', 'ทำอย่างไร', 'ขั้นตอน', 'กำหนด')):
            return 'announcements'
        return 'regulations'

    if any(t in q for t in ('คำร้อง', 'แบบฟอร์ม', 'RO-', 'ลาออก', 'ลาป่วย', 'ลากิจ', 'ทัณฑ์บน', 'วินัย', 'ตัดคะแนนความประพฤติ', 'สอบซ้อน', 'เข้าสอบ')):
        return 'regulations'

    # Announcements signals.
    if 'ประกาศ' in q or 'announcement' in ql:
        return 'announcements'

    return None


def fallback_domains_for_domain(primary: str | None) -> list[str] | None:
    """Prefer nearby domains before widening retrieval across everything."""
    p = (primary or '').strip().lower()
    if p == 'announcements':
        return ['announcements', 'regulations']
    if p == 'regulations':
        return ['regulations', 'announcements']
    if p == 'curriculum':
        return ['curriculum', 'announcements']
    return None


def fallback_min_results() -> int:
    """Minimum retrieval count before trying a wider domain fallback."""
    try:
        return max(1, int(os.getenv('RAG_DOMAIN_FALLBACK_MIN_RESULTS', '2') or '2'))
    except Exception:
        return 2

def est_tokens(text: str) -> int:
    return max(1, int(math.ceil(len(text) / CHAR_PER_TOKEN)))


def _cite_label(c: Dict) -> str:
    src = c.get('source') or c.get('path') or 'unknown'
    try:
        name = Path(str(src)).name
    except Exception:
        name = str(src)
    page = c.get('page_start')
    try:
        page_i = int(page) if page is not None else 0
    except Exception:
        page_i = 0
    return f"{name}/{page_i}"


def _extract_reference_filename(question: str) -> str | None:
    """Extract a hinted source filename from the question.

    Supports patterns used in evaluation CSV, e.g. "(อ้างอิง: t_fee.txt)".
    Returns only the basename (no directories).
    """
    q = (question or '')
    m = re.search(r"\(\s*อ้างอิง\s*:\s*([^\)]+)\)", q)
    if not m:
        return None
    raw = (m.group(1) or '').strip().strip('"').strip("'")
    if not raw:
        return None
    # If user wrote multiple, pick the first token.
    raw = raw.split(',')[0].strip()
    try:
        return Path(raw).name
    except Exception:
        return raw


def _reference_candidates(question: str) -> list[str]:
    """Return likely filename variants for an '(อ้างอิง: ...)' hint."""
    ref = _extract_reference_filename(question)
    if not ref:
        return []
    try:
        base = Path(ref).name
    except Exception:
        base = str(ref).strip()
    base = (base or '').strip()
    if not base:
        return []

    try:
        p = Path(base)
        stem = p.stem
        ext = p.suffix
    except Exception:
        stem, ext = base, ''

    variants = [
        base,
        base.replace('-', '_'),
        base.replace('_', '-'),
    ]

    # Add .txt if missing or different
    if ext.lower() != '.txt':
        variants.append(stem + '.txt')

    # Normalize stem dash/underscore
    variants.append(stem.replace('-', '_') + '.txt')
    variants.append(stem.replace('_', '-') + '.txt')

    out: list[str] = []
    seen: set[str] = set()
    for v in variants:
        v = (v or '').strip()
        if not v:
            continue
        k = v.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(v)
    return out


def _infer_domain_from_reference(question: str) -> str | None:
    """Infer domain by checking for the referenced file under repo data/<domain>/."""
    cands = _reference_candidates(question)
    if not cands:
        return None
    data_root = Path(ROOT_DIR) / 'data'
    for dom in KNOWN_DOMAINS:
        for c in cands:
            try:
                if (data_root / dom / c).exists():
                    return dom
            except Exception:
                continue
    return None


def _filter_chunks_by_reference(chunks: List[Dict], question: str, strict: bool = False) -> List[Dict]:
    """If question explicitly references a source file, keep only matching chunks.

    If strict=True and the reference doesn't match any chunk, return an empty list.
    Otherwise (default), behaves conservatively and keeps the original list.
    """
    cands = _reference_candidates(question)
    if not cands:
        return chunks
    cand_l = {c.lower() for c in cands}

    def _src_name(d: Dict) -> str:
        src = d.get('source') or d.get('path') or (d.get('metadata') or {}).get('source') or (d.get('metadata') or {}).get('path')
        try:
            return Path(str(src)).name.lower()
        except Exception:
            return str(src or '').lower()

    filtered = [c for c in (chunks or []) if _src_name(c) in cand_l]
    # If strict match fails, allow "contains" (handles slightly different stored names).
    if not filtered:
        filtered = [c for c in (chunks or []) if any(cl in _src_name(c) for cl in cand_l)]

    # Keep original if we'd lose essentially all context (unless strict).
    if strict:
        return filtered
    if len(filtered) >= 2 or (len(filtered) == 1 and len(chunks) <= 3):
        return filtered
    return chunks


def hybrid_retrieve(question: str, k_vec: int = 20, k_kw: int = 30) -> List[Dict]:
    return retrieve_all_domains(question, k_vec=k_vec, k_kw=k_kw)


def retrieve_all_domains(
    question: str,
    k_vec: int = 20,
    k_kw: int = 30,
    domains: List[str] | None = None,
) -> List[Dict]:
    doms = [d.strip().lower() for d in (domains or list(KNOWN_DOMAINS)) if (d or '').strip()]
    if not doms:
        doms = list(KNOWN_DOMAINS)

    bank: Dict[str, Dict] = {}
    ranks: Dict[str, float] = {}

    for dom in doms:
        try:
            results = retrieve_by_domain(question, domain=dom, k_vec=k_vec, k_kw=k_kw)
        except Exception:
            # Best-effort: if one domain is missing/corrupt, still answer from others.
            continue

        # retrieve_by_domain already returns a ranked list; fuse across domains via RRF.
        for r, d in enumerate(results, 1):
            doc_id = d.get('doc_id') or d.get('source') or f'unk_{r}'
            key = f"{dom}:{doc_id}"
            if key not in bank:
                bank[key] = {**d, 'doc_id': doc_id, 'domain': dom}
            else:
                bank[key].setdefault('domain', dom)
            ranks[key] = ranks.get(key, 0.0) + 1.0 / (RRF_K + r)

    merged = [{**bank[k], 'score_rrf': v} for k, v in ranks.items()]
    merged.sort(key=lambda x: x.get('score_rrf', 0.0), reverse=True)
    return merged[:MAX_CONTEXTS]


def retrieve_by_domain(question: str, domain: str | None, k_vec: int = 20, k_kw: int = 30) -> List[Dict]:
    def _augment_curriculum_query(original_question: str, base_query: str) -> str:
        """Domain-specific query expansion for curriculum questions.

        Curriculum data relies heavily on course code matching and structured data.
        We add hints for common question patterns to improve recall.
        """
        q = (original_question or '').strip()
        if not q:
            return base_query

        hints: list[str] = []

        # Course description/title queries
        if any(t in q for t in ('คือวิชาอะไร', 'คือ', 'ชื่อ', 'ชื่อวิชา', 'เรื่องอะไร')):
            hints.extend(['รายวิชา', 'คำอธิบายวิชา', 'course description', 'title'])

        # Credit/unit queries
        if any(t in q for t in ('หน่วยกิต', 'กี่หน่วย', 'หน่วยการศึกษา', 'หน่วยกิตรวม')):
            hints.extend(['หน่วยกิต', 'credit', 'units', 'ชั่วโมง'])

        # Year/semester queries
        if any(t in q for t in ('ปีไหน', 'ชั้นปี', 'ปีที่', 'เทอม', 'ภาค')):
            hints.extend(['ปีที่', 'ชั้นปี', 'ภาคการศึกษา', 'semester', 'year'])

        # Category/group queries
        if any(t in q for t in ('กลุ่มวิชา', 'หมวดวิชา', 'แผนกวิชา', 'สาขา')):
            hints.extend(['หมวดวิชา', 'กลุ่มวิชา', 'category', 'group'])

        # Prerequisite queries
        if any(t in q for t in ('ต้องผ่าน', 'บังคับก่อน', 'ก่อนเรียน', 'prerequisite')):
            hints.extend(['วิชาบังคับก่อน', 'prerequisite', 'requirement', 'ต้องมีพื้นฐาน'])

        # Lecturer queries
        if any(t in q for t in ('ใครสอน', 'อาจารย์', 'ผู้สอน', 'teacher')):
            hints.extend(['อาจารย์', 'ผู้สอน', 'lecturer', 'instructor', 'teacher'])

        # Course code patterns
        if re.search(r"\b[A-Za-z]{2,6}\s*\d{3}\b", q):
            hints.extend(['รายวิชา', 'course code', 'course number'])

        # De-dup while preserving order.
        seen: set[str] = set()
        compact: list[str] = []
        for h in hints:
            s = (h or '').strip()
            if not s:
                continue
            k = s.lower()
            if k in seen:
                continue
            seen.add(k)
            compact.append(s)

        if not compact:
            return base_query

        # Keep it short; keyword search benefits from a few clause anchors.
        compact = compact[:12]
        hint_block = ' '.join(compact)
        if hint_block and hint_block not in (base_query or ''):
            return f"{base_query} {hint_block}".strip()
        return base_query

    def _augment_regulations_query(original_question: str, base_query: str) -> str:
        """Domain-specific query expansion for regulations.

        SQLite FTS tokenization for Thai can be brittle (few spaces), and some
        regulation texts contain typos (e.g., 'ออกหากห้องสอบ'). We append a
        compact set of high-signal keywords/clauses to improve recall.
        """
        q = (original_question or '').strip()
        if not q:
            return base_query

        hints: list[str] = []

        # Exam room entry/late arrival
        if ('เข้าห้องสอบ' in q) or ('มาสาย' in q) or ('สาย' in q and 'สอบ' in q):
            hints.extend([
                'ห้องสอบ', 'การสอบ',
                'ข้อ 12',
                'สิบห้านาที', '15',
                'หกสิบนาที', '60',
                'ยื่นคำร้อง',
                'ประธานกรรมการจัดการสอบ',
            ])

        # Leaving exam room (permanent)
        if ('ออกห้องสอบ' in q) or ('ออกจากห้องสอบ' in q):
            hints.extend([
                'ห้องสอบ', 'การสอบ',
                'ข้อ 15',
                'ออกหากห้องสอบ',  # typo present in source
                'หกสิบนาที', '60',
            ])

        # Temporary leave
        if ('ชั่วคราว' in q) or ('ออกห้องสอบชั่วคราว' in q):
            hints.extend([
                'ห้องสอบ', 'ชั่วคราว',
                'ข้อ 16',
                'กรรมการคุมสอบ',
                'เครื่องมือสื่อสาร',
            ])

        # Central committee term / duties
        if 'คณะกรรมการ' in q and ('กลาง' in q or 'สอบกลาง' in q):
            hints.extend([
                'คณะกรรมการกลาง', 'การสอบ', 'ทุจริต',
                'ข้อ 19', 'วาระ', 'สี่ปี', '4 ปี',
                'ข้อ 20', 'อำนาจหน้าที่',
            ])

        # Appeal process
        if 'อุทธรณ์' in q or ('ลงโทษ' in q and 'อุทธรณ์' in q):
            hints.extend([
                'หมวดที่ 5', 'การอุทธรณ์',
                'ข้อ 26', 'ข้อ 27', 'ข้อ 28', 'ข้อ 29', 'ข้อ 30',
                'อธิการบดี',
                'สิบห้าวัน', '15 วัน',
            ])

        # De-dup while preserving order.
        seen: set[str] = set()
        compact: list[str] = []
        for h in hints:
            s = (h or '').strip()
            if not s:
                continue
            k = s.lower()
            if k in seen:
                continue
            seen.add(k)
            compact.append(s)

        if not compact:
            return base_query

        # Keep it short; keyword search benefits from a few clause anchors.
        compact = compact[:18]
        hint_block = ' '.join(compact)
        if hint_block and hint_block not in (base_query or ''):
            return f"{base_query} {hint_block}".strip()
        return base_query

    def _clip_long_regulations_text(item: Dict, original_question: str) -> Dict:
        """Clip very long regulation texts to a relevant excerpt.

        Some regulation sources are indexed as a single large text blob. When
        that happens, `pack_context()` may skip them entirely due to the token
        budget, even if retrieval selected the correct document. We keep the
        same metadata but replace `text` with a focused excerpt.
        """
        try:
            txt = str(item.get('text') or '')
        except Exception:
            return item
        if not txt:
            return item

        # Only clip when the block is huge.
        max_chars = int(os.getenv('RAG_REGULATIONS_CLIP_CHARS', '2200') or '2200')
        if len(txt) <= max_chars:
            return item

        q = (original_question or '').strip()
        anchors: list[str] = []

        # Exam rules
        if ('มาสาย' in q) or ('เข้าห้องสอบ' in q):
            anchors += ['ข้อ 12']
        if ('ออกห้องสอบชั่วคราว' in q) or ('ชั่วคราว' in q and 'ห้องสอบ' in q):
            anchors += ['ข้อ 16']
        if ('ออกห้องสอบ' in q) or ('ออกจากห้องสอบ' in q):
            anchors += ['ข้อ 15', 'ข้อ 17']

        # Committee
        if 'คณะกรรมการ' in q and ('กลาง' in q or 'สอบกลาง' in q):
            anchors += ['ข้อ 19', 'ข้อ 20', 'คณะกรรมการกลาง']

        # Appeal
        if 'อุทธรณ์' in q:
            anchors += ['หมวดที่ 5', 'การอุทธรณ์', 'ข้อ 26', 'ข้อ 27', 'ข้อ 28', 'ข้อ 29', 'ข้อ 30']

        # De-dup anchors
        seen: set[str] = set()
        dedup: list[str] = []
        for a in anchors:
            s = (a or '').strip()
            if not s:
                continue
            k = s.lower()
            if k in seen:
                continue
            seen.add(k)
            dedup.append(s)
        anchors = dedup

        # Find a best anchor position.
        pos = -1
        hit = ''
        for a in anchors:
            p = txt.find(a)
            if p != -1:
                pos = p
                hit = a
                break

        # If no anchor found, fallback to the first part.
        if pos == -1:
            clipped = txt[:max_chars].rstrip()
        else:
            # Keep a window around the anchor; prefer expanding to newline boundaries.
            window = int(os.getenv('RAG_REGULATIONS_CLIP_WINDOW', '1600') or '1600')
            half = max(200, window // 2)
            start = max(0, pos - half)
            end = min(len(txt), pos + half)

            # Expand to nearest newlines (best-effort) to keep it readable.
            nl_left = txt.rfind('\n', 0, start)
            if nl_left != -1 and (start - nl_left) < 200:
                start = nl_left + 1
            nl_right = txt.find('\n', end)
            if nl_right != -1 and (nl_right - end) < 200:
                end = nl_right

            clipped = txt[start:end].strip()
            if hit and hit not in clipped:
                # Safety: ensure anchor appears in excerpt.
                clipped = (hit + " ...\n" + clipped).strip()

        out = dict(item)
        out['text'] = clipped
        return out

    def _question_terms_for_rerank(text: str) -> list[str]:
        q = (text or '').strip()
        if not q:
            return []
        stop_terms = {
            'อะไร', 'อย่างไร', 'หรือ', 'และ', 'ของ', 'ใน', 'ที่', 'ได้', 'ไหม', 'บ้าง', 'จาก', 'ให้', 'กับ',
            'เรื่อง', 'ข้อมูล', 'เอกสาร', 'ระบุ', 'ถาม', 'ตอบ', 'หน่อย', 'ครับ', 'ค่ะ', 'คะ', 'คือ', 'มี',
            'เท่าไร', 'เท่าไหร่', 'เมื่อไร', 'วันที่', 'วัน', 'หลักสูตร', 'วิชา', 'รายวิชา'
        }
        out: list[str] = []
        seen: set[str] = set()
        for token in re.findall(r"[\u0E00-\u0E7F]{3,}|[A-Za-z]{2,}|\d{2,4}", q):
            key = token.lower()
            if key in stop_terms or key in seen:
                continue
            seen.add(key)
            out.append(token)
        return out[:8]

    def _apply_lexical_rerank(items: List[Dict], original_question: str, active_domain: str) -> List[Dict]:
        dom = (active_domain or '').strip().lower()
        if dom not in ('announcements', 'regulations') or not items:
            return items
        terms = _question_terms_for_rerank(original_question)
        if not terms:
            return items
        boosted: List[Dict] = []
        for item in items:
            text = ' '.join(
                [
                    str(item.get('text') or ''),
                    str(item.get('source') or ''),
                    str(item.get('path') or ''),
                ]
            ).lower()
            matches = sum(1 for term in terms if term.lower() in text)
            updated = dict(item)
            updated['score_rrf'] = float(updated.get('score_rrf') or 0.0) + (matches * 0.08)
            boosted.append(updated)
        boosted.sort(key=lambda x: float(x.get('score_rrf') or 0.0), reverse=True)
        return boosted

    def _apply_curriculum_rerank(items: List[Dict], original_question: str, target_codes: set[str]) -> List[Dict]:
        """Curriculum-specific reranking to boost exact course code matches.

        Prioritizes documents that directly match extracted course codes.
        """
        if not items or not target_codes:
            return items
        
        boosted: List[Dict] = []
        for item in items:
            updated = dict(item)
            base_score = float(updated.get('score_rrf') or 0.0)
            
            # Check if item matches any target course code
            if _item_matches_course_codes(item, target_codes):
                # Boost score significantly for exact matches
                updated['score_rrf'] = base_score + 0.5
                updated['_curriculum_match'] = True
            
            boosted.append(updated)
        
        # Sort: exact matches first, then by original RRF score
        def sort_key(x):
            has_match = float(x.get('_curriculum_match', False))
            return (has_match, float(x.get('score_rrf', 0.0)))
        
        boosted.sort(key=sort_key, reverse=True)
        
        # Clean up temporary fields
        for item in boosted:
            item.pop('_curriculum_match', None)
        
        return boosted

    def _hydrate_from_sqlite(items: List[Dict], sqlite_path: str | None) -> List[Dict]:
        """Replace item text/metadata from SQLite when doc_id is known.

        Chroma collections can be stale or OCR-corrupted compared to the SQLite index.
        When both share doc_id, prefer SQLite as the canonical source of truth for
        context packing.
        """
        if not items or not sqlite_path:
            return items
        doc_ids: List[str] = []
        seen: set[str] = set()
        for it in items:
            did = it.get('doc_id')
            if isinstance(did, str) and did and did not in seen:
                doc_ids.append(did)
                seen.add(did)
        if not doc_ids:
            return items
        docs = fetch_docs_with_path(doc_ids, sqlite_path=sqlite_path)
        by_id = {d.get('doc_id'): d for d in docs if d.get('doc_id')}
        out: List[Dict] = []
        for it in items:
            did = it.get('doc_id')
            db = by_id.get(did) if isinstance(did, str) else None
            if not db:
                out.append(it)
                continue
            # Preserve semantic scores/fields on `it`, but prefer canonical metadata/text from SQLite.
            merged = dict(it)
            for k in (
                'text',
                'source',
                'path',
                'file_type',
                'page_start',
                'page_end',
                'owner',
                'sensitivity',
                'updated_at',
                'tokens_est',
            ):
                if db.get(k) is not None:
                    merged[k] = db.get(k)
            out.append(merged)
        return out

    def _meta_get(item: Dict, key: str):
        if key in item:
            return item.get(key)
        md = item.get('metadata') or {}
        if isinstance(md, dict):
            return md.get(key)
        return None

    def _normalize_code_text(text: str) -> str:
        return re.sub(r"[^A-Za-z0-9]", "", (text or '').upper())

    def _item_section_path(item: Dict) -> list[str]:
        raw = _meta_get(item, 'section_path')
        if isinstance(raw, list):
            return [str(x) for x in raw]
        if isinstance(raw, str):
            s = raw.strip()
            if not s:
                return []
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except Exception:
                pass
            return [s]
        return []

    def _is_faculty_course_relation(item: Dict) -> bool:
        dt = str(_meta_get(item, 'doc_type') or '').strip().lower()
        if dt == 'faculty_course_relation':
            return True
        sec = str(_meta_get(item, 'section') or '').strip().lower()
        if sec == 'facultycourserelation':
            return True
        section_path = '/'.join(_item_section_path(item)).lower()
        return 'facultycourserelation' in section_path

    def _item_matches_course_codes(item: Dict, target_codes: set[str]) -> bool:
        if not target_codes:
            return False

        candidates: list[str] = []
        for k in ('course_code', 'course_code_norm', 'course', 'course_id', 'entity_key'):
            v = _meta_get(item, k)
            if v is not None:
                candidates.append(str(v))
        aliases = _meta_get(item, 'aliases')
        if isinstance(aliases, list):
            candidates.extend([str(x) for x in aliases if x is not None])
        links_to = _meta_get(item, 'links_to')
        if isinstance(links_to, list):
            candidates.extend([str(x) for x in links_to if x is not None])
        candidates.extend(_item_section_path(item))
        txt = item.get('text')
        if isinstance(txt, str) and txt:
            candidates.append(txt)

        for c in candidates:
            norm = _normalize_code_text(c)
            if not norm:
                continue
            for t in target_codes:
                if t and (t == norm or t in norm):
                    return True
        return False

    def _contains_target_code_in_visible_fields(item: Dict, target_codes: set[str]) -> bool:
        if not target_codes:
            return False
        blob = ' '.join(
            [
                str(item.get('text') or ''),
                str(item.get('source') or ''),
                str(item.get('path') or ''),
            ]
        )
        norm_blob = _normalize_code_text(blob)
        if not norm_blob:
            return False
        for t in target_codes:
            if t and t in norm_blob:
                return True
        return False

    dom = (domain or '').strip().lower()
    add_metric('retrieval_domain', dom or 'auto')

    # Use the original question to detect explicit reference hints, but use a cleaned query
    # string for retrieval so the hint doesn't pollute embedding/keyword search.
    q_search = search_query_from_question(question)
    if dom == 'regulations':
        q_search = _augment_regulations_query(question, q_search)
    elif dom == 'curriculum':
        q_search = _augment_curriculum_query(question, q_search)

    ref_allow = _reference_candidates(question)
    source_allowlist: Sequence[str] | None = ref_allow if ref_allow else None
    strict_ref_hints = (os.getenv('STRICT_REFERENCE_HINTS', '1') or '1').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )
    strict_ref = bool(source_allowlist) and strict_ref_hints
    add_metric('retrieval_ref_hint_count', len(ref_allow or []))
    add_metric('retrieval_strict_ref', int(strict_ref))

    # Domain 1&2: vector + keyword/FTS
    if dom in ('announcements', 'regulations'):
        sqlite_path = domain_sqlite_path(dom)

        with time_block('vector_search'):
            sem = semantic_search_domain(q_search, top_k=k_vec, domain=dom, source_allowlist=source_allowlist)
        with time_block('hydrate_sqlite'):
            sem = _hydrate_from_sqlite(sem, sqlite_path)
        with time_block('keyword_search'):
            kw_ids = keyword_search(q_search, limit=k_kw, sqlite_path=sqlite_path, source_allowlist=source_allowlist)
        with time_block('fetch_kw_docs'):
            kw_docs = fetch_docs_with_path(kw_ids, sqlite_path=sqlite_path)
        add_metric('retrieval_sem_n', len(sem))
        add_metric('retrieval_kw_n', len(kw_docs))

        # If the user explicitly referenced a source, stay within it (avoid cross-doc hallucinations).
        if (not strict_ref) and source_allowlist and (len(sem) + len(kw_docs) < 2):
            add_metric('retrieval_source_fallback_used', 1)
            with time_block('vector_search_fallback'):
                sem = semantic_search_domain(q_search, top_k=k_vec, domain=dom, source_allowlist=None)
            with time_block('hydrate_sqlite_fallback'):
                sem = _hydrate_from_sqlite(sem, sqlite_path)
            with time_block('keyword_search_fallback'):
                kw_ids = keyword_search(q_search, limit=k_kw, sqlite_path=sqlite_path, source_allowlist=None)
            with time_block('fetch_kw_docs_fallback'):
                kw_docs = fetch_docs_with_path(kw_ids, sqlite_path=sqlite_path)
            add_metric('retrieval_sem_n', len(sem))
            add_metric('retrieval_kw_n', len(kw_docs))

        bank: Dict[str, Dict] = {}
        ranks: Dict[str, float] = {}

        for r, d in enumerate(sem, 1):
            doc_id = d.get('doc_id') or d.get('source') or f'vec_{r}'
            bank[doc_id] = d
            ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + r)

        for r, d in enumerate(kw_docs, 1):
            doc_id = d.get('doc_id') or f'kw_{r}'
            bank.setdefault(doc_id, d)
            ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + r)

        merged = [{**bank[k], 'score_rrf': v, 'doc_id': k} for k, v in ranks.items()]
        merged.sort(key=lambda x: x['score_rrf'], reverse=True)
        merged = _apply_lexical_rerank(merged, question, dom)
        add_metric('retrieval_merged_n', len(merged))
        add_metric('retrieval_final_n', min(len(merged), MAX_CONTEXTS))
        picked = merged[:MAX_CONTEXTS]
        if dom == 'regulations':
            picked = [_clip_long_regulations_text(it, question) for it in picked]
        return picked

    # Domain 3: curriculum = vector + keyword + graph expansion
    # If no domain was provided, keep legacy behavior (vector+keyword on default env paths)
    sqlite_path = domain_sqlite_path(dom) if dom else None

    with time_block('vector_search'):
        sem = semantic_search_domain(q_search, top_k=k_vec, domain=dom or None, source_allowlist=source_allowlist)
    with time_block('hydrate_sqlite'):
        sem = _hydrate_from_sqlite(sem, sqlite_path)
    with time_block('keyword_search'):
        kw_ids = keyword_search(q_search, limit=k_kw, sqlite_path=sqlite_path, source_allowlist=source_allowlist)
    with time_block('fetch_kw_docs'):
        kw_docs = fetch_docs_with_path(kw_ids, sqlite_path=sqlite_path)
    add_metric('retrieval_sem_n', len(sem))
    add_metric('retrieval_kw_n', len(kw_docs))

    if (not strict_ref) and source_allowlist and (len(sem) + len(kw_docs) < 2):
        add_metric('retrieval_source_fallback_used', 1)
        with time_block('vector_search_fallback'):
            sem = semantic_search_domain(q_search, top_k=k_vec, domain=dom or None, source_allowlist=None)
        with time_block('hydrate_sqlite_fallback'):
            sem = _hydrate_from_sqlite(sem, sqlite_path)
        with time_block('keyword_search_fallback'):
            kw_ids = keyword_search(q_search, limit=k_kw, sqlite_path=sqlite_path, source_allowlist=None)
        with time_block('fetch_kw_docs_fallback'):
            kw_docs = fetch_docs_with_path(kw_ids, sqlite_path=sqlite_path)
        add_metric('retrieval_sem_n', len(sem))
        add_metric('retrieval_kw_n', len(kw_docs))

    # Heuristic: users often ask "LNGxxx มีวิชาอะไรให้เลือกเรียนบ้าง" without naming languages.
    # Pull in curriculum chunks anchored by the "รายวิชา: LNG" header to increase recall.
    lng_docs: List[Dict] = []
    lng_diverse_docs: List[Dict] = []
    wants_lng_list = False
    q = (question or '')
    q_lower = q.lower()
    codes = sorted(extract_course_codes(question))
    target_codes = {_normalize_code_text(c) for c in codes if _normalize_code_text(c)}

    exact_code_docs: List[Dict] = []
    exact_code_doc_ids: set[str] = set()
    exact_first_enabled = (os.getenv('RAG_CURRICULUM_EXACT_CODE_FIRST', '1') or '1').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )
    add_metric('retrieval_exact_code_route_enabled', int(exact_first_enabled))
    if dom == 'curriculum' and target_codes and exact_first_enabled:
        # Exact-first retrieval path for course-code questions.
        candidate_docs = [*sem, *kw_docs]
        for d in candidate_docs:
            did = d.get('doc_id')
            if not isinstance(did, str) or did in exact_code_doc_ids:
                continue
            if _item_matches_course_codes(d, target_codes):
                exact_code_docs.append(d)
                exact_code_doc_ids.add(did)

        # If merged candidates still miss exact hits, query SQLite by normalized code variants.
        if not exact_code_docs:
            exact_ids: List[str] = []
            seen_ids: set[str] = set()
            for code in sorted(target_codes):
                if len(code) < 4:
                    continue
                needles = [code]
                mcode = re.match(r"^([A-Z]{2,6})(\d{3})$", code)
                if mcode:
                    needles = [f"{mcode.group(1)} {mcode.group(2)}", code, f"รายวิชา: {mcode.group(1)}"]
                for needle in needles:
                    for did in keyword_search(needle, limit=max(40, k_kw), sqlite_path=sqlite_path):
                        if did and did not in seen_ids:
                            exact_ids.append(did)
                            seen_ids.add(did)
                    if len(exact_ids) >= max(80, k_kw * 2):
                        break
                if len(exact_ids) >= max(80, k_kw * 2):
                    break
            if exact_ids:
                exact_fetched = fetch_docs_with_path(exact_ids, sqlite_path=sqlite_path)
                # Keep only chunks that truly contain the target course code and have usable text.
                exact_code_docs = [
                    d
                    for d in exact_fetched
                    if _item_matches_course_codes(d, target_codes)
                    and _contains_target_code_in_visible_fields(d, target_codes)
                    and str(d.get('text') or '').strip()
                ]
                exact_code_doc_ids = {d.get('doc_id') for d in exact_code_docs if isinstance(d.get('doc_id'), str)}

    add_metric('retrieval_exact_code_hits_n', len(exact_code_docs))
    if dom == 'curriculum':
        wants_lng_list = (
            re.search(r"LNG", q, re.IGNORECASE) is not None
            and any(t in q for t in ('เลือกเรียน', 'มีวิชา', 'วิชาอะไร', 'เลือกได้', 'ตัวเลือก'))
        )
        if wants_lng_list:
            add_metric('retrieval_lng_query', 1)
            with time_block('lng_keyword_search'):
                lng_ids = keyword_search('รายวิชา: LNG', limit=max(80, k_kw * 2), sqlite_path=sqlite_path)
            with time_block('lng_fetch_docs'):
                lng_docs = fetch_docs_with_path(lng_ids, sqlite_path=sqlite_path)

            # If Neo4j is configured, also fetch LNG* chunks via graph to improve recall.
            with time_block('neo4j_course_prefix'):
                graph_lng_ids = graph_doc_ids_for_course_prefix('LNG', domain=dom, limit=160)
            if graph_lng_ids:
                with time_block('neo4j_fetch_docs'):
                    lng_docs.extend(fetch_docs_with_path(graph_lng_ids, sqlite_path=sqlite_path))

            # Prefer diversity across *non-English* languages rather than many English-only chunks.
            # Many curriculum chunks start with "รายวิชา: LNG ... ภาษาอังกฤษ..." and can crowd out
            # Japanese/Chinese/Burmese/etc. So we pick non-English first.
            def _lang_name(txt: str) -> str | None:
                m = re.search(r"ภาษา([\u0E00-\u0E7F]{2,20})", txt or '')
                return m.group(1) if m else None

            non_en: dict[str, Dict] = {}
            en: dict[str, Dict] = {}
            other: list[Dict] = []
            for d in lng_docs:
                txt = (d.get('text') or '')
                name = _lang_name(txt)
                if not name:
                    other.append(d)
                    continue
                if name.startswith('อังกฤษ') or name.startswith('ไทย'):
                    en.setdefault(name, d)
                else:
                    non_en.setdefault(name, d)

            # Seed some specific languages if present (helps when OCR variations exist).
            priority_markers = ['ญี่ปุ่น', 'จีน', 'พม่า', 'เกาหลี', 'ฝรั่งเศส', 'สเปน', 'เยอรมัน', 'รัสเซีย']
            picked_ids: set[str] = set()
            for mkr in priority_markers:
                for d in lng_docs:
                    did = d.get('doc_id')
                    if not isinstance(did, str) or did in picked_ids:
                        continue
                    if mkr in (d.get('text') or ''):
                        lng_diverse_docs.append(d)
                        picked_ids.add(did)
                        break

            for _name, d in non_en.items():
                did = d.get('doc_id')
                if isinstance(did, str) and did not in picked_ids:
                    lng_diverse_docs.append(d)
                    picked_ids.add(did)
                if len(lng_diverse_docs) >= 14:
                    break

            # Keep a couple of English chunks too (often required in answers).
            for _name, d in en.items():
                did = d.get('doc_id')
                if isinstance(did, str) and did not in picked_ids:
                    lng_diverse_docs.append(d)
                    picked_ids.add(did)
                if len(lng_diverse_docs) >= 18:
                    break
            add_metric('retrieval_lng_docs_n', len(lng_diverse_docs or lng_docs))

    # Default context cap; expand for list-style LNG questions.
    max_contexts = max(MAX_CONTEXTS, 20) if wants_lng_list else MAX_CONTEXTS

    wants_prereq = False
    if dom == 'curriculum':
        ql = q.lower()
        wants_prereq = any(
            t in ql
            for t in (
                'ต้องผ่าน',
                'บังคับก่อน',
                'วิชาบังคับก่อน',
                'ก่อนเรียน',
                'prerequisite',
                'pre-requisite',
                'pre requisite',
            )
        )

    simple_curriculum_lookup = False
    if dom == 'curriculum':
        simple_curriculum_lookup = bool(codes) or any(
            t in q_lower for t in ('รวมกี่หน่วยกิต', 'หน่วยกิตรวมของหลักสูตร', 'จำนวนหน่วยกิตรวม', 'ตลอดหลักสูตร')
        )

    # Heuristic: short course-prefix queries like "SSC" often get drowned out by generic
    # curriculum chunks containing the word "วิชา". If users are clearly asking for courses
    # under a prefix, force-boost prefix-matching chunks.
    prefix_docs: List[Dict] = []
    wants_prefix_list = False
    if dom == 'curriculum':
        # Capture standalone ASCII prefixes (2-6 letters) like SSC, LNG, GEN.
        prefixes = [m.upper() for m in re.findall(r"\b[A-Za-z]{2,6}\b", q or '')]
        # Drop overly-generic/common English words that can appear in questions.
        stop = {
            'AND', 'OR', 'NOT', 'THE', 'THIS', 'THAT', 'WITH', 'FROM', 'WHAT', 'HOW', 'WHY',
            'CAN', 'COULD', 'SHOULD', 'WANT', 'FIND', 'COURSE', 'COURSES', 'CODE'
        }
        prefixes = [p for p in prefixes if p not in stop]

        wants_prefix_list = bool(prefixes) and any(
            t in (q or '')
            for t in (
                'หาวิชา', 'หา', 'วิชา', 'รายวิชา', 'มีวิชา', 'รหัสวิชา', 'เลือกเรียน', 'ตัวเลือก'
            )
        )

        if wants_prefix_list:
            add_metric('retrieval_prefix_query', 1)
            pref_ids: List[str] = []
            seen: set[str] = set()
            # Pull a wider candidate pool then let ranking/packing decide.
            for pref in prefixes:
                # Prefer exact prefix hits (e.g., "SSC 162")
                for needle in (f"{pref} ", pref):
                    ids = keyword_search(needle, limit=max(80, k_kw * 3), sqlite_path=sqlite_path)
                    for did in ids:
                        if did and did not in seen:
                            pref_ids.append(did)
                            seen.add(did)
                if len(pref_ids) >= 200:
                    break
            prefix_docs = fetch_docs_with_path(pref_ids, sqlite_path=sqlite_path)
            add_metric('retrieval_prefix_docs_n', len(prefix_docs))

    # Graph expansion (best-effort; requires Neo4j + graph ingested)
    add_metric('course_codes', len(codes))
    graph_docs: List[Dict] = []
    if dom == 'curriculum' and codes and not simple_curriculum_lookup:
        with time_block('neo4j_codes'):
            graph_ids = graph_doc_ids_for_codes(codes=codes, domain=dom, limit=max(30, MAX_CONTEXTS * 8))
        with time_block('neo4j_fetch_docs'):
            graph_docs = fetch_docs_with_path(graph_ids, sqlite_path=sqlite_path)
        add_metric('retrieval_graph_docs_n', len(graph_docs))

    prereq_docs: List[Dict] = []
    if dom == 'curriculum' and wants_prereq and codes and not simple_curriculum_lookup:
        with time_block('neo4j_prereq'):
            prereq_ids = graph_doc_ids_for_requisites(codes=codes, domain=dom, kind='prereq', limit=max(60, MAX_CONTEXTS * 10))
        if prereq_ids:
            with time_block('neo4j_fetch_docs'):
                prereq_docs = fetch_docs_with_path(prereq_ids, sqlite_path=sqlite_path)
        add_metric('retrieval_prereq_docs_n', len(prereq_docs))

    # Graph neighborhood expansion from retrieved chunks (works even without course codes)
    graph_neighbor_docs: List[Dict] = []
    if dom == 'curriculum' and not simple_curriculum_lookup:
        seed_ids: List[str] = []
        for d in (sem[:8] + kw_docs[:8]):
            did = d.get('doc_id')
            if did and did not in seed_ids:
                seed_ids.append(did)
        if seed_ids:
            with time_block('neo4j_neighbors'):
                neighbor_ids = graph_expand_from_seed_chunks(seed_ids, domain=dom, window=2, limit=max(60, MAX_CONTEXTS * 8))
            with time_block('neo4j_fetch_docs'):
                graph_neighbor_docs = fetch_docs_with_path(neighbor_ids, sqlite_path=sqlite_path)
        add_metric('retrieval_neighbor_docs_n', len(graph_neighbor_docs))

    bank: Dict[str, Dict] = {}
    ranks: Dict[str, float] = {}

    # vector ranks
    for r, d in enumerate(sem, 1):
        doc_id = d.get('doc_id') or d.get('source') or f'vec_{r}'
        bank[doc_id] = d
        ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + r)
    # keyword ranks
    credit_total_re = None
    if dom == 'curriculum' and ('หน่วยกิต' in (question or '')):
        credit_total_re = re.compile(r"จ\s*า\s*น\s*ว\s*น\s*หน่วยกิต\s*ที่\s*เรียน\s*ตลอด\s*หลักสูตร[^\d]{0,60}(\d{2,3})\s*หน่วยกิต")

    for r, d in enumerate(kw_docs, 1):
        doc_id = d.get('doc_id') or f'kw_{r}'
        bank.setdefault(doc_id, d)
        ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + r)

        # Extra boost when the chunk clearly contains the total-credits statement.
        if credit_total_re is not None:
            txt = (d.get('text') or '')
            if txt and credit_total_re.search(txt):
                ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0

    # LNG anchor ranks (boost diverse languages to surface options beyond EN/TH)
    if wants_lng_list and lng_diverse_docs:
        for r, d in enumerate(lng_diverse_docs, 1):
            doc_id = d.get('doc_id') or f'lng_{r}'
            bank.setdefault(doc_id, d)
            # Stronger boost for list-style questions so multiple languages appear in context.
            ranks[doc_id] = ranks.get(doc_id, 0.0) + 6.0 / (RRF_K + r)

    # Course-prefix anchor ranks (e.g., SSC/GEN/LNG*)
    if dom == 'curriculum' and wants_prefix_list and prefix_docs:
        for r, d in enumerate(prefix_docs, 1):
            doc_id = d.get('doc_id') or f'pref_{r}'
            bank.setdefault(doc_id, d)
            # Strong boost so prefix-relevant chunks survive the top-k cutoff.
            ranks[doc_id] = ranks.get(doc_id, 0.0) + 8.0 / (RRF_K + r)

    # graph ranks
    for r, d in enumerate(graph_docs, 1):
        doc_id = d.get('doc_id') or f'graph_{r}'
        bank.setdefault(doc_id, d)
        ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + r)

    # neighborhood ranks (slightly down-weight by shifting rank)
    for r, d in enumerate(graph_neighbor_docs, 1):
        doc_id = d.get('doc_id') or f'graphn_{r}'
        bank.setdefault(doc_id, d)
        ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + (r + 10))

    # prereq ranks (boost when question is explicitly about prerequisites)
    if dom == 'curriculum' and wants_prereq and prereq_docs:
        for r, d in enumerate(prereq_docs, 1):
            doc_id = d.get('doc_id') or f'prereq_{r}'
            bank.setdefault(doc_id, d)
            ranks[doc_id] = ranks.get(doc_id, 0.0) + 2.5 / (RRF_K + r)

    if dom == 'curriculum':
        teacher_markers = (
            'ใครสอน',
            'ผู้สอน',
            'อาจารย์',
            'สอนวิชา',
            'คนสอน',
            'ผู้รับผิดชอบวิชา',
            'instructor',
            'teacher',
            'teaches',
        )
        wants_teacher_for_course = bool(codes) and any(m in q_lower for m in teacher_markers)
        if wants_teacher_for_course:
            try:
                relation_boost = float(os.getenv('RAG_FACULTY_RELATION_BOOST', '1.2') or '1.2')
            except Exception:
                relation_boost = 1.2

            boosted = 0
            for doc_id, d in bank.items():
                if not _is_faculty_course_relation(d):
                    continue
                if not _item_matches_course_codes(d, target_codes):
                    continue
                ranks[doc_id] = ranks.get(doc_id, 0.0) + relation_boost
                boosted += 1

            add_metric('retrieval_teacher_course_intent', 1)
            add_metric('retrieval_fac_rel_boosted_n', boosted)

    merged = [{**bank[k], 'score_rrf': v, 'doc_id': k} for k, v in ranks.items()]
    merged.sort(key=lambda x: x['score_rrf'], reverse=True)
    
    # Apply curriculum-specific reranking to boost exact course code matches
    if dom == 'curriculum' and target_codes:
        merged = _apply_curriculum_rerank(merged, question, target_codes)

    if dom == 'curriculum' and exact_code_docs:
        # Force-include a few exact course-code hits before generic ranking.
        must_include = min(5, max_contexts)
        picked: List[Dict] = []
        seen: set[str] = set()

        # Prioritize exact chunks that visibly include the target code and non-empty text.
        exact_sorted = sorted(
            exact_code_docs,
            key=lambda d: (
                0 if _contains_target_code_in_visible_fields(d, target_codes) else 1,
                0 if str(d.get('text') or '').strip() else 1,
                len((d.get('text') or '').strip()) if isinstance(d.get('text'), str) else 10**9,
            ),
        )
        for d in exact_sorted:
            did = d.get('doc_id')
            if isinstance(did, str) and did not in seen:
                picked.append(d)
                seen.add(did)
                if len(picked) >= must_include:
                    break

        for m in merged:
            did = m.get('doc_id')
            if isinstance(did, str) and did not in seen:
                picked.append(m)
                seen.add(did)
                if len(picked) >= max_contexts:
                    break
        add_metric('retrieval_merged_n', len(merged))
        add_metric('retrieval_final_n', len(picked))
        return picked

    if dom == 'curriculum' and wants_prefix_list and prefix_docs:
        pref_set = {d.get('doc_id') for d in prefix_docs if d.get('doc_id')}
        must_include = min(2, max_contexts)
        picked: List[Dict] = []
        seen: set[str] = set()
        # Force-include a couple prefix chunks first.
        for m in merged:
            did = m.get('doc_id')
            if isinstance(did, str) and did in pref_set and did not in seen:
                picked.append(m)
                seen.add(did)
                if len(picked) >= must_include:
                    break
        # Then fill as usual.
        for m in merged:
            did = m.get('doc_id')
            if isinstance(did, str) and did not in seen:
                picked.append(m)
                seen.add(did)
                if len(picked) >= max_contexts:
                    break
            add_metric('retrieval_merged_n', len(merged))
            add_metric('retrieval_final_n', len(picked))
        return picked

    if dom == 'curriculum' and graph_neighbor_docs:
        neighbor_set = {d.get('doc_id') for d in graph_neighbor_docs if d.get('doc_id')}
        # Force-include up to 2 neighbor chunks to make graph expansion observable/useful.
        must_include = min(2, max_contexts)
        picked: List[Dict] = []
        seen: set[str] = set()
        for m in merged:
            did = m.get('doc_id')
            if isinstance(did, str) and did in neighbor_set and did not in seen:
                picked.append(m)
                seen.add(did)
                if len(picked) >= must_include:
                    break
        for m in merged:
            did = m.get('doc_id')
            if isinstance(did, str) and did not in seen:
                picked.append(m)
                seen.add(did)
                if len(picked) >= max_contexts:
                    break
        add_metric('retrieval_merged_n', len(merged))
        add_metric('retrieval_final_n', len(picked))
        return picked

    add_metric('retrieval_merged_n', len(merged))
    add_metric('retrieval_final_n', min(len(merged), max_contexts))
    return merged[:max_contexts]


def pack_context(
    chunks: List[Dict],
    budget_tokens: int = TOKEN_BUDGET,
    truncate_chars: int | None = None,
) -> Tuple[str, Dict[int, str]]:
    packed_blocks = []
    used = 0
    cites = {}
    for i, c in enumerate(chunks, 1):
        cite = _cite_label(c)
        txt = (c.get('text', '') or '').strip()
        if truncate_chars is not None and truncate_chars > 0 and len(txt) > truncate_chars:
            txt = txt[:truncate_chars].rstrip() + ' ...'
        block = f"[{cite}] {txt}"
        t = est_tokens(block)
        if used + t > budget_tokens:
            # Don't stop entirely; later chunks may be smaller and still fit.
            continue
        packed_blocks.append(block)
        used += t
        cites[i] = cite
    return '\n\n'.join(packed_blocks), cites


def build_prompt(question: str, ctx: str, cites: Dict[int, str]) -> str:
    require_citations = (os.getenv('RAG_REQUIRE_CITATIONS', '0') or '0').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )

    allowed_cites: list[str] = []
    seen: set[str] = set()
    for c in (cites or {}).values():
        s = (c or '').strip()
        if not s or s in seen:
            continue
        seen.add(s)
        allowed_cites.append(s)

    allowed_block = "\n".join([f"- [{c}]" for c in allowed_cites])

    if require_citations:
        instruction = (
            "คุณคือผู้ช่วยของภาควิชาวิศวกรรมคอมพิวเตอร์ ณ มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี ตอบเป็นภาษาไทย.\n"
            "หลักการตอบ:\n"
            "1) ใช้เฉพาะข้อมูลในบริบทที่ให้ หากไม่พบคำตอบแบบชัดเจน ให้ตอบสิ่งที่สรุปได้จากบริบทเท่านั้น และระบุชัดเจนว่าเอกสารไม่ได้กล่าวตรง ๆ หรือไม่มีข้อความยืนยันโดยตรง.\n"
            "2) ให้ตอบเป็น bullet เป็นหลัก (ขึ้นต้นด้วย '- ') และแต่ละ bullet ต้องลงท้ายด้วยการอ้างอิงอย่างน้อย 1 รายการต่อบรรทัด โดยใส่ท้ายบรรทัดในรูปแบบ [source/page].\n"
            "3) ห้ามเดาข้อมูลนอกรายการที่มี ใช้เฉพาะข้อมูลที่มีในบริบทเท่านั้น.\n"
            "4) หากคำถามขอ 'สรุป' หรือ 'โครงสร้าง' ให้จัดลำดับหัวข้อก่อนรายละเอียด.\n"
            "5) หากคำถามกำกวม/สั้นมาก (เช่น พิมพ์แค่ชื่อภาษา หรือ xxx) ให้ถามกลับ 1 คำถามสั้น ๆ เพื่อขอรายละเอียดที่จำเป็นก่อน.\n"
            "6) ห้ามให้ URL/ลิงก์ภายนอก เว้นแต่ URL นั้นปรากฏอยู่ในบริบท.\n"
            "7) เรื่องวัน/วันที่/เดดไลน์: ให้ระบุเฉพาะวันที่ที่มีข้อความยืนยันตรง ๆ ในบริบทเท่านั้น ห้ามอนุมานเดดไลน์จากคำว่า 'ประกาศ ณ วันที่ ...' หรือวันที่ที่ไม่ได้ระบุว่าเป็นกำหนดการ/เส้นตาย.\n"
            
        )
    else:
        instruction = (
            "คุณคือผู้ช่วยของภาควิชาวิศวกรรมคอมพิวเตอร์ ณ มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี ตอบเป็นภาษาไทย.\n"
            "หลักการตอบ:\n"
            "1) ใช้เฉพาะข้อมูลในบริบทที่ให้ หากไม่พบคำตอบแบบชัดเจน ให้ตอบสิ่งที่สรุปได้จากบริบทเท่านั้น และระบุชัดเจนว่าเอกสารไม่ได้กล่าวตรง ๆ หรือไม่มีข้อความยืนยันโดยตรง.\n"
            "2) ให้ตอบเป็น bullet เป็นหลัก (ขึ้นต้นด้วย '- ') และตอบให้ตรงคำถาม กระชับ ชัดเจน.\n"
            "3) ห้ามเดาข้อมูลนอกรายการที่มี ใช้เฉพาะข้อมูลที่มีในบริบทเท่านั้น.\n"
            "4) หากคำถามขอ 'สรุป' หรือ 'โครงสร้าง' ให้จัดลำดับหัวข้อก่อนรายละเอียด.\n"
            "5) หากคำถามกำกวม/สั้นมาก (เช่น พิมพ์แค่ชื่อภาษา หรือ xxx) ให้ถามกลับ 1 คำถามสั้น ๆ เพื่อขอรายละเอียดที่จำเป็นก่อน.\n"
            "6) ห้ามให้ URL/ลิงก์ภายนอก เว้นแต่ URL นั้นปรากฏอยู่ในบริบท.\n"
            "7) เรื่องวัน/วันที่/เดดไลน์: ให้ระบุเฉพาะวันที่ที่มีข้อความยืนยันตรง ๆ ในบริบทเท่านั้น ห้ามอนุมานเดดไลน์จากคำว่า 'ประกาศ ณ วันที่ ...' หรือวันที่ที่ไม่ได้ระบุว่าเป็นกำหนดการ/เส้นตาย.\n"
        )

    if require_citations:
        return (
            f"{instruction}\n"
            f"คำถาม:\n{question}\n\n"
            f"บริบท:\n{ctx}\n\n"
            f"รายชื่ออ้างอิงที่อนุญาต (ใช้ได้เฉพาะรายการนี้เท่านั้น):\n{allowed_block}\n\n"
            f"คำตอบ:\n"
        )
    return (
        f"{instruction}\n"
        f"คำถาม:\n{question}\n\n"
        f"บริบท:\n{ctx}\n\n"
        f"คำตอบ:\n"
    )


def rag_query(question: str) -> Dict:
    q_display = normalize_question(question)
    q_search = search_query_from_question(question)
    ref_allow = _reference_candidates(question)
    strict_ref_hints = (os.getenv('STRICT_REFERENCE_HINTS', '1') or '1').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )
    has_ref = bool(ref_allow) and strict_ref_hints
    # Some intents (e.g., intermission leave) require both policy/calendar and forms.
    if 'ลาพัก' in q_display:
        dom = None
        add_metric('inferred_domain', 'multi:announcements+regulations')
        retrieved = retrieve_all_domains(q_search, domains=['announcements', 'regulations'])
    else:
        dom = infer_domain(q_display) or _infer_domain_from_reference(question)
        add_metric('inferred_domain', dom or 'auto')
        if dom:
            retrieved = retrieve_by_domain(question, domain=dom)
            # If too few results, widen cautiously to nearby domains first.
            if (not has_ref) and len(retrieved) < fallback_min_results():
                add_metric('retrieval_domain_fallback_used', 1)
                retrieved = retrieve_all_domains(q_search, domains=fallback_domains_for_domain(dom))
        else:
            retrieved = retrieve_all_domains(q_search)

    retrieved = _filter_chunks_by_reference(retrieved, question, strict=has_ref)
    ctx, cites = pack_context(retrieved)
    prompt = build_prompt(q_display, ctx, cites)
    return {
        'prompt': prompt,
        'contexts': [
            {
                'doc_id': r.get('doc_id'),
                'domain': r.get('domain'),
                'source': r.get('source'),
                'path': r.get('path'),
                'page_start': r.get('page_start'),
                'page_end': r.get('page_end'),
                'score_rrf': r.get('score_rrf'),
            } for r in retrieved
        ],
        'token_est': est_tokens(ctx)
    }


def rag_query_domain(question: str, domain: str | None) -> Dict:
    q_display = normalize_question(question)
    q_search = search_query_from_question(question)
    add_metric('inferred_domain', (domain or '').strip().lower() or 'auto')
    retrieved = retrieve_by_domain(question, domain=domain)

    strict_ref_hints = (os.getenv('STRICT_REFERENCE_HINTS', '1') or '1').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )
    retrieved = _filter_chunks_by_reference(
        retrieved,
        question,
        strict=bool(_reference_candidates(question)) and strict_ref_hints,
    )
    wants_lng_list = (
        re.search(r"LNG", q_display, re.IGNORECASE) is not None
        and any(t in q_display for t in ('เลือกเรียน', 'มีวิชา', 'วิชาอะไร', 'เลือกได้', 'ตัวเลือก'))
    )
    ctx, cites = pack_context(retrieved, truncate_chars=(450 if wants_lng_list else None))
    prompt = build_prompt(q_display, ctx, cites)
    return {
        'prompt': prompt,
        'contexts': [
            {
                'doc_id': r.get('doc_id'),
                'source': r.get('source') or (r.get('metadata') or {}).get('source'),
                'path': r.get('path') or (r.get('metadata') or {}).get('path'),
                'page_start': r.get('page_start') or (r.get('metadata') or {}).get('page_start'),
                'page_end': r.get('page_end') or (r.get('metadata') or {}).get('page_end'),
                'score_rrf': r.get('score_rrf'),
            } for r in retrieved
        ],
        'token_est': est_tokens(ctx)
    }
