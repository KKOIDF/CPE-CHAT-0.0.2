import os
import re
import logging
import traceback
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any
from .orchestration import rag_query, rag_query_domain, structured_curriculum_answer
from .llm import llm_engine
from .sqlite_client import close_thread_connections
from .neo4j_client import close_driver
from .perf import request_timing, time_block, add_metric, set_observer
from .mlflow_observability import init_mlflow_observability

logger = logging.getLogger("rag-service")

# Ensure timing logs are emitted when enabled.
if (os.getenv("RAG_TIMING", "0") or "0").strip().lower() in ("1", "true", "yes", "on"):
    try:
        logger.setLevel(logging.INFO)
        # Uvicorn's default logging config may not attach handlers to custom loggers.
        # Add a simple StreamHandler to ensure [TIMING] lines appear in container logs.
        if not logger.handlers:
            _h = logging.StreamHandler()
            _h.setLevel(logging.INFO)
            logger.addHandler(_h)
    except Exception:
        pass

_USE_LANGCHAIN = os.getenv('RAG_USE_LANGCHAIN', '0') in ('1', 'true', 'True')

# If LangChain is enabled but dependencies are missing, fall back gracefully.
_LANGCHAIN_READY = False
_langchain_rag = None
if _USE_LANGCHAIN:
    try:
        from . import langchain_rag as _langchain_rag  # type: ignore
        _LANGCHAIN_READY = True
    except Exception as e:
        logger.warning(
            "RAG_USE_LANGCHAIN enabled but LangChain is unavailable (%s). Falling back to built-in RAG.",
            str(e),
        )
        _USE_LANGCHAIN = False

_USE_STRUCTURED_CURRICULUM = os.getenv('RAG_USE_STRUCTURED_CURRICULUM', '1') in ('1', 'true', 'True')

_CITE_CAPTURE_RE = re.compile(r"\[([^\]]+?/\d+)\]")
_CITE_MATCH_RE = re.compile(r"\[[^\]]+?/\d+\]")
_BRACKET_RE = re.compile(r"\[[^\]]*\]")


def _extract_allowed_cites(prompt: str) -> list[str]:
    p = prompt or ''
    marker = 'รายชื่ออ้างอิงที่อนุญาต'
    if marker not in p:
        return []
    after = p.split(marker, 1)[1]
    if '\n\nคำตอบ:' in after:
        after = after.split('\n\nคำตอบ:', 1)[0]
    found = _CITE_CAPTURE_RE.findall(after)
    out: list[str] = []
    seen: set[str] = set()
    for c in found:
        if not c or c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out


def _has_citations(answer: str) -> bool:
    return bool(_CITE_MATCH_RE.search(answer or ''))


def _repair_answer_with_citations(answer: str, prompt: str) -> str:
    """Best-effort one-shot rewrite enforcing required citations.

    This is intentionally conservative: if we can't get citations, caller can
    decide to return the original answer or fallback.
    """
    allowed = _extract_allowed_cites(prompt)
    if not allowed:
        return answer
    if _has_citations(answer):
        return answer

    allowed_lines = "\n".join([f"- [{c}]" for c in allowed])
    repair_prompt = (
        "เขียนคำตอบใหม่จากคำตอบเดิม โดยบังคับรูปแบบดังนี้:\n"
        "- ต้องตอบเป็น bullet ทุกบรรทัด (ขึ้นต้นด้วย '- ')\n"
        "- ทุก bullet ต้องลงท้ายด้วยการอ้างอิงอย่างน้อย 1 รายการในรูปแบบ [source/page]\n"
        "- อนุญาตให้อ้างอิงได้เฉพาะรายการใน 'รายชื่ออ้างอิงที่อนุญาต' เท่านั้น\n"
        "- ห้ามใช้วงเล็บเหลี่ยม [] สำหรับอย่างอื่น\n\n"
        "รายชื่ออ้างอิงที่อนุญาต:\n"
        f"{allowed_lines}\n\n"
        "คำตอบเดิม:\n"
        f"{(answer or '').strip()}\n"
    )
    repaired = llm_engine.generate(repair_prompt)
    return repaired or answer


def _sanitize_answer_citations(answer: str, prompt: str) -> str:
    """Remove disallowed citations and ensure each bullet has >=1 allowed cite.

    Deterministic and conservative: never invents new cite labels; only uses
    the allowed list embedded in the prompt.
    """
    a = (answer or '').strip()
    allowed = _extract_allowed_cites(prompt)
    if not a or not allowed:
        return a

    allowed_set = set(allowed)
    fallback = allowed[0]

    # Drop any [source/page] citations not in the allowed list.
    def _keep_or_drop(m: re.Match) -> str:
        c = (m.group(1) or '').strip()
        return f"[{c}]" if c in allowed_set else ""

    a = _CITE_CAPTURE_RE.sub(_keep_or_drop, a)

    # Ensure every bullet-start line has at least one allowed citation.
    out_lines: list[str] = []
    for ln in a.splitlines():
        s = ln.rstrip()
        if s.lstrip().startswith('- ') and not _CITE_MATCH_RE.search(s):
            s = f"{s} [{fallback}]"
        out_lines.append(s)
    return "\n".join(out_lines).strip()


def _context_source_names(result: dict, limit: int = 6) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for ctx in (result.get('contexts') or []):
        src = str((ctx or {}).get('source') or (ctx or {}).get('path') or '').strip()
        if not src:
            continue
        name = src.replace('\\', '/').split('/')[-1]
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
        if len(out) >= limit:
            break
    return out

app = FastAPI(title="RAG Service", version="0.1.0")


@app.on_event("startup")
def _startup_observability() -> None:
    obs = init_mlflow_observability()
    if obs and getattr(obs, "enabled", lambda: False)():
        set_observer(obs.observe)


@app.on_event('shutdown')
def _shutdown_cleanup():
    # Flush and stop observability thread (best-effort).
    try:
        obs = init_mlflow_observability()
        if obs and getattr(obs, "enabled", lambda: False)():
            try:
                obs.flush_now()
            except Exception:
                pass
            try:
                obs.stop()
            except Exception:
                pass
    except Exception:
        pass

    # Best-effort cleanup (useful in dev/reload; safe to ignore failures).
    try:
        close_thread_connections()
    except Exception:
        pass
    try:
        close_driver()
    except Exception:
        pass

# CORS (for browser-based clients)
# Configure via env: CORS_ORIGINS="https://your.domain,https://other.domain"
_cors_origins = [
    o.strip() for o in (os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(','))
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"],
)

class RagRequest(BaseModel):
    question: str
    domain: str | None = None

class RagResponse(BaseModel):
    prompt: str
    contexts: list
    token_est: int
    meta: dict[str, Any] | None = None

class RagAnswerRequest(BaseModel):
    question: str
    domain: str | None = None

class RagAnswerResponse(BaseModel):
    question: str
    prompt: str
    answer: str
    contexts: list
    token_est: int
    meta: dict[str, Any] | None = None


# OpenAI API compatible models
class ChatCompletionChoice(BaseModel):
    index: int
    message: dict
    finish_reason: str = "stop"

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: dict = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


_FALLBACK = 'ไม่พบข้อมูลในเอกสาร'

_STANDALONE_CODE_RE = re.compile(r"^\s*[A-Za-z]{2,6}\s*[- ]?\s*\d{3}\s*$")

