from __future__ import annotations

from typing import Dict, List, Optional
import os
from pathlib import Path
import re
from dataclasses import dataclass, field

from .config import KNOWN_DOMAINS, ROOT_DIR

_AGGRESSIVE_BINARY_ROUTING = (os.getenv('RAG_AGGRESSIVE_BINARY_ROUTING', '0') or '0').strip().lower() in (
    '1', 'true', 'yes', 'on'
)

@dataclass
class RouteDecision:
    normalized_question: str
    requested_domain: Optional[str]
    inferred_domain: Optional[str]
    effective_domain: Optional[str]
    primary_intent: str
    is_multi_intent: bool
    subqueries: List[str]
    entities: List[str]
    structured_eligible: bool
    structured_kind: str
    structured_eligibility_reason: str = 'none'
    requires_clause_anchor: bool = False
    needs_exact_schema: bool = False
    timeout_policy: str = 'normal'
    fallback_policy: str = 'broad'
    resolved_entity_type: str = ''
    resolved_entity_value: str = ''
    resolved_entity_confidence: int = 0

@dataclass
class ResolutionStrategy:
    # structured_exact: Must strictly match structure logic, else drop to RAG
    # structured_fuzzy: Allows partial structure extraction
    # keyword_only: Just boolean keyword lookups
    # multi_intent_split: Split into subqueries and merge answers/contexts
    # multi_intent_structured_or_extract: Multi-intent regulations fact lookup via deterministic/extractive path
    # structured_regulation_form: Deterministic regulations form lookup
    # full_rag: The heavy generative pipeline
    resolution_path: str  # "structured_exact", "structured_fuzzy", "keyword_only", "multi_intent_split", "multi_intent_structured_or_extract", "structured_regulation_form", "full_rag"

