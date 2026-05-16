import sqlite3
from pathlib import Path
from typing import Iterable, Dict, Any, List

from .config import RAG_GLOBAL_SQLITE_PATH, SQLITE_PATH
from .toon_converter import read_toon

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

CREATE TABLE IF NOT EXISTS rag_chunks (
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

CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts USING fts5(
  stable_chunk_id UNINDEXED,
  source_id UNINDEXED,
  domain UNINDEXED,
  source_name,
  title,
  section_heading,
  text
);
"""


def get_conn(sqlite_path: Path | None = None):
  path = sqlite_path or SQLITE_PATH
  path.parent.mkdir(parents=True, exist_ok=True)
  conn = sqlite3.connect(str(path))
  return conn


def _init_db_at(path: Path):
  conn = get_conn(path)
  cur = conn.cursor()
  for stmt in SCHEMA.strip().split(';'):
    s = stmt.strip()
    if s:
      cur.execute(s)
  conn.commit()
  conn.close()


def init_db():
  _init_db_at(SQLITE_PATH)
  _init_db_at(RAG_GLOBAL_SQLITE_PATH)


def _insert_chunks_at(chunks: Iterable[Dict[str, Any]], path: Path):
  conn = get_conn(path)
  cur = conn.cursor()
  for c in chunks:
    doc_id = c.get('doc_id')
    text = c.get('text')

    cur.execute(
      """
      INSERT INTO documents(doc_id,source,path,file_type,page_start,page_end,chunk_id,owner,sensitivity,updated_at,tokens_est,text)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(doc_id) DO UPDATE SET
        source=excluded.source,
        path=excluded.path,
        file_type=excluded.file_type,
        page_start=excluded.page_start,
        page_end=excluded.page_end,
        chunk_id=excluded.chunk_id,
        owner=excluded.owner,
        sensitivity=excluded.sensitivity,
        updated_at=excluded.updated_at,
        tokens_est=excluded.tokens_est,
        text=excluded.text
      """,
      (
        doc_id, c.get('source'), c.get('path'), c.get('file_type'),
        c.get('page_start'), c.get('page_end'), c.get('chunk_id'), c.get('owner'),
        c.get('sensitivity'), c.get('updated_at'), c.get('tokens_est'), text
      )
    )

    # Keep FTS in sync (one row per doc_id).
    # FTS5 virtual tables don't enforce uniqueness, so delete then insert.
    if doc_id is not None:
      cur.execute("DELETE FROM docs_fts WHERE doc_id = ?", (doc_id,))
    cur.execute(
      "INSERT INTO docs_fts(content, doc_id) VALUES (?,?)",
      (text, doc_id)
    )
    stable_chunk_id = c.get('stable_chunk_id') or doc_id
    cur.execute(
      """
      INSERT INTO rag_chunks(
        stable_chunk_id,source_id,domain,source_name,source_path,file_name,title,section_heading,page,text,corpus_id,chunk_index,content_type,indexed_at
      ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(stable_chunk_id) DO UPDATE SET
        source_id=excluded.source_id,
        domain=excluded.domain,
        source_name=excluded.source_name,
        source_path=excluded.source_path,
        file_name=excluded.file_name,
        title=excluded.title,
        section_heading=excluded.section_heading,
        page=excluded.page,
        text=excluded.text,
        corpus_id=excluded.corpus_id,
        chunk_index=excluded.chunk_index,
        content_type=excluded.content_type,
        indexed_at=excluded.indexed_at
      """,
      (
        stable_chunk_id,
        c.get('source_id'),
        c.get('domain'),
        c.get('source_name') or c.get('source'),
        c.get('source_path') or c.get('path'),
        c.get('file_name'),
        c.get('title') or c.get('doc_title'),
        c.get('section_heading'),
        c.get('page') or c.get('page_start'),
        text,
        c.get('corpus_id'),
        c.get('chunk_index'),
        c.get('content_type') or c.get('document_type'),
        c.get('indexed_at'),
      )
    )
    cur.execute("DELETE FROM rag_chunks_fts WHERE stable_chunk_id = ?", (stable_chunk_id,))
    cur.execute(
      "INSERT INTO rag_chunks_fts(stable_chunk_id,source_id,domain,source_name,title,section_heading,text) VALUES (?,?,?,?,?,?,?)",
      (
        stable_chunk_id,
        c.get('source_id'),
        c.get('domain'),
        c.get('source_name') or c.get('source'),
        c.get('title') or c.get('doc_title'),
        c.get('section_heading'),
        text,
      )
    )
  conn.commit()
  conn.close()


def insert_chunks(chunks: Iterable[Dict[str, Any]]):
  rows = list(chunks)
  _insert_chunks_at(rows, SQLITE_PATH)
  _insert_chunks_at(rows, RAG_GLOBAL_SQLITE_PATH)


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


def load_chunks_from_toon(toon_path: str = 'data/db/chunks.toon') -> List[Dict[str, Any]]:
  """Load chunks from TOON file"""
  try:
    data = read_toon(toon_path)
    if isinstance(data, dict) and 'chunks' in data:
      return data['chunks']
    return data if isinstance(data, list) else []
  except FileNotFoundError:
    return []


def load_records_from_toon(toon_path: str = 'data/db/records.toon') -> List[Dict[str, Any]]:
  """Load records from TOON file"""
  try:
    data = read_toon(toon_path)
    if isinstance(data, dict) and 'records' in data:
      return data['records']
    return data if isinstance(data, list) else []
  except FileNotFoundError:
    return []
