import os
import re
from typing import List, Optional, Set

from functools import lru_cache

try:
    from neo4j import GraphDatabase  # type: ignore
except Exception:  # pragma: no cover
    GraphDatabase = None  # type: ignore


_THAI_TO_ARABIC = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')

COURSE_CODE_PATTERNS = [
    re.compile(r"\b[0-9\u0E50-\u0E59]{6}\b"),
    re.compile(r"\b[0-9\u0E50-\u0E59]{3}[-–][0-9\u0E50-\u0E59]{3}\b"),
    re.compile(r"\b[0-9\u0E50-\u0E59]{3}[ .\t]+[0-9\u0E50-\u0E59]{3}\b"),
    re.compile(r"\b[A-Z]{2,6}\s*[-–]?\s*[0-9]{3}\b"),
]


def extract_course_codes(text: str) -> Set[str]:
    if not text:
        return set()
    norm = text.translate(_THAI_TO_ARABIC)
    # Normalize dash variants and common digit typos inside codes (e.g., "1O1" -> "101").
    norm = norm.replace('–', '-').replace('—', '-').replace('−', '-')
    norm = re.sub(r"(?<=\d)[oO](?=\d)", "0", norm)
    out: Set[str] = set()
    for patt in COURSE_CODE_PATTERNS:
        for m in patt.findall(norm):
            code = m.replace('-', '').replace('–', '').replace(' ', '').replace('\t', '').replace('.', '')
            out.add(code)
    return out


def _driver():
    if GraphDatabase is None:
        return None
    uri = os.getenv('NEO4J_URI')
    user = os.getenv('NEO4J_USER') or os.getenv('NEO4J_USERNAME')
    password = os.getenv('NEO4J_PASSWORD')
    if not (uri and user and password):
        return None
    # Driver creation can be expensive; cache it for the process lifetime.
    pool_size = int(os.getenv('NEO4J_POOL_SIZE', '10') or '10')
    timeout_s = float(os.getenv('NEO4J_TIMEOUT_S', '3') or '3')
    try:
        return GraphDatabase.driver(
            uri,
            auth=(user, password),
            max_connection_pool_size=pool_size,
            connection_timeout=timeout_s,
        )
    except TypeError:
        # Older neo4j driver versions may not support these kwargs.
        return GraphDatabase.driver(uri, auth=(user, password))


@lru_cache(maxsize=1)
def _driver_cached():
    return _driver()


def close_driver() -> None:
    try:
        drv = _driver_cached()
        if drv:
            drv.close()
    except Exception:
        pass
    try:
        _driver_cached.cache_clear()
    except Exception:
        pass


def _session(drv):
    db = os.getenv('NEO4J_DATABASE')
    if db:
        return drv.session(database=db)
    return drv.session()


def graph_doc_ids_for_codes(codes: List[str], domain: str, limit: int = 50) -> List[str]:
    """Return Chunk.doc_id values connected to Course codes for a domain.

    This keeps Neo4j payload light; full chunk text is fetched from SQLite.
    If Neo4j isn't configured, returns empty list.
    """
    drv = _driver_cached()
    if not drv or not codes:
        return []

    dom = (domain or 'curriculum').strip().lower()
    codes = [c.replace('-', '') for c in codes if c]

    cypher = (
        "MATCH (co:Course) WHERE co.code IN $codes "
        "MATCH (co)-[:MENTIONED_IN]->(ch:Chunk {domain:$domain}) "
        "RETURN ch.doc_id AS doc_id "
        "LIMIT $limit"
    )

    try:
        with _session(drv) as session:
            rows = session.run(cypher, codes=codes, domain=dom, limit=limit)
            out = [r.get('doc_id') for r in rows if r.get('doc_id')]
    except Exception as e:
        # Graceful fallback if Neo4j is unavailable
        print(f"[Neo4j] Connection error in graph_doc_ids_for_codes, skipping: {e}")
        return []
    return out


def graph_doc_ids_for_course_prefix(prefix: str, domain: str, limit: int = 80) -> List[str]:
    """Return Chunk.doc_id values connected to Course nodes by a code prefix.

    Example: prefix="LNG" will match courses like LNG275, LNG280, etc.
    If Neo4j isn't configured, returns empty list.
    """
    drv = _driver_cached()
    if not drv or not prefix:
        return []

    dom = (domain or 'curriculum').strip().lower()
    pref = re.sub(r"[^A-Za-z0-9]", "", (prefix or "")).upper()
    if len(pref) < 2:
        return []

    cypher = (
        "MATCH (co:Course) WHERE co.code STARTS WITH $prefix "
        "MATCH (co)-[:MENTIONED_IN]->(ch:Chunk {domain:$domain}) "
        "RETURN DISTINCT ch.doc_id AS doc_id "
        "LIMIT $limit"
    )

    try:
        with _session(drv) as session:
            rows = session.run(cypher, prefix=pref, domain=dom, limit=int(limit))
            out = [r.get('doc_id') for r in rows if r.get('doc_id')]
    except Exception as e:
        print(f"[Neo4j] Connection error in graph_doc_ids_for_course_prefix, skipping: {e}")
        return []
    return out


