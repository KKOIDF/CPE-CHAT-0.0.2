import chromadb
from chromadb.config import Settings
from typing import List
from .config import CHROMA_DIR, EMBEDDING_MODEL, EMBED_BATCH
import os

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None  # type: ignore

_client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
_collection = _client.get_or_create_collection(name='documents')

_embedder = None
_is_bge_m3 = False
_EMBED_DEVICE = os.getenv('EMBED_DEVICE', 'cuda')  # set to 'cpu' to free GPU for LLM
if SentenceTransformer and EMBEDDING_MODEL:
    try:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
        _is_bge_m3 = 'bge-m3' in EMBEDDING_MODEL.lower()
        if _is_bge_m3:
            print(f"[RAG] Loaded BGE-M3 model: {EMBEDDING_MODEL}")
        if _EMBED_DEVICE == 'cpu':
            try:
                _embedder.to('cpu')  # type: ignore
                print(f"[Embed] Moved embedding model to CPU")
            except Exception:
                pass
    except Exception as e:
        print('Embedder load failed:', e)


def embed_texts(texts: List[str], is_query: bool = False) -> List[List[float]]:
    """Embed texts with BGE-M3 instruction support
    
    Args:
        texts: List of texts to embed
        is_query: If True and using BGE-M3, adds query instruction prefix
    """
    if _embedder:
        # BGE-M3: Add instruction for queries only
        texts_to_encode = texts
        if _is_bge_m3 and is_query:
            query_instruction = "Represent this sentence for searching relevant passages: "
            texts_to_encode = [query_instruction + t for t in texts]
        
        return _embedder.encode(texts_to_encode, batch_size=EMBED_BATCH, normalize_embeddings=True, device=_EMBED_DEVICE).tolist()  # type: ignore
    return [[float((sum(bytearray(t.encode('utf-8'))) % 100) / 100.0)] for t in texts]


def semantic_search(query: str, top_k: int = 12) -> List[dict]:
    # Embed query with instruction (for BGE-M3)
    qvec = embed_texts([query], is_query=True)[0]
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
