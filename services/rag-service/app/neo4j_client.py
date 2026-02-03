import os
import re
from typing import List, Optional, Set

try:
    from neo4j import GraphDatabase  # type: ignore
except Exception:  # pragma: no cover
    GraphDatabase = None  # type: ignore


_THAI_TO_ARABIC = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')

COURSE_CODE_PATTERNS = [
    re.compile(r"\b[0-9\u0E50-\u0E59]{6}\b"),
    re.compile(r"\b[0-9\u0E50-\u0E59]{3}[-–][0-9\u0E50-\u0E59]{3}\b"),
    re.compile(r"\b[0-9\u0E50-\u0E59]{3}[ .\t]+[0-9\u0E50-\u0E59]{3}\b"),
    re.compile(r"\b[A-Z]{2,6}[-–]?[0-9]{3}\b"),
]


def extract_course_codes(text: str) -> Set[str]:
    if not text:
        return set()
    norm = text.translate(_THAI_TO_ARABIC)
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
    return GraphDatabase.driver(uri, auth=(user, password))


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
    drv = _driver()
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

    with _session(drv) as session:
        rows = session.run(cypher, codes=codes, domain=dom, limit=limit)
        out = [r.get('doc_id') for r in rows if r.get('doc_id')]

    try:
        drv.close()
    except Exception:
        pass

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
    drv = _driver()
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
    finally:
        try:
            drv.close()
        except Exception:
            pass

    # preserve order + uniqueness
    seen = set(seed)
    uniq: List[str] = []
    for d in out:
        if d and d not in seen:
            uniq.append(d)
            seen.add(d)
    return uniq
