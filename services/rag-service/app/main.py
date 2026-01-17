from fastapi import FastAPI
from pydantic import BaseModel
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
    system_msg = { 'role': 'system', 'content': 'คุณคือผู้ช่วยของภาควิชาวิศวกรรมคอมพิวเตอร์ ใช้เฉพาะข้อมูลอ้างอิงในการตอบ ตอบเป็น bullet พร้อม [n] citation หากไม่มีให้ตอบว่า ไม่พบข้อมูลในเอกสารที่เกี่ยวข้อง' }
    user_msg = { 'role': 'user', 'content': result['prompt'] }
    answer = llm_engine.generate(result['prompt'], messages=[system_msg, user_msg])
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
