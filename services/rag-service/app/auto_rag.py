from __future__ import annotations

import json
import os
import re
from typing import Any

from .llm import generate_text
from .normalization import normalize_question
from .structured_artifacts import summarize_document_profiles


_AUTO_RAG_RUNTIME = (os.getenv('RAG_AUTO_RUNTIME_ENABLE', '1') or '1').strip().lower() in ('1', 'true', 'yes', 'on')
_AUTO_RAG_VERIFIER = (os.getenv('RAG_AUTO_VERIFIER_ENABLE', '1') or '1').strip().lower() in ('1', 'true', 'yes', 'on')
_COURSE_CODE_RE = re.compile(r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b")
_FORM_CODE_RE = re.compile(r"\b(?:RO\s*[- ]?\s*\d{2}|ก\.ค\.\s*18|สทน\.\s*\d{2})\b", re.IGNORECASE)
_TERM_RE = re.compile(r"(?:ภาค(?:การศึกษา)?ที่\s*[1-3](?:/\d{4})?|เทอม\s*[1-3]|[1-3]/\d{4}|ปีการศึกษา\s*\d{4})")
_LANGUAGE_PATTERNS = {
    'ภาษาจีน': ('ภาษาจีน', 'จีน', 'chinese'),
    'ภาษาญี่ปุ่น': ('ภาษาญี่ปุ่น', 'ญี่ปุ่น', 'japanese'),
    'ภาษาเยอรมัน': ('ภาษาเยอรมัน', 'เยอรมัน', 'german'),
    'ภาษาอังกฤษ': ('ภาษาอังกฤษ', 'english'),
}
_CONTACT_PATTERNS = ('ติดต่อ', 'อีเมล', 'email', 'โทร', 'เบอร์', 'ช่องทาง')
_SHORT_STYLE_PATTERNS = ('สั้นๆ', 'สั้น ๆ', 'สรุปสั้น', 'ตอบสั้น', 'ขอสั้น', 'ย่อๆ', 'ย่อ ๆ', 'สั้น')
_DETAILED_STYLE_PATTERNS = ('ละเอียด', 'ละเอียดหน่อย', 'ขอละเอียด', 'อธิบายเพิ่ม', 'อธิบายละเอียด', 'แบบละเอียด', 'ขอแบบละเอียด')


def _normalize_course_code_text(text: str) -> str:
    m = _COURSE_CODE_RE.search(text or '')
    if not m:
        return ''
    return f"{str(m.group(1) or '').upper()} {str(m.group(2) or '').strip()}".strip()


def _extract_last_person(text: str) -> str:
    normalized = str(text or '').strip()
    if not normalized:
        return ''
    m = re.search(r"(?:ผศ\.ดร\.|รศ\.ดร\.|ผศ\.|รศ\.|ศ\.|ดร\.|อ\.)\s*[ก-๙A-Za-z]+(?:\s+[ก-๙A-Za-z]+){0,4}", normalized)
    return re.sub(r"\s+", " ", str(m.group(0) or '').strip()) if m else ''


def extract_structured_memory(
    question: str,
    history: list[dict[str, Any]] | None = None,
    entities: dict[str, Any] | None = None,
    previous_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = dict(previous_state or {})
    recent_text = " ".join(
        [str((msg or {}).get('content') or '').strip() for msg in list(history or [])[-6:] if str((msg or {}).get('content') or '').strip()]
    ).strip()
    q = normalize_question(question)
    combined = f"{recent_text} {q}".strip()
    entities = entities or {}

    course_code = (
        str(entities.get('course_code') or '').strip()
        or _normalize_course_code_text(q)
        or _normalize_course_code_text(recent_text)
    )
    if course_code:
        state['last_course_code'] = course_code
        state['last_topic'] = course_code

    form_code_match = _FORM_CODE_RE.search(combined)
    if form_code_match:
        state['last_form'] = re.sub(r"\s+", "", str(form_code_match.group(0) or '').upper()).replace('RO.', 'RO-')
        state['last_topic'] = state['last_form']

    person = (
        str(entities.get('person') or '').strip()
        or _extract_last_person(q)
        or _extract_last_person(recent_text)
    )
    if person:
        state['last_person'] = person
        state['last_topic'] = person

    term_match = _TERM_RE.search(combined)
    if term_match:
        state['last_term'] = re.sub(r"\s+", " ", str(term_match.group(0) or '').strip())

    q_lower = combined.lower()
    for normalized, aliases in _LANGUAGE_PATTERNS.items():
        if any(alias.lower() in q_lower for alias in aliases):
            state['last_language'] = normalized
            state['last_topic'] = normalized
            break

    if any(token in q_lower for token in _CONTACT_PATTERNS) and state.get('last_person'):
        state['last_contact_target'] = state.get('last_person')
    elif any(token in q_lower for token in _CONTACT_PATTERNS) and state.get('last_course_code'):
        state['last_contact_target'] = state.get('last_course_code')

    field = str(entities.get('field') or '').strip()
    if field:
        state['last_field'] = field

    if any(token in q_lower for token in _SHORT_STYLE_PATTERNS):
        state['preferred_response_style'] = 'short'
    elif any(token in q_lower for token in _DETAILED_STYLE_PATTERNS):
        state['preferred_response_style'] = 'detailed'
    elif not state.get('preferred_response_style'):
        state['preferred_response_style'] = 'normal'

    return state


def _extract_json_object(text: str) -> dict[str, Any] | None:
    raw = str(text or '').strip()
    if not raw:
        return None
    raw = raw.replace('```json', '```').replace('```JSON', '```')
    if raw.startswith('```'):
        raw = raw.strip('`').strip()
        if raw.lower().startswith('json'):
            raw = raw[4:].strip()
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _history_to_text(messages: list[dict[str, Any]] | None, limit: int = 8) -> str:
    rows: list[str] = []
    for msg in list(messages or [])[-limit:]:
        role = str(msg.get('role') or 'user').strip().lower() or 'user'
        content = str(msg.get('content') or '').strip()
        if not content:
            continue
        rows.append(f"{role}: {content}")
    return "\n".join(rows).strip()


def rewrite_followup_with_llm(
    question: str,
    history: list[dict[str, Any]] | None,
    domain: str | None = None,
    structured_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fallback = {
        'standalone_question': normalize_question(question),
        'is_followup': False,
        'entities': {},
        'confidence': 0.0,
        'source': 'fallback',
    }
    if not _AUTO_RAG_RUNTIME:
        return fallback
    history_text = _history_to_text(history)
    memory = extract_structured_memory(question, history, previous_state=structured_state)
    if not history_text and not memory:
        return fallback
    messages = [
        {
            'role': 'system',
            'content': (
                "คุณทำหน้าที่แปลงคำถามต่อเนื่องให้เป็นคำถามสมบูรณ์สำหรับระบบ RAG มหาวิทยาลัย "
                "ห้ามตอบคำถามเอง ห้ามแต่งข้อมูลใหม่ ใช้เฉพาะบริบทบทสนทนาเท่าที่มี "
                "ถ้ามี structured memory ให้ใช้ช่วย resolve คำว่า วิชานี้ คนนี้ ฟอร์มนี้ เทอมนี้ โดยไม่ต้องถามกลับ "
                "ตอบ JSON เท่านั้น ด้วย schema: "
                "{\"standalone_question\":\"...\",\"is_followup\":true,\"entities\":{},\"confidence\":0.0}"
            ),
        },
        {
            'role': 'user',
            'content': (
                f"domain={domain or 'auto'}\n"
                f"structured_memory={json.dumps(memory, ensure_ascii=False)}\n"
                f"conversation=\n{history_text}\n\n"
                f"current_question={question}"
            ),
        },
    ]
    raw = generate_text("(auto rag followup rewrite)", messages=messages, task='rewrite')
    obj = _extract_json_object(raw) or {}
    standalone = normalize_question(str(obj.get('standalone_question') or '').strip())
    if not standalone:
        return fallback
    confidence = float(obj.get('confidence') or 0.0)
    return {
        'standalone_question': standalone,
        'is_followup': bool(obj.get('is_followup')) or (standalone != normalize_question(question)),
        'entities': obj.get('entities') if isinstance(obj.get('entities'), dict) else {},
        'confidence': confidence,
        'source': 'llm',
    }


def plan_retrieval_with_llm(question: str, domain: str | None = None, structured_state: dict[str, Any] | None = None) -> dict[str, Any]:
    q = normalize_question(question)
    fallback = {
        'intent': 'general',
        'search_queries': [q],
        'preferred_domains': [domain] if domain else [],
        'needed_evidence': [],
        'answer_type': 'general',
        'source': 'fallback',
    }
    if not _AUTO_RAG_RUNTIME or not q:
        return fallback
    preferred_domains_hint = [domain] if domain else ['curriculum', 'regulations', 'announcements']
    profile_summary = summarize_document_profiles(preferred_domains_hint, limit_per_domain=3)
    messages = [
        {
            'role': 'system',
            'content': (
                "คุณทำหน้าที่วางแผน retrieval สำหรับระบบ RAG มหาวิทยาลัย "
                "ห้ามตอบคำถามเอง ตอบ JSON เท่านั้น ด้วย schema: "
                "{\"intent\":\"course_lookup | calendar_lookup | form_lookup | procedure_lookup | contact_lookup | policy_lookup | general\","
                "\"search_queries\":[\"...\"],\"preferred_domains\":[\"curriculum|regulations|announcements\"],"
                "\"needed_evidence\":[\"...\"],\"answer_type\":\"definition | date_range | list | procedure | contact | yes_no | general\"}"
                "พิจารณา document profiles ประกอบการเลือก domain และ query ด้วย"
            ),
        },
        {
            'role': 'user',
            'content': (
                f"domain_hint={domain or 'auto'}\n"
                f"structured_memory={json.dumps(structured_state or {}, ensure_ascii=False)}\n"
                f"document_profiles={json.dumps(profile_summary, ensure_ascii=False)}\n"
                f"question={q}"
            ),
        },
    ]
    raw = generate_text("(auto rag retrieval planner)", messages=messages, task='routing')
    obj = _extract_json_object(raw) or {}
    queries = [normalize_question(str(v or '').strip()) for v in (obj.get('search_queries') or []) if str(v or '').strip()]
    preferred = [str(v or '').strip().lower() for v in (obj.get('preferred_domains') or []) if str(v or '').strip()]
    if not queries:
        queries = [q]
    return {
        'intent': str(obj.get('intent') or fallback['intent']).strip() or 'general',
        'search_queries': queries[:4],
        'preferred_domains': preferred[:3],
        'needed_evidence': [str(v or '').strip() for v in (obj.get('needed_evidence') or []) if str(v or '').strip()][:8],
        'answer_type': str(obj.get('answer_type') or fallback['answer_type']).strip() or 'general',
        'source': 'llm' if obj else 'fallback',
    }


def _fallback_verify(question: str, evidence_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = list(evidence_rows or [])
    if not rows:
        return {
            'is_answerable': False,
            'support_level': 'none',
            'missing_evidence': ['no_retrieved_evidence'],
            'irrelevant_context': [],
            'safe_answer_strategy': 'say_not_found',
            'source': 'fallback',
        }
    q_tokens = set(re.findall(r"[A-Za-z0-9ก-๙]+", normalize_question(question).lower()))
    top = rows[:3]
    overlap_hits = 0
    irrelevant: list[str] = []
    for row in top:
        text = str(row.get('text') or '').lower()
        overlap = sum(1 for tok in q_tokens if tok and tok in text)
        if overlap > 0:
            overlap_hits += 1
        else:
            irrelevant.append(str(row.get('source') or row.get('path') or 'unknown'))
    support = 'strong' if overlap_hits >= 2 else ('partial' if overlap_hits == 1 else 'none')
    return {
        'is_answerable': overlap_hits >= 1,
        'support_level': support,
        'missing_evidence': [] if overlap_hits >= 1 else ['question_terms_not_supported'],
        'irrelevant_context': irrelevant[:3],
        'safe_answer_strategy': 'answer_directly' if overlap_hits >= 2 else ('answer_with_caveat' if overlap_hits == 1 else 'say_not_found'),
        'source': 'fallback',
    }


def verify_evidence_with_llm(question: str, evidence_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    fallback = _fallback_verify(question, evidence_rows)
    if not _AUTO_RAG_VERIFIER:
        return fallback
    rows = list(evidence_rows or [])[:5]
    if not rows:
        return fallback
    evidence_text = "\n\n".join(
        [
            f"[{idx+1}] source={row.get('source') or row.get('path') or 'unknown'}\n{str(row.get('text') or '').strip()[:1200]}"
            for idx, row in enumerate(rows)
            if str(row.get('text') or '').strip()
        ]
    ).strip()
    if not evidence_text:
        return fallback
    messages = [
        {
            'role': 'system',
            'content': (
                "คุณทำหน้าที่ตรวจว่าหลักฐานที่ดึงมาสามารถตอบคำถามได้จริงหรือไม่ "
                "ห้ามใช้ความรู้ภายนอก ตอบ JSON เท่านั้น ด้วย schema: "
                "{\"is_answerable\":true,\"support_level\":\"strong | partial | weak | none\","
                "\"missing_evidence\":[\"...\"],\"irrelevant_context\":[\"...\"],"
                "\"safe_answer_strategy\":\"answer_directly | answer_with_caveat | say_not_found\"}"
            ),
        },
        {
            'role': 'user',
            'content': f"question={normalize_question(question)}\n\nevidence=\n{evidence_text}",
        },
    ]
    raw = generate_text("(auto rag evidence verifier)", messages=messages, task='routing')
    obj = _extract_json_object(raw) or {}
    if not obj:
        return fallback
    return {
        'is_answerable': bool(obj.get('is_answerable')),
        'support_level': str(obj.get('support_level') or fallback['support_level']).strip() or fallback['support_level'],
        'missing_evidence': [str(v or '').strip() for v in (obj.get('missing_evidence') or []) if str(v or '').strip()][:6],
        'irrelevant_context': [str(v or '').strip() for v in (obj.get('irrelevant_context') or []) if str(v or '').strip()][:6],
        'safe_answer_strategy': str(obj.get('safe_answer_strategy') or fallback['safe_answer_strategy']).strip() or fallback['safe_answer_strategy'],
        'source': 'llm',
    }
