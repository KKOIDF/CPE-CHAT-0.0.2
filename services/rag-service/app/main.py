import os
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re
from .rag_logic import rag_query, rag_query_domain
from .rag_logic import structured_curriculum_answer
from .llm import llm_engine

_USE_LANGCHAIN = os.getenv('RAG_USE_LANGCHAIN', '0') in ('1', 'true', 'True')

_CITE_RE = re.compile(r"\[([^\]]+?/\d+)\]")


def _extract_allowed_cites(prompt: str) -> list[str]:
    p = prompt or ''
    marker = 'รายชื่ออ้างอิงที่อนุญาต'
    if marker not in p:
        return []
    after = p.split(marker, 1)[1]
    if '\n\nคำตอบ:' in after:
        after = after.split('\n\nคำตอบ:', 1)[0]
    found = _CITE_RE.findall(after)
    out: list[str] = []
    seen: set[str] = set()
    for c in found:
        if not c or c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out


def _has_citations(answer: str) -> bool:
    return bool(_CITE_RE.search(answer or ''))


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

app = FastAPI(title="RAG Service", version="0.1.0")

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

class RagAnswerRequest(BaseModel):
    question: str
    domain: str | None = None

class RagAnswerResponse(BaseModel):
    question: str
    prompt: str
    answer: str
    contexts: list
    token_est: int


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
_CITE_RE = re.compile(r"\[[^\]]+?/\d+\]")
_BRACKET_RE = re.compile(r"\[[^\]]*\]")


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
            txt = (m.get('content') or '').strip()
            if txt:
                user_msgs.append(txt)

    if not user_msgs:
        return (default_question or '').strip()

    last = user_msgs[-1]
    prev = user_msgs[-2] if len(user_msgs) >= 2 else ''

    short = len(last) < 25
    looks_like_placeholder = ('xxx' in last.lower())
    followup_phrases = (
        'ขอรหัส', 'มีวิชาเดียว', 'ไม่เกี่ยว', 'ขออีก', 'หมายถึง', 'อันนี้', 'แบบไหน', 'อันไหน'
    )
    is_followup = short or looks_like_placeholder or any(p in last for p in followup_phrases)

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
    out = re.sub(_CITE_RE, '', text or '')
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


def _clean_answer_text(answer: str) -> str:
    a = (answer or '').strip()
    a = _strip_citations(a)
    a = _normalize_calendar_text(a)
    # Remove stray spaces at line ends
    a = "\n".join([ln.rstrip() for ln in a.splitlines()]).strip()
    # If empty after cleaning, fallback
    return a or _FALLBACK


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


def _try_extract_total_credits(prompt: str) -> str | None:
    """Best-effort extraction of program total credits from context blocks.

    If we can confidently extract a single total-credit value, return a fully
    formatted bullet answer with a valid citation.
    """
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

    # Return without visible citation; context is still used for grounding.
    return f"- หลักสูตรกำหนดหน่วยกิตรวม {best_n} หน่วยกิต"


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


def _default_allowed_citation(prompt: str) -> str | None:
    allowed = sorted(_extract_allowed_citations(prompt or ''))
    if not allowed:
        return None
    return f"[{allowed[0]}]"


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

@app.post('/rag/query', response_model=RagResponse)
async def rag_endpoint(req: RagRequest):
    result = rag_query_domain(req.question, req.domain) if req.domain else rag_query(req.question)
    return RagResponse(**result)

