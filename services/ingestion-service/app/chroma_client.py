from pathlib import Path
from typing import List, Dict, Any
import os

import chromadb
from chromadb.config import Settings

from .config import CHROMA_DIR, EMBEDDING_MODEL, EMBED_BATCH, EMBEDDING_API_BASE, EMBEDDING_API_KEY

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None  # type: ignore

_client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
_collection = _client.get_or_create_collection(name="documents")

_embedder = None
if SentenceTransformer and EMBEDDING_MODEL and not EMBEDDING_API_BASE:
    try:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    except Exception as e:
        print("Embedding model load failed, will fallback to API if configured:", e)


def _fallback_vec(text: str, dim: int) -> List[float]:
    b = bytearray(text.encode('utf-8', 'ignore')) or bytearray(b'0')
    # simple rolling hash -> deterministic pseudo vector
    out = []
    acc = 0
    for i in range(dim):
        acc = (acc + b[i % len(b)] * (i + 1)) % 9973
        out.append((acc / 9973.0))
    return out


def _embed_texts(texts: List[str]) -> List[List[float]]:
    # Local model
    if _embedder:
        try:
            embs = _embedder.encode(texts, batch_size=EMBED_BATCH, normalize_embeddings=True).tolist()  # type: ignore
        except Exception as e:
            print("Local embedding encode failed, falling back to hashing:", e)
            embs = []
        else:
            # ensure non-empty and consistent
            dim = len(embs[0]) if embs and len(embs[0]) > 0 else 0
            if dim == 0:
                embs = []
        if embs:
            return embs
    # Remote API
    if EMBEDDING_API_BASE and EMBEDDING_API_KEY:
        import requests
        out: List[List[float]] = []
        dim_detected = None
        for t in texts:
            try:
                resp = requests.post(
                    f"{EMBEDDING_API_BASE.rstrip('/')}/embeddings",
                    headers={"Authorization": f"Bearer {EMBEDDING_API_KEY}"},
                    json={"input": t, "model": EMBEDDING_MODEL}, timeout=60
                )
                resp.raise_for_status()
                data = resp.json()
                vec = (data.get('data') or [{}])[0].get('embedding')
            except Exception as e:
                print("Embedding API error, using fallback vector:", e)
                vec = None
            if vec and isinstance(vec, list) and len(vec) > 0:
                if dim_detected is None:
                    dim_detected = len(vec)
                out.append(vec)
            else:
                if dim_detected is None:
                    dim_detected = 32
                out.append(_fallback_vec(t, dim_detected))
        return out
    # Final deterministic fallback (hash-based) with fixed dim
    return [_fallback_vec(t, 32) for t in texts]


def upsert_chunks(chunks: List[Dict[str, Any]]):
    if not chunks:
        print("No chunks to embed; skipping upsert.")
        return
    texts = [c.get('text','') for c in chunks]
    embeddings = _embed_texts(texts)
    if not embeddings or any(len(e) == 0 for e in embeddings):
        print("Embeddings empty after fallback; skipping upsert to avoid error.")
        return
    # enforce consistent dimension
    dim = len(embeddings[0])
    fixed = []
    for e in embeddings:
        if len(e) != dim:
            # resize by truncating or padding with mean value
            if len(e) > dim:
                e = e[:dim]
            else:
                meanv = sum(e) / (len(e) or 1)
                e = e + [meanv] * (dim - len(e))
        fixed.append(e)
    ids: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    documents: List[str] = []
    for i, c in enumerate(chunks):
        cid = f"{c.get('doc_id') or c.get('source','')}-{i}"
        ids.append(cid)
        metadatas.append({
            'source': c.get('source'),
            'path': c.get('path'),
            'page_start': c.get('page_start'),
            'page_end': c.get('page_end'),
            'file_type': c.get('file_type'),
            'status': c.get('status'),
        })
        documents.append(c.get('text',''))
    _collection.upsert(ids=ids, embeddings=fixed, documents=documents, metadatas=metadatas)  # type: ignore[arg-type]
    print(f"Upserted {len(ids)} chunks into Chroma (dim={dim}).")


def semantic_search(query: str, n_results: int = 10) -> List[Dict[str, Any]]:
    res = _collection.query(query_texts=[query], n_results=n_results)
    ids_list = res.get('ids') or [[]]
    docs_list = res.get('documents') or [[]]
    meta_list = res.get('metadatas') or [[]]
    dist_list = res.get('distances') or [[]]
    results: List[Dict[str, Any]] = []
    length = min(len(ids_list[0]), len(docs_list[0]), len(meta_list[0]))
    for i in range(length):
        dist = dist_list[0][i] if dist_list and dist_list[0] and i < len(dist_list[0]) else None
        results.append({
            'id': ids_list[0][i],
            'text': docs_list[0][i],
            'metadata': meta_list[0][i],
            'distance': dist,
        })
    return results
