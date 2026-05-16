import importlib
import sqlite3
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = REPO_ROOT / "services" / "rag-service"
for key in list(sys.modules):
    if key == "app" or key.startswith("app."):
        sys.modules.pop(key, None)
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))


def test_keyword_search_exact_phrase(tmp_path, monkeypatch):
    db_path = tmp_path / "global.sqlite"
    monkeypatch.setenv("RAG_GLOBAL_SQLITE_PATH", str(db_path))
    import app.config as config  # noqa: E402
    import app.sqlite_client as sqlite_client  # noqa: E402

    importlib.reload(config)
    importlib.reload(sqlite_client)

    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE rag_chunks (
          stable_chunk_id TEXT PRIMARY KEY,
          source_id TEXT,
          domain TEXT,
          source_name TEXT,
          source_path TEXT,
          file_name TEXT,
          title TEXT,
          section_heading TEXT,
          page INTEGER,
          text TEXT,
          corpus_id TEXT,
          chunk_index INTEGER,
          content_type TEXT,
          indexed_at TEXT
        );
        CREATE VIRTUAL TABLE rag_chunks_fts USING fts5(
          stable_chunk_id UNINDEXED,
          source_id UNINDEXED,
          domain UNINDEXED,
          source_name,
          title,
          section_heading,
          text
        );
        """
    )
    conn.execute(
        "INSERT INTO rag_chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("chunk-1", "src-1", "curriculum", "curriculum.txt", "curriculum.txt", "curriculum.txt", "หลักสูตร", "เงื่อนไข", 12, "หลักสูตรต้องเรียนครบ 120 หน่วยกิต", "cpe_chat", 0, "plain", "now"),
    )
    conn.execute(
        "INSERT INTO rag_chunks_fts VALUES (?,?,?,?,?,?,?)",
        ("chunk-1", "src-1", "curriculum", "curriculum.txt", "หลักสูตร", "เงื่อนไข", "หลักสูตรต้องเรียนครบ 120 หน่วยกิต"),
    )
    conn.commit()
    conn.close()

    results = sqlite_client.keyword_search_global_chunks("120 หน่วยกิต", limit=5)
    assert results
    assert results[0]["stable_chunk_id"] == "chunk-1"
