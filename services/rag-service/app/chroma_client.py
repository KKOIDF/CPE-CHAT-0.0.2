import chromadb
from chromadb.config import Settings
from typing import List
from .config import CHROMA_DIR, EMBEDDING_MODEL, EMBED_BATCH

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None  # type: ignore

_client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
_collection = _client.get_or_create_collection(name='documents')

_embedder = None
if SentenceTransformer and EMBEDDING_MODEL:
    try:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    except Exception as e:
        print('Embedder load failed:', e)


def embed_texts(texts: List[str]) -> List[List[float]]:
    if _embedder:
        return _embedder.encode(texts, batch_size=EMBED_BATCH, normalize_embeddings=True).tolist()  # type: ignore
    return [[float((sum(bytearray(t.encode('utf-8'))) % 100) / 100.0)] for t in texts]


def semantic_search(query: str, top_k: int = 12) -> List[dict]:
    qvec = embed_texts([query])[0]
    res = _collection.query(query_embeddings=[qvec], n_results=top_k, include=['documents','metadatas','distances'])
    out = []
    if not res.get('ids'):
        return out
    for i in range(len(res['ids'][0])):
        out.append({
            'doc_id': res['ids'][0][i],
            'text': res['documents'][0][i],
            **(res['metadatas'][0][i] or {}),
            'distance': (res.get('distances') or [[None]])[0][i]
        })
    return out