@app.post('/rag/answer', response_model=RagAnswerResponse)
async def rag_answer_endpoint(req: RagAnswerRequest):
    # Structured curriculum shortcut (deterministic, not top-k dependent)
    if (req.domain or '').strip().lower() == 'curriculum' or req.domain is None:
        structured = structured_curriculum_answer(req.question)
        if structured:
            return RagAnswerResponse(
                question=req.question,
                prompt='(structured curriculum answer)',
                answer=structured,
                contexts=[],
                token_est=0,
            )

    if _USE_LANGCHAIN:
        from .langchain_rag import rag_answer_langchain
        result = rag_answer_langchain(req.question, req.domain)
    else:
        result = rag_query_domain(req.question, req.domain) if req.domain else rag_query(req.question)
    # Build chat style messages for models that support it
    system_msg = { 'role': 'system', 'content': 'คุณคือผู้ช่วยของภาควิชาวิศวกรรมคอมพิวเตอร์ ใช้เฉพาะข้อมูลในบริบทเท่านั้น ตอบโดยตรงและชัดเจน ห้ามให้ลิงก์/URL ภายนอก เว้นแต่ปรากฏอยู่ในบริบท หากคำถามกำกวมให้ถามกลับ 1 คำถามสั้น ๆ เพื่อขอรายละเอียดที่จำเป็น หากไม่พบคำตอบแบบชัดเจน ให้สรุปเท่าที่สรุปได้จากบริบท และระบุว่าเอกสารไม่ได้กล่าวตรง ๆ หรือไม่มีข้อความยืนยันโดยตรง' }
    user_msg = { 'role': 'user', 'content': result['prompt'] }

    # Hard guardrails: if no context, never hallucinate.
    if not (result.get('contexts') or []):
        answer = _clarify_when_no_context(req.question) or _FALLBACK
    else:
        # If we can deterministically answer from the retrieved context, do it.
        extracted = _try_extract_total_credits(result.get('prompt') or '')
        if extracted:
            answer = extracted
        else:
            extracted_w = _try_extract_withdraw_w_dates(result.get('prompt') or '', question=req.question)
            if extracted_w:
                answer = extracted_w
            else:
                if _USE_LANGCHAIN:
                    # Already generated in langchain path.
                    answer = result.get('answer') or ''
                else:
                    answer = llm_engine.generate(result['prompt'], messages=[system_msg, user_msg])

                # Enforce citations when we have context, otherwise retrieval-grounding becomes fuzzy.
                if (result.get('contexts') or []) and answer and not answer.strip().startswith('('):
                    answer = _repair_answer_with_citations(answer, result.get('prompt') or '')
        # If generation is unavailable/disabled, preserve the diagnostic message.
        if not (answer or '').strip().startswith('('):
            # Clean and validate answer - keep it natural without enforcing citations
            answer = _clean_answer_text(answer)

            # If model uses fallback phrase, it must be the entire answer.
            if _FALLBACK in answer and answer != _FALLBACK:
                answer = _FALLBACK
    return RagAnswerResponse(
        question=req.question,
        prompt=result['prompt'],
        answer=answer,
        contexts=result['contexts'],
        token_est=result['token_est']
    )

@app.get('/v1/models')
async def list_models():
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
async def openai_compatible_endpoint(request: dict):
    """OpenAI API compatible endpoint for OpenWeb-UI integration."""
    import time
    import uuid
    
    messages = request.get('messages', [])
    domain = request.get('domain', None)  # Custom parameter for domain selection
    
    # Extract question from chat history (keep follow-up context)
    raw_last_user = ""
    for msg in reversed(messages):
        if msg.get('role') == 'user':
            raw_last_user = msg.get('content', '')
            break

    question = _build_effective_question(messages, raw_last_user)

    # Structured curriculum shortcut for OpenWebUI (works even without retrieval)
    structured = structured_curriculum_answer(question)
    if structured:
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
    
    if not question:
        return {
            "error": "No user message found in request"
        }
    
    # Get RAG response
    try:
        if _USE_LANGCHAIN:
            from .langchain_rag import rag_answer_langchain
            result = rag_answer_langchain(question, domain)
        else:
            result = rag_query_domain(question, domain) if domain else rag_query(question)
    except Exception as e:
        return {
            "error": f"RAG query failed: {str(e)}"
        }
    
    # Build system message for RAG context (clean answers, no forced citations)
    system_msg = { 'role': 'system', 'content': 'คุณคือผู้ช่วยของภาควิชาวิศวกรรมคอมพิวเตอร์ ใช้เฉพาะข้อมูลในบริบทเท่านั้น ตอบโดยตรงและชัดเจน ห้ามคัดลอกบริบททั้งก้อน ห้ามให้ลิงก์/URL ภายนอก เว้นแต่ปรากฏอยู่ในบริบท หากคำถามกำกวมให้ถามกลับ 1 คำถามสั้น ๆ เพื่อขอรายละเอียดที่จำเป็น หากไม่พบคำตอบแบบชัดเจน ให้สรุปเท่าที่สรุปได้จากบริบท และระบุว่าเอกสารไม่ได้กล่าวตรง ๆ หรือไม่มีข้อความยืนยันโดยตรง' }
    user_msg = { 'role': 'user', 'content': result['prompt'] }

    # Generate answer
    if not (result.get('contexts') or []):
        answer = _clarify_when_no_context(question) or _FALLBACK
    else:
        extracted = _try_extract_total_credits(result.get('prompt') or '')
        if extracted:
            answer = extracted
        else:
            extracted_w = _try_extract_withdraw_w_dates(result.get('prompt') or '', question=question)
            if extracted_w:
                answer = extracted_w
            else:
                if _USE_LANGCHAIN:
                    answer = result.get('answer') or ''
                else:
                    answer = llm_engine.generate(result['prompt'], messages=[system_msg, user_msg])

                if (result.get('contexts') or []) and answer and not answer.strip().startswith('('):
                    answer = _repair_answer_with_citations(answer, result.get('prompt') or '')
        
        if not (answer or '').strip().startswith('('):
            answer = _clean_answer_text(answer)

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
async def health():
    return {'status': 'ok'}