def _extract_course_codes_local(text: str) -> List[str]:
    q = (text or '').strip()
    out = []
    seen = set()
    for m in re.finditer(r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b", q):
        code = f"{(m.group(1) or '').upper()}{m.group(2) or ''}"
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out


def apply_resolved_entity_context(question: str, resolved_entity: dict | None = None) -> str:
    q = (question or '').strip()
    if not q:
        return q
    if q.startswith('บริบทก่อนหน้า:'):
        return q
    if re.search(r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b", q):
        return q
    if not isinstance(resolved_entity, dict):
        return q
    value = str(resolved_entity.get('value') or '').strip()
    confidence = int(resolved_entity.get('confidence') or 0)
    if not value or confidence <= 0:
        return q
    return f"บริบทก่อนหน้า: {value}\nคำถามต่อเนื่อง: {q}".strip()


def _is_claim_verification_question(question: str) -> bool:
    q = (question or '').strip().lower()
    if not q:
        return False
    claim_markers = (
        'ใช่หรือไม่', 'จริงหรือไม่', 'หรือไม่', 'ถูกต้องหรือไม่', 'ใช่ไหม', 'ใช่มั้ย', 'จริงไหม',
    )
    if not any(m in q for m in claim_markers):
        return False
    if _AGGRESSIVE_BINARY_ROUTING:
        # Aggressive mode prioritizes recall for binary evals.
        return len(q) >= 6
    has_subject_signal = bool(re.search(r"\b[a-z]{2,6}\s*[- ]?\s*\d{3}\b", q)) or any(
        t in q for t in ('วิชาบังคับก่อน', 'วิชาบังคับ', 'วิชาเลือก', 'หมวด')
    )
    return has_subject_signal

def is_multi_doc_question(q: str) -> bool:
    """Heuristic: detect questions that likely require combining multiple sources."""
    ql = (q or '').strip().lower()
    if not ql:
        return False

    # Treat compact curriculum two-slot factual asks as single-intent.
    if ('หลักสูตร' in ql) and (('ระดับ' in ql and 'กี่ปี' in ql) or ('ครั้งที่' in ql and 'วันที่' in ql)):
        return False

    # Year/term credit aggregation is deterministic curriculum math, not true multi-intent.
    if (
        re.search(r"(?:ชั้นปีที่|ปีที่|ปี)\s*[1-4]", ql)
        and ('หน่วยกิต' in ql)
        and any(t in ql for t in ('รวม', 'ทั้งหมด', 'ทั้ง 2 ภาค', 'ทั้งสองภาค'))
    ):
        return False

    # Strong explicit signals.
    if any(t in ql for t in (
        'เปรียบเทียบ', 'ต่างกัน', 'เหมือนกัน', 'ทั้ง', 'พร้อมกัน', 'conflict',
        'ตอบพร้อมกันสองเรื่อง', 'ตอบสองเรื่องในคำตอบเดียว', 'ขอสองคำตอบพร้อมกัน', 'สรุปสองเรื่องพร้อมกัน',
    )):
        return True

    # Cross-domain intent detection (e.g. curriculum + registrar)
    curriculum_cues = ('prereq', 'วิชาบังคับก่อน', 'หน่วยกิต', 'หลักสูตร', 'เรียนอะไร', 'อาจารย์')
    registrar_cues = ('ลงทะเบียน', 'registration', 'สอบ', 'ปฏิทิน', 'เวลา', 'กำหนดการ', 'จ่ายเงิน', 'ค่าเทอม')
    if any(c in ql for c in curriculum_cues) and any(r in ql for r in registrar_cues):
        return True

    # Multiple clauses / intents.
    signals = (' แล้ว', ' และ', ' รวมถึง', ' พร้อม', ' กรณี', ',', ';', ':', ' and ', ' กับ ')
    sig_hits = sum(1 for s in signals if s in ql)

    qmark_hits = ql.count('?')
    multi_intent = any(t in ql for t in ('ต้องทำยังไง', 'ทำอย่างไร', 'ขั้นตอน', 'เงื่อนไข', 'ต้องใช้', 'ต้องมี', 'ได้ไหม', 'คืออะไร'))

    if qmark_hits >= 2:
        return True
    if sig_hits >= 2:
        return True
    if sig_hits >= 1 and multi_intent:
        return True
    return False

def classify_intent(question: str) -> str:
    """Classify the user intent into one of a unified set of primary intents."""
    q = (question or '').strip()
    ql = q.lower()

    unanswerable_terms = (
        'เดาข้อสอบ', 'ช่วยเดาข้อสอบ', 'ข้อสอบจะออก', 'สอบจะออกอะไร', 'เฉลยข้อสอบ', 'ทำนายข้อสอบ', 'ใบ้ข้อสอบ',
        'ตัดสินเกรด', 'ตัดเกรดให้', 'ขอให้ปรับเกรด', 'ปรับเกรดให้', 'เปลี่ยนเกรดให้', 'การันตีเกรด',
        'ผลสอบล่วงหน้า', 'ผลสอบก่อนประกาศ', 'บอกเกรดล่วงหน้า', 'ยืนยันผลสอบล่วงหน้า',
    )
    if any(t in ql for t in unanswerable_terms):
        return 'unanswerable'

    if _is_claim_verification_question(q):
        return 'claim_verification'

    if is_multi_doc_question(q):
        return 'multi_intent'

    if any(t in ql for t in ('ใครสอน', 'ผู้สอน', 'อาจารย์', 'คนสอน', 'instructor', 'lecturer', 'teacher')):
        return 'instructor_lookup'
    if any(t in ql for t in ('หน่วยกิต', 'กี่หน่วยกิต', 'credit', 'credits')):
        return 'credit_lookup'
    # Prerequisite detection should be curriculum-scoped only.
    # Avoid false positives from regulations phrasing like "ต้องผ่านไปกี่นาที".
    prerequisite_terms = ('บังคับก่อน', 'ก่อนเรียน', 'prerequisite', 'pre-requisite', 'pre requisite', 'pre-req', 'prereq')
    has_course_signal = bool(re.search(r"\b[A-Za-z]{2,6}\s*[- ]?\s*\d{3}\b", q)) or any(
        t in q for t in ('รายวิชา', 'รหัสวิชา', 'วิชา')
    )
    exam_room_signal = any(t in q for t in ('สอบ', 'ห้องสอบ', 'เข้าห้องสอบ', 'ออกห้องสอบ', 'นาที'))
    if any(t in ql for t in prerequisite_terms):
        if has_course_signal and not exam_room_signal:
            return 'prerequisite_lookup'
    if ('ต้องผ่าน' in ql) and has_course_signal and not exam_room_signal:
        return 'prerequisite_lookup'

    _exam_policy_terms = (
        'ห้องสอบ', 'เข้าห้องสอบ', 'ออกห้องสอบ', 'ออกจากห้องสอบ', 'ออกห้องสอบชั่วคราว',
        'มาสาย', 'สายเกิน', 'เข้าห้องสอบได้', 'กรรมการคุมสอบ', 'คุมสอบ', 'ทุจริต', 'ส่อ', 'ลงโทษ', 'อุทธรณ์', 'ข้อสอบ', 'วินัย'
    )
    if any(t in q for t in _exam_policy_terms):
        return 'exam_policy'

    _academic_status_terms = (
        'ติดโปร', 'probation', 'ไทร์', 'retire', 'พ้นสภาพ', 'พ้นสถานภาพ', 'เกรด f', 'ได้ f', 'ได้f'
    )
    if any(t in ql for t in _academic_status_terms):
        return 'academic_status_policy'

    if any(t in ql for t in ('ลงทะเบียน', 'เพิ่มถอน', 'ลงเพิ่ม', 'ถอน', 'drop', 'register', 'enroll')):
        return 'registration_policy'

    # Study-plan style questions (e.g., "ปี 1 เรียนอะไรบ้าง") should be
    # treated as curriculum lookup so they can use deterministic routing.
    year_hint = re.search(r"(?:ชั้นปีที่|ปีที่|ปี)\s*[1-4]", q) is not None
    study_plan_hint = any(
        t in q
        for t in (
            'เรียนอะไร',
            'เรียนอะไรบ้าง',
            'วิชาอะไร',
            'มีอะไรบ้าง',
            'มีวิชาอะไร',
            'ลงอะไร',
            'รายวิชา',
            'ภาคการศึกษา',
            'เทอม',
        )
    )
    if year_hint and study_plan_hint:
        return 'curriculum_course_info'
    
    if any(t in ql for t in ('วัน', 'วันที่', 'เมื่อไร', 'กำหนด', 'deadline', 'ปฏิทิน', 'calendar')):
        return 'calendar_deadline'

    if any(t in ql for t in ('หลักสูตร', 'รายวิชา', 'วิชา', 'รหัสวิชา', 'course')):
        return 'curriculum_course_info'

    if any(t in ql for t in ('คำร้อง', 'แบบฟอร์ม', 'ลาออก', 'ลาป่วย', 'ลากิจ', 'ทัณฑ์บน')):
        return 'regulation_forms'

    if any(t in ql for t in ('ประกาศ', 'announcement')):
        return 'announcement'

    if len(q) < 5 and not re.search(r"[A-Za-z0-9ก-๙]", q):
        return 'noisy_query'

    return 'general_info'

def analyze_route(question: str, requested_domain: Optional[str] = None, resolved_entity: dict | None = None) -> RouteDecision:
    """Analyze query to understand intent, extract entities, and populate RouteDecision schema."""
    raw_q = (question or '').strip()
    q = apply_resolved_entity_context(raw_q, resolved_entity)
    primary_intent = classify_intent(q)
    inferred = infer_domain(q)
    
    # Domain override rule for prerequisites
    if primary_intent == 'prerequisite_lookup' and requested_domain != 'curriculum':
        effective_domain = 'curriculum'
    else:
        effective_domain = requested_domain or inferred or 'auto'

    is_multi = primary_intent == 'multi_intent' or is_multi_doc_question(q)
    subqs = decompose_question(q) if is_multi else []
    entities = _extract_course_codes_local(q)
    resolved_type = str((resolved_entity or {}).get('type') or '').strip()
    resolved_value = str((resolved_entity or {}).get('value') or '').strip()
    resolved_confidence = int((resolved_entity or {}).get('confidence') or 0)
    if resolved_type == 'course' and resolved_value:
        norm = resolved_value.replace('-', '').replace(' ', '').upper()
        if norm and norm not in entities:
            entities.append(norm)
    
    # Structured Eligibility evaluation
    use_structured_curriculum = (os.getenv('RAG_USE_STRUCTURED_CURRICULUM', '1') or '1').strip().lower() in ('1', 'true', 'yes', 'on')
    
    curric_eligible = use_structured_curriculum and (effective_domain in ('curriculum', 'auto')) and primary_intent in (
        'instructor_lookup', 'credit_lookup', 'prerequisite_lookup', 'curriculum_course_info', 'claim_verification'
    )
    
    structured_regulation_intents = {
        'exam_policy',
        'academic_status_policy',
        'registration_policy',
        'regulation_forms',
    }
    reg_eligible = effective_domain in ('regulations', 'auto') and primary_intent in structured_regulation_intents
    
    structured_eligible = curric_eligible or reg_eligible
    structured_kind = 'curriculum' if curric_eligible else ('regulations' if reg_eligible else 'none')

    if structured_eligible:
        structured_eligibility_reason = 'qualified'
    elif not use_structured_curriculum and primary_intent in (
        'instructor_lookup', 'credit_lookup', 'prerequisite_lookup', 'curriculum_course_info'
    ):
        structured_eligibility_reason = 'env_disabled'
    elif effective_domain not in ('curriculum', 'regulations', 'auto'):
        structured_eligibility_reason = 'domain_mismatch'
    else:
        structured_eligibility_reason = 'intent_mismatch'

    requires_clause_anchor = bool(re.search(r"ข้อ\s*[๐-๙0-9]+(?:\.[๐-๙0-9]+)?", q))
    needs_exact_schema = primary_intent in ('credit_lookup', 'prerequisite_lookup', 'instructor_lookup', 'exam_policy', 'claim_verification')
    is_regulations_multi_fact = (
        is_multi
        and (effective_domain in ('regulations', 'auto'))
        and primary_intent in ('multi_intent', 'exam_policy', 'academic_status_policy', 'registration_policy')
    )
    if is_regulations_multi_fact:
        timeout_policy = 'strict_multi_extract'
    else:
        timeout_policy = 'generous' if is_multi else ('fast' if needs_exact_schema else 'normal')
    
    # Fallback policy for retrieval strictness
    fallback_policy = 'strict' if primary_intent in ('exam_policy', 'registration_policy') else 'broad'
    
    return RouteDecision(
        normalized_question=q,
        requested_domain=requested_domain,
        inferred_domain=inferred,
        effective_domain=effective_domain,
        primary_intent=primary_intent,
        is_multi_intent=is_multi,
        subqueries=subqs,
        entities=entities,
        structured_eligible=structured_eligible,
        structured_kind=structured_kind,
        structured_eligibility_reason=structured_eligibility_reason,
        requires_clause_anchor=requires_clause_anchor,
        needs_exact_schema=needs_exact_schema,
        timeout_policy=timeout_policy,
        fallback_policy=fallback_policy,
        resolved_entity_type=resolved_type,
        resolved_entity_value=resolved_value,
        resolved_entity_confidence=resolved_confidence,
    )

def select_resolution_strategy(decision: RouteDecision) -> ResolutionStrategy:
    """Determine the optimal resolution path based on intent and constraints."""
    if decision.primary_intent == 'regulation_forms' and decision.structured_kind == 'regulations':
        return ResolutionStrategy(resolution_path="structured_regulation_form")

    if decision.is_multi_intent:
        fact_intents = {
            'exam_policy',
            'academic_status_policy',
            'registration_policy',
            'regulation_forms',
        }
        subqs = decompose_question(decision.normalized_question, max_parts=3)
        if subqs:
            subq_domains = [(infer_domain(sq) or decision.effective_domain or '').strip().lower() for sq in subqs]
            subq_intents = [classify_intent(sq) for sq in subqs]
            if all(d == 'regulations' for d in subq_domains) and all(i in fact_intents for i in subq_intents):
                return ResolutionStrategy(resolution_path="multi_intent_structured_or_extract")
        return ResolutionStrategy(resolution_path="multi_intent_split")

    if decision.structured_eligible:
        # Factual lookups must succeed completely (exact schema requirements)
        if decision.primary_intent in ('credit_lookup', 'prerequisite_lookup', 'instructor_lookup', 'exam_policy', 'claim_verification'):
            return ResolutionStrategy(resolution_path="structured_exact")
        else:
            return ResolutionStrategy(resolution_path="structured_fuzzy")

    return ResolutionStrategy(resolution_path="full_rag")

def decompose_question(q: str, max_parts: int = 3) -> List[str]:
    """Split multi-clause questions into a small set of sub-questions."""
    raw = (q or '').strip()
    if not raw:
        return []

    raw = re.sub(
        r"^(?:ตอบพร้อมกันสองเรื่อง|ตอบสองเรื่องในคำตอบเดียว|ขอสองคำตอบพร้อมกัน|สรุปสองเรื่องพร้อมกัน|ตอบพร้อมกัน|สรุปสองเรื่อง)\s*:?\s*",
        '',
        raw,
        flags=re.IGNORECASE,
    ).strip()

    # Keep the original question first (important for global intent).
    parts: List[str] = [raw]

    # Split on common Thai connectors. Avoid exploding into too many sub-questions.
    segs = re.split(r"\s*(?:แล้ว|และ|รวมถึง|พร้อมกับ|พร้อม|กรณี|\/|\,|\;|:)+\s*", raw)
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
        'ปีที่',               # year level (full form)
        'ชั้นปี',              # academic year/level
        'ภาคการศึกษา',        # semester
        'ต้องมีพื้นฐาน',       # must have foundation
        # Short-form year queries: "วิชาปี 1", "ปี 2 เทอม 2" etc.
        'วิชาปี',              # bare year course list
        'เรียนปี',             # year course list phrasing
        'ปี 1', 'ปี 2', 'ปี 3', 'ปี 4',  # bare year numbers
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
        'มาสาย', 'สายเกิน', 'เข้าห้องสอบได้', 'เข้าห้องสอบได้ไหม', 'เข้าห้องสอบได้ปะ',
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

    if any(t in q for t in ('คำร้อง', 'แบบฟอร์ม', 'RO-', 'ใบลา', 'เอกสารใบลา', 'ลาออก', 'ลาป่วย', 'ลากิจ', 'ทัณฑ์บน', 'วินัย', 'ตัดคะแนนความประพฤติ', 'สอบซ้อน', 'เข้าสอบ')):
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


def fallback_domains_for_domain(primary: str | None, question: str | None = None) -> list[str] | None:
    """Prefer nearby domains before widening retrieval across everything."""
    p = (primary or '').strip().lower()
    q = (question or '').strip().lower()
    exam_policy_intent = (
        any(t in q for t in ('สอบ', 'ห้องสอบ', 'คุมสอบ', 'มาสาย', 'สายเกิน', 'ทุจริต', 'อุทธรณ์', 'ข้อ 12', 'ข้อ 15', 'ข้อ 16', 'ข้อ 28'))
        and any(t in q for t in ('ระเบียบ', 'ข้อ', 'ได้ไหม', 'ได้ปะ', 'อย่างไร', 'นาที', 'ชั่วโมง', 'ชั่วคราว', 'อุทธรณ์'))
    )
    if p == 'announcements':
        return ['announcements', 'regulations']
    if p == 'regulations':
        if exam_policy_intent:
            return ['regulations']
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
