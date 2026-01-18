import sqlite3
import re
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

    like_ids: List[str] = []

    # Thai/OCR text: FTS tokenization often misses matches (or returns noisy matches).
    # For our small per-domain DBs, LIKE-based substring matching is acceptable.
    # If query contains Thai characters, run LIKE search even if FTS returned something.
    if (not ids) or re.search(r"[\u0E00-\u0E7F]", query):
        # Extract candidate keywords (Thai runs, ascii words, digits incl. Thai digits)
        thai_to_arabic = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')
        norm_q = query.translate(thai_to_arabic)
        candidates: List[str] = []
        candidates += re.findall(r"[\u0E00-\u0E7F]{2,}", norm_q)
        candidates += re.findall(r"[A-Za-z]{2,}", norm_q)
        candidates += re.findall(r"\d{2,}", norm_q)

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

        # Remove duplicates, prefer longer tokens, cap count
        uniq: List[str] = []
        seen = set()
        for c in sorted(set(candidates), key=len, reverse=True):
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
                for u in uniq:
                    if len(like_ids) >= limit:
                        break
                    needle = f"%{u}%"
                    needle2 = f"%{u.replace(' ', '')}%"
                    cur = conn.execute(
                        "SELECT doc_id FROM documents WHERE text LIKE ? OR REPLACE(text, ' ', '') LIKE ? LIMIT ?",
                        (needle, needle2, limit),
                    )
                    for (did,) in cur.fetchall():
                        if did and did not in seen_like:
                            like_ids.append(did)
                            seen_like.add(did)
                        if len(like_ids) >= limit:
                            break
            except Exception:
                like_ids = []
    
    conn.close()
    if not like_ids:
        return ids

    # Union while preserving order (FTS first, then LIKE additions).
    merged: List[str] = []
    seen = set()
    for did in (ids + like_ids):
        if did and did not in seen:
            merged.append(did)
            seen.add(did)
        if len(merged) >= limit:
            break
    return merged


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
    conn.close()

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
