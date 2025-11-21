from fastapi import FastAPI
from pydantic import BaseModel
from .rag_logic import rag_query

app = FastAPI(title="RAG Service", version="0.1.0")

class RagRequest(BaseModel):
    question: str

class RagResponse(BaseModel):
    prompt: str
    contexts: list
    token_est: int

@app.post('/rag/query', response_model=RagResponse)
async def rag_endpoint(req: RagRequest):
    result = rag_query(req.question)
    return RagResponse(**result)

@app.get('/health')
async def health():
    return {'status': 'ok'}
