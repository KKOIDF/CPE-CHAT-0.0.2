import sqlite3
from pathlib import Path
from typing import Iterable, Dict, Any, List

from .config import SQLITE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT,
  path TEXT,
  page_start INTEGER,
  page_end INTEGER,
  owner TEXT,
  sensitivity TEXT,
  updated_at INTEGER,
  tokens_est INTEGER,
  text TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
  text,
  source,
  owner,
  sensitivity,
  content='documents', content_rowid='id'
);
"""

TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
  INSERT INTO documents_fts(rowid, text, source, owner, sensitivity)
  VALUES (new.id, new.text, new.source, new.owner, new.sensitivity);
END;
CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
  INSERT INTO documents_fts(documents_fts, rowid, text, source, owner, sensitivity)
  VALUES('delete', old.id, old.text, old.source, old.owner, old.sensitivity);
END;
CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
  INSERT INTO documents_fts(documents_fts, rowid, text, source, owner, sensitivity)
  VALUES('delete', old.id, old.text, old.source, old.owner, old.sensitivity);
  INSERT INTO documents_fts(rowid, text, source, owner, sensitivity)
  VALUES (new.id, new.text, new.source, new.owner, new.sensitivity);
END;
"""


def get_conn():
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SQLITE_PATH))
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    for stmt in SCHEMA.strip().split(';'):
        s = stmt.strip()
        if s:
            cur.execute(s)
    for stmt in TRIGGERS.strip().split(';'):
        s = stmt.strip()
        if s:
            cur.execute(s)
    conn.commit()
    conn.close()


def insert_chunks(chunks: Iterable[Dict[str, Any]]):
    conn = get_conn()
    cur = conn.cursor()
    rows = [(
        c.get('source'), c.get('path'), c.get('page_start'), c.get('page_end'),
        c.get('owner'), c.get('sensitivity'), c.get('updated_at'), c.get('tokens_est'), c.get('text')
    ) for c in chunks]
    cur.executemany("""
        INSERT INTO documents(source,path,page_start,page_end,owner,sensitivity,updated_at,tokens_est,text)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, rows)
    conn.commit()
    conn.close()


def keyword_search(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT d.id, d.source, d.path, d.page_start, d.page_end, d.owner, d.sensitivity, d.updated_at, d.tokens_est, d.text
        FROM documents_fts f JOIN documents d ON f.rowid = d.id
        WHERE documents_fts MATCH ? ORDER BY rank LIMIT ?
    """, (query, limit))
    cols = [c[0] for c in cur.description]
    out = [dict(zip(cols, row)) for row in cur.fetchall()]
    conn.close()
    return out
