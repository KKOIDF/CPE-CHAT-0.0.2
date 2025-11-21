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


def _embed_texts(texts: List[str]) -> List[List[float]]:
    if _embedder:
        return _embedder.encode(texts, batch_size=EMBED_BATCH, normalize_embeddings=True).tolist()  # type: ignore
    if EMBEDDING_API_BASE and EMBEDDING_API_KEY:
        import requests
        out = []
        for t in texts:
            resp = requests.post(
                f"{EMBEDDING_API_BASE.rstrip('/')}/embeddings",
                headers={"Authorization": f"Bearer {EMBEDDING_API_KEY}"},
                json={"input": t, "model": EMBEDDING_MODEL}, timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            vec = (data.get('data') or [{}])[0].get('embedding')
            out.append(vec or [])
        return out
    # last resort dummy embedding
    return [[float((sum(bytearray(t.encode('utf-8'))) % 100) / 100.0)] for t in texts]


def upsert_chunks(chunks: List[Dict[str, Any]]):
    texts = [c['text'] for c in chunks]
    embeddings = _embed_texts(texts)
    ids = []
    metadatas = []
    documents = []
    for i, c in enumerate(chunks):
        cid = f"{c.get('source','')}-{c.get('page_start','')}-{i}"
        ids.append(cid)
        metadatas.append({
            'source': c.get('source'),
            'path': c.get('path'),
            'page_start': c.get('page_start'),
            'page_end': c.get('page_end'),
            'owner': c.get('owner'),
            'sensitivity': c.get('sensitivity'),
        })
        documents.append(c['text'])
    _collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)


def semantic_search(query: str, n_results: int = 10) -> List[Dict[str, Any]]:
    res = _collection.query(query_texts=[query], n_results=n_results)
    out = []
    for i in range(len(res.get('ids', [[]])[0])):
        out.append({
            'id': res['ids'][0][i],
            'text': res['documents'][0][i],
            'metadata': res['metadatas'][0][i],
            'distance': res['distances'][0][i] if 'distances' in res else None,
        })
    return out
