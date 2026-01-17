import os
import re
from typing import Any, Dict, List, Optional, Set

try:
    from neo4j import GraphDatabase  # type: ignore
except Exception:  # pragma: no cover
    GraphDatabase = None  # type: ignore


COURSE_CODE_PATTERNS = [
    re.compile(r"\b\d{6}\b"),
    re.compile(r"\b\d{3}-\d{3}\b"),
    re.compile(r"\b[A-Z]{2,6}-?\d{3}\b"),
]


def extract_course_codes(text: str) -> Set[str]:
    if not text:
        return set()
    out: Set[str] = set()
    for patt in COURSE_CODE_PATTERNS:
        for m in patt.findall(text):
            out.add(m.replace('-', ''))
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

    with drv.session() as session:
        rows = session.run(cypher, codes=codes, domain=dom, limit=limit)
        out = [r.get('doc_id') for r in rows if r.get('doc_id')]

    try:
        drv.close()
    except Exception:
        pass

    return out
