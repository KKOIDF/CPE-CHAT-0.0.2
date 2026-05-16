import sqlite3
import re
import threading
import os
from typing import List, Dict, Optional, Sequence, Any
from pathlib import Path

from .config import RAG_GLOBAL_SQLITE_PATH, SQLITE_PATH, domain_paths


_thread_local = threading.local()


def _conn_cache() -> dict[str, Any]:
    cache = getattr(_thread_local, 'sqlite_conns', None)
    if cache is None:
        cache = {}
        setattr(_thread_local, 'sqlite_conns', cache)
    return cache


def _file_signature(path: Path) -> tuple[int, int]:
    """Best-effort file signature for cache invalidation (mtime_ns, size)."""
    try:
        st = path.stat()
        return int(st.st_mtime_ns), int(st.st_size)
    except Exception:
        return -1, -1


def close_thread_connections() -> None:
    cache = getattr(_thread_local, 'sqlite_conns', None)
    if not cache:
        return
    for entry in list(cache.values()):
        if isinstance(entry, dict):
            conn = entry.get('conn')
        else:
            conn = entry
        if conn is None:
            continue
        try:
            conn.close()
        except Exception:
            pass
    try:
        cache.clear()
    except Exception:
        pass

def get_conn(sqlite_path: Optional[str] = None):
    p = Path(sqlite_path) if sqlite_path else Path(SQLITE_PATH)
    key = str(p.resolve())
    cache = _conn_cache()
    sig = _file_signature(p)

    cached = cache.get(key)
    conn = None
    cached_sig = None
    if isinstance(cached, dict):
        conn = cached.get('conn')
        cached_sig = cached.get('sig')
    else:
        conn = cached

    # Auto-refresh connection when the sqlite file was replaced/updated.
    if conn is not None and cached_sig == sig:
        return conn

    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        cache.pop(key, None)

    # Prefer read-only connections for safety + concurrency.
    # If the file doesn't exist yet (e.g., misconfigured volume), fall back to normal connect.
    try:
        uri = f"file:{p.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    except Exception:
        conn = sqlite3.connect(str(p))

    try:
        conn.row_factory = sqlite3.Row
    except Exception:
        pass

    # A few lightweight PRAGMAs for read-mostly workload.
    try:
        conn.execute('PRAGMA query_only=ON')
        conn.execute('PRAGMA temp_store=MEMORY')
        # Negative cache_size means KiB (approx). Keep it modest.
        conn.execute('PRAGMA cache_size=-20000')
    except Exception:
        pass

    cache[key] = {'conn': conn, 'sig': sig}
    return conn


