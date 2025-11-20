import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Iterable

DB_PATH = Path(__file__).resolve().parent.parent / 'data' / 'db' / 'ingestion.sqlite'

SCHEMA = [
    "PRAGMA journal_mode=WAL;",
    "CREATE TABLE IF NOT EXISTS documents (\n"
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "  source_path TEXT NOT NULL,\n"
    "  file_type TEXT NOT NULL,\n"
    "  ingest_time DATETIME DEFAULT CURRENT_TIMESTAMP,\n"
    "  metadata_json TEXT\n"
    ");",
    # FTS5 virtual table for full text search over chunks
    "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(\n"
    "  content,\n"
    "  document_id UNINDEXED,\n"
    "  chunk_index UNINDEXED,\n"
    "  tokenize = 'porter'\n"
    ");",
    # Mapping table for chunk metadata (embedding id etc.)
    "CREATE TABLE IF NOT EXISTS chunks_meta (\n"
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "  document_id INTEGER NOT NULL,\n"
    "  chunk_index INTEGER NOT NULL,\n"
    "  embedding_id TEXT,\n"
    "  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE\n"
    ");",
    "CREATE INDEX IF NOT EXISTS idx_chunks_meta_doc ON chunks_meta(document_id);"
]


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        for stmt in SCHEMA:
            conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()


def insert_document(source_path: str, file_type: str, metadata: Optional[Dict[str, Any]] = None) -> int:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO documents(source_path, file_type, metadata_json) VALUES (?, ?, ?)",
            (source_path, file_type, json.dumps(metadata or {}))
        )
        doc_id = cur.lastrowid
        conn.commit()
        return doc_id
    finally:
        conn.close()


def insert_chunks(document_id: int, chunks: Iterable[str], embedding_ids: Optional[List[str]] = None) -> None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        for idx, chunk in enumerate(chunks):
            cur.execute(
                "INSERT INTO chunks_fts(content, document_id, chunk_index) VALUES (?, ?, ?)",
                (chunk, document_id, idx)
            )
            emb_id = embedding_ids[idx] if embedding_ids and idx < len(embedding_ids) else None
            cur.execute(
                "INSERT INTO chunks_meta(document_id, chunk_index, embedding_id) VALUES (?, ?, ?)",
                (document_id, idx, emb_id)
            )
        conn.commit()
    finally:
        conn.close()


def search_fulltext(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT rowid, content, document_id, chunk_index FROM chunks_fts WHERE chunks_fts MATCH ? LIMIT ?",
            (query, limit)
        )
        rows = cur.fetchall()
        return [
            {"rowid": r[0], "content": r[1], "document_id": r[2], "chunk_index": r[3]} for r in rows
        ]
    finally:
        conn.close()


def get_document(doc_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, source_path, file_type, ingest_time, metadata_json FROM documents WHERE id = ?", (doc_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "source_path": row[1],
            "file_type": row[2],
            "ingest_time": row[3],
            "metadata": json.loads(row[4] or '{}')
        }
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print(f"Initialized DB at {DB_PATH}")
