import sqlite3
from pathlib import Path
from typing import Iterable, Dict, Any, List

from .config import SQLITE_PATH

# New schema: explicit chunk metadata + separate FTS table + OCR quality log
SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_id TEXT UNIQUE,
  source TEXT,
  path TEXT,
  file_type TEXT,
  page_start INTEGER,
  page_end INTEGER,
  chunk_id INTEGER,
  owner TEXT,
  sensitivity TEXT,
  updated_at INTEGER,
  tokens_est INTEGER,
  text TEXT
);

CREATE TABLE IF NOT EXISTS ocr_quality (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_id TEXT,
  page_num INTEGER,
  quality_score REAL,
  engine TEXT,
  status TEXT,
  notes TEXT,
  created_at INTEGER
);

CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
  content,
  doc_id UNINDEXED
);
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
  conn.commit()
  conn.close()


def insert_chunks(chunks: Iterable[Dict[str, Any]]):
  conn = get_conn()
  cur = conn.cursor()
  for c in chunks:
    cur.execute(
      """
      INSERT OR IGNORE INTO documents(doc_id,source,path,file_type,page_start,page_end,chunk_id,owner,sensitivity,updated_at,tokens_est,text)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
      """,
      (
        c.get('doc_id'), c.get('source'), c.get('path'), c.get('file_type'),
        c.get('page_start'), c.get('page_end'), c.get('chunk_id'), c.get('owner'),
        c.get('sensitivity'), c.get('updated_at'), c.get('tokens_est'), c.get('text')
      )
    )
    # FTS content
    cur.execute(
      "INSERT INTO docs_fts(content, doc_id) VALUES (?,?)",
      (c.get('text'), c.get('doc_id'))
    )
  conn.commit()
  conn.close()


def log_ocr_quality(entries: Iterable[Dict[str, Any]]):
  conn = get_conn()
  cur = conn.cursor()
  rows = [(
    e.get('doc_id'), e.get('page_num'), e.get('quality_score'), e.get('engine'),
    e.get('status'), e.get('notes'), e.get('created_at')
  ) for e in entries]
  cur.executemany("""
    INSERT INTO ocr_quality(doc_id,page_num,quality_score,engine,status,notes,created_at)
    VALUES (?,?,?,?,?,?,?)
  """, rows)
  conn.commit()
  conn.close()


def keyword_search(query: str, limit: int = 10) -> List[Dict[str, Any]]:
  conn = get_conn()
  cur = conn.cursor()
  cur.execute(
    "SELECT doc_id FROM docs_fts WHERE docs_fts MATCH ? LIMIT ?",
    (query, limit)
  )
  ids = [r[0] for r in cur.fetchall()]
  if not ids:
    conn.close()
    return []
  placeholders = ','.join('?' for _ in ids)
  cur.execute(
    f"SELECT doc_id, source, path, file_type, page_start, page_end, owner, sensitivity, updated_at, tokens_est, text FROM documents WHERE doc_id IN ({placeholders})",
    ids
  )
  cols = [c[0] for c in cur.description]
  out = [dict(zip(cols, row)) for row in cur.fetchall()]
  conn.close()
  return out
