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
        import sqlite3
        import json
        from pathlib import Path
        from typing import Optional, List, Dict, Any
        from datetime import datetime
        from uuid import uuid4

        DB_PATH = Path(__file__).resolve().parent.parent / 'data' / 'db' / 'metadata.db'

        SCHEMA = [
            "PRAGMA journal_mode=WAL;",
            "CREATE TABLE IF NOT EXISTS documents (\n"
            "  id INTEGER PRIMARY KEY,\n"
            "  doc_id TEXT UNIQUE,\n"
            "  file_path TEXT,\n"
            "  file_type TEXT,\n"
            "  page_num INTEGER,\n"
            "  chunk_id INTEGER,\n"
            "  created_at DATETIME DEFAULT CURRENT_TIMESTAMP\n"
            ");",
            "CREATE TABLE IF NOT EXISTS ocr_quality (\n"
            "  id INTEGER PRIMARY KEY,\n"
            "  doc_id TEXT,\n"
            "  page_num INTEGER,\n"
            "  quality_score REAL,\n"
            "  ocr_engine TEXT,\n"
            "  status TEXT,\n"
            "  notes TEXT\n"
            ");",
            "CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(\n"
            "  content,\n"
            "  doc_id UNINDEXED\n"
            ");",
            "CREATE INDEX IF NOT EXISTS idx_documents_docid ON documents(doc_id);",
        ]


        def get_conn() -> sqlite3.Connection:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(DB_PATH))
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


        def insert_document(doc_id: Optional[str], file_path: str, file_type: str, page_num: Optional[int] = None, chunk_id: Optional[int] = None) -> int:
            """Insert a document record. Returns the numeric id."""
            conn = get_conn()
            try:
                cur = conn.cursor()
                if not doc_id:
                    doc_id = str(uuid4())
                cur.execute(
                    "INSERT OR IGNORE INTO documents(doc_id, file_path, file_type, page_num, chunk_id) VALUES (?, ?, ?, ?, ?)",
                    (doc_id, file_path, file_type, page_num, chunk_id)
                )
                # fetch id
                cur.execute("SELECT id FROM documents WHERE doc_id = ?", (doc_id,))
                row = cur.fetchone()
                if row:
                    doc_numeric_id = row[0]
                else:
                    doc_numeric_id = cur.lastrowid
                conn.commit()
                return doc_numeric_id
            finally:
                conn.close()


        def add_to_fts(doc_id: str, content: str) -> int:
            """Add a content blob to the FTS table tied to doc_id. Returns rowid."""
            conn = get_conn()
            try:
                cur = conn.cursor()
                cur.execute("INSERT INTO docs_fts(content, doc_id) VALUES (?, ?)", (content, doc_id))
                rowid = cur.lastrowid
                conn.commit()
                return rowid
            finally:
                conn.close()


        def insert_ocr_quality(doc_id: str, page_num: Optional[int], quality_score: float, ocr_engine: str, status: str = 'ok', notes: Optional[str] = None) -> int:
            conn = get_conn()
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO ocr_quality(doc_id, page_num, quality_score, ocr_engine, status, notes) VALUES (?, ?, ?, ?, ?, ?)",
                    (doc_id, page_num, quality_score, ocr_engine, status, notes)
                )
                rowid = cur.lastrowid
                conn.commit()
                return rowid
            finally:
                conn.close()


        def search_fts(query: str, limit: int = 10) -> List[Dict[str, Any]]:
            conn = get_conn()
            try:
                cur = conn.cursor()
                cur.execute("SELECT rowid, content, doc_id FROM docs_fts WHERE docs_fts MATCH ? LIMIT ?", (query, limit))
                rows = cur.fetchall()
                return [{"rowid": r[0], "content": r[1], "doc_id": r[2]} for r in rows]
            finally:
                conn.close()


        def get_document_by_doc_id(doc_id: str) -> Optional[Dict[str, Any]]:
            conn = get_conn()
            try:
                cur = conn.cursor()
                cur.execute("SELECT id, doc_id, file_path, file_type, page_num, chunk_id, created_at FROM documents WHERE doc_id = ?", (doc_id,))
                r = cur.fetchone()
                if not r:
                    return None
                return {
                    "id": r[0],
                    "doc_id": r[1],
                    "file_path": r[2],
                    "file_type": r[3],
                    "page_num": r[4],
                    "chunk_id": r[5],
                    "created_at": r[6]
                }
            finally:
                conn.close()


        if __name__ == "__main__":
            init_db()
            print(f"Initialized metadata DB at {DB_PATH}")