def graph_expand_from_seed_chunks(
    seed_doc_ids: List[str],
    domain: str,
    window: int = 2,
    limit: int = 80,
) -> List[str]:
    """Expand context around seed chunks via Neo4j.

    Uses:
    - (:Document)-[:HAS_CHUNK]->(:Chunk)
    - (:Chunk)-[:NEXT]->(:Chunk)

    Returns additional Chunk.doc_id values (no text payload).
    """
    drv = _driver_cached()
    if not drv or not seed_doc_ids:
        return []

    dom = (domain or 'curriculum').strip().lower()
    seed = [s for s in seed_doc_ids if s]
    if not seed:
        return []

    cypher = (
        "MATCH (ch:Chunk {domain:$domain}) WHERE ch.doc_id IN $seed "
        "MATCH (ch)<-[:HAS_CHUNK]-(d:Document {domain:$domain})-[:HAS_CHUNK]->(sib:Chunk {domain:$domain}) "
        "WHERE sib.chunk_id IS NOT NULL AND ch.chunk_id IS NOT NULL AND abs(sib.chunk_id - ch.chunk_id) <= $window "
        "WITH DISTINCT sib.doc_id AS doc_id "
        "WHERE doc_id IS NOT NULL AND NOT doc_id IN $seed "
        "RETURN doc_id "
        "LIMIT $limit"
    )

    # NEXT edges (prev)
    cypher_prev = (
        "UNWIND $seed AS sid "
        "MATCH (ch:Chunk {domain:$domain, doc_id:sid}) "
        "MATCH (p:Chunk {domain:$domain})-[:NEXT]->(ch) "
        "WITH DISTINCT p.doc_id AS doc_id "
        "WHERE doc_id IS NOT NULL AND NOT doc_id IN $seed "
        "RETURN doc_id "
        "LIMIT $limit"
    )

    # NEXT edges (next)
    cypher_next = (
        "UNWIND $seed AS sid "
        "MATCH (ch:Chunk {domain:$domain, doc_id:sid}) "
        "MATCH (ch)-[:NEXT]->(n:Chunk {domain:$domain}) "
        "WITH DISTINCT n.doc_id AS doc_id "
        "WHERE doc_id IS NOT NULL AND NOT doc_id IN $seed "
        "RETURN doc_id "
        "LIMIT $limit"
    )

    out: List[str] = []
    try:
        with _session(drv) as session:
            rows = session.run(cypher, seed=seed, domain=dom, window=int(window), limit=int(limit))
            out.extend([r.get('doc_id') for r in rows if r.get('doc_id')])
            rows2 = session.run(cypher_prev, seed=seed, domain=dom, limit=int(limit))
            out.extend([r.get('doc_id') for r in rows2 if r.get('doc_id')])
            rows3 = session.run(cypher_next, seed=seed, domain=dom, limit=int(limit))
            out.extend([r.get('doc_id') for r in rows3 if r.get('doc_id')])
    except Exception as e:
        # Graceful fallback if Neo4j is unavailable
        print(f"[Neo4j] Connection error, skipping graph expansion: {e}")
        return []
    # preserve order + uniqueness
    seen = set(seed)
    uniq: List[str] = []
    for d in out:
        if d and d not in seen:
            uniq.append(d)
            seen.add(d)
    return uniq


def graph_doc_ids_for_requisites(
    codes: List[str],
    domain: str,
    kind: str = 'prereq',
    limit: int = 80,
) -> List[str]:
    """Return Chunk.doc_id values for courses related via PREREQ/COREQ.

    We traverse:
      (:Course {code})-[:PREREQ|:COREQ]->(:Course)-[:MENTIONED_IN]->(:Chunk)

    This is used to answer questions like "ลงวิชา X ต้องผ่านอะไร" by pulling
    chunks about the prerequisite courses as supporting context.
    """
    drv = _driver_cached()
    if not drv or not codes:
        return []

    dom = (domain or 'curriculum').strip().lower()
    codes = [c.replace('-', '') for c in codes if c]
    if not codes:
        return []

    rel = 'COREQ' if (kind or '').strip().lower() == 'coreq' else 'PREREQ'
    cypher = (
        f"MATCH (co:Course) WHERE co.code IN $codes "
        f"MATCH (co)-[:{rel} {{domain:$domain}}]->(req:Course) "
        f"MATCH (req)-[:MENTIONED_IN]->(ch:Chunk {{domain:$domain}}) "
        f"RETURN DISTINCT ch.doc_id AS doc_id "
        f"LIMIT $limit"
    )

    try:
        with _session(drv) as session:
            rows = session.run(cypher, codes=codes, domain=dom, limit=int(limit))
            out = [r.get('doc_id') for r in rows if r.get('doc_id')]
    except Exception as e:
        print(f"[Neo4j] Connection error in graph_doc_ids_for_requisites, skipping: {e}")
        return []
    return out
