from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from .config import KNOWN_DOMAINS
from .routing import classify_intent


_THAI_TO_ARABIC = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')
_COURSE_CODE_RE = re.compile(r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b")
_STANDALONE_CODE_RE = re.compile(r"^\s*[A-Za-z]{2,6}\s*[- ]?\s*\d{3}\s*$")
_INSTRUCTOR_RE = re.compile(r"(?:อาจารย์|อ\.|ผศ\.|รศ\.|ศ\.|ดร\.)\s*([ก-๙A-Za-z]+(?:\s+[ก-๙A-Za-z]+){0,3})")
_TERM_RE = re.compile(r"(?:ภาค(?:การศึกษา)?ที่\s*[1-3](?:/\d{4})?|เทอม\s*[1-3]|[1-3]/\d{4}|ปีการศึกษา\s*\d{4})")
_META_TASK_RE = re.compile(
    r"(?:^|\n)\s*(?:#+\s*)?task\s*:[\s\S]{0,200}?"
    r"(?:"
    r"suggest\s*3\s*-\s*5\s*relevant\s*follow-up\s*questions"
    r"|generate\s+(?:a\s+)?concise[\s,]+3\s*-\s*5\s*word\s*title"
    r"|generate\s+1\s*-\s*3\s*broad\s*tags"
    r")",
    re.IGNORECASE,
)
_META_TASK_HINTS = (
    'task: suggest 3-5 relevant follow-up questions',
    'generate a concise, 3-5 word title',
    'generate 1-3 broad tags categorizing',
    'json format: { "follow_ups":',
    'response must be a json array of strings',
)
_USER_REQUEST_RE = re.compile(r"<userRequest>\s*(.*?)\s*</userRequest>", re.IGNORECASE | re.DOTALL)
_NOISE_BLOCK_TAGS = (
    'attachments',
    'context',
    'editorContext',
    'reminderInstructions',
    'environment_info',
    'workspace_info',
)
_NOISE_LINE_HINTS = (
    'chat customizations index:',
    'here is a list of instruction files that contain rules',
    'task: suggest 3-5 relevant follow-up questions',
    'response must be a json array of strings',
    'json format: { "follow_ups":',
    'generate a concise, 3-5 word title',
    'generate 1-3 broad tags categorizing',
    'guidelines:',
    'output:',
)


class SessionStore(Protocol):
    def get_chat_history(self, session_id: str) -> list[str]:
        ...

    def append_chat_turn(self, session_id: str, user_question: str) -> None:
        ...

    def get_followup_hint(self, session_id: str) -> dict[str, str] | None:
        ...

    def put_followup_hint(self, session_id: str, *, question: str, domain: str, intent: str) -> None:
        ...


class InMemorySessionStore:
    def __init__(self, *, max_sessions: int = 512, max_turns: int = 6) -> None:
        self.max_sessions = max(32, int(max_sessions or 512))
        self.max_turns = max(2, int(max_turns or 6))
        self._chat_memory: dict[str, list[str]] = {}
        self._followup_hints: dict[str, dict[str, str]] = {}

    def get_chat_history(self, session_id: str) -> list[str]:
        sid = str(session_id or '').strip()
        if not sid:
            return []
        vals = self._chat_memory.get(sid) or []
        return [str(v or '').strip() for v in vals if str(v or '').strip()]

    def append_chat_turn(self, session_id: str, user_question: str) -> None:
        sid = str(session_id or '').strip()
        txt = str(user_question or '').strip()
        if not sid or not txt:
            return
        prev = self._chat_memory.get(sid) or []
        prev.append(txt)
        self._chat_memory[sid] = prev[-self.max_turns:]
        while len(self._chat_memory) > self.max_sessions:
            self._chat_memory.pop(next(iter(self._chat_memory)), None)

    def get_followup_hint(self, session_id: str) -> dict[str, str] | None:
        sid = str(session_id or '').strip()
        if not sid:
            return None
        return self._followup_hints.get(sid)

    def put_followup_hint(self, session_id: str, *, question: str, domain: str, intent: str) -> None:
        sid = str(session_id or '').strip()
        if not sid:
            return
        prev = self._followup_hints.get(sid) or {}
        self._followup_hints[sid] = {
            'question': str(question or '').strip(),
            'domain': str(domain or '').strip().lower(),
            'intent': str(intent or '').strip().lower(),
            'prev_question': str(prev.get('question') or '').strip(),
            'prev_domain': str(prev.get('domain') or '').strip().lower(),
        }
        while len(self._followup_hints) > self.max_sessions:
            self._followup_hints.pop(next(iter(self._followup_hints)), None)


class RedisSessionStore(InMemorySessionStore):
    def __init__(self, *, redis_url: str, ttl_seconds: int = 3600, max_sessions: int = 512, max_turns: int = 6) -> None:
        super().__init__(max_sessions=max_sessions, max_turns=max_turns)
        self.ttl_seconds = max(60, int(ttl_seconds or 3600))
        self.redis_url = str(redis_url or '').strip()
        self._redis = None
        try:
            import redis  # type: ignore
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        except Exception:
            self._redis = None

    def _chat_key(self, session_id: str) -> str:
        return f"chat_followup:history:{session_id}"

    def _hint_key(self, session_id: str) -> str:
        return f"chat_followup:hint:{session_id}"

    def get_chat_history(self, session_id: str) -> list[str]:
        sid = str(session_id or '').strip()
        if not sid or self._redis is None:
            return super().get_chat_history(session_id)
        try:
            vals = self._redis.lrange(self._chat_key(sid), 0, self.max_turns - 1) or []
            return [str(v or '').strip() for v in vals if str(v or '').strip()]
        except Exception:
            return super().get_chat_history(session_id)

    def append_chat_turn(self, session_id: str, user_question: str) -> None:
        sid = str(session_id or '').strip()
        txt = str(user_question or '').strip()
        if not sid or not txt or self._redis is None:
            super().append_chat_turn(session_id, user_question)
            return
        try:
            key = self._chat_key(sid)
            self._redis.lpush(key, txt)
            self._redis.ltrim(key, 0, self.max_turns - 1)
            self._redis.expire(key, self.ttl_seconds)
        except Exception:
            super().append_chat_turn(session_id, user_question)

    def get_followup_hint(self, session_id: str) -> dict[str, str] | None:
        sid = str(session_id or '').strip()
        if not sid or self._redis is None:
            return super().get_followup_hint(session_id)
        try:
            raw = self._redis.get(self._hint_key(sid))
            if not raw:
                return None
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return super().get_followup_hint(session_id)

    def put_followup_hint(self, session_id: str, *, question: str, domain: str, intent: str) -> None:
        sid = str(session_id or '').strip()
        if not sid or self._redis is None:
            super().put_followup_hint(session_id, question=question, domain=domain, intent=intent)
            return
        try:
            prev = self.get_followup_hint(sid) or {}
            payload = {
                'question': str(question or '').strip(),
                'domain': str(domain or '').strip().lower(),
                'intent': str(intent or '').strip().lower(),
                'prev_question': str(prev.get('question') or '').strip(),
                'prev_domain': str(prev.get('domain') or '').strip().lower(),
            }
            key = self._hint_key(sid)
            self._redis.setex(key, self.ttl_seconds, json.dumps(payload, ensure_ascii=False))
        except Exception:
            super().put_followup_hint(session_id, question=question, domain=domain, intent=intent)


def build_session_store_from_env() -> SessionStore:
    max_sessions = max(32, int((os.getenv('RAG_SESSION_FOLLOWUP_MAX', '512') or '512').strip()))
    max_turns = max(2, int((os.getenv('RAG_SESSION_CHAT_TURNS_MAX', '6') or '6').strip()))
    redis_url = str(os.getenv('RAG_SESSION_REDIS_URL') or '').strip()
    ttl_seconds = max(60, int((os.getenv('RAG_SESSION_TTL_SECONDS', '3600') or '3600').strip()))
    if redis_url:
        return RedisSessionStore(
            redis_url=redis_url,
            ttl_seconds=ttl_seconds,
            max_sessions=max_sessions,
            max_turns=max_turns,
        )
    return InMemorySessionStore(max_sessions=max_sessions, max_turns=max_turns)


@dataclass(frozen=True)
class PreparedChatRequest:
    question: str
    domain: str | None
    session_id: str
    messages: list[dict[str, Any]]
    raw_last_user: str
    lock_applied: bool
    lock_reason: str
    followup_meta: dict[str, str | int]


def _normalize_noisy_question_text(text: str) -> str:
    q = (text or '').strip()
    if not q:
        return ''
    q = unicodedata.normalize('NFKC', q)
    q = q.translate(_THAI_TO_ARABIC)
    q = q.replace('–', '-').replace('—', '-').replace('−', '-')
    q = re.sub(r"\b([A-Za-z]{2,6})\s*[-]?\s*(\d{3})\b", lambda m: f"{(m.group(1) or '').upper()} {(m.group(2) or '').strip()}", q)
    for src, dst in (
        ('วิชาอารัย', 'วิชาอะไร'),
        ('อารัย', 'อะไร'),
        ('ได้ปะ', 'ได้ไหม'),
        ('ได้มั้ย', 'ได้ไหม'),
        ('เรียนไรบ้าง', 'เรียนอะไรบ้าง'),
        ('เรียนไร', 'เรียนอะไร'),
        ('วิชาไรบ้าง', 'วิชาอะไรบ้าง'),
        ('วิชาไร', 'วิชาอะไร'),
        ('มีไรบ้าง', 'มีอะไรบ้าง'),
        ('มีไร', 'มีอะไร'),
        ('คือไร', 'คืออะไร'),
        ('ทำไร', 'ทำอะไร'),
        ('เอาไร', 'เอาอะไร'),
        ('ใช้ไร', 'ใช้อะไร'),
        ('ได้ไร', 'ได้อะไร'),
    ):
        q = q.replace(src, dst)
    q = re.sub(r"(\d{1,3})\s*(นาที|วัน|เครื่อง|ชม\.?|ชั่วโมง)", r"\1 \2", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q


def sanitize_user_question_text(text: str) -> str:
    t = (text or '').strip()
    if not t:
        return ''
    m = _USER_REQUEST_RE.search(t)
    if m:
        t = (m.group(1) or '').strip()
    for tag in _NOISE_BLOCK_TAGS:
        t = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", " ", t, flags=re.IGNORECASE | re.DOTALL)
    cleaned_lines: list[str] = []
    for line in t.splitlines():
        s = line.strip()
        if not s:
            cleaned_lines.append('')
            continue
        s_l = s.lower()
        if any(h in s_l for h in _NOISE_LINE_HINTS):
            continue
        if re.fullmatch(r"</?[^>]+>", s):
            continue
        cleaned_lines.append(line)
    t = '\n'.join(cleaned_lines)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = t.strip()
    return _normalize_noisy_question_text(t)


def content_to_text(content: object) -> str:
    if content is None:
        return ''
    if isinstance(content, list):
        parts: list[str] = []
        for p in content:
            if isinstance(p, dict):
                if (p.get('type') or '').lower() == 'text' and p.get('text'):
                    parts.append(str(p.get('text')))
            else:
                parts.append(str(p))
        joined = ' '.join([x for x in (s.strip() for s in parts) if x]).strip()
        return sanitize_user_question_text(joined)
    return sanitize_user_question_text(str(content))


def coerce_chat_messages(messages: object) -> list[dict[str, Any]]:
    if not isinstance(messages, list):
        return []
    normalized: list[dict[str, Any]] = []
    for m in messages:
        if isinstance(m, dict):
            normalized.append(m)
            continue
        if m is None:
            continue
        txt = content_to_text(m)
        if txt:
            normalized.append({'role': 'user', 'content': txt})
    return normalized


def extract_session_id_from_request(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ''
    candidate_keys = (
        'session_id', 'sessionId', 'chat_id', 'chatId', 'conversation_id',
        'conversationId', 'thread_id', 'threadId',
    )
    def _pick(obj: object) -> str:
        if not isinstance(obj, dict):
            return ''
        for key in candidate_keys:
            v = obj.get(key)
            if v is not None:
                s = str(v).strip()
                if s:
                    return s[:128]
        return ''
    for obj in (payload, payload.get('metadata'), payload.get('extra')):
        sid = _pick(obj)
        if sid:
            return sid
    return ''


def _extract_course_codes_from_text(text: str) -> list[str]:
    return [f"{(a or '').upper()} {(b or '')}".strip() for a, b in _COURSE_CODE_RE.findall(text or '')]


def _latest_course_code_from_messages(messages: list[dict] | None) -> str:
    normalized = coerce_chat_messages(messages)
    for m in reversed(normalized):
        txt = content_to_text(m.get('content'))
        if not txt:
            continue
        mm = _COURSE_CODE_RE.search(txt)
        if mm:
            return f"{(mm.group(1) or '').upper()} {(mm.group(2) or '')}".strip()
    return ''


def _extract_instructor_mentions(text: str) -> list[str]:
    out: list[str] = []
    for m in _INSTRUCTOR_RE.finditer(text or ''):
        name = re.sub(r"\s+", " ", str(m.group(1) or '').strip())
        if name:
            name = re.split(
                r"\s+(?:สอนวิชาอะไร|วิชาที่สอน|มีวิชาอะไรบ้าง|วิชาอะไรบ้าง|คือใคร|คืออะไร|เรียนเกี่ยวกับอะไร|กี่หน่วยกิต)\b",
                name,
                maxsplit=1,
            )[0].strip()
        if name:
            out.append(name)
    return out


def _resolved_entity_from_effective_question(text: str) -> str:
    q = re.sub(r"\s+", " ", str(text or '').strip())
    if not q.startswith('บริบทก่อนหน้า:'):
        return ''
    anchor = q.replace('บริบทก่อนหน้า:', '', 1).strip()
    if 'คำถามต่อเนื่อง:' in anchor:
        anchor = anchor.split('คำถามต่อเนื่อง:', 1)[0].strip()
    return anchor


def _extract_term_mentions(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", str(m.group(0) or '').strip()) for m in _TERM_RE.finditer(text or '') if str(m.group(0) or '').strip()]


def _extract_topic_anchor(text: str) -> str:
    txt = re.sub(r"\s+", " ", str(text or '').strip())
    if not txt:
        return ''
    if any(rx.search(txt) for rx in (_COURSE_CODE_RE, _INSTRUCTOR_RE, _TERM_RE)):
        return ''
    if len(txt) <= 40 and not any(p in txt.lower() for p in ('อะไร', 'เมื่อไร', 'ยังไง', 'อย่างไร', 'ไหม', 'มั้ย', 'กี่', 'where', 'when', 'what')):
        return txt
    return ''


def _extract_reference_entities(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for code in _extract_course_codes_from_text(text):
        if code not in seen:
            seen.add(code)
            out.append(code)
    for name in _extract_instructor_mentions(text):
        anchor = f"อาจารย์{name}".strip()
        if anchor not in seen:
            seen.add(anchor)
            out.append(anchor)
    for term in _extract_term_mentions(text):
        if term not in seen:
            seen.add(term)
            out.append(term)
    topic = _extract_topic_anchor(text)
    if topic and topic not in seen:
        out.append(topic)
    return out


def _has_explicit_reference(text: str) -> bool:
    return bool(_extract_reference_entities(text))


def _entity_type_for_value(value: str) -> str:
    v = str(value or '').strip()
    if not v:
        return ''
    if _COURSE_CODE_RE.search(v):
        return 'course'
    if v.startswith('อาจารย์'):
        return 'instructor'
    if _TERM_RE.search(v):
        return 'term'
    return 'topic'


def _rank_followup_candidates(messages: list[dict] | None) -> list[tuple[str, str, int]]:
    normalized = coerce_chat_messages(messages)
    ranked: list[tuple[str, str, int]] = []
    seen: set[str] = set()
    score = 3
    for m in reversed(normalized):
        if (m.get('role') or '').strip().lower() != 'user':
            continue
        txt = content_to_text(m.get('content'))
        if not txt:
            continue
        refs = _extract_reference_entities(txt)
        if not refs:
            continue
        for ref in reversed(refs):
            key = ref.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            ranked.append((_entity_type_for_value(key), key, max(1, score)))
        score = max(1, score - 1)
    return ranked


def _latest_followup_anchor_from_messages(messages: list[dict] | None) -> str:
    normalized = coerce_chat_messages(messages)
    for m in reversed(normalized):
        if (m.get('role') or '').strip().lower() != 'user':
            continue
        txt = content_to_text(m.get('content'))
        if not txt:
            continue
        refs = _extract_reference_entities(txt)
        if refs:
            return refs[-1]
    return ''


def is_meta_followup_generation_prompt(text: str) -> bool:
    t = (text or '').strip()
    if not t:
        return False
    if _META_TASK_RE.search(t):
        return True
    tl = t.lower()
    if any(h in tl for h in _META_TASK_HINTS):
        return True
    return ('### chat history:' in tl) and ('follow-up questions' in tl)


def analyze_followup_entities(messages: list[dict] | None, effective_question: str) -> dict[str, str | int]:
    out: dict[str, str | int] = {
        'followup_latest_entity': '',
        'followup_previous_entity': '',
        'followup_entity_overridden': 0,
        'followup_entity_conflict': 0,
        'followup_resolved_entity_type': '',
        'followup_resolved_entity_value': '',
        'followup_resolved_entity_confidence': 0,
        'followup_resolved_entity_candidates': '',
        'followup_needs_clarification': 0,
    }
    normalized = coerce_chat_messages(messages)
    user_msgs = [content_to_text(m.get('content')) for m in normalized if (m.get('role') or '').strip().lower() == 'user']
    user_msgs = [m for m in user_msgs if m]
    if not user_msgs:
        return out
    last = user_msgs[-1]
    prev = user_msgs[-2] if len(user_msgs) >= 2 else ''
    latest_codes = _extract_course_codes_from_text(last)
    prev_codes = _extract_course_codes_from_text(prev)
    latest_instructors = _extract_instructor_mentions(last)
    prev_instructors = _extract_instructor_mentions(prev)
    latest = latest_codes[-1] if latest_codes else (f"อาจารย์{latest_instructors[-1]}" if latest_instructors else '')
    previous = prev_codes[-1] if prev_codes else (f"อาจารย์{prev_instructors[-1]}" if prev_instructors else '')
    out['followup_latest_entity'] = latest
    out['followup_previous_entity'] = previous
    if latest and previous and latest != previous:
        out['followup_entity_overridden'] = 1
        eff_codes = _extract_course_codes_from_text(effective_question or '')
        eff_instructors = _extract_instructor_mentions(effective_question or '')
        eff_latest = eff_codes[-1] if eff_codes else (f"อาจารย์{eff_instructors[-1]}" if eff_instructors else '')
        if (not eff_latest) or eff_latest != latest or previous in (effective_question or ''):
            out['followup_entity_conflict'] = 1

    resolved_value = ''
    resolved_confidence = 0
    resolved_type = ''
    ranked = _rank_followup_candidates(messages)
    anchor_from_effective_q = _resolved_entity_from_effective_question(str(effective_question or ''))
    if anchor_from_effective_q:
        resolved_value = anchor_from_effective_q
        resolved_type = _entity_type_for_value(resolved_value)
        resolved_confidence = 3
    elif latest:
        resolved_value = latest
        resolved_type = _entity_type_for_value(resolved_value)
        resolved_confidence = 2
    elif previous:
        resolved_value = previous
        resolved_type = _entity_type_for_value(resolved_value)
        resolved_confidence = 1

    out['followup_resolved_entity_type'] = resolved_type
    out['followup_resolved_entity_value'] = resolved_value
    out['followup_resolved_entity_confidence'] = resolved_confidence
    out['followup_resolved_entity_candidates'] = '|'.join(
        f"{etype}:{value}:{conf}" for etype, value, conf in ranked[:5]
    )
    if ranked:
        top_conf = ranked[0][2]
        second_conf = ranked[1][2] if len(ranked) > 1 else 0
        same_top_type = len(ranked) > 1 and ranked[0][0] == ranked[1][0]
        needs_clarification = (top_conf <= 1) or (same_top_type and second_conf >= top_conf)
        out['followup_needs_clarification'] = int(needs_clarification)
    return out


def looks_coreference_followup(text: str) -> bool:
    t = (text or '').strip().lower()
    if not t:
        return False
    coref_terms = (
        'อันนั้น', 'ตัวนั้น', 'อันนี้', 'ตัวนี้', 'วิชานั้น', 'อันก่อนหน้า', 'เมื่อกี้', 'เพิ่มเติม',
        'แล้ว', 'ต่อ', 'ต่อจาก', 'ใครสอน', 'มีกี่หน่วยกิต', 'กี่หน่วยกิต', 'หน่วยกิตเท่าไร',
        'ชื่อวิชาอะไร', 'วิชาอะไร', 'เรียนเกี่ยวกับอะไร', 'คำอธิบายรายวิชา', 'บังคับก่อนอะไร',
        'prerequisite อะไร', 'prereq อะไร', 'เปิดสอน', 'เงื่อนไขอะไร', 'วิชาที่สอน',
        'สอนวิชาอะไร', 'มีวิชาอะไรบ้าง', 'วิชาอะไรบ้าง'
    )
    return any(k in t for k in coref_terms)


def _is_underspecified_followup(text: str) -> bool:
    t = re.sub(r"\s+", " ", str(text or '').strip().lower())
    if not t or _has_explicit_reference(text):
        return False
    if len(t) <= 24:
        return True
    if any(k in t for k in (
        'อะไร', 'เมื่อไร', 'ยังไง', 'อย่างไร', 'กี่', 'ไหม', 'มั้ย', 'หรือไม่',
        'ที่สอน', 'ที่เรียน', 'ที่ใช้', 'ที่ต้องยื่น', 'รายละเอียด'
    )):
        return True
    return False


def build_effective_question(messages: list[dict] | None, default_question: str) -> str:
    normalized = coerce_chat_messages(messages)
    if not normalized:
        return str(default_question or '').strip()
    user_msgs = [content_to_text(m.get('content')) for m in normalized if (m.get('role') or '').strip().lower() == 'user']
    user_msgs = [m for m in user_msgs if m]
    if not user_msgs:
        return str(default_question or '').strip()
    last = user_msgs[-1]
    prev = user_msgs[-2] if len(user_msgs) >= 2 else ''
    if is_meta_followup_generation_prompt(last):
        return last
    last_l = last.lower()
    looks_like_placeholder = 'xxx' in last_l
    looks_like_new_code = _STANDALONE_CODE_RE.fullmatch(last) is not None
    looks_like_greeting = any(t in last_l for t in ('สวัสดี', 'หวัดดี', 'hello', 'hi'))
    followup_phrases = ('ขอรหัส', 'มีวิชาเดียว', 'ไม่เกี่ยว', 'ขออีก', 'หมายถึง', 'อันนี้', 'แบบไหน', 'อันไหน')
    is_followup = looks_like_placeholder or looks_coreference_followup(last) or any(p in last for p in followup_phrases)
    has_code_in_last = _COURSE_CODE_RE.search(last) is not None
    has_code_in_prev = _COURSE_CODE_RE.search(prev) is not None
    recent_user_window = user_msgs[-3:] if len(user_msgs) >= 3 else user_msgs
    if looks_like_new_code or looks_like_greeting:
        return last
    if has_code_in_last:
        return last
    if (looks_coreference_followup(last) or _is_underspecified_followup(last)) and not has_code_in_last:
        anchor_entity = _latest_followup_anchor_from_messages(normalized[:-1])
        if anchor_entity:
            return f"บริบทก่อนหน้า: {anchor_entity}\nคำถามต่อเนื่อง: {last}".strip()
        anchor = ' | '.join(recent_user_window[:-1]).strip(' |')
        if anchor:
            return f"{anchor}\nคำถามต่อเนื่อง: {last}".strip()
    if is_followup and prev and not (has_code_in_prev and has_code_in_last):
        return f"{prev}\nคำถามต่อเนื่อง: {last}".strip()
    return last


def is_short_ambiguous_followup(text: str) -> bool:
    q = (text or '').strip().lower()
    if not q:
        return False
    if _COURSE_CODE_RE.search(q):
        return False
    if any(t in q for t in ('มาสาย', 'ห้องสอบ', 'รหัสวิชา', 'prereq', 'instructor')):
        return False
    if not any(t in q for t in ('สรุป', 'สั้นๆ', 'ย้ำ', 'อีกครั้ง', 'อีกที', 'ขอสรุป', 'ขอแบบสั้น', 'short summary')):
        return False
    return len(re.sub(r"\s+", "", q)) <= 28


def looks_summary_followup(text: str) -> bool:
    q = (text or '').strip().lower()
    return bool(q) and any(t in q for t in ('สรุป', 'สั้นๆ', 'ย่อ', 'ย่อให้', 'ย้ำ', 'อีกครั้ง', 'อีกที', 'รวบยอด', 'summary', 'recap'))


def build_followup_summary_answer(summary_request: str, anchor_question: str, domain: str | None) -> str | None:
    req = (summary_request or '').strip().lower()
    anchor = (anchor_question or '').strip().lower()
    dom = (domain or '').strip().lower()
    if not looks_summary_followup(req):
        return None
    if dom == 'regulations' and ('มาสาย' in anchor and 'ออกจากห้องสอบชั่วคราว' in anchor):
        return (
            "สรุปสั้นๆ จากที่ถามก่อนหน้า:\n"
            "- มาสายเกิน 15 แต่ไม่เกิน 60 นาที ต้องยื่นคำร้องขออนุญาตเข้าห้องสอบก่อน; ถ้าเกิน 60 นาทีหมดสิทธิ์เข้าสอบ [rule_exam2560.txt/1]\n"
            "- ออกจากห้องสอบชั่วคราวได้เมื่อได้รับอนุญาตจากกรรมการคุมสอบ และห้ามนำเครื่องมือสื่อสารติดตัว [rule_exam2560.txt/1]"
        )
    return None


def apply_session_followup_lock(
    question: str,
    requested_domain: str | None,
    session_id: str,
    session_store: SessionStore,
) -> tuple[str, str | None, bool, str]:
    q = (question or '').strip()
    req_dom = (requested_domain or '').strip().lower() or None
    if not q:
        return q, requested_domain, False, 'empty_question'
    if not is_short_ambiguous_followup(q):
        return q, requested_domain, False, 'not_ambiguous_short_followup'
    hint = session_store.get_followup_hint(session_id)
    if not hint:
        return q, requested_domain, False, 'no_session_hint'
    hint_q = (hint.get('question') or '').strip()
    hint_dom = (hint.get('domain') or '').strip().lower()
    if not hint_q or hint_dom not in ('regulations', 'curriculum'):
        return q, requested_domain, False, 'hint_not_lockable'
    if req_dom and req_dom in KNOWN_DOMAINS and req_dom != hint_dom:
        return q, requested_domain, False, 'explicit_domain_override'
    prev_q = str(hint.get('prev_question') or '').strip()
    prev_dom = str(hint.get('prev_domain') or '').strip().lower()
    locked_q = f"{prev_q} แล้ว {hint_q}".strip() if prev_q and prev_dom == hint_dom else hint_q
    return locked_q, hint_dom, True, 'session_domain_lock_applied'


def remember_session_followup_hint(session_id: str, question: str, decision: Any, session_store: SessionStore) -> None:
    sid = (session_id or '').strip()
    q = (question or '').strip()
    if not sid or not q or is_meta_followup_generation_prompt(q):
        return
    intent = str(getattr(decision, 'primary_intent', '') or classify_intent(q)).strip().lower()
    if intent == 'general_info' and is_short_ambiguous_followup(q):
        return
    dom = str(getattr(decision, 'effective_domain', '') or '').strip().lower()
    if not dom or dom == 'auto':
        dom = str(getattr(decision, 'inferred_domain', '') or '').strip().lower()
    if not dom:
        return
    session_store.put_followup_hint(sid, question=q, domain=dom, intent=intent)


def prepare_chat_request(
    *,
    question: str,
    domain: str | None,
    session_id: str | None,
    messages: object,
    session_store: SessionStore,
    question_preparer,
) -> PreparedChatRequest:
    raw_input_question = str(question or '').strip()
    normalized_messages = coerce_chat_messages(messages)
    sid = str(session_id or '').strip()
    if (not normalized_messages) and sid:
        remembered = session_store.get_chat_history(sid)
        if remembered:
            normalized_messages = [{'role': 'user', 'content': txt} for txt in remembered]
            if raw_input_question:
                normalized_messages.append({'role': 'user', 'content': raw_input_question})
    raw_last_user = ''
    for msg in reversed(normalized_messages):
        if (msg.get('role') or '').strip().lower() == 'user':
            raw_last_user = content_to_text(msg.get('content', ''))
            break
    effective_question = build_effective_question(normalized_messages, raw_last_user or raw_input_question)
    effective_question = question_preparer(effective_question or raw_input_question, domain)
    effective_question, effective_domain, lock_applied, lock_reason = apply_session_followup_lock(
        effective_question,
        domain,
        sid,
        session_store,
    )
    meta = analyze_followup_entities(normalized_messages, effective_question)
    return PreparedChatRequest(
        question=effective_question,
        domain=effective_domain,
        session_id=sid,
        messages=normalized_messages,
        raw_last_user=raw_last_user,
        lock_applied=lock_applied,
        lock_reason=lock_reason,
        followup_meta=meta,
    )


def remember_chat_turn(session_id: str, raw_last_user: str, raw_input_question: str, effective_question: str, session_store: SessionStore) -> None:
    session_store.append_chat_turn(session_id, raw_last_user or raw_input_question or effective_question)
