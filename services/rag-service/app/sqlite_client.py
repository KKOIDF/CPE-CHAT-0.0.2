import sqlite3
from typing import List, Dict, Optional
from pathlib import Path
from .config import SQLITE_PATH, domain_paths

def get_conn(sqlite_path: Optional[str] = None):
    p = Path(sqlite_path) if sqlite_path else Path(SQLITE_PATH)
    return sqlite3.connect(str(p))


def keyword_search(query: str, limit: int = 30, sqlite_path: Optional[str] = None) -> List[str]:
    conn = get_conn(sqlite_path)
    
    # Sanitize query for FTS5 - escape special characters
    # FTS5 special chars: " ( ) - / AND OR NOT
    sanitized = query.replace('"', '""')
    # Remove other special characters that might cause syntax errors
    for char in ['/', '(', ')', '-', ':', '*', '?', '[', ']', '{', '}']:
        sanitized = sanitized.replace(char, ' ')
    
    # If query becomes empty after sanitization, return empty list
    if not sanitized.strip():
        conn.close()
        return []
    
    try:
        cur = conn.execute(
            "SELECT doc_id FROM docs_fts WHERE docs_fts MATCH ? LIMIT ?",
            (sanitized, limit)
        )
        ids = [row[0] for row in cur.fetchall()]
    except Exception:
        # If still fails, return empty list
        ids = []
    
    conn.close()
    return ids


def fetch_docs(doc_ids: List[str]) -> List[Dict]:
    return fetch_docs_with_path(doc_ids, sqlite_path=None)


def fetch_docs_with_path(doc_ids: List[str], sqlite_path: Optional[str] = None) -> List[Dict]:
    if not doc_ids:
        return []
    conn = get_conn(sqlite_path)
    placeholders = ','.join('?' for _ in doc_ids)
    cur = conn.execute(
        f"SELECT doc_id, source, path, file_type, page_start, page_end, owner, sensitivity, updated_at, tokens_est, text FROM documents WHERE doc_id IN ({placeholders})",
        doc_ids
    )
    cols = [c[0] for c in cur.description]
    base_rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()
    return base_rows


def domain_sqlite_path(domain: Optional[str]) -> str:
    _, sqlite_path = domain_paths(domain)
    return str(sqlite_path)