_COURSE_CODE_RE = re.compile(r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b")


def _content_to_text(content: object) -> str:
    """Best-effort conversion of chat message content to plain text."""
    if content is None:
        return ''
    # OpenAI-compatible APIs may send structured content (list of parts).
    if isinstance(content, list):
        parts: list[str] = []
        for p in content:
            if isinstance(p, dict):
                if (p.get('type') or '').lower() == 'text' and p.get('text'):
                    parts.append(str(p.get('text')))
            else:
                parts.append(str(p))
        return ' '.join([x for x in (s.strip() for s in parts) if x]).strip()
    return str(content).strip()


def _latest_course_code_from_messages(messages: list[dict] | None) -> str:
    """Best-effort latest course code mentioned in recent chat (user/assistant)."""
    if not messages:
        return ''
    for m in reversed(messages):
        txt = str((m or {}).get('content') or '').strip()
        if not txt:
            continue
        mm = _COURSE_CODE_RE.search(txt)
        if not mm:
            continue
        return f"{(mm.group(1) or '').upper()} {(mm.group(2) or '')}".strip()
    return ''


def _looks_coreference_followup(text: str) -> bool:
    t = (text or '').strip().lower()
    if not t:
        return False
    coref_terms = (
        'อันนั้น', 'ตัวนั้น', 'อันนี้', 'ตัวนี้', 'วิชานั้น', 'อันก่อนหน้า', 'เมื่อกี้', 'เพิ่มเติม',
        'แล้ว', 'ต่อ', 'ต่อจาก', 'ใครสอน', 'มีกี่หน่วยกิต', 'เปิดสอน', 'เงื่อนไขอะไร'
    )
    return any(k in t for k in coref_terms)
 


def _build_effective_question(messages: list[dict] | None, default_question: str) -> str:
    """Use a bit of chat history so follow-up questions keep context.

    OpenWebUI often sends multiple turns, but this service previously used only the
    last user message, causing follow-ups like "มีวิชาเดียวหรอ" to lose intent.
    """
    if not messages:
        return (default_question or '').strip()

    user_msgs: list[str] = []
    for m in messages:
        if (m or {}).get('role') == 'user':
            txt = _content_to_text((m or {}).get('content'))
            if txt:
                user_msgs.append(txt)

    if not user_msgs:
        return (default_question or '').strip()

    last = user_msgs[-1]
    prev = user_msgs[-2] if len(user_msgs) >= 2 else ''

    last_l = last.lower()
    looks_like_placeholder = ('xxx' in last_l)
    looks_like_new_code = _STANDALONE_CODE_RE.fullmatch(last) is not None
    looks_like_greeting = any(t in last_l for t in ('สวัสดี', 'หวัดดี', 'hello', 'hi'))
    followup_phrases = (
        'ขอรหัส', 'มีวิชาเดียว', 'ไม่เกี่ยว', 'ขออีก', 'หมายถึง', 'อันนี้', 'แบบไหน', 'อันไหน'
    )

    # Be conservative: only carry previous turn when the last message clearly
    # refers to earlier context (coreference/follow-up phrases/placeholder).
    is_followup = (
        looks_like_placeholder
        or _looks_coreference_followup(last)
        or any(p in last for p in followup_phrases)
    )
    has_code_in_last = _COURSE_CODE_RE.search(last) is not None
    recent_user_window = user_msgs[-3:] if len(user_msgs) >= 3 else user_msgs

    # Avoid carrying previous turn when user starts a new standalone topic/code.
    if looks_like_new_code or looks_like_greeting:
        return last

    # Coreference follow-up (e.g., "ใครสอน", "อันนั้นมีกี่หน่วยกิต"):
    # recover the latest mentioned course code/topic from recent turns.
    if _looks_coreference_followup(last) and not has_code_in_last:
        code = _latest_course_code_from_messages(messages)
        if code:
            return f"บริบทก่อนหน้า: {code}\nคำถามต่อเนื่อง: {last}".strip()
        if recent_user_window:
            anchor = ' | '.join(recent_user_window[:-1]).strip(' |')
            if anchor:
                return f"{anchor}\nคำถามต่อเนื่อง: {last}".strip()

    if is_followup and prev:
        return f"{prev}\nคำถามต่อเนื่อง: {last}".strip()
    return last


def _clarify_when_no_context(question: str) -> str | None:
    q = (question or '').strip()
    if not q:
        return None

    # Placeholder patterns: LNGxxx / CPExxx
    if re.search(r"\b[a-z]{2,6}xxx\b", q, re.IGNORECASE) or 'xxx' in q.lower():
        return (
            "ผมยังไม่แน่ใจว่าคุณหมายถึงรหัสวิชาแบบไหนครับ — ช่วยพิมพ์รหัสเต็ม (เช่น LNG 275 หรือ CPE 223) "
            "หรือบอกว่าอยากได้ ‘รายชื่อวิชาในหมวด LNG’ สำหรับภาคการศึกษาไหน (เช่น 2568/2)"
        )

    if 'รหัสวิชา' in q or re.search(r"\b(LNG|CPE|SSC|GEN)\b", q, re.IGNORECASE):
        return (
            "ผมยังไม่พบข้อมูลที่ยืนยันรหัสวิชาจากเอกสารที่ค้นได้ตอนนี้ครับ — "
            "ช่วยระบุเพิ่มนิดนึงว่าอยากได้ (1) รหัสวิชาแบบ ‘LNG 275’ หรือ (2) รหัสกลุ่ม/section ในตารางเรียน "
            "และเป็นภาคการศึกษาใด"
        )

    if 'ภาษา' in q:
        return "หมายถึงวิชา LNG ภาษาอะไรในหลักสูตร (เช่น ภาษาจีน/ญี่ปุ่น/มลายู) หรืออยากทราบรหัสวิชา/คำอธิบายรายวิชาครับ?"

    return None

_THAI_MONTHS = (
    'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
    'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'
)
_MONTH_RE = re.compile(r"(" + "|".join(map(re.escape, _THAI_MONTHS)) + r")")
_DOW_RE = re.compile(r"(จันทร์|อังคาร|พุธ|พฤหัสบดี|ศุกร์|เสาร์|อาทิตย์)")


def _strip_citations(text: str) -> str:
    # Remove packed-context cite labels like [file.txt/1]
    out = re.sub(_CITE_MATCH_RE, '', text or '')
    # Remove any remaining bracket blocks (models sometimes echo them)
    out = re.sub(_BRACKET_RE, '', out)
    return out


def _normalize_day_token(day_token: str) -> str:
    tok = re.sub(r"\D", "", (day_token or ''))
    if not tok:
        return day_token

    def _ok(n: int) -> bool:
        return 1 <= n <= 31

    # Try direct
    try:
        n = int(tok)
        if _ok(n):
            return str(n)
    except Exception:
        pass

    # Heuristics for OCR/table artifacts like 108 ตุลาคม, 109 พฤศจิกายน, 1936 มิถุนายน
    candidates: list[str] = []
    if len(tok) >= 2:
        candidates.append(tok[-2:])
        candidates.append(tok[:2])
    candidates.append(tok[-1:])

    for c in candidates:
        try:
            n = int(c)
        except Exception:
            continue
        if _ok(n):
            return str(n)

    return day_token


def _normalize_calendar_text(text: str) -> str:
    t = (text or '').replace('\u00a0', ' ')

    # OCR/table artifacts sometimes break numbers across lines (e.g., "1\n0").
    t = re.sub(r"(\d)\s*\n\s*(\d)", r"\1\2", t)

    # Normalize odd term formatting like 25692 -> 2569/2 when it appears after keyword.
    t = re.sub(r"(ภาคการศึกษาที่\s*)(\d{4})\s*([12])\b", r"\1\2/\3", t)

    # Fix day tokens that were merged (e.g., 108 ตุลาคม -> 8 ตุลาคม)
    def _fix_day_month(m: re.Match) -> str:
        day = _normalize_day_token(m.group(1))
        month = m.group(2)
        return f"{day} {month}"

    t = re.sub(rf"\b(\d{{3,4}})\s*{_MONTH_RE.pattern}\b", _fix_day_month, t)
    t = re.sub(
        rf"(ที่\s*)(\d{{3,4}})\s*{_MONTH_RE.pattern}\b",
        lambda m: f"{m.group(1)}{_normalize_day_token(m.group(2))} {m.group(3)}",
        t,
    )

    # Collapse excessive whitespace
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\s*\n\s*", "\n", t).strip()
    return t


def _clean_answer_text(answer: str, *, strip_citations: bool) -> str:
    a = (answer or '').strip()
    if strip_citations:
        a = _strip_citations(a)
    a = _normalize_calendar_text(a)
    # Remove stray spaces at line ends
    a = "\n".join([ln.rstrip() for ln in a.splitlines()]).strip()
    # If empty after cleaning, fallback
    return a or _FALLBACK


_LOW_CONF_THAI_STOPWORDS = {
    'อะไร', 'อย่างไร', 'หรือ', 'และ', 'ของ', 'ใน', 'ที่', 'ได้', 'ไหม', 'บ้าง', 'จาก', 'ให้', 'กับ',
    'เรื่อง', 'เกี่ยวกับ', 'ข้อมูล', 'เอกสาร', 'ระบุ', 'ถาม', 'ตอบ', 'หน่อย', 'ครับ', 'ค่ะ', 'คะ',
    'คือ', 'มี', 'ทำ', 'ยังไง', 'อย่าง', 'เช่น', 'ตรง', 'ไหน', 'เมื่อไร', 'เท่าไร', 'เท่าไหร่',
}


def _question_signal_terms(question: str) -> list[str]:
    q = (question or '').strip()
    if not q:
        return []

    terms: list[str] = []
    seen: set[str] = set()

    def _add(term: str) -> None:
        s = (term or '').strip()
        if not s:
            return
        key = s.lower()
        if key in seen:
            return
        seen.add(key)
        terms.append(s)

    for m in re.finditer(r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b", q):
        prefix = (m.group(1) or '').upper()
        num = m.group(2) or ''
        _add(f"{prefix}{num}")
        _add(f"{prefix} {num}")

    for token in re.findall(r"[\u0E00-\u0E7F]{4,}|[A-Za-z]{3,}|\d{2,4}", q):
        if re.fullmatch(r"[\u0E00-\u0E7F]{4,}", token):
            if token in _LOW_CONF_THAI_STOPWORDS:
                continue
            # Thai questions commonly arrive as one long unsegmented run; using that as a
            # mandatory lexical signal makes the guardrail abstain too aggressively.
            if len(token) > 12:
                continue
        _add(token)

    return terms[:12]


def _has_date_intent(question: str) -> bool:
    q = (question or '')
    # Do not treat exam-room policy questions as calendar-date questions.
    # Example: "ออกห้องสอบเมื่อไร" is typically answered in minutes (e.g., 60 นาที),
    # not a specific day/date.
    if any(t in q for t in ('ห้องสอบ', 'กรรมการคุมสอบ', 'คุมสอบ', 'ทุจริต', 'อุทธรณ์')):
        return any(t in q for t in ('วัน', 'วันที่', 'กำหนด', 'ปฏิทิน', 'ช่วงไหน', 'ภายในวัน'))
    return any(t in q for t in ('วัน', 'วันที่', 'เมื่อไร', 'กำหนด', 'ปฏิทิน', 'ช่วงไหน', 'ภายในวัน'))


def _has_exact_date_intent(question: str) -> bool:
    q = (question or '')
    if any(t in q for t in ('ห้องสอบ', 'กรรมการคุมสอบ', 'คุมสอบ', 'ทุจริต', 'อุทธรณ์')):
        return any(t in q for t in ('วันที่เท่าไร', 'วันไหน', 'วันใด', 'วันที่อะไร'))
    return any(t in q for t in ('วันที่เท่าไร', 'วันไหน', 'วันใด', 'เมื่อไหร่', 'วันที่อะไร'))


def _try_extract_exam_exit_rule(prompt: str, question: str) -> str | None:
    """Extract exam-room exit timing rule (ข้อ 15) from context if present."""
    q = (question or '').strip()
    if not q:
        return None
    # If the user asks about temporary leave, prefer clause 16.
    if 'ชั่วคราว' in q:
        return None
    if not any(t in q for t in ('ออกห้องสอบ', 'ออกจากห้องสอบ')):
        return None

    blocks = _extract_ctx_blocks(prompt)
    if not blocks:
        return None

    for cite, text in blocks:
        t = (text or '')
        if 'ข้อ 15' in t and ('หกสิบนาที' in t or '60' in t):
            stmt = t.replace('ออกหากห้องสอบ', 'ออกจากห้องสอบ')

            # Prefer extracting only clause 15 (stop before clause 16/17).
            m = re.search(r"ข้อ\s*15\s*(.+?)(?=(?:\n\s*)?ข้อ\s*1[67]\b|$)", stmt, flags=re.DOTALL)
            if m:
                core = (m.group(0) or '').strip()
            else:
                start = stmt.find('ข้อ 15')
                core = stmt[start:].strip() if start != -1 else stmt.strip()
                cut = re.search(r"(?:\n\s*)?ข้อ\s*1[67]\b", core)
                if cut:
                    core = core[:cut.start()].strip()

            if len(core) > 260:
                core = core[:260].rstrip() + ' ...'
            return f"- {core} [{cite}]"
    return None


def _try_extract_exam_temp_leave_rule(prompt: str, question: str) -> str | None:
    """Extract exam-room temporary leave rule (ข้อ 16) from context if present."""
    q = (question or '').strip()
    if not q:
        return None
    if 'ชั่วคราว' not in q and 'ออกห้องสอบชั่วคราว' not in q:
        return None

    blocks = _extract_ctx_blocks(prompt)
    if not blocks:
        return None

    for cite, text in blocks:
        t = (text or '')
        if 'ข้อ 16' in t and ('ออกจากห้องสอบ' in t or 'ห้องสอบ' in t):
            stmt = t.replace('ออกหากห้องสอบ', 'ออกจากห้องสอบ')
            m = re.search(r"ข้อ\s*16\s*(.+?)(?=(?:\n\s*)?ข้อ\s*17\b|$)", stmt, flags=re.DOTALL)
            core = (m.group(0) or '').strip() if m else stmt[stmt.find('ข้อ 16'):].strip()
            if len(core) > 260:
                core = core[:260].rstrip() + ' ...'
            return f"- {core} [{cite}]"
    return None


def _try_extract_exam_late_entry_rule(prompt: str, question: str) -> str | None:
    """Extract late-entry policy (ข้อ 12) from context when asked."""
    q = (question or '').strip()
    if not q:
        return None
    ql = q.lower()
    if not (('สอบ' in ql or 'ห้องสอบ' in ql) and ('มาสาย' in ql or 'สาย' in ql or 'เข้าห้องสอบ' in ql)):
        return None

    blocks = _extract_ctx_blocks(prompt)
    if not blocks:
        return None

    for cite, text in blocks:
        t = (text or '')
        if ('ข้อ 12' in t) and ('ห้องสอบ' in t) and (('สิบห้านาที' in t) or ('15' in t)) and (('หกสิบนาที' in t) or ('60' in t)):
            return (
                f"- หากมาสายเกิน 15 นาที แต่ไม่เกิน 60 นาที ต้องยื่นคำร้องขอเข้าห้องสอบเพื่อพิจารณาอนุญาตก่อนเข้าห้องสอบ [{cite}]\n"
                f"- หากมาสายเกิน 60 นาที ถือว่าหมดสิทธิ์เข้าห้องสอบ [{cite}]"
            )
    return None


def _has_date_evidence(text: str) -> bool:
    t = (text or '')
    if _MONTH_RE.search(t) or _DOW_RE.search(t):
        return True
    return bool(re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}\b", t))


def _has_exact_date_evidence(text: str) -> bool:
    t = (text or '')
    if _MONTH_RE.search(t) or _DOW_RE.search(t):
        return True
    return bool(re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", t))


def _low_confidence_guardrail(question: str, result: dict) -> str | None:
    contexts = result.get('contexts') or []
    if not contexts:
        return None

    blocks = _extract_ctx_blocks(result.get('prompt') or '')
    if not blocks:
        return None

    joined = "\n".join([f"{cite} {text}" for cite, text in blocks]).lower()
    signal_terms = _question_signal_terms(question)
    matched_terms = [term for term in signal_terms if term.lower() in joined]

    if signal_terms and not matched_terms:
        add_metric('guardrail_low_confidence', 1)
        return _clarify_when_no_context(question) or 'ไม่พบข้อความยืนยันโดยตรงในเอกสารที่ค้นได้'

    if _has_exact_date_intent(question) and not _has_exact_date_evidence(joined):
        add_metric('guardrail_missing_exact_date_evidence', 1)
        return 'ไม่พบข้อความยืนยันวันหรือวันที่ที่ถามโดยตรงในเอกสารที่ค้นได้'

    if _has_date_intent(question) and not _has_date_evidence(joined):
        add_metric('guardrail_missing_date_evidence', 1)
        return 'ไม่พบข้อความยืนยันวันหรือวันที่ที่ถามโดยตรงในเอกสารที่ค้นได้'

    return None


def _extract_ctx_blocks(prompt: str) -> list[tuple[str, str]]:
    """Return list of (cite, text) blocks from the packed context section in the prompt."""
    p = prompt or ''
    start_marker = 'บริบท'
    end_marker = 'รายชื่ออ้างอิงที่อนุญาต'
    # Newer prompt format may not include the allowed-citation section; fall back to the answer header.
    end_marker_alt = '\n\nคำตอบ:'
    if start_marker not in p or (end_marker not in p and end_marker_alt not in p):
        return []
    mid = p.split(start_marker, 1)[1]
    if end_marker in mid:
        mid = mid.split(end_marker, 1)[0]
    elif end_marker_alt in mid:
        mid = mid.split(end_marker_alt, 1)[0]
    # Each packed block is like: [name.pdf/12] some text...
    blocks: list[tuple[str, str]] = []
    for m in re.finditer(r"\[([^\]]+?/\d+)\]\s*", mid):
        cite = m.group(1)
        start = m.end()
        next_m = re.search(r"\n\n\[[^\]]+?/\d+\]\s*", mid[start:])
        end = start + (next_m.start() if next_m else len(mid[start:]))
        text = (mid[start:end] or '').strip()
        if text:
            blocks.append((cite, text))
    return blocks


def _try_extract_total_credits(prompt: str, question: str | None = None) -> str | None:
    """Best-effort extraction of program total credits from context blocks.

    If we can confidently extract a single total-credit value, return a fully
    formatted bullet answer with a valid citation.
    """
    q = (question or '').strip()
    if q and not any(t in q for t in ('รวมกี่หน่วยกิต', 'หน่วยกิตรวมของหลักสูตร', 'จำนวนหน่วยกิตรวม', 'ตลอดหลักสูตร')):
        return None

    blocks = _extract_ctx_blocks(prompt)
    if not blocks:
        return None

    # Thai patterns often look like:
    # - "จำนวนหน่วยกิตที่เรียนตลอดหลักสูตร 130 หน่วยกิต"
    # - "หน่วยกิตรวม 130 หน่วยกิต" / "รวม ... 130 หน่วยกิต" / "ไม่น้อยกว่า 130 หน่วยกิต"
    # Heuristic: prefer 80-200 range to avoid picking per-course credits.
    pat = re.compile(
        r"(จำนวนหน่วยกิต(?:ที่เรียน)?(?:ตลอดหลักสูตร)?|จานวนหน่วยกิต(?:ที่เรียน)?(?:ตลอดหลักสูตร)?|หน่วยกิต(?:รวม|ตลอดหลักสูตร|ที่เรียนตลอดหลักสูตร)|รวม(?:ทั้งสิ้น)?|รวมไม่น้อยกว่า|ไม่น้อยกว่า)"
        r"[^\d]{0,60}(\d{2,3})\s*หน่วยกิต"
    )
    found: list[tuple[int, str]] = []
    for cite, text in blocks:
        for mm in pat.finditer(text):
            try:
                n = int(mm.group(2))
            except Exception:
                continue
            if 80 <= n <= 200:
                found.append((n, cite))

    if not found:
        return None

    # Pick the most frequent value; tie-breaker = first seen.
    counts: dict[int, int] = {}
    first_cite: dict[int, str] = {}
    for n, cite in found:
        counts[n] = counts.get(n, 0) + 1
        first_cite.setdefault(n, cite)
    best_n = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    cite = first_cite.get(best_n)
    if not cite:
        return None

    return f"- หลักสูตรกำหนดหน่วยกิตรวม {best_n} หน่วยกิต [{cite}]"


def _extract_course_codes(text: str) -> list[str]:
    q = (text or '').strip()
    if not q:
        return []

    out: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b", q):
        code = f"{(m.group(1) or '').upper()}{m.group(2) or ''}"
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def _load_context_texts_from_sqlite(contexts: list, domain: str | None = None) -> list[tuple[str, str]]:
    """Load full chunk text by doc_id from domain SQLite and return [(cite, text)]."""
    if not contexts:
        return []

    try:
        from .config import domain_paths  # local import to avoid cycles at module load
    except Exception:
        return []

    dom = (domain or '').strip().lower() or None
    try:
        _chroma_dir, sqlite_path = domain_paths(dom)
    except Exception:
        return []

    db_path = str(sqlite_path)
    if not db_path or not os.path.exists(db_path):
        return []

    doc_rows: list[tuple[str, str]] = []
    ids: list[str] = []
    id_seen: set[str] = set()
    for c in contexts:
        did = str((c or {}).get('doc_id') or '').strip()
        if not did or did in id_seen:
            continue
        id_seen.add(did)
        ids.append(did)

    if not ids:
        return []

    text_by_id: dict[str, str] = {}
    try:
        con = sqlite3.connect(db_path)
        placeholders = ','.join(['?'] * len(ids))
        q = f"SELECT doc_id, text FROM documents WHERE doc_id IN ({placeholders})"
        for row in con.execute(q, ids).fetchall():
            did = str((row or [None])[0] or '').strip()
            txt = str((row or [None, ''])[1] or '')
            if did and txt:
                text_by_id[did] = txt
    except Exception:
        return []
    finally:
        try:
            con.close()  # type: ignore[name-defined]
        except Exception:
            pass

    for c in contexts:
        did = str((c or {}).get('doc_id') or '').strip()
        txt = text_by_id.get(did, '')
        if not txt:
            continue
        source = str((c or {}).get('source') or 'unknown').strip()
        page = (c or {}).get('page_start') or 1
        cite = f"{source}/{page}"
        doc_rows.append((cite, txt))
    return doc_rows


def _find_instructors_from_sqlite_by_codes(domain: str | None, codes: list[str], limit_rows: int = 200) -> list[tuple[str, str]]:
    """Fallback search across the domain SQLite for instructor-course co-occurrences.

    Returns list of (name, cite) pairs.
    """
    if not codes:
        return []

    try:
        from .config import domain_paths  # local import to avoid cycles at module load
    except Exception:
        return []

    dom = (domain or '').strip().lower() or None
    if dom is None:
        # Heuristic: course-code questions in this project map to curriculum domain.
        if any((c or '').upper().startswith('CPE') for c in codes):
            dom = 'curriculum'

    try:
        _chroma_dir, sqlite_path = domain_paths(dom)
    except Exception:
        return []

    db_path = str(sqlite_path)
    if not db_path or not os.path.exists(db_path):
        return []

    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    title_name_re = re.compile(r"((?:ศ\.ดร\.|รศ\.ดร\.|ผศ\.ดร\.|ดร\.|อ\.)\s*[^\n\[\]]{2,120})")
    stop_tokens = (
        'Assoc.', 'Assistant Professor', 'Professor', 'ภาระงานสอน',
        'ประวัติการศึกษา', 'รายวิชา', 'อนุมัติจากสภา', 'International'
    )

    con = None
    try:
        con = sqlite3.connect(db_path)
        for code in codes:
            pref, num = code[:-3], code[-3:]
            like1 = f"%{pref} {num}%"
            like2 = f"%{pref}{num}%"
            rows = con.execute(
                "SELECT text FROM documents WHERE text LIKE ? OR text LIKE ? LIMIT ?",
                (like1, like2, int(limit_rows)),
            ).fetchall()

            for row in rows:
                txt = str((row or [''])[0] or '')
                if not txt:
                    continue
                for m in title_name_re.finditer(txt):
                    raw = (m.group(1) or '').strip()
                    if not raw:
                        continue

                    cleaned = raw
                    for tok in stop_tokens:
                        pos = cleaned.find(tok)
                        if pos > 0:
                            cleaned = cleaned[:pos].strip()
                    # Drop trailing qualification/noise after separators.
                    cleaned = re.split(r"\s+-\s+|\s+\(|\s+Assoc\.|\s+Professor", cleaned, maxsplit=1)[0].strip()
                    cleaned = cleaned.strip(' -,:;()[]')
                    if len(cleaned) < 6:
                        continue
                    if not re.search(r"[\u0E00-\u0E7F]", cleaned):
                        continue

                    norm = re.sub(r"\s+", "", cleaned)
                    if norm in seen:
                        continue
                    seen.add(norm)
                    # We don't have exact source/page here; use sqlite-domain citation.
                    out.append((cleaned, "sqlite_lookup/1"))
    except Exception:
        return out
    finally:
        try:
            if con is not None:
                con.close()
        except Exception:
            pass

    return out


def _try_extract_course_instructors(
    prompt: str,
    question: str | None = None,
    contexts: list | None = None,
    domain: str | None = None,
) -> str | None:
    """Extract instructor names for course-code questions (e.g., CPE314)."""
    q = (question or '').strip()
    if not q:
        return None

    intent_tokens = (
        'ใครสอน', 'ผู้สอน', 'อาจารย์', 'อาจานย์', 'สอนโดย',
        'instructor', 'teacher', 'teaches'
    )
    if not any(t in q.lower() for t in [tok.lower() for tok in intent_tokens]):
        return None

    target_codes = _extract_course_codes(q)
    if not target_codes:
        return None

    blocks = _extract_ctx_blocks(prompt)
    sqlite_blocks = _load_context_texts_from_sqlite(contexts or [], domain=domain)
    all_blocks = [*blocks, *sqlite_blocks]
    if not all_blocks:
        return None

    # Thai/academic titles commonly present before instructor names in OCR text.
    title_name_re = re.compile(r"((?:ศ\.ดร\.|รศ\.ดร\.|ผศ\.ดร\.|ดร\.|อ\.)\s*[^\n\[\]]{2,120})")
    stop_tokens = (
        'Assoc.', 'Assistant Professor', 'Professor', 'ภาระงานสอน',
        'ประวัติการศึกษา', 'รายวิชา', 'อนุมัติจากสภา', 'International'
    )

    found: list[tuple[str, str]] = []  # (name, cite)
    for cite, text in all_blocks:
        t = (text or '')
        if not t.strip():
            continue

        # Keep only blocks that mention at least one asked course code.
        mentions_code = False
        for code in target_codes:
            pref, num = code[:-3], code[-3:]
            if re.search(rf"\b{re.escape(pref)}\s*[- ]?\s*{re.escape(num)}\b", t, flags=re.IGNORECASE):
                mentions_code = True
                break
        if not mentions_code:
            continue

        for m in title_name_re.finditer(t):
            raw = (m.group(1) or '').strip()
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

    if not found:
        found = _find_instructors_from_sqlite_by_codes(domain=domain, codes=target_codes)
        if not found:
            return None

    # Deduplicate while preserving order.
    uniq_names: list[str] = []
    first_cite: dict[str, str] = {}
    seen_norm: set[str] = set()
    for name, cite in found:
        norm = re.sub(r"\s+", "", name)
        if norm in seen_norm:
            continue
        seen_norm.add(norm)
        uniq_names.append(name)
        first_cite[name] = cite

    if not uniq_names:
        return None

    code_disp = f"{target_codes[0][:-3]} {target_codes[0][-3:]}"
    if len(uniq_names) == 1:
        n = uniq_names[0]
        return f"- รายวิชา {code_disp} ระบุผู้สอนเป็น {n} [{first_cite.get(n, '')}]"

    out = [f"- รายวิชา {code_disp} พบชื่อผู้สอนที่เกี่ยวข้องในเอกสารดังนี้"]
    for n in uniq_names[:6]:
        out.append(f"- {n} [{first_cite.get(n, '')}]")
    return "\n".join(out)


def _try_extract_withdraw_w_dates(prompt: str, question: str | None = None) -> str | None:
    q = (question or '').lower()
    if q and ('ถอน' not in q or 'w' not in q):
        # If question is provided and doesn't look like W-withdrawal, skip.
        return None

    blocks = _extract_ctx_blocks(prompt)
    if not blocks:
        return None

    # Merge all text from context blocks (strip cite labels).
    raw = "\n".join([t for _c, t in blocks])
    raw = _normalize_calendar_text(_strip_citations(raw))

    # Fast path: extract a clear date range after the W-withdraw marker.
    # This avoids accidentally grabbing unrelated deadlines that appear before the marker
    # (common in OCR/table chunks where everything is on one long line).
    marker_re = re.compile(r"วันถอนรายวิชา[^\n]{0,80}?W", re.IGNORECASE)
    mm = marker_re.search(raw)
    window = raw[mm.start():] if mm else raw
    window = window[:1200]

    date_re = re.compile(
        rf"วัน(?P<dow>{_DOW_RE.pattern})ที่\s*(?P<day>\d{{1,4}})\s*(?P<month>{_MONTH_RE.pattern})(?:\s*(?P<year>\d{{4}}))?"
    )

    def _range_from_text(txt: str) -> str | None:
        ms = list(date_re.finditer(txt or ''))
        if len(ms) < 2:
            return None
        m1, m2 = ms[0], ms[1]
        y1, y2 = m1.group('year'), m2.group('year')
        if not y1 and y2:
            y1 = y2
        if not y2 and y1:
            y2 = y1

        def _fmt(m: re.Match, year: str | None) -> str:
            dow = (m.group('dow') or '').strip()
            day = _normalize_day_token(m.group('day') or '')
            month = (m.group('month') or '').strip()
            tail = f" {year}" if year else ""
            return f"วัน{dow}ที่ {day} {month}{tail}".strip()

        return f"{_fmt(m1, y1)} – {_fmt(m2, y2)}"

    date_range = _range_from_text(window)
    saw_acis = ('new acis' in window.lower()) or ('new acis' in raw.lower())

    def _extract_term(qtext: str) -> str | None:
        qq = qtext or ''
        m1 = re.search(r"ภาคการศึกษาที่\s*(\d{1,2})\s*/\s*(\d{4})", qq)
        if m1:
            return f"{m1.group(1)}/{m1.group(2)}"
        m2 = re.search(r"ภาคการศึกษาที่\s*(\d{4})\s*/\s*([12])", qq)
        if m2:
            return f"{m2.group(1)}/{m2.group(2)}"
        return None

    if date_range:
        term = _extract_term(question or '')
        term_part = f" ภาคการศึกษาที่ {term}" if term else ""
        out = [f"- วันถอนรายวิชาติด W{term_part}: {date_range}"]
        if saw_acis:
            out.append("- การถอนรายวิชาติด W ต้องดำเนินการผ่านระบบ New ACIS")
        return "\n".join(out).strip()

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]

    # Capture only within the W-withdrawal section if present.
    in_w = False
    captured: list[str] = []
    for ln in lines:
        if ('วันถอนรายวิชา' in ln and 'W' in ln) or ('วันถอนรายวิชา' in ln and 'ติด W' in ln):
            in_w = True
            split_m = re.search(r"วันถอนรายวิชา.*?W", ln)
            if split_m and split_m.end() < len(ln):
                tail = (ln[split_m.end():] or '').strip(' :-\t')
                if tail:
                    captured.append(tail)
            continue
        if in_w and ln.startswith('หมายเหตุ'):
            break
        if in_w:
            captured.append(ln)

    if not captured:
        return None

    # Parse label -> date line pairs based on nearest preceding label.
    label: str | None = None
    dates: dict[str, str] = {}
    saw_acis = False
    for ln in captured:
        low = ln.lower()
        if 'new acis' in low:
            saw_acis = True

        if 'รายวิชาทั่วไป/โมดูล' in ln or ('รายวิชาทั่วไป' in ln and 'โมดูล' in ln):
            label = 'รายวิชาทั่วไปและรายวิชาโมดูล'
        if 'รายวิชาทั่วไป' in ln and 'โมดูล' not in ln:
            label = 'รายวิชาทั่วไป'
        if 'รายวิชาโมดูล 10' in ln:
            label = 'รายวิชาโมดูล 10 สัปดาห์'
        if 'รายวิชาโมดูล 5' in ln:
            label = 'รายวิชาโมดูล 5 สัปดาห์'

        # Date-ish line.
        is_dateish = (
            (_DOW_RE.search(ln) is not None and _MONTH_RE.search(ln) is not None) or
            (ln.startswith('ภายในวัน') and _MONTH_RE.search(ln) is not None)
        )
        if is_dateish and label and label not in dates:
            dates[label] = _range_from_text(ln) or ln

    if not dates and not saw_acis:
        return None

    # Compose clean, user-facing answer.
    out: list[str] = []
    if 'รายวิชาทั่วไปและรายวิชาโมดูล' in dates:
        out.append(f"- วันถอนรายวิชาติด W (รายวิชาทั่วไป/รายวิชาโมดูล): {dates['รายวิชาทั่วไปและรายวิชาโมดูล']}")
    if 'รายวิชาทั่วไป' in dates:
        out.append(f"- วันถอนรายวิชาติด W (รายวิชาทั่วไป): {dates['รายวิชาทั่วไป']}")
    if 'รายวิชาโมดูล 10 สัปดาห์' in dates:
        out.append(f"- วันถอนรายวิชาติด W (รายวิชาโมดูล 10 สัปดาห์): {dates['รายวิชาโมดูล 10 สัปดาห์']}")
    if 'รายวิชาโมดูล 5 สัปดาห์' in dates:
        out.append(f"- วันถอนรายวิชาติด W (รายวิชาโมดูล 5 สัปดาห์): {dates['รายวิชาโมดูล 5 สัปดาห์']}")
    if saw_acis:
        out.append("- การถอนรายวิชาติด W ต้องดำเนินการผ่านระบบ New ACIS")
    return "\n".join(out).strip() if out else None


def _try_extract_intermission_leave(prompt: str, question: str | None = None) -> str | None:
    q = (question or '').strip().lower()
    if q and not any(t in q for t in ('ลาพัก', 'ลาพักการเรียน', 'ลาพักการศึกษา', 'intermission', 'พักการเรียน')):
        return None

    blocks = _extract_ctx_blocks(prompt)
    if not blocks:
        return None

    # Look for explicit policy sentence in academic calendar/regulations.
    policy_line: tuple[str, str] | None = None  # (text, cite)
    approval_hint: tuple[str, str] | None = None
    for cite, text in blocks:
        # Remove common publication-date tail that models often misinterpret.
        cleaned = re.sub(r"ประกาศ\s*ณ\s*วันที่[^\n]{0,120}", "", text)
        cleaned = re.sub(r"ประกาศณ\s*วันที่[^\n]{0,120}", "", cleaned)
        m = re.search(
            r"(นักศึกษาที่ประสงค์จะลา(?:พักการเรียน|พักการศึกษา)[^\n]{0,260}?(?:ก่อนวันลงทะเบียนรักษาสภาพ|ก่อนวันลงทะเบียน)[^\n]{0,160})",
            cleaned,
        )
        if m:
            policy_line = (m.group(1).strip(), cite)
            break
        # Fallback: ensure we capture the approval requirement even if phrasing differs.
        m2 = re.search(
            r"(ลา(?:พักการเรียน|พักการศึกษา)[^\n]{0,200}?ขออนุมัติจากคณะ[^\n]{0,200}?(?:ก่อนวันลงทะเบียนรักษาสภาพ|ก่อนวันลงทะเบียน)[^\n]{0,160})",
            cleaned,
        )
        if m2:
            policy_line = (m2.group(1).strip(), cite)
            break

        # Capture simpler approval requirement (often only present in form description).
        m3 = re.search(
            r"(ใช้ขอ[^\n]{0,220}?(?:ต้องได้รับอนุมัติจากคณะ|ขออนุมัติจากคณะ)[^\n]{0,80})",
            cleaned,
        )
        if m3 and approval_hint is None:
            approval_text = (m3.group(1) or '').strip()
            approval_text = re.sub(r"ลิงก์\s*:\s*https?://\S+", "", approval_text).strip()
            approval_text = re.sub(r"https?://\S+", "", approval_text).strip()
            approval_text = approval_text.strip(' :-\t')
            if approval_text:
                approval_hint = (approval_text, cite)

    # Look for the specific form reference/link (RO-12) if present.
    form_line: tuple[str, str] | None = None
    form_url: str | None = None

    def _trim_pdf(url: str) -> str:
        u = (url or '').rstrip(')];,')
        m = re.search(r"(?i)\.pdf", u)
        if not m:
            return u
        return u[: m.end()]

    ro12_url: str | None = None
    ro12_cite: str | None = None
    line_url: str | None = None
    line_cite: str | None = None

    for cite, text in blocks:
        # Prefer explicit RO-12 links anywhere in the block (robust to line breaks).
        compact = re.sub(r"\s+", "", text or "")
        pdf_urls = re.findall(r"https?://[^\s]+?\.pdf", compact, re.IGNORECASE)
        for u in pdf_urls:
            if 'RO-12' in (u or '').upper():
                ro12_url = _trim_pdf(u)
                ro12_cite = cite
                break
        if ro12_url and ro12_cite:
            break

        # Otherwise, only accept a URL if it appears on the same line as the intermission-leave form name.
        if line_url is not None:
            continue
        for ln in (text or '').splitlines():
            if not ln:
                continue
            if ('คำร้องขอลาพักการศึกษา' not in ln) and ('Intermission Leave' not in ln) and ('Request Form for Intermission Leave' not in ln):
                continue
            urls = re.findall(r"https?://\S+", ln)
            if not urls:
                # If the URL is broken across lines, the compact RO-12 scan above should catch it.
                continue
            pick = None
            for u in urls:
                if 'RO-12' in (u or '').upper():
                    pick = u
                    break
            if pick is None and len(urls) == 1:
                pick = urls[0]
            if pick:
                line_url = _trim_pdf(pick)
                line_cite = cite
                break

    if ro12_url and ro12_cite:
        form_url = ro12_url
        form_line = ("ต้องใช้คำร้องขอลาพักการศึกษา (RO-12)", ro12_cite)
    elif line_url and line_cite:
        form_url = line_url
        form_line = ("ต้องใช้คำร้องขอลาพักการศึกษา (Request Form for Intermission Leave)", line_cite)

    if not policy_line and not approval_hint and not form_line:
        return None

    out: list[str] = []
    if policy_line:
        out.append(f"- {policy_line[0]} [{policy_line[1]}]")
    elif approval_hint:
        out.append(f"- {approval_hint[0]} [{approval_hint[1]}]")
    if form_line:
        if form_url:
            out.append(f"- {form_line[0]}: {form_url} [{form_line[1]}]")
        else:
            out.append(f"- {form_line[0]} [{form_line[1]}]")
    return "\n".join(out).strip()


def _default_allowed_citation(prompt: str) -> str | None:
    allowed = sorted(_extract_allowed_citations(prompt or ''))
    if not allowed:
        return None
    return f"[{allowed[0]}]"


# Valid citation block format, e.g. [foo.txt/1]
_CITE_RE = re.compile(r"\[[^\]/]+/\d+\]")


def _repair_citations(answer: str, prompt: str) -> str:
    """Repair missing/invalid bracket blocks and ensure each bullet has a citation."""
    ans = (answer or '').strip()
    if not ans:
        return ans

    default_cite = _default_allowed_citation(prompt)
    if not default_cite:
        return ans

    bullets = _split_bullets(ans)
    fixed: list[str] = []
    for b in bullets:
        bb = (b or '').strip()
        if not bb:
            continue
        # Remove bracket blocks that are not [src/page] citations to satisfy guardrails.
        bb = re.sub(r"\[[^\]]*\]", lambda m: m.group(0) if _CITE_RE.fullmatch(m.group(0)) else '', bb).strip()
        if not _CITE_RE.search(bb):
            # Ensure every bullet ends with a valid allowed citation.
            bb = bb.rstrip() + f" {default_cite}"
        fixed.append(bb)
    return "\n".join(fixed).strip()


def _split_bullets(text: str) -> list[str]:
    lines = (text or '').splitlines()
    bullets: list[str] = []
    current: list[str] = []
    for ln in lines:
        if ln.lstrip().startswith('- '):
            if current:
                bullets.append('\n'.join(current).strip())
                current = []
            current.append(ln.strip())
        else:
            if current:
                current.append(ln.rstrip())
    if current:
        bullets.append('\n'.join(current).strip())
    if not bullets and (text or '').strip():
        bullets = [(text or '').strip()]
    return bullets


def _extract_allowed_citations(prompt: str) -> set[str]:
    """Parse allowed citations from the dedicated section in the prompt."""
    p = prompt or ''
    marker = 'รายชื่ออ้างอิงที่อนุญาต'
    if marker not in p:
        return set()
    after = p.split(marker, 1)[1]
    # Keep only the section until the answer header.
    if '\n\nคำตอบ:' in after:
        after = after.split('\n\nคำตอบ:', 1)[0]
    cites = re.findall(r"\[([^\]]+?/\d+)\]", after)
    return set(cites)


def _require_citations() -> bool:
    return (os.getenv('RAG_REQUIRE_CITATIONS', '0') or '0').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )


def _infer_primary_intent(question: str) -> str:
    q = (question or '').strip().lower()
    if not q:
        return 'unknown'

    if any(t in q for t in ('ใครสอน', 'ผู้สอน', 'อาจารย์', 'คนสอน', 'instructor', 'lecturer', 'teacher')):
        return 'instructor_lookup'
    if any(t in q for t in ('หน่วยกิต', 'กี่หน่วยกิต', 'credit', 'credits')):
        return 'credit_lookup'
    if any(t in q for t in ('บังคับก่อน', 'prerequisite', 'pre-req', 'prereq', 'ต้องผ่าน')):
        return 'prerequisite_lookup'
    if any(t in q for t in ('ห้องสอบ', 'คุมสอบ', 'มาสาย', 'ออกจากห้องสอบ', 'ทุจริต', 'อุทธรณ์')):
        return 'exam_policy'
    if any(t in q for t in ('ลงทะเบียน', 'เพิ่มถอน', 'ลงเพิ่ม', 'ถอน', 'drop', 'register', 'enroll')):
        return 'registration_policy'
    if any(t in q for t in ('วัน', 'วันที่', 'เมื่อไร', 'กำหนด', 'deadline', 'ปฏิทิน', 'calendar')):
        return 'calendar_deadline'
    if any(t in q for t in ('หลักสูตร', 'รายวิชา', 'วิชา', 'รหัสวิชา', 'course')):
        return 'curriculum_course_info'
    return 'general_info'


def _observe_entry_metrics(question: str, requested_domain: str | None, *, use_langchain: bool) -> None:
    q_clean = (question or '').strip()
    add_metric('q_len', len(q_clean))
    add_metric('question', q_clean)
    add_metric('requested_domain', (requested_domain or '').strip().lower() or 'auto')
    add_metric('use_langchain', int(bool(use_langchain)))
    add_metric('intent_primary', _infer_primary_intent(q_clean))


def _observe_default_request_metrics(*, structured_eligible: bool) -> None:
    # Emit explicit zeros so per-request rates can be computed as rolling averages.
    add_metric('structured_path_eligible', int(bool(structured_eligible)))
    add_metric('structured_path_hit', 0)
    add_metric('structured_path_fallback_nonstructured', 0)
    add_metric('path_langchain_used', 0)
    add_metric('path_nonstructured_used', 0)
    add_metric('citation_repair_attempt', 0)
    add_metric('citation_repair_success', 0)
    add_metric('fallback_answer_used', 0)

@app.post('/rag/query', response_model=RagResponse)
def rag_endpoint(req: RagRequest):
    with request_timing('rag_query', endpoint='/rag/query', domain=req.domain):
        use_langchain = bool(_USE_LANGCHAIN and _LANGCHAIN_READY and _langchain_rag is not None)
        lc = _langchain_rag
        _observe_entry_metrics(req.question, req.domain, use_langchain=use_langchain)
        _observe_default_request_metrics(structured_eligible=False)

        if use_langchain and lc is not None:
            add_metric('path_langchain_used', 1)
            with time_block('langchain_rag'):
                result = lc.rag_query_langchain(req.question, req.domain)
        else:
            add_metric('path_nonstructured_used', 1)
            with time_block('rag_query'):
                result = rag_query_domain(req.question, req.domain) if req.domain else rag_query(req.question)

        add_metric('ctx_n', len(result.get('contexts') or []))
        add_metric('token_est', result.get('token_est', 0))
        add_metric('token_est_per_question', result.get('token_est', 0))
        add_metric('ctx_sources', ','.join(_context_source_names(result)))
        add_metric('prompt_chars', len(result.get('prompt') or ''))
        return RagResponse(**result)

@app.post('/rag/answer', response_model=RagAnswerResponse)
def rag_answer_endpoint(req: RagAnswerRequest):
    with request_timing('rag_answer', endpoint='/rag/answer', domain=req.domain):
        use_langchain = bool(_USE_LANGCHAIN and _LANGCHAIN_READY and _langchain_rag is not None)
        lc = _langchain_rag
        _observe_entry_metrics(req.question, req.domain, use_langchain=use_langchain)
        structured_eligible = bool(
            _USE_STRUCTURED_CURRICULUM
            and (((req.domain or '').strip().lower() == 'curriculum') or req.domain is None)
        )
        _observe_default_request_metrics(structured_eligible=structured_eligible)

        # Structured curriculum shortcut (deterministic, not top-k dependent)
        if structured_eligible:
            with time_block('structured_curriculum'):
                structured = structured_curriculum_answer(req.question)
            if structured:
                add_metric('structured_curriculum_hit', 1)
                add_metric('structured_path_hit', 1)
                add_metric('ctx_n', 0)
                add_metric('token_est', 0)
                add_metric('token_est_per_question', 0)
                add_metric('ctx_sources', '')
                add_metric('answer', structured)
                add_metric('answer_chars', len(structured))
                return RagAnswerResponse(
                    question=req.question,
                    prompt='(structured curriculum answer)',
                    answer=structured,
                    contexts=[],
                    token_est=0,
                )
            add_metric('structured_path_fallback_nonstructured', 1)

        try:
            if use_langchain and lc is not None:
                add_metric('path_langchain_used', 1)
                with time_block('langchain_rag'):
                    result = lc.rag_answer_langchain(req.question, req.domain)
            else:
                add_metric('path_nonstructured_used', 1)
                with time_block('rag_query'):
                    result = rag_query_domain(req.question, req.domain) if req.domain else rag_query(req.question)
        except Exception as e:
            logger.error("/rag/answer failed: %s\n%s", str(e), traceback.format_exc())
            add_metric('error', 1)
            add_metric('failure_intent', _infer_primary_intent(req.question))
            return RagAnswerResponse(
                question=req.question,
                prompt=f"(exception) {type(e).__name__}: {e}",
                answer=f"(exception) {type(e).__name__}: {e}",
                contexts=[],
                token_est=0,
            )

        add_metric('ctx_n', len(result.get('contexts') or []))
        add_metric('token_est', result.get('token_est', 0))
        add_metric('token_est_per_question', result.get('token_est', 0))
        add_metric('ctx_sources', ','.join(_context_source_names(result)))
        add_metric('prompt_chars', len(result.get('prompt') or ''))

        # Build chat style messages for models that support it
        system_msg = { 'role': 'system', 'content': 'คุณคือผู้ช่วยของภาควิชาวิศวกรรมคอมพิวเตอร์ ใช้เฉพาะข้อมูลในบริบทเท่านั้น ตอบโดยตรงและชัดเจน ห้ามให้ลิงก์/URL ภายนอก เว้นแต่ปรากฏอยู่ในบริบท หากคำถามกำกวมให้ถามกลับ 1 คำถามสั้น ๆ เพื่อขอรายละเอียดที่จำเป็น หากไม่พบคำตอบแบบชัดเจน ให้สรุปเท่าที่สรุปได้จากบริบท และระบุว่าเอกสารไม่ได้กล่าวตรง ๆ หรือไม่มีข้อความยืนยันโดยตรง' }
        user_msg = { 'role': 'user', 'content': result['prompt'] }

        # Hard guardrails: if no context, never hallucinate.
        if not (result.get('contexts') or []):
            answer = _clarify_when_no_context(req.question) or _FALLBACK
        else:
            # If we can deterministically answer from the retrieved context, do it.
            extracted = _try_extract_total_credits(result.get('prompt') or '', question=req.question)
            if extracted:
                answer = extracted
            else:
                extracted_instructor = _try_extract_course_instructors(
                    result.get('prompt') or '',
                    question=req.question,
                    contexts=result.get('contexts') or [],
                    domain=req.domain,
                )
                if extracted_instructor:
                    answer = extracted_instructor
                else:
                    extracted_leave = _try_extract_intermission_leave(result.get('prompt') or '', question=req.question)
                    if extracted_leave:
                        answer = extracted_leave
                    else:
                        extracted_w = _try_extract_withdraw_w_dates(result.get('prompt') or '', question=req.question)
                        if extracted_w:
                            answer = extracted_w
                        else:
                            # Exam-room policies can be multi-intent (e.g., มาสาย + ออกชั่วคราว).
                            # Don't return early on the first extractor hit; combine when applicable.
                            extracted_exam_late = _try_extract_exam_late_entry_rule(result.get('prompt') or '', question=req.question)
                            extracted_exam_temp = _try_extract_exam_temp_leave_rule(result.get('prompt') or '', question=req.question)
                            extracted_exam_exit = _try_extract_exam_exit_rule(result.get('prompt') or '', question=req.question)

                            if extracted_exam_late and extracted_exam_temp:
                                answer = f"{extracted_exam_late}\n{extracted_exam_temp}"
                            elif extracted_exam_late:
                                answer = extracted_exam_late
                            elif extracted_exam_exit:
                                answer = extracted_exam_exit
                            elif extracted_exam_temp:
                                answer = extracted_exam_temp
                            else:
                                guarded = _low_confidence_guardrail(req.question, result)
                                if guarded:
                                    add_metric('guardrail_triggered', 1)
                                    answer = guarded
                                else:
                                    if _USE_LANGCHAIN:
                                        # Already generated in langchain path.
                                        answer = result.get('answer') or ''
                                    else:
                                        with time_block('llm_generate'):
                                            answer = llm_engine.generate(result['prompt'], messages=[system_msg, user_msg])

                    # Optionally enforce citations when we have context.
                    if _require_citations() and (result.get('contexts') or []) and answer and not answer.strip().startswith('('):
                        had_citations_before = _has_citations(answer)
                        if not had_citations_before:
                            add_metric('citation_repair_attempt', 1)
                        with time_block('repair_citations_llm'):
                            answer = _repair_answer_with_citations(answer, result.get('prompt') or '')
                        with time_block('sanitize_citations'):
                            answer = _sanitize_answer_citations(answer, result.get('prompt') or '')
                        if (not had_citations_before) and _has_citations(answer):
                            add_metric('citation_repair_success', 1)

            # If generation is unavailable/disabled, preserve the diagnostic message.
            if not (answer or '').strip().startswith('('):
                # Clean and validate answer - keep it natural without enforcing citations
                with time_block('clean_answer'):
                    answer = _clean_answer_text(answer, strip_citations=(not _require_citations()))

                # If model uses fallback phrase, it must be the entire answer.
                if _FALLBACK in answer and answer != _FALLBACK:
                    answer = _FALLBACK

        if (answer or '').strip() == _FALLBACK:
            add_metric('fallback_answer_used', 1)
            add_metric('failure_intent', _infer_primary_intent(req.question))

        add_metric('answer', (answer or '').strip())
        add_metric('answer_chars', len((answer or '').strip()))

        return RagAnswerResponse(
            question=req.question,
            prompt=result['prompt'],
            answer=answer,
            contexts=result['contexts'],
            token_est=result['token_est'],
            meta=result.get('meta'),
        )

@app.get('/v1/models')
def list_models():
    """OpenAI API compatible models endpoint for OpenWeb-UI."""
    import time
    from .config import LLM_MODEL
    
    return {
        "object": "list",
        "data": [
            {
                "id": LLM_MODEL or "typhoon-v2.5-30b-a3b-instruct",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "cpe-chat-rag"
            }
        ]
    }

@app.post('/v1/chat/completions')
def openai_compatible_endpoint(request: dict):
    """OpenAI API compatible endpoint for OpenWeb-UI integration."""
    import time
    import uuid
    
    messages = request.get('messages', [])
    domain = request.get('domain', None)  # Custom parameter for domain selection
    
    # Extract question from chat history (keep follow-up context)
    raw_last_user = ""
    for msg in reversed(messages):
        if msg.get('role') == 'user':
            raw_last_user = _content_to_text(msg.get('content', ''))
            break

    question = _build_effective_question(messages, raw_last_user)

    if (os.getenv("RAG_TIMING", "0") or "0").strip().lower() in ("1", "true", "yes", "on"):
        try:
            logger.info("[EFFECTIVE_Q] %s", (question or '').replace("\n", " | ")[:500])
        except Exception:
            pass

    with request_timing(
        'v1_chat_completions',
        endpoint='/v1/chat/completions',
        domain=domain,
        model=request.get('model', 'typhoon-rag'),
        msg_n=len(messages or []),
    ):
        use_langchain = bool(_USE_LANGCHAIN and _LANGCHAIN_READY and _langchain_rag is not None)
        lc = _langchain_rag
        _observe_entry_metrics(question, domain, use_langchain=use_langchain)
        structured_eligible = bool(_USE_STRUCTURED_CURRICULUM)
        _observe_default_request_metrics(structured_eligible=structured_eligible)

        # Structured curriculum shortcut for OpenWebUI (works even without retrieval)
        structured = None
        if structured_eligible:
            with time_block('structured_curriculum'):
                structured = structured_curriculum_answer(question)
        if structured:
            add_metric('structured_curriculum_hit', 1)
            add_metric('structured_path_hit', 1)
            add_metric('ctx_n', 0)
            add_metric('token_est', 0)
            add_metric('token_est_per_question', 0)
            add_metric('ctx_sources', '')
            add_metric('answer', structured)
            add_metric('answer_chars', len(structured))
            import time
            import uuid
            return {
                "id": f"chatcpe-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.get('model', 'typhoon-rag'),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": structured},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
        elif structured_eligible:
            add_metric('structured_path_fallback_nonstructured', 1)

        if not question:
            add_metric('error', 1)
            add_metric('failure_intent', 'empty_question')
            return {
                "error": "No user message found in request"
            }

        # Get RAG response
        try:
            if use_langchain and lc is not None:
                add_metric('path_langchain_used', 1)
                with time_block('langchain_rag'):
                    result = lc.rag_answer_langchain(question, domain)
            else:
                add_metric('path_nonstructured_used', 1)
                with time_block('rag_query'):
                    result = rag_query_domain(question, domain) if domain else rag_query(question)
        except Exception as e:
            add_metric('error', 1)
            add_metric('failure_intent', _infer_primary_intent(question))
            return {
                "error": f"RAG query failed: {str(e)}"
            }

        add_metric('ctx_n', len(result.get('contexts') or []))
        add_metric('token_est', result.get('token_est', 0))
        add_metric('token_est_per_question', result.get('token_est', 0))
        add_metric('ctx_sources', ','.join(_context_source_names(result)))
        add_metric('prompt_chars', len(result.get('prompt') or ''))

        # Build system message for RAG context (clean answers, no forced citations)
        system_msg = { 'role': 'system', 'content': 'คุณคือผู้ช่วยของภาควิชาวิศวกรรมคอมพิวเตอร์ ใช้เฉพาะข้อมูลในบริบทเท่านั้น ตอบโดยตรงและชัดเจน ห้ามคัดลอกบริบททั้งก้อน ห้ามให้ลิงก์/URL ภายนอก เว้นแต่ปรากฏอยู่ในบริบท หากคำถามกำกวมให้ถามกลับ 1 คำถามสั้น ๆ เพื่อขอรายละเอียดที่จำเป็น หากไม่พบคำตอบแบบชัดเจน ให้สรุปเท่าที่สรุปได้จากบริบท และระบุว่าเอกสารไม่ได้กล่าวตรง ๆ หรือไม่มีข้อความยืนยันโดยตรง' }
        user_msg = { 'role': 'user', 'content': result['prompt'] }

        # Generate answer
        if not (result.get('contexts') or []):
            answer = _clarify_when_no_context(question) or _FALLBACK
        else:
            extracted = _try_extract_total_credits(result.get('prompt') or '', question=question)
            if extracted:
                answer = extracted
            else:
                extracted_instructor = _try_extract_course_instructors(
                    result.get('prompt') or '',
                    question=question,
                    contexts=result.get('contexts') or [],
                    domain=domain,
                )
                if extracted_instructor:
                    answer = extracted_instructor
                else:
                    extracted_leave = _try_extract_intermission_leave(result.get('prompt') or '', question=question)
                    if extracted_leave:
                        answer = extracted_leave
                    else:
                        extracted_w = _try_extract_withdraw_w_dates(result.get('prompt') or '', question=question)
                        if extracted_w:
                            answer = extracted_w
                        else:
                            extracted_exam_late = _try_extract_exam_late_entry_rule(result.get('prompt') or '', question=question)
                            if extracted_exam_late:
                                answer = extracted_exam_late
                            else:
                                guarded = _low_confidence_guardrail(question, result)
                                if guarded:
                                    add_metric('guardrail_triggered', 1)
                                    answer = guarded
                                else:
                                    if _USE_LANGCHAIN:
                                        answer = result.get('answer') or ''
                                    else:
                                        with time_block('llm_generate'):
                                            answer = llm_engine.generate(result['prompt'], messages=[system_msg, user_msg])

            if not (answer or '').strip().startswith('('):
                answer = _clean_answer_text(answer, strip_citations=True)

        if (answer or '').strip() == _FALLBACK:
            add_metric('fallback_answer_used', 1)
            add_metric('failure_intent', _infer_primary_intent(question))

        add_metric('answer', (answer or '').strip())
        add_metric('answer_chars', len((answer or '').strip()))

        # Return OpenAI-compatible response
        return {
            "id": f"chatcpe-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.get('model', 'typhoon-rag'),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": answer
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": result.get('token_est', 0),
                "completion_tokens": 0,
                "total_tokens": result.get('token_est', 0)
            }
        }

