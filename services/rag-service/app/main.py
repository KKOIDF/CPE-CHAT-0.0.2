from fastapi import FastAPI
from pydantic import BaseModel
from .rag_logic import rag_query
from .llm import llm_engine

app = FastAPI(title="RAG Service", version="0.1.0")

class RagRequest(BaseModel):
    question: str

class RagResponse(BaseModel):
    prompt: str
    contexts: list
    token_est: int

class RagAnswerRequest(BaseModel):
    question: str

class RagAnswerResponse(BaseModel):
    question: str
    prompt: str
    answer: str
    contexts: list
    token_est: int

@app.post('/rag/query', response_model=RagResponse)
async def rag_endpoint(req: RagRequest):
    result = rag_query(req.question)
    return RagResponse(**result)

@app.post('/rag/answer', response_model=RagAnswerResponse)
async def rag_answer_endpoint(req: RagAnswerRequest):
    result = rag_query(req.question)
    # Use combined prompt for generation
    answer = llm_engine.generate(result['prompt'])
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
