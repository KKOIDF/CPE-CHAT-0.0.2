import argparse
import sys
from pathlib import Path
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag_logic import rag_query_domain
from app.chroma_client import semantic_search_domain
from app.sqlite_client import keyword_search, fetch_docs_with_path, domain_sqlite_path
from app.neo4j_client import graph_expand_from_seed_chunks

try:
    from neo4j import GraphDatabase  # type: ignore
except Exception:
    GraphDatabase = None  # type: ignore


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--domain", default="curriculum")
    p.add_argument(
        "--question",
        default="เกณฑ์การสำเร็จการศึกษา หลักสูตรวิศวกรรมคอมพิวเตอร์",
    )
    args = p.parse_args()

    dom = args.domain
    print('NEO4J_DATABASE', os.getenv('NEO4J_DATABASE'))
    print('NEO4J_URI_set', bool(os.getenv('NEO4J_URI')))
    print('NEO4J_USER_set', bool(os.getenv('NEO4J_USER') or os.getenv('NEO4J_USERNAME')))
    print('NEO4J_PASSWORD_set', bool(os.getenv('NEO4J_PASSWORD')))
    sqlite_path = domain_sqlite_path(dom)
    sem = semantic_search_domain(args.question, top_k=20, domain=dom)
    kw_ids = keyword_search(args.question, limit=30, sqlite_path=sqlite_path)
    kw_docs = fetch_docs_with_path(kw_ids, sqlite_path=sqlite_path)

    seed_ids = []
    for d in (sem[:8] + kw_docs[:8]):
        did = d.get('doc_id')
        if did and did not in seed_ids:
            seed_ids.append(did)

    neighbor_ids = graph_expand_from_seed_chunks(seed_ids, domain=dom, window=2, limit=80) if seed_ids else []
    print('sem_top', len(sem), 'kw_docs', len(kw_docs))
    print('seed_ids', len(seed_ids))
    print('neighbor_ids', len(neighbor_ids), 'sample', neighbor_ids[:10])

    if GraphDatabase is not None and seed_ids and os.getenv('NEO4J_URI') and (os.getenv('NEO4J_USER') or os.getenv('NEO4J_USERNAME')) and os.getenv('NEO4J_PASSWORD'):
        uri = os.getenv('NEO4J_URI')
        user = os.getenv('NEO4J_USER') or os.getenv('NEO4J_USERNAME')
        password = os.getenv('NEO4J_PASSWORD')
        db = os.getenv('NEO4J_DATABASE')
        drv = GraphDatabase.driver(uri, auth=(user, password))
        try:
            session_kwargs = {'database': db} if db else {}
            with drv.session(**session_kwargs) as session:
                c1 = session.run(
                    "MATCH (ch:Chunk) WHERE ch.doc_id IN $seed RETURN count(ch) AS c",
                    seed=seed_ids,
                ).single()["c"]
                c2 = session.run(
                    "MATCH (ch:Chunk {domain:$domain}) WHERE ch.doc_id IN $seed RETURN count(ch) AS c",
                    seed=seed_ids,
                    domain=dom,
                ).single()["c"]
                print('neo4j_seed_matches_any_domain', c1)
                print('neo4j_seed_matches_domain', c2)

                rows = session.run(
                    "MATCH (ch:Chunk) RETURN ch.domain AS d, count(*) AS c ORDER BY c DESC LIMIT 5"
                )
                dom_counts = [(r.get('d'), r.get('c')) for r in rows]
                print('neo4j_chunk_domain_counts_top5', dom_counts)
        finally:
            try:
                drv.close()
            except Exception:
                pass

    r = rag_query_domain(args.question, dom)
    print("contexts", len(r.get("contexts") or []))
    top = (r.get("contexts") or [])[:10]
    top_ids = [c.get("doc_id") for c in top]
    print("top_doc_ids", top_ids)
    print('top_contains_neighbors', any(d in set(neighbor_ids) for d in top_ids if d))


if __name__ == "__main__":
    main()
