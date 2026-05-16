import chromadb
from chromadb.config import Settings
from typing import Any, List, Optional, Sequence
from functools import lru_cache
from pathlib import Path
from .config import (
    CHROMA_DIR,
    EMBEDDING_MODEL,
    EMBED_BATCH,
    EMBEDDING_DIM,
    RAG_CHROMA_COLLECTION,
    RAG_CHROMA_DIR,
    domain_paths,
)
from .perf import time_block
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
def _get_collection_for_domain(domain: str) -> Any:
    dom = (domain or '').strip().lower()
    chroma_dir, _ = domain_paths(dom)
    chroma_dir = Path(chroma_dir)
    chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_dir), settings=Settings(anonymized_telemetry=False))
    return client.get_or_create_collection(name='documents')


@lru_cache(maxsize=2)
def _get_global_collection() -> Any:
    chroma_dir = Path(RAG_CHROMA_DIR)
    chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_dir), settings=Settings(anonymized_telemetry=False))
    return client.get_or_create_collection(name=RAG_CHROMA_COLLECTION)


def _collection_vector_dim(collection: Any, fallback: int = EMBEDDING_DIM) -> int:
    try:
        peek = collection.peek(limit=1)
        embeddings = peek.get('embeddings')
        shape = getattr(embeddings, 'shape', None)
        if shape and len(shape) >= 2 and int(shape[1]) > 0:
            return int(shape[1])
        if embeddings is not None and len(embeddings) > 0 and len(embeddings[0]) > 0:
            return int(len(embeddings[0]))
    except Exception:
        pass
    return int(fallback)

_embedder = None
_is_bge_m3 = False


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


def semantic_search_global(
    query: str,
    top_k: int = 12,
    where: Optional[dict[str, Any]] = None,
) -> List[dict]:
    collection = _get_global_collection()
    with time_block('embed_query_ms'):
        qvec = embed_texts([query], is_query=True)[0]
    qvec = _resize_embedding(qvec, _collection_vector_dim(collection))
    try:
        with time_block('chroma_query_ms'):
            res = collection.query(
                query_embeddings=[qvec],
                n_results=top_k,
                include=['documents', 'metadatas', 'distances'],
                where=where,
            ) if where else collection.query(
                query_embeddings=[qvec],
                n_results=top_k,
                include=['documents', 'metadatas', 'distances'],
            )
    except Exception as e:
        msg = str(e).lower()
        if 'dimension' in msg or 'dim' in msg:
            print(
                f"[RAG] Global Chroma query failed (likely dimension mismatch). "
                f"Configured EMBEDDING_DIM={EMBEDDING_DIM}. "
                f"If your global index was built with a different dim, delete {RAG_CHROMA_DIR} and re-ingest. Error: {e}"
            )
            return []
        raise
    out: list[dict[str, Any]] = []
    if not res.get('ids'):
        return out
    for i in range(len(res['ids'][0])):
        raw_id = res['ids'][0][i]
        meta = (res['metadatas'][0][i] or {})
        out.append({
            'stable_chunk_id': meta.get('stable_chunk_id') or raw_id,
            'doc_id': meta.get('stable_chunk_id') or raw_id,
            'chroma_id': raw_id,
            'text': res['documents'][0][i],
            **meta,
            'source': meta.get('source_name') or meta.get('source') or meta.get('file_name'),
            'path': meta.get('source_path') or meta.get('path'),
            'page_start': meta.get('page') or meta.get('page_start'),
            'page_end': meta.get('page') or meta.get('page_end'),
            'distance': (res.get('distances') or [[None]])[0][i],
            'vector_score': 1.0 - float((res.get('distances') or [[1.0]])[0][i] or 1.0),
            'embedding': None,
        })
    return out


