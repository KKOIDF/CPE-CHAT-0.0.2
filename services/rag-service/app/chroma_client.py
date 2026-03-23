import chromadb
from chromadb.config import Settings
from typing import List, Optional, Sequence
from functools import lru_cache
from pathlib import Path
from .config import CHROMA_DIR, EMBEDDING_MODEL, EMBED_BATCH, EMBEDDING_DIM, domain_paths
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


def _resolve_embed_device() -> str:
    """Resolve embedding device from env + availability.

    - EMBED_DEVICE can be: 'auto' (default), 'cuda', 'cuda:0', 'cpu'
    - If CUDA is requested but unavailable, falls back to 'cpu'.
    """
    requested = (os.getenv('EMBED_DEVICE', 'auto') or 'auto').strip().lower()
    if requested in ('', 'auto'):
        if torch is not None:
            try:
                if torch.cuda.is_available():
                    return 'cuda'
            except Exception:
                pass
        return 'cpu'

    if requested.startswith('cuda'):
        if torch is None:
            return 'cpu'
        try:
            if torch.cuda.is_available():
                return requested
        except Exception:
            pass
        return 'cpu'

    return 'cpu'


_EMBED_DEVICE = _resolve_embed_device()

# Optional mixed precision for CUDA embeddings (reduce VRAM usage)
_EMBED_MIXED_PRECISION = (os.getenv('EMBED_MIXED_PRECISION', '0') or '0').strip().lower() in (
    '1', 'true', 'yes', 'on'
)
_EMBED_DTYPE = (os.getenv('EMBED_DTYPE', 'fp16') or 'fp16').strip().lower()  # fp16|bf16|fp32


def _autocast_context(device: str):
    if not _EMBED_MIXED_PRECISION:
        return None
    if torch is None:
        return None
    if not (device or '').startswith('cuda'):
        return None
    try:
        if _EMBED_DTYPE in ('bf16', 'bfloat16'):
            dtype = torch.bfloat16  # type: ignore[attr-defined]
        elif _EMBED_DTYPE in ('fp32', 'float32'):
            dtype = torch.float32  # type: ignore[attr-defined]
        else:
            dtype = torch.float16  # type: ignore[attr-defined]
        return torch.autocast(device_type='cuda', dtype=dtype)  # type: ignore[attr-defined]
    except Exception:
        return None
if SentenceTransformer and EMBEDDING_MODEL:
    try:
        try:
            _embedder = SentenceTransformer(EMBEDDING_MODEL, device=_EMBED_DEVICE)
        except TypeError:
            _embedder = SentenceTransformer(EMBEDDING_MODEL)
        _is_bge_m3 = 'bge-m3' in EMBEDDING_MODEL.lower()
        if _is_bge_m3:
            print(f"[RAG] Loaded BGE-M3 model: {EMBEDDING_MODEL} (device={_EMBED_DEVICE})")
        else:
            print(f"[RAG] Loaded embedding model: {EMBEDDING_MODEL} (device={_EMBED_DEVICE})")
    except Exception as e:
        print('Embedder load failed:', e)


def embed_texts(texts: List[str], is_query: bool = False) -> List[List[float]]:
    """Embed texts with BGE-M3 instruction support
    
    Args:
        texts: List of texts to embed
        is_query: If True and using BGE-M3, adds query instruction prefix
    """
    def _l2_normalize(vec: List[float]) -> List[float]:
        s = 0.0
        for x in vec:
            try:
                s += float(x) * float(x)
            except Exception:
                pass
        if s <= 0.0:
            return vec
        inv = (s ** 0.5)
        if inv == 0.0:
            return vec
        inv = 1.0 / inv
        return [float(x) * inv for x in vec]

    def _resize_embedding(vec: List[float], target_dim: int) -> List[float]:
        if target_dim <= 0:
            return vec
        if not vec:
            return [0.0] * target_dim
        if len(vec) == target_dim:
            return vec
        if len(vec) > target_dim:
            return vec[:target_dim]
        meanv = sum(vec) / (len(vec) or 1)
        return vec + [float(meanv)] * (target_dim - len(vec))

    def _fallback_vec(text: str, dim: int) -> List[float]:
        b = bytearray(text.encode('utf-8', 'ignore')) or bytearray(b'0')
        out: List[float] = []
        acc = 0
        for i in range(dim):
            acc = (acc + b[i % len(b)] * (i + 1)) % 9973
            out.append((acc / 9973.0))
        return out

    if _embedder:
        # BGE-M3: Add instruction for queries only
        texts_to_encode = texts
        if _is_bge_m3 and is_query:
            query_instruction = "Represent this sentence for searching relevant passages: "
            texts_to_encode = [query_instruction + t for t in texts]
        
        try:
            ctx = _autocast_context(_EMBED_DEVICE)
            if ctx is None:
                embs = _embedder.encode(
                    texts_to_encode,
                    batch_size=EMBED_BATCH,
                    normalize_embeddings=True,
                    device=_EMBED_DEVICE,
                ).tolist()  # type: ignore
            else:
                with ctx:
                    embs = _embedder.encode(
                        texts_to_encode,
                        batch_size=EMBED_BATCH,
                        normalize_embeddings=True,
                        device=_EMBED_DEVICE,
                    ).tolist()  # type: ignore
        except Exception as e:
            # Common case: torch CPU build + EMBED_DEVICE=cuda
            if _EMBED_DEVICE == 'cuda':
                try:
                    embs = _embedder.encode(
                        texts_to_encode,
                        batch_size=EMBED_BATCH,
                        normalize_embeddings=True,
                        device='cpu',
                    ).tolist()  # type: ignore
                except Exception:
                    pass
            raise e
        return [_l2_normalize(_resize_embedding(list(e), EMBEDDING_DIM)) for e in embs]

    # Deterministic fallback (hash-based) with fixed dim
    return [_l2_normalize(_resize_embedding(_fallback_vec(t, EMBEDDING_DIM), EMBEDDING_DIM)) for t in texts]


