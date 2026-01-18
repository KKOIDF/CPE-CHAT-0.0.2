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
        answer = llm_engine.generate(result['prompt'], messages=[system_msg, user_msg])
        # If generation is unavailable/disabled, preserve the diagnostic message.
        if not (answer or '').strip().startswith('('):
            answer = (answer or '').strip()

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
