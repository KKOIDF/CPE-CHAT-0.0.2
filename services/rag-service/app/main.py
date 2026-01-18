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
        answer = 'ไม่พบข้อมูลในเอกสาร'
    else:
        answer = llm_engine.generate(result['prompt'], messages=[system_msg, user_msg])
        # If generation is unavailable/disabled, preserve the diagnostic message.
        if not (answer or '').strip().startswith('('):
            # Require at least one [src/page] citation in the answer.
            if not re.search(r"\[[^\]]+?/\d+\]", answer or ''):
                answer = 'ไม่พบข้อมูลในเอกสาร'
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