def keyword_search(
    query: str,
    limit: int = 30,
    sqlite_path: Optional[str] = None,
    source_allowlist: Optional[Sequence[str]] = None,
) -> List[str]:
    conn = get_conn(sqlite_path)

    allow_src: list[str] = []
    if source_allowlist:
        # Normalize to basenames in lowercase.
        seen = set()
        for s in source_allowlist:
            if not s:
                continue
            try:
                name = Path(str(s)).name.lower()
            except Exception:
                name = str(s).strip().lower()
            if not name or name in seen:
                continue
            allow_src.append(name)
            seen.add(name)

    def _allow_source_clause(col: str) -> tuple[str, list[str]]:
        """Build a source allowlist clause that matches both exact and path-suffix sources.

        Some ingesters store `source` as a basename (e.g., 't_fee.txt'), others store
        a relative/absolute path (e.g., 'data/announcements/t_fee.txt').
        """
        if not allow_src:
            return "", []
        in_placeholders = ','.join('?' for _ in allow_src)
        parts: list[str] = [f"LOWER({col}) IN ({in_placeholders})"]
        params: list[str] = [*allow_src]
        # Also match suffixes that end with '/<name>' or '\\<name>'
        for s in allow_src:
            parts.append(f"LOWER({col}) LIKE ?")
            params.append(f"%/{s}")
            parts.append(f"LOWER({col}) LIKE ?")
            params.append(f"%\\\\{s}")
        return "(" + " OR ".join(parts) + ")", params
    
    # Sanitize query for FTS5 - escape special characters
    # FTS5 special chars: " ( ) - / AND OR NOT
    sanitized = query.replace('"', '""')
    # Remove other special characters that might cause syntax errors
    for char in ['/', '(', ')', '-', ':', '*', '?', '[', ']', '{', '}']:
        sanitized = sanitized.replace(char, ' ')
    
    # If query becomes empty after sanitization, return empty list
    if not sanitized.strip():
        return []
    
    try:
        if allow_src:
            clause, clause_params = _allow_source_clause('documents.source')
            cur = conn.execute(
                (
                    "SELECT documents.doc_id "
                    "FROM docs_fts JOIN documents ON documents.doc_id = docs_fts.doc_id "
                    "WHERE docs_fts MATCH ? AND "
                    + clause
                    + " LIMIT ?"
                ),
                (sanitized, *clause_params, limit),
            )
        else:
            cur = conn.execute(
                "SELECT doc_id FROM docs_fts WHERE docs_fts MATCH ? LIMIT ?",
                (sanitized, limit),
            )
        ids = [row[0] for row in cur.fetchall()]
    except Exception:
        # If still fails, return empty list
        ids = []

    like_ids: List[str] = []

    # Thai/OCR text: FTS tokenization can miss substring matches, but broad LIKE fallback
    # also increases noise substantially. Default to LIKE only when FTS returns no hits.
    try:
        like_fallback_min_hits = max(0, int(os.getenv('SQLITE_LIKE_FALLBACK_MIN_HITS', '0') or '0'))
    except Exception:
        like_fallback_min_hits = 0

    if (not ids) or len(ids) <= like_fallback_min_hits:
        # Extract candidate keywords (Thai runs, ascii words, digits incl. Thai digits)
        thai_to_arabic = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')
        norm_q = query.translate(thai_to_arabic)
        candidates: List[str] = []
        # Thai runs: also add suffix/prefix slices to handle compound tokens such as
        # "ไปรษณีย์ลงทะเบียน" where the corpus may contain OCR newlines inside the word.
        # Keeping a short suffix often captures the meaningful term (e.g., "ลงทะเบียน").
        thai_runs = re.findall(r"[\u0E00-\u0E7F]{2,}", norm_q)
        candidates += thai_runs
        for t in thai_runs:
            tt = (t or '').strip()
            if len(tt) >= 8:
                candidates.append(tt[-8:])
                candidates.append(tt[:8])
            if len(tt) >= 10:
                candidates.append(tt[-10:])
        # Upper-case ASCII tokens so course-prefix logic works even if user types "lng".
        ascii_words = [w.upper() for w in re.findall(r"[A-Za-z]{2,}", norm_q)]
        # Support placeholder-like course prefixes such as "LNGxxx" by also searching the prefix ("LNG").
        # This helps when users refer to a family of courses without a specific numeric suffix.
        expanded: List[str] = []
        for w in ascii_words:
            if re.fullmatch(r"[A-Z]{2,6}[xX]{2,}", w):
                prefix = re.sub(r"[xX]+$", "", w)
                if len(prefix) >= 2:
                    expanded.append(prefix)
            else:
                expanded.append(w)
        candidates += expanded
        candidates += re.findall(r"\d{2,}", norm_q)

        # If the query references a course prefix (e.g., "LNG"), add curriculum-shaped anchors.
        # This helps pull course description chunks instead of generic narrative text.
        course_prefixes = {w for w in expanded if re.fullmatch(r"[A-Z]{2,6}", w)}
        if course_prefixes:
            for pref in sorted(course_prefixes):
                candidates += [
                    f"รายวิชา: {pref}",
                    f"รายวิชา {pref}",
                    f"{pref} ",
                ]

        # Heuristic expansions for common Thai curriculum questions.
        # OCR often introduces extra spaces; we'll also use a space-insensitive LIKE below.
        if 'หน่วยกิต' in norm_q:
            candidates += [
                'หน่วยกิต',
                'จำนวนหน่วยกิต',
                'จานวนหน่วยกิต',
                'หน่วยกิตที่เรียน',
                'หน่วยกิตที่เรียนตลอดหลักสูตร',
                'จานวนหน่วยกิตที่เรียนตลอดหลักสูตร',
                'ตลอดหลักสูตร',
            ]
        if 'รวม' in norm_q:
            candidates += ['รวม', 'รวมทั้งสิ้น', 'รวมไม่น้อยกว่า', 'ไม่น้อยกว่า']

        # Remove duplicates and rank tokens.
        # Prefer course-like tokens/prefixes first, then longer tokens.
        def _token_priority(tok: str) -> tuple[int, int]:
            # Lower is better.
            if re.fullmatch(r"รายวิชา[: ]+[A-Z]{2,6}\s*", tok) or re.fullmatch(r"รายวิชา[: ]+[A-Z]{2,6}", tok):
                return (0, -len(tok))
            if re.fullmatch(r"[A-Z]{2,6}\s*", tok) or re.fullmatch(r"[A-Z]{2,6}", tok):
                return (1, -len(tok))
            return (2, -len(tok))

        uniq: List[str] = []
        seen = set()
        for c in sorted(set(candidates), key=lambda s: (_token_priority(s.strip()), -len(s.strip()), s)):
            c = c.strip()
            if not c or c in seen:
                continue
            # avoid overly-long LIKE needles
            if len(c) > 64:
                c = c[:64]
            uniq.append(c)
            seen.add(c)
            if len(uniq) >= 6:
                break

        if uniq:
            # Space-insensitive search helps with OCR that inserts spaces between Thai characters/words.
            # Query per-token (longest first) to prioritize specific matches.
            try:
                seen_like = set()
                # Don't let the first broad token consume the entire limit;
                # allocate a small quota per token to improve recall diversity.
                per_token = max(4, int(limit / max(1, len(uniq))))
                # OCR often inserts newlines/tabs mid-word; make a compact text form
                # to improve substring match recall.
                compact_expr = (
                    "REPLACE(REPLACE(REPLACE(REPLACE(text, ' ', ''), char(10), ''), char(13), ''), char(9), '')"
                )
                for u in uniq:
                    if len(like_ids) >= limit:
                        break
                    needle = f"%{u}%"
                    needle2 = f"%{u.replace(' ', '')}%"
                    if allow_src:
                        clause, clause_params = _allow_source_clause('source')
                        cur = conn.execute(
                            (
                                "SELECT doc_id FROM documents "
                                f"WHERE (text LIKE ? OR {compact_expr} LIKE ?) "
                                "AND "
                                + clause
                                + " LIMIT ?"
                            ),
                            (needle, needle2, *clause_params, per_token),
                        )
                    else:
                        cur = conn.execute(
                            f"SELECT doc_id FROM documents WHERE text LIKE ? OR {compact_expr} LIKE ? LIMIT ?",
                            (needle, needle2, per_token),
                        )
                    for (did,) in cur.fetchall():
                        if did and did not in seen_like:
                            like_ids.append(did)
                            seen_like.add(did)
                        if len(like_ids) >= limit:
                            break
            except Exception:
                like_ids = []
    
    if not like_ids:
        return ids

    merged: List[str] = []
    seen = set()
    for did in (ids + like_ids):
        if did and did not in seen:
            merged.append(did)
            seen.add(did)
        if len(merged) >= limit:
            break
    return merged


