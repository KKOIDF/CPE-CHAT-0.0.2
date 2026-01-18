from fastapi import FastAPI
from pydantic import BaseModel
import re
from .rag_logic import rag_query, rag_query_domain
from .llm import llm_engine

app = FastAPI(title="RAG Service", version="0.1.0")

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


_FALLBACK = 'ไม่พบข้อมูลในเอกสาร'
_CITE_RE = re.compile(r"\[[^\]]+?/\d+\]")
_BRACKET_RE = re.compile(r"\[[^\]]*\]")


def _extract_ctx_blocks(prompt: str) -> list[tuple[str, str]]:
    """Return list of (cite, text) blocks from the packed context section in the prompt."""
    p = prompt or ''
    start_marker = 'บริบท'
    end_marker = 'รายชื่ออ้างอิงที่อนุญาต'
    if start_marker not in p or end_marker not in p:
        return []
    mid = p.split(start_marker, 1)[1]
    if end_marker in mid:
        mid = mid.split(end_marker, 1)[0]
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

    return f"- หลักสูตรกำหนดหน่วยกิตรวม {best_n} หน่วยกิต [{cite}]"


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
    result = rag_query_domain(req.question, req.domain) if req.domain else rag_query(req.question)
    # Build chat style messages for models that support it
    system_msg = { 'role': 'system', 'content': 'คุณคือผู้ช่วยของภาควิชาวิศวกรรมคอมพิวเตอร์ ใช้เฉพาะข้อมูลในบริบทเท่านั้น ตอบเป็น bullet และทุก bullet ต้องลงท้ายด้วยอ้างอิงรูปแบบ [src/page] (เช่น [foo.pdf/3]) หากข้อมูลในบริบทไม่พอให้ตอบว่า ไม่พบข้อมูลในเอกสาร' }
    user_msg = { 'role': 'user', 'content': result['prompt'] }

    # Hard guardrails: if no context, never hallucinate.
    if not (result.get('contexts') or []):
        answer = _FALLBACK
    else:
        # If we can deterministically answer from the retrieved context, do it.
        extracted = _try_extract_total_credits(result.get('prompt') or '')
        if extracted:
            answer = extracted
        else:
            answer = llm_engine.generate(result['prompt'], messages=[system_msg, user_msg])
        # If generation is unavailable/disabled, preserve the diagnostic message.
        if not (answer or '').strip().startswith('('):
            answer = _repair_citations((answer or '').strip(), result.get('prompt') or '')

            # If model uses fallback phrase, it must be the entire answer.
            if _FALLBACK in answer and answer != _FALLBACK:
                answer = _FALLBACK
            else:
                allowed = _extract_allowed_citations(result.get('prompt') or '')
                cited = set(re.findall(r"\[([^\]]+?/\d+)\]", answer))

                # 1) Must contain at least one valid [src/page] citation.
                if not _CITE_RE.search(answer or ''):
                    answer = _FALLBACK
                # 2) Forbid any bracketed blocks that are not [src/page] citations.
                elif any(not _CITE_RE.fullmatch(b) for b in _BRACKET_RE.findall(answer or '')):
                    answer = _FALLBACK
                # 3) All citations must be in allowed list.
                elif allowed and cited and not cited.issubset(allowed):
                    answer = _FALLBACK
                else:
                    # 4) Every bullet must have a citation.
                    bullets = _split_bullets(answer)
                    if any(not _CITE_RE.search(b or '') for b in bullets):
                        answer = _FALLBACK
    return RagAnswerResponse(
        question=req.question,
        prompt=result['prompt'],
        answer=answer,
        contexts=result['contexts'],
        token_est=result['token_est']
    )

@app.get('/health')
async def health():
    return {'status': 'ok'}
