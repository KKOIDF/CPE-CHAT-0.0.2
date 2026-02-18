from pathlib import Path
from typing import List, Dict, Any
import json
import os

import chromadb
from chromadb.config import Settings

from .config import CHROMA_DIR, EMBEDDING_MODEL, EMBED_BATCH, EMBEDDING_API_BASE, EMBEDDING_API_KEY, EMBEDDING_DIM
from .utils import clean_and_spell_correct_thai

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None  # type: ignore

_client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
_collection = _client.get_or_create_collection(name="documents")

_embedder = None
_is_bge_m3 = False
if SentenceTransformer and EMBEDDING_MODEL and not EMBEDDING_API_BASE:
    try:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
        _is_bge_m3 = 'bge-m3' in EMBEDDING_MODEL.lower()
        if _is_bge_m3:
            print(f"Loaded BGE-M3 model: {EMBEDDING_MODEL}")
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


def _embed_texts(texts: List[str], is_query: bool = False) -> List[List[float]]:
    """Embed texts with BGE-M3 instruction support
    
    Args:
        texts: List of texts to embed
        is_query: If True and using BGE-M3, adds query instruction prefix
    """
    # Local model
    if _embedder:
        try:
            # BGE-M3: Add instruction for queries only
            texts_to_encode = texts
            if _is_bge_m3 and is_query:
                query_instruction = "Represent this sentence for searching relevant passages: "
                texts_to_encode = [query_instruction + t for t in texts]
            
            embs = _embedder.encode(texts_to_encode, batch_size=EMBED_BATCH, normalize_embeddings=True).tolist()  # type: ignore
        except Exception as e:
            print("Local embedding encode failed, falling back to hashing:", e)
            embs = []
        else:
            # ensure non-empty and consistent
            dim = len(embs[0]) if embs and len(embs[0]) > 0 else 0
            if dim == 0:
                embs = []
        if embs:
            resized = [_l2_normalize(_resize_embedding(list(e), EMBEDDING_DIM)) for e in embs]
            return resized
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
                out.append(_l2_normalize(_resize_embedding([float(x) for x in vec], EMBEDDING_DIM)))
            else:
                if dim_detected is None:
                    dim_detected = EMBEDDING_DIM
                out.append(_l2_normalize(_resize_embedding(_fallback_vec(t, dim_detected), EMBEDDING_DIM)))
        return out
    # Final deterministic fallback (hash-based) with fixed dim
    return [_l2_normalize(_resize_embedding(_fallback_vec(t, EMBEDDING_DIM), EMBEDDING_DIM)) for t in texts]


def upsert_chunks(chunks: List[Dict[str, Any]]):
    if not chunks:
        print("No chunks to embed; skipping upsert.")
        return
    texts = [c.get('text','') for c in chunks]
    try:
        cleaned_texts = [clean_and_spell_correct_thai(t) for t in texts]
    except Exception:
        cleaned_texts = texts
    # Documents: no query instruction needed
    embeddings = _embed_texts(cleaned_texts, is_query=False)
    if not embeddings or any(len(e) == 0 for e in embeddings):
        print("Embeddings empty after fallback; skipping upsert to avoid error.")
        return
    # Enforce configured embedding dimension for storage.
    dim = EMBEDDING_DIM
    fixed = [_l2_normalize(_resize_embedding(list(e), dim)) for e in embeddings]
    ids: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    documents: List[str] = []
    for i, c in enumerate(chunks):
        cid = f"{c.get('doc_id') or c.get('source','')}-{i}"
        ids.append(cid)
        meta: Dict[str, Any] = {
            'source': c.get('source'),
            'path': c.get('path'),
            'page_start': c.get('page_start'),
            'page_end': c.get('page_end'),
            'file_type': c.get('file_type'),
            'status': c.get('status'),
        }
        # Pass-through optional metadata (curriculum course-centric)
        for k in [
            'doc_type', 'program', 'course_code', 'course_th', 'course_en',
            'category', 'section', 'section_heading', 'source_file', 'year',
            'chunk_uid', 'source_priority',
            # Curriculum multi-granularity
            'program_year', 'section_path', 'source_scope', 'lang', 'priority',
            'chunk_key', 'canonical_key',
            'course_code_norm', 'course_code_raw', 'credits_breakdown',
            'credits_total', 'credits',
            'learning_outcomes',
            'plo_id', 'sub_plo_id',
            'plos_covered',
            'term_label', 'plan_label', 'term_courses',
            'old_code', 'new_code',
            'person_id', 'person_name_th', 'person_name_en',
            'academic_rank_th', 'academic_rank_en',
            'degrees',
            'teaching_current',
            'teaching_in_program',
            'publications_5y', 'publications_years',
            # Announcements / shared
            'doc_title', 'topic', 'year_be', 'effective_from', 'audience',
            'clause_id', 'supersedes', 'amends', 'delta_type', 'targets',
            # Regulations
            'effective_to', 'section_path', 'term', 'semester_scope',
            'table_keys', 'target_clause',
            'person_name', 'email', 'phone',
            'form_name_th', 'purpose', 'url',
        ]:
            v = c.get(k)
            if v is None:
                continue
            # Keep metadata JSON-serializable
            if isinstance(v, (str, int, float, bool)):
                meta[k] = v
            else:
                try:
                    meta[k] = json.dumps(v, ensure_ascii=False)
                except Exception:
                    meta[k] = str(v)
        metadatas.append(meta)
        # Store cleaned text in vector store for better retrieval, keep metadata unchanged
        documents.append(cleaned_texts[i] if i < len(cleaned_texts) else c.get('text',''))
    try:
        _collection.upsert(ids=ids, embeddings=fixed, documents=documents, metadatas=metadatas)  # type: ignore[arg-type]
    except Exception as e:
        msg = str(e)
        if 'dimension' in msg.lower() or 'dim' in msg.lower():
            print(
                f"Chroma upsert failed (likely dimension mismatch). "
                f"Configured EMBEDDING_DIM={EMBEDDING_DIM}. "
                f"If your existing Chroma index was built with a different dim, delete the domain chroma dir under {CHROMA_DIR} and re-ingest. Error: {e}"
            )
            return
        raise
    print(f"Upserted {len(ids)} chunks into Chroma (dim={dim}).")


def semantic_search(query: str, n_results: int = 10) -> List[Dict[str, Any]]:
    # Clean query and embed with query instruction (for BGE-M3)
    try:
        cleaned_query = clean_and_spell_correct_thai(query)
    except Exception:
        cleaned_query = query
    
    query_embedding = _embed_texts([cleaned_query], is_query=True)[0]
    try:
        res = _collection.query(query_embeddings=[query_embedding], n_results=n_results)
    except Exception as e:
        msg = str(e)
        if 'dimension' in msg.lower() or 'dim' in msg.lower():
            print(
                f"Chroma query failed (likely dimension mismatch). "
                f"Configured EMBEDDING_DIM={EMBEDDING_DIM}. "
                f"If your existing Chroma index was built with a different dim, delete {CHROMA_DIR} and re-ingest. Error: {e}"
            )
            return []
        raise
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