def _build_chunk_row(row: Any) -> Dict[str, Any]:
    data = dict(row) if not isinstance(row, dict) else row
    return {
        'stable_chunk_id': data.get('stable_chunk_id') or data.get('doc_id'),
        'doc_id': data.get('stable_chunk_id') or data.get('doc_id'),
        'source_id': data.get('source_id'),
        'domain': data.get('domain'),
        'source_name': data.get('source_name') or data.get('source'),
        'source': data.get('source_name') or data.get('source'),
        'source_path': data.get('source_path') or data.get('path'),
        'path': data.get('source_path') or data.get('path'),
        'file_name': data.get('file_name'),
        'title': data.get('title'),
        'section_heading': data.get('section_heading'),
        'page': data.get('page'),
        'page_start': data.get('page'),
        'page_end': data.get('page'),
        'text': data.get('text'),
        'keyword_score': float(data.get('bm25') or 0.0),
    }


def keyword_search_global_chunks(
    query: str,
    limit: int = 30,
    strict_domain: str | None = None,
    sqlite_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    path = sqlite_path or str(RAG_GLOBAL_SQLITE_PATH)
    conn = get_conn(path)
    sanitized = (query or '').replace('"', '""')
    for char in ['/', '(', ')', '-', ':', '*', '?', '[', ']', '{', '}']:
        sanitized = sanitized.replace(char, ' ')
    if not sanitized.strip():
        return []
    params: list[Any] = [sanitized]
    where = ""
    if strict_domain:
        where = " AND c.domain = ?"
        params.append(strict_domain)
    params.append(limit)
    sql = (
        "SELECT c.*, bm25(rag_chunks_fts) AS bm25 "
        "FROM rag_chunks_fts "
        "JOIN rag_chunks c ON c.stable_chunk_id = rag_chunks_fts.stable_chunk_id "
        "WHERE rag_chunks_fts MATCH ?"
        f"{where} "
        "ORDER BY bm25 LIMIT ?"
    )
    try:
        cur = conn.execute(sql, params)
        rows = [_build_chunk_row(row) for row in cur.fetchall()]
        if rows:
            return rows
    except Exception:
        pass

    like_query = f"%{query.strip()}%"
    try:
        if strict_domain:
            cur = conn.execute(
                "SELECT * FROM rag_chunks WHERE domain = ? AND (text LIKE ? OR source_name LIKE ? OR title LIKE ? OR section_heading LIKE ?) LIMIT ?",
                (strict_domain, like_query, like_query, like_query, like_query, limit),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM rag_chunks WHERE text LIKE ? OR source_name LIKE ? OR title LIKE ? OR section_heading LIKE ? LIMIT ?",
                (like_query, like_query, like_query, like_query, limit),
            )
        return [_build_chunk_row(row) for row in cur.fetchall()]
    except Exception:
        return []


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
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    # Preserve the original input ordering (IN (...) has undefined ordering).
    by_id = {r.get('doc_id'): r for r in rows if r.get('doc_id')}
    ordered: List[Dict] = []
    for did in doc_ids:
        r = by_id.get(did)
        if r is not None:
            ordered.append(r)
    return ordered


def domain_sqlite_path(domain: Optional[str]) -> str:
    _, sqlite_path = domain_paths(domain)
    return str(sqlite_path)
