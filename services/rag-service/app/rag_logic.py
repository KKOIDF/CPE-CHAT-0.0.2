from typing import List, Dict, Tuple
import math

from .sqlite_client import keyword_search, fetch_docs
from .chroma_client import semantic_search, embed_texts
from .config import TOKEN_BUDGET, RRF_K, MAX_CONTEXTS

# Simple token counter heuristic (~4 chars/token Thai)
CHAR_PER_TOKEN = 4.0

def est_tokens(text: str) -> int:
    return max(1, int(math.ceil(len(text) / CHAR_PER_TOKEN)))


def hybrid_retrieve(question: str, k_vec: int = 20, k_kw: int = 30) -> List[Dict]:
    sem = semantic_search(question, top_k=k_vec)
    kw_ids = keyword_search(question, limit=k_kw)
    kw_docs = fetch_docs(kw_ids)
    bank: Dict[str, Dict] = {}
    ranks: Dict[str, float] = {}

    # vector ranks
    for r, d in enumerate(sem, 1):
        doc_id = d.get('doc_id') or d.get('source') or f'vec_{r}'
        bank[doc_id] = d
        ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + r)
    # keyword ranks
    for r, d in enumerate(kw_docs, 1):
        doc_id = d.get('doc_id') or f'kw_{r}'
        bank.setdefault(doc_id, d)
        ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + r)

    merged = [{**bank[k], 'score_rrf': v, 'doc_id': k} for k, v in ranks.items()]
    merged.sort(key=lambda x: x['score_rrf'], reverse=True)
    return merged[:MAX_CONTEXTS]


def pack_context(chunks: List[Dict], budget_tokens: int = TOKEN_BUDGET) -> Tuple[str, Dict[int, str]]:
    packed_blocks = []
    used = 0
    cites = {}
    for i, c in enumerate(chunks, 1):
        cite = f"{c.get('source') or c.get('path')}:{c.get('page_start')}"
        block = f"[{i}] {c.get('text','').strip()}"
        t = est_tokens(block)
        if used + t > budget_tokens:
            break
        packed_blocks.append(block)
        used += t
        cites[i] = cite
    return '\n\n'.join(packed_blocks), cites


def build_prompt(question: str, ctx: str, cites: Dict[int, str]) -> str:
    cite_list = '\n'.join([f"[{i}] {c}" for i, c in cites.items()])
    return (
        "คุณคือผู้ช่วยของภาควิชาวิศวกรรมคอมพิวเตอร์ ใช้เฉพาะข้อมูลอ้างอิงในการตอบ ถ้าไม่มีข้อมูลให้ตอบว่าไม่พบ.\n\n"
        f"คำถาม:\n{question}\n\nบริบท:\n{ctx}\n\nอ้างอิง:\n{cite_list}\n"
    )


def rag_query(question: str) -> Dict:
    retrieved = hybrid_retrieve(question)
    ctx, cites = pack_context(retrieved)
    prompt = build_prompt(question, ctx, cites)
    return {
        'prompt': prompt,
        'contexts': [
            {
                'doc_id': r.get('doc_id'),
                'source': r.get('source'),
                'path': r.get('path'),
                'page_start': r.get('page_start'),
                'page_end': r.get('page_end'),
                'score_rrf': r.get('score_rrf'),
            } for r in retrieved
        ],
        'token_est': est_tokens(ctx)
    }
