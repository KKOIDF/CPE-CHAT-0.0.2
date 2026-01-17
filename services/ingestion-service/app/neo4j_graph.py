import os
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:
    from neo4j import GraphDatabase  # type: ignore
except Exception:  # pragma: no cover
    GraphDatabase = None  # type: ignore


COURSE_CODE_PATTERNS = [
    # Thai university common: 6 digits course codes
    re.compile(r"\b\d{6}\b"),
    # Hyphenated variant: 261-101
    re.compile(r"\b\d{3}-\d{3}\b"),
    # English style: CPE101, ENG-101
    re.compile(r"\b[A-Z]{2,6}-?\d{3}\b"),
]


def _extract_course_codes(text: str) -> Set[str]:
    if not text:
        return set()
    out: Set[str] = set()
    for patt in COURSE_CODE_PATTERNS:
        for m in patt.findall(text):
            out.add(m.replace('-', ''))
    return out


def _neo4j_driver():
    if GraphDatabase is None:
        return None
    uri = os.getenv('NEO4J_URI')
    user = os.getenv('NEO4J_USER') or os.getenv('NEO4J_USERNAME')
    password = os.getenv('NEO4J_PASSWORD')
    if not (uri and user and password):
        return None
    return GraphDatabase.driver(uri, auth=(user, password))


def _ensure_schema(tx):
    # Constraints/indexes are idempotent on Neo4j 5+ with IF NOT EXISTS
    tx.run("CREATE CONSTRAINT chunk_doc_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.doc_id IS UNIQUE")
    tx.run("CREATE CONSTRAINT course_code IF NOT EXISTS FOR (c:Course) REQUIRE c.code IS UNIQUE")
    tx.run("CREATE INDEX chunk_domain IF NOT EXISTS FOR (c:Chunk) ON (c.domain)")


def upsert_chunks_to_neo4j(chunks: Iterable[Dict[str, Any]], domain: Optional[str] = None) -> int:
    """Upsert chunk nodes and Course mentions into Neo4j.

    This is intentionally lightweight: it links course codes to chunks via (:Course)-[:MENTIONED_IN]->(:Chunk).
    If Neo4j env vars are not configured, it becomes a no-op.

        Required env:
            - NEO4J_URI (e.g. bolt://localhost:7687)
            - NEO4J_USERNAME (or NEO4J_USER)
            - NEO4J_PASSWORD
    """
    drv = _neo4j_driver()
    if not drv:
        return 0

    neo4j_db = os.getenv('NEO4J_DATABASE')

    domain = (domain or os.getenv('CPE_DOMAIN', 'curriculum')).strip().lower() or 'curriculum'

    rows: List[Tuple[str, str, int, int, List[str]]] = []
    for c in chunks:
        doc_id = str(c.get('doc_id') or '')
        if not doc_id:
            continue
        text = str(c.get('text') or '')
        path = str(c.get('path') or '')
        try:
            page_start = int(c.get('page_start') or 0)
        except Exception:
            page_start = 0
        try:
            page_end = int(c.get('page_end') or page_start)
        except Exception:
            page_end = page_start
        codes = sorted(_extract_course_codes(text))
        # Store only lightweight metadata in Neo4j; full text stays in SQLite/Chroma
        rows.append((doc_id, path, page_start, page_end, codes))

    if not rows:
        return 0

    def _apply_schema(tx):
        _ensure_schema(tx)

    def _upsert_batch(tx, batch_rows):
        tx.run(
            """
            UNWIND $rows AS r
            MERGE (ch:Chunk {doc_id: r.doc_id})
            SET ch.path = r.path,
                ch.page_start = r.page_start,
                ch.page_end = r.page_end,
                ch.domain = $domain
            WITH ch, r
            UNWIND r.codes AS code
            MERGE (co:Course {code: code})
            MERGE (co)-[:MENTIONED_IN]->(ch)
            """,
            rows=batch_rows,
            domain=domain,
        )

    with drv.session(database=neo4j_db) as session:
        # Neo4j Aura forbids mixing schema modification + writes in one transaction.
        session.execute_write(_apply_schema)

        batch_size = int(os.getenv('NEO4J_UPSERT_BATCH', '200'))
        total = len(rows)
        sent = 0
        for i in range(0, total, batch_size):
            sub = rows[i:i+batch_size]
            batch_rows = [
                {
                    'doc_id': doc_id,
                    'path': path,
                    'page_start': page_start,
                    'page_end': page_end,
                    'codes': codes,
                }
                for (doc_id, path, page_start, page_end, codes) in sub
            ]
            session.execute_write(_upsert_batch, batch_rows)
            sent += len(sub)
            if sent % (batch_size * 5) == 0 or sent == total:
                print(f"[Neo4j] Upserted {sent}/{total} chunks...")

    try:
        drv.close()
    except Exception:
        pass

    return len(rows)