def semantic_search(query: str, top_k: int = 12) -> List[dict]:
    return semantic_search_domain(query, top_k=top_k, domain=None)


def semantic_search_domain(
    query: str,
    top_k: int = 12,
    domain: Optional[str] = None,
    source_allowlist: Optional[Sequence[str]] = None,
) -> List[dict]:
    dom = (domain or os.getenv('CPE_DOMAIN', '')).strip().lower()
    collection = _get_collection_for_domain(dom)
    # Embed query with instruction (for BGE-M3)
    qvec = embed_texts([query], is_query=True)[0]
    allow_src: list[str] = []
    if source_allowlist:
        seen = set()
        for s in source_allowlist:
            if not s:
                continue
            try:
                name = Path(str(s)).name
            except Exception:
                name = str(s).strip()
            if not name:
                continue
            key = name.strip().lower()
            if not key or key in seen:
                continue
            allow_src.append(name.strip())
            seen.add(key)

    where = None
    if allow_src:
        # Chroma where syntax can vary by version. We'll try $in first.
        where = {"source": {"$in": allow_src}} if len(allow_src) > 1 else {"source": allow_src[0]}

    try:
        if where is not None:
            res = collection.query(
                query_embeddings=[qvec],
                n_results=top_k,
                include=['documents', 'metadatas', 'distances', 'embeddings'],
                where=where,
            )
        else:
            res = collection.query(query_embeddings=[qvec], n_results=top_k, include=['documents','metadatas','distances','embeddings'])
    except Exception as e:
        msg = str(e)
        if 'dimension' in msg.lower() or 'dim' in msg.lower():
            chroma_dir, _ = domain_paths(dom)
            print(
                f"[RAG] Chroma query failed (likely dimension mismatch). "
                f"Configured EMBEDDING_DIM={EMBEDDING_DIM}. "
                f"If your existing Chroma index was built with a different dim, delete {chroma_dir} and re-ingest. Error: {e}"
            )
            return []
        # If where-filter isn't supported in this Chroma build, fall back to unfiltered search.
        if where is not None:
            try:
                res = collection.query(query_embeddings=[qvec], n_results=top_k, include=['documents','metadatas','distances','embeddings'])
            except Exception:
                raise
        else:
            raise
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
            'distance': (res.get('distances') or [[None]])[0][i],
            'embedding': (res.get('embeddings') or [[None]])[0][i]
        })
    # In case the backend didn't apply filtering (or we fell back), enforce allowlist client-side.
    if allow_src:
        allowed_lower = {str(s).strip().lower() for s in allow_src if str(s).strip()}
        def _src_name(d: dict) -> str:
            try:
                return Path(str(d.get('source') or '')).name.strip().lower()
            except Exception:
                return ''
        out = [d for d in out if _src_name(d) in allowed_lower]
    return out

def fetch_embeddings_for_docs(docs: List[dict], domain: Optional[str] = None) -> None:
    """In-place populate d['embedding'] from Chroma for matched texts/doc_ids."""
    missing = [d for d in docs if d.get('embedding') is None]
    if not missing:
        return
        
    dom = (domain or os.getenv('CPE_DOMAIN', '')).strip().lower()
    try:
        collection = _get_collection_for_domain(dom)
    except Exception:
        return
        
    sources = list({str(d.get('source', '')).strip() for d in missing if str(d.get('source', '')).strip()})
    
    if not sources:
        return
        
    try:
        if len(sources) == 1:
            where = {"source": sources[0]}
        else:
            where = {"source": {"$in": sources}}
            
        res = collection.get(where=where, include=['embeddings', 'documents'])
        text_map = {}
        if res and res.get('documents'):
            for i in range(len(res['documents'])):
                txt = (res['documents'][i] or '').strip()
                emb = res['embeddings'][i]
                if txt:
                    text_map[txt] = emb

        for d in missing:
            txt = (d.get('text') or '').strip()
            if txt and txt in text_map:
                d['embedding'] = text_map[txt]
    except Exception:
        pass
