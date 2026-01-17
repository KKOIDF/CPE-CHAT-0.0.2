import chromadb
from chromadb.config import Settings
from typing import List, Optional
from functools import lru_cache
from pathlib import Path
from .config import CHROMA_DIR, EMBEDDING_MODEL, EMBED_BATCH, domain_paths
import os

try:
    import torch  # type: ignore
except Exception:
    torch = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None  # type: ignore

@lru_cache(maxsize=8)
def _get_collection_for_domain(domain: str) -> any:
    dom = (domain or '').strip().lower()
    chroma_dir, _ = domain_paths(dom)
    chroma_dir = Path(chroma_dir)
    chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_dir), settings=Settings(anonymized_telemetry=False))
    return client.get_or_create_collection(name='documents')

_embedder = None
_is_bge_m3 = False
_EMBED_DEVICE = os.getenv('EMBED_DEVICE', 'cpu')  # default to cpu for broad compatibility
if _EMBED_DEVICE == 'cuda' and torch is not None:
    try:
        if not torch.cuda.is_available():
            _EMBED_DEVICE = 'cpu'
    except Exception:
        _EMBED_DEVICE = 'cpu'
if SentenceTransformer and EMBEDDING_MODEL:
    try:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
        _is_bge_m3 = 'bge-m3' in EMBEDDING_MODEL.lower()
        if _is_bge_m3:
            print(f"[RAG] Loaded BGE-M3 model: {EMBEDDING_MODEL}")
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
        
        try:
            return _embedder.encode(
                texts_to_encode,
                batch_size=EMBED_BATCH,
                normalize_embeddings=True,
                device=_EMBED_DEVICE,
            ).tolist()  # type: ignore
        except Exception as e:
            # Common case: torch CPU build + EMBED_DEVICE=cuda
            if _EMBED_DEVICE == 'cuda':
                try:
                    return _embedder.encode(
                        texts_to_encode,
                        batch_size=EMBED_BATCH,
                        normalize_embeddings=True,
                        device='cpu',
                    ).tolist()  # type: ignore
                except Exception:
                    pass
            raise e
    return [[float((sum(bytearray(t.encode('utf-8'))) % 100) / 100.0)] for t in texts]


def semantic_search(query: str, top_k: int = 12) -> List[dict]:
    return semantic_search_domain(query, top_k=top_k, domain=None)


def semantic_search_domain(query: str, top_k: int = 12, domain: Optional[str] = None) -> List[dict]:
    dom = (domain or os.getenv('CPE_DOMAIN', '')).strip().lower()
    collection = _get_collection_for_domain(dom)
    # Embed query with instruction (for BGE-M3)
    qvec = embed_texts([query], is_query=True)[0]
    res = collection.query(query_embeddings=[qvec], n_results=top_k, include=['documents','metadatas','distances'])
    out = []
    if not res.get('ids'):
        return out
    for i in range(len(res['ids'][0])):
        raw_id = res['ids'][0][i]
        base_id = raw_id
        try:
            head, tail = str(raw_id).rsplit('-', 1)
            if len(head) == 32 and all(c in '0123456789abcdef' for c in head.lower()) and tail.isdigit():
                base_id = head
        except Exception:
            base_id = raw_id
        out.append({
            'doc_id': base_id,
            'chroma_id': raw_id,
            'text': res['documents'][0][i],
            **(res['metadatas'][0][i] or {}),
            'distance': (res.get('distances') or [[None]])[0][i]
        })
    return out
