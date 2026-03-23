from __future__ import annotations

from typing import Dict, List
import os
from pathlib import Path
import re

from .config import KNOWN_DOMAINS, ROOT_DIR


def is_multi_doc_question(q: str) -> bool:
    """Heuristic: detect questions that likely require combining multiple sources."""
    ql = (q or '').strip().lower()
    if not ql:
        return False

    # Strong explicit signals.
    if any(t in ql for t in ('เปรียบเทียบ', 'ต่างกัน', 'เหมือนกัน', 'ทั้ง', 'พร้อมกัน', 'conflict')):
        return True

    # Multiple clauses / intents.
    signals = (' แล้ว', ' และ', ' รวมถึง', ' พร้อม', ' กรณี', ',', ';')
    sig_hits = sum(1 for s in signals if s in ql)

    qmark_hits = ql.count('?')
    multi_intent = any(t in ql for t in ('ต้องทำยังไง', 'ทำอย่างไร', 'ขั้นตอน', 'เงื่อนไข', 'ต้องใช้', 'ต้องมี', 'ได้ไหม'))

    if qmark_hits >= 2:
        return True
    if sig_hits >= 2:
        return True
    if sig_hits >= 1 and multi_intent:
        return True
    return False


def decompose_question(q: str, max_parts: int = 3) -> List[str]:
    """Split multi-clause questions into a small set of sub-questions."""
    raw = (q or '').strip()
    if not raw:
        return []

    # Keep the original question first (important for global intent).
    parts: List[str] = [raw]

    # Split on common Thai connectors. Avoid exploding into too many sub-questions.
    segs = re.split(r"\s*(?:แล้ว|และ|รวมถึง|พร้อมกับ|พร้อม|กรณี|\/|\,|\;)+\s*", raw)
    for s in segs:
        ss = (s or '').strip()
        if not ss:
            continue
        if ss == raw:
            continue
        parts.append(ss)

    out: List[str] = []
    seen: set[str] = set()
    for p in parts:
        pp = (p or '').strip()
        if not pp:
            continue
        key = re.sub(r"\s+", " ", pp.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(pp)
        if len(out) >= max(1, int(max_parts)):
            break
    return out


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
        'รหัสวิชา',           # course code lookup
        'เรียนวิชา',          # year-plan course list phrasing
        'วิชาอะไรบ้าง',       # list intent phrasing
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

    # Academic status/policy (probation, dismissal, retire) should prefer regulations.
    _academic_status_terms = (
        'ติดโปร', 'probation', 'ไทร์', 'retire', 'พ้นสภาพ', 'พ้นสถานภาพ',
        'เกณฑ์', 'เงื่อนไขพ้นสภาพ', 'ได้ f', 'ได้f', 'เกรด f',
    )
    if any(t in ql for t in _academic_status_terms):
        return 'regulations'

    # Schedule / calendar / registration timing: these usually live in announcements.
    if any(t in q for t in ('กำหนดการลงทะเบียน', 'ตารางลงทะเบียน', 'ลงทะเบียนเรียนเทอม', 'ลงทะเบียนเทอม')):
        return 'announcements'
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


def infer_domain_bias(question: str) -> str | None:
    """Lightweight fallback domain bias when infer_domain() is inconclusive.

    Used only as a soft hint (never a hard gate) by all-domain fusion.
    """
    q = (question or '').strip().lower()
    if not q:
        return None

    # Strong hint: course-code questions are usually curriculum, unless explicitly about exam schedules.
    has_course_code = re.search(r"\b[a-z]{2,6}\s*[- ]?\s*\d{3}\b", q, flags=re.IGNORECASE) is not None
    examish = any(t in q for t in ('ตารางสอบ', 'สอบกลางภาค', 'สอบปลายภาค', 'วันสอบ', 'สอบ'))
    if has_course_code and not examish:
        return 'curriculum'

    curriculum_terms = [
        'หน่วยกิต', 'หลักสูตร', 'วิชาศึกษาทั่วไป', 'วิชาเลือก', 'วิชาบังคับ', 'ก่อนเรียน',
        'prerequisite', 'pre-requisite',
    ]
    regulations_terms = [
        'ระเบียบ', 'ข้อบังคับ', 'อุทธรณ์', 'ทุจริต', 'มาสาย', 'หมดสิทธิ์', 'วินัย',
    ]
    announcements_terms = [
        'ประกาศ', 'กำหนดการ', 'ปฏิทิน', 'เปิด', 'ปิด', 'ชำระ', 'ค่าธรรมเนียม',
    ]

    if any(t in q for t in curriculum_terms):
        return 'curriculum'
    if any(t in q for t in regulations_terms):
        return 'regulations'
    if any(t in q for t in announcements_terms):
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