@app.get('/health')
def health():
    return {'status': 'ok'}


def _truthy_env(v: str) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y"}


def _public_config() -> dict:
    # Import locally to avoid import cycles at module import time.
    from app import config as cfg  # type: ignore

    # Explicit allow-list (anything secret-like is never included).
    env_allow = [
        "DATA_DIR",
        "CHROMA_DIR",
        "SQLITE_PATH",
        "CPE_INDEX_ROOT",
        "CPE_DOMAIN",
        "EMBEDDING_MODEL",
        "EMBED_BATCH",
        "EMBEDDING_DIM",
        "TOKEN_BUDGET",
        "RRF_K",
        "MAX_CONTEXTS",
        "LLM_ENABLE",
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_MAX_TOKENS",
        "LLM_TEMPERATURE",
        "OPENAI_BASE_URL",
        "OPENAI_TIMEOUT_S",
        "TYPHOON_BASE_URL",
        "TYPHOON_TIMEOUT_S",
        "NEO4J_URI",
        "NEO4J_USERNAME",
        "NEO4J_USER",
        "NEO4J_DATABASE",
        "RAG_USE_LANGCHAIN",
        "RAG_LC_MULTIQUERY",
        "RAG_LC_MULTIQUERY_N",
        "RAG_LC_MULTIQUERY_ALL",
        "RAG_LC_PARALLEL",
        "RAG_LC_PARALLEL_WORKERS",
        "RAG_LC_RERANK",
        "RAG_LC_RERANK_TOPN",
        "RAG_LC_RERANK_ALL",
        "RAG_LC_COMPRESS",
        "RAG_LC_COMPRESS_MAX_CHARS",
        "RAG_LC_COMPRESS_ALL",
        "RAG_LC_ROUTE_LLM",
        "RAG_LC_STRUCTURED",
        "RAG_LC_ENFORCE_CITATIONS",
    ]

    deny = ("KEY", "TOKEN", "SECRET", "PASSWORD")
    env_out = {}
    for k in env_allow:
        if not k:
            continue
        if any(d in k.upper() for d in deny):
            continue
        if k in os.environ:
            env_out[k] = os.environ.get(k)

    # Also include resolved (post-default) values from config.py.
    resolved = {
        "ROOT_DIR": str(getattr(cfg, "ROOT_DIR", "")),
        "DATA_DIR": str(getattr(cfg, "DATA_DIR", "")),
        "CHROMA_DIR": str(getattr(cfg, "CHROMA_DIR", "")),
        "SQLITE_PATH": str(getattr(cfg, "SQLITE_PATH", "")),
        "EMBEDDING_MODEL": getattr(cfg, "EMBEDDING_MODEL", ""),
        "EMBED_BATCH": getattr(cfg, "EMBED_BATCH", None),
        "EMBEDDING_DIM": getattr(cfg, "EMBEDDING_DIM", None),
        "TOKEN_BUDGET": getattr(cfg, "TOKEN_BUDGET", None),
        "RRF_K": getattr(cfg, "RRF_K", None),
        "MAX_CONTEXTS": getattr(cfg, "MAX_CONTEXTS", None),
        "LLM_ENABLE": getattr(cfg, "LLM_ENABLE", None),
        "LLM_PROVIDER": getattr(cfg, "LLM_PROVIDER", ""),
        "LLM_MODEL": getattr(cfg, "LLM_MODEL", ""),
        "LLM_MAX_TOKENS": getattr(cfg, "LLM_MAX_TOKENS", None),
        "LLM_TEMPERATURE": getattr(cfg, "LLM_TEMPERATURE", None),
    }

    # Redact any accidental secrets.
    def _redact_key(k: str, v):
        if any(d in (k or "").upper() for d in deny):
            return "***REDACTED***"
        return v

    env_out = {k: _redact_key(k, v) for k, v in env_out.items()}
    resolved = {k: _redact_key(k, v) for k, v in resolved.items()}

    return {
        "service": {"name": "rag-service", "version": getattr(app, "version", "")},
        "env": env_out,
        "resolved": resolved,
    }


@app.get('/debug/config')
def debug_config():
    # Disabled by default; enable explicitly for local debugging & experiment tracking.
    if not _truthy_env(os.getenv("RAG_EXPOSE_CONFIG", "0")):
        raise HTTPException(status_code=404, detail="Not found")
    return _public_config()
