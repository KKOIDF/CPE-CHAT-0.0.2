import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = REPO_ROOT / "services" / "rag-service"
for key in list(sys.modules):
    if key == "app" or key.startswith("app."):
        sys.modules.pop(key, None)
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))


def test_chroma_upsert_and_query(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("RAG_CHROMA_COLLECTION", "test_chunks")
    import app.chroma_client as chroma_client  # noqa: E402
    import app.config as config  # noqa: E402

    importlib.reload(config)
    importlib.reload(chroma_client)

    collection = chroma_client._get_global_collection()
    texts = [
        "หลักสูตรต้องเรียนครบ 120 หน่วยกิต",
        "ประกาศล่าสุดเปลี่ยนกำหนดการยื่นเอกสาร",
    ]
    embeddings = chroma_client.embed_texts(texts, is_query=False)
    ids = ["chunk-a", "chunk-b"]
    metadatas = [
        {"stable_chunk_id": "chunk-a", "domain": "curriculum", "source_name": "curriculum.txt", "source_path": "curriculum.txt"},
        {"stable_chunk_id": "chunk-b", "domain": "announcements", "source_name": "announcement.txt", "source_path": "announcement.txt"},
    ]
    collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

    results = chroma_client.semantic_search_global("ต้องเรียนกี่หน่วยกิต", top_k=2)
    assert results
    assert results[0]["stable_chunk_id"] == "chunk-a"