def semantic_search_domain(
    query: str,
    top_k: int = 12,
    domain: Optional[str] = None,
    source_allowlist: Optional[Sequence[str]] = None,
) -> List[dict]:
    dom = (domain or os.getenv('CPE_DOMAIN', '')).strip().lower()
    collection = _get_collection_for_domain(dom)
    # Embed query with instruction (for BGE-M3)
    with time_block('embed_query_ms'):
        qvec = embed_texts([query], is_query=True)[0]
    qvec = _resize_embedding(qvec, _collection_vector_dim(collection))
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
            with time_block('chroma_query_ms'):
                res = collection.query(
                    query_embeddings=[qvec],
                    n_results=top_k,
                    include=['documents', 'metadatas', 'distances'],
                    where=where,
                )
        else:
            with time_block('chroma_query_ms'):
                res = collection.query(
                    query_embeddings=[qvec],
                    n_results=top_k,
                    include=['documents', 'metadatas', 'distances'],
                )
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
                with time_block('chroma_query_ms'):
                    res = collection.query(
                        query_embeddings=[qvec],
                        n_results=top_k,
                        include=['documents', 'metadatas', 'distances'],
                    )
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
            'embedding': None
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

def fetch_embeddings_for_docs(docs: List[dict], domain: Optional[str] = None) -> int:
    """In-place populate d['embedding'] from Chroma for matched texts/doc_ids.

    Matching priority:
      1. chroma_id (exact Chroma row ID) — most reliable
      2. doc_id prefix match on chroma_id
      3. text content match (fallback)

    Returns the number of actual Chroma collection.get() calls made
    (for metric logging: embedding_fetch_chroma_calls).
    """
    missing = [d for d in docs if d.get('embedding') is None]
    if not missing:
        return 0

    dom = (domain or os.getenv('CPE_DOMAIN', '')).strip().lower()
    try:
        collection = _get_collection_for_domain(dom)
    except Exception:
        return 0

    chroma_calls = 0  # count actual collection.get() calls
    # ── Strategy 1: bulk fetch by chroma_id (most accurate & fast) ─────────
    chroma_ids_to_fetch = [
        str(d['chroma_id'])
        for d in missing
        if d.get('chroma_id') is not None
    ]

    filled: set = set()   # track indices filled

    if chroma_ids_to_fetch:
        try:
            chroma_calls += 1
            res = collection.get(
                ids=chroma_ids_to_fetch,
                include=['embeddings', 'documents'],
            )
            id_emb_map: dict = {}
            if res and res.get('ids'):
                for rid, remb in zip(res['ids'], res['embeddings']):
                    if remb is not None:
                        id_emb_map[str(rid)] = remb

            for i, d in enumerate(missing):
                cid = str(d.get('chroma_id') or '')
                if cid and cid in id_emb_map:
                    d['embedding'] = id_emb_map[cid]
                    filled.add(i)
        except Exception:
            pass  # fallback to strategy 2/3

    still_missing = [d for i, d in enumerate(missing) if i not in filled]
    if not still_missing:
        return chroma_calls

    # ── Strategy 2/3: bulk fetch by source → match by doc_id or text ───────
    sources = list({
        str(d.get('source', '')).strip()
        for d in still_missing
        if str(d.get('source', '')).strip()
    })

    if not sources:
        return chroma_calls

    try:
        if len(sources) == 1:
            where: dict = {"source": sources[0]}
        else:
            where = {"source": {"$in": sources}}

        chroma_calls += 1
        res2 = collection.get(where=where, include=['embeddings', 'documents', 'metadatas'])

        doc_id_map: dict = {}   # doc_id prefix → embedding
        text_map: dict = {}     # text content → embedding

        if res2 and res2.get('documents'):
            ids2 = res2.get('ids') or []
            for i, (txt, emb) in enumerate(zip(res2['documents'], res2['embeddings'])):
                if emb is None:
                    continue
                # Build doc_id prefix key (strip trailing -<chunk_n>)
                raw_id = ids2[i] if i < len(ids2) else ''
                base_id = raw_id
                try:
                    head2, tail2 = str(raw_id).rsplit('-', 1)
                    if len(head2) == 32 and all(c in '0123456789abcdef' for c in head2.lower()) and tail2.isdigit():
                        base_id = head2
                except Exception:
                    pass
                if base_id and base_id not in doc_id_map:
                    doc_id_map[base_id] = emb
                cleaned = (txt or '').strip()
                if cleaned:
                    text_map[cleaned] = emb

        for d in still_missing:
            if d.get('embedding') is not None:
                continue
            # Try doc_id match first
            did = str(d.get('doc_id') or '').strip()
            if did and did in doc_id_map:
                d['embedding'] = doc_id_map[did]
                continue
            # Fallback: text match
            txt = (d.get('text') or '').strip()
            if txt and txt in text_map:
                d['embedding'] = text_map[txt]

    except Exception:
        pass

    return chroma_calls
