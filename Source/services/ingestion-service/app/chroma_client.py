from pathlib import Path
from typing import List, Dict, Any, Iterable
import chromadb
from chromadb.utils import embedding_functions

CHROMA_DIR = Path(__file__).resolve().parent.parent / 'data' / 'chroma'
COLLECTION_NAME = 'ingestion_chunks'

_client = None
_collection = None


def get_client():
    global _client
    if _client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def get_collection():
    global _collection
    if _collection is None:
        client = get_client()
        try:
            _collection = client.get_collection(COLLECTION_NAME)
        except Exception:
            _collection = client.create_collection(COLLECTION_NAME, metadata={"description": "RAG ingestion chunks"})
    return _collection

# Placeholder embedding function (Typhoon/LLaMA embeddings should be integrated later)
# For now we can use a simple SentenceTransformer or default embedding if available
try:
    default_ef = embedding_functions.DefaultEmbeddingFunction()
except Exception:
    default_ef = None


def add_chunks(document_id: int, chunks: Iterable[str]) -> List[str]:
    collection = get_collection()
    ids = []
    texts = []
    metadatas = []
    for idx, ch in enumerate(chunks):
        chunk_id = f"doc{document_id}_chunk{idx}"
        ids.append(chunk_id)
        texts.append(ch)
        metadatas.append({"document_id": document_id, "chunk_index": idx})
    if default_ef:
        collection.add(ids=ids, documents=texts, metadatas=metadatas)
    else:
        # Fallback without embeddings (Chroma will embed with default, may raise if none configured)
        collection.add(ids=ids, documents=texts, metadatas=metadatas)
    return ids


def semantic_search(query: str, n_results: int = 5) -> List[Dict[str, Any]]:
    collection = get_collection()
    results = collection.query(query_texts=[query], n_results=n_results)
    out = []
    for i in range(len(results.get('ids', [])[0])):
        out.append({
            "id": results['ids'][0][i],
            "document": results['documents'][0][i],
            "metadata": results['metadatas'][0][i],
            "distance": results['distances'][0][i] if 'distances' in results else None
        })
    return out

if __name__ == "__main__":
    print(get_collection().name)
