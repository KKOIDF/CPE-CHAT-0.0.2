import os
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:
    from neo4j import GraphDatabase  # type: ignore
except Exception:  # pragma: no cover
    GraphDatabase = None  # type: ignore


_THAI_TO_ARABIC = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')

COURSE_CODE_PATTERNS = [
    # Thai university common: 6 digits course codes (261101)
    re.compile(r"\b[0-9\u0E50-\u0E59]{6}\b"),
    # Hyphenated variant: 261-101
    re.compile(r"\b[0-9\u0E50-\u0E59]{3}[-–][0-9\u0E50-\u0E59]{3}\b"),
    # Spaced/dotted variant: 261 101, 261.101
    re.compile(r"\b[0-9\u0E50-\u0E59]{3}[ .\t]+[0-9\u0E50-\u0E59]{3}\b"),
    # English style: CPE101, ENG-101
    re.compile(r"\b[A-Z]{2,6}[-–]?[0-9]{3}\b"),
]


def _extract_course_codes(text: str) -> Set[str]:
    if not text:
        return set()
    norm = text.translate(_THAI_TO_ARABIC)
    out: Set[str] = set()
    for patt in COURSE_CODE_PATTERNS:
        for m in patt.findall(norm):
            code = m.replace('-', '').replace('–', '').replace(' ', '').replace('\t', '').replace('.', '')
            out.add(code)
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
    tx.run("CREATE CONSTRAINT document_key IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_key IS UNIQUE")
    tx.run("CREATE INDEX chunk_domain IF NOT EXISTS FOR (c:Chunk) ON (c.domain)")
    tx.run("CREATE INDEX document_domain IF NOT EXISTS FOR (d:Document) ON (d.domain)")


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

    rows: List[Tuple[str, str, int, int, int, List[str]]] = []
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
        try:
            chunk_id = int(c.get('chunk_id') or 0)
        except Exception:
            chunk_id = 0
        codes = sorted(_extract_course_codes(text))
        # Store only lightweight metadata in Neo4j; full text stays in SQLite/Chroma
        rows.append((doc_id, path, page_start, page_end, chunk_id, codes))

    if not rows:
        return 0

    def _apply_schema(tx):
        _ensure_schema(tx)

    def _upsert_batch(tx, batch_rows):
        tx.run(
            """
            UNWIND $rows AS r
            MERGE (d:Document {doc_key: r.doc_key})
            SET d.path = r.path,
                d.domain = $domain
            MERGE (ch:Chunk {doc_id: r.doc_id})
            SET ch.path = r.path,
                ch.page_start = r.page_start,
                ch.page_end = r.page_end,
                ch.chunk_id = r.chunk_id,
                ch.domain = $domain
            MERGE (d)-[:HAS_CHUNK]->(ch)
            WITH ch, r
            UNWIND r.codes AS code
            MERGE (co:Course {code: code})
            MERGE (co)-[:MENTIONED_IN]->(ch)
            """,
            rows=batch_rows,
            domain=domain,
        )

    def _upsert_next_edges(tx, edges_rows):
        tx.run(
            """
            UNWIND $edges AS e
            MATCH (a:Chunk {doc_id: e.a})
            MATCH (b:Chunk {doc_id: e.b})
            MERGE (a)-[:NEXT {domain:$domain}]->(b)
            """,
            edges=edges_rows,
            domain=domain,
        )

    with drv.session(database=neo4j_db) as session:
        # Neo4j Aura forbids mixing schema modification + writes in one transaction.
        session.execute_write(_apply_schema)

        batch_size = int(os.getenv('NEO4J_UPSERT_BATCH', '200'))
        total = len(rows)
        sent = 0
        # Build NEXT edges per document (best-effort ordering)
        by_path: Dict[str, List[Tuple[int, int, str]]] = {}
        for (doc_id, path, page_start, _page_end, chunk_id, _codes) in rows:
            by_path.setdefault(path, []).append((page_start, chunk_id, doc_id))
        edges: List[Dict[str, str]] = []
        for path, items in by_path.items():
            items.sort(key=lambda x: (x[0], x[1]))
            for j in range(len(items) - 1):
                edges.append({'a': items[j][2], 'b': items[j+1][2]})

        for i in range(0, total, batch_size):
            sub = rows[i:i+batch_size]
            batch_rows = [
                {
                    'doc_id': doc_id,
                    'path': path,
                    'page_start': page_start,
                    'page_end': page_end,
                    'chunk_id': chunk_id,
                    'doc_key': f"{domain}|{path}",
                    'codes': codes,
                }
                for (doc_id, path, page_start, page_end, chunk_id, codes) in sub
            ]
            session.execute_write(_upsert_batch, batch_rows)
            sent += len(sub)
            if sent % (batch_size * 5) == 0 or sent == total:
                print(f"[Neo4j] Upserted {sent}/{total} chunks...")

        # NEXT edges in separate write batches
        if edges:
            total_e = len(edges)
            done = 0
            for i in range(0, total_e, batch_size * 2):
                sube = edges[i:i + batch_size * 2]
                session.execute_write(_upsert_next_edges, sube)
                done += len(sube)
                if done % (batch_size * 10) == 0 or done == total_e:
                    print(f"[Neo4j] Upserted NEXT {done}/{total_e} edges...")

    try:
        drv.close()
    except Exception:
        pass

    return len(rows)
