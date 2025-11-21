import sqlite3
from typing import List, Dict
from .config import SQLITE_PATH

def get_conn():
    return sqlite3.connect(str(SQLITE_PATH))


def keyword_search(query: str, limit: int = 30) -> List[str]:
    conn = get_conn()
    cur = conn.execute(
        "SELECT doc_id FROM docs_fts WHERE docs_fts MATCH ? LIMIT ?",
        (query, limit)
    )
    ids = [row[0] for row in cur.fetchall()]
    conn.close()
    return ids


def fetch_docs(doc_ids: List[str]) -> List[Dict]:
    if not doc_ids:
        return []
    conn = get_conn()
    placeholders = ','.join('?' for _ in doc_ids)
    cur = conn.execute(
        f"SELECT doc_id, source, path, file_type, page_start, page_end, owner, sensitivity, updated_at, tokens_est, text FROM documents WHERE doc_id IN ({placeholders})",
        doc_ids
    )
    cols = [c[0] for c in cur.description]
    base_rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()
    return base_rows
