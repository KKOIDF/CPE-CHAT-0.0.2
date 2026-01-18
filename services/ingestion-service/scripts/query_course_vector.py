import argparse
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore


def main():
    p = argparse.ArgumentParser(description='Query Neo4j course vector index (course_embedding) using BGE-M3 embeddings')
    p.add_argument('query', help='text query (Thai/English)')
    p.add_argument('--domain', default='curriculum', help='domain name (default: curriculum)')
    p.add_argument('--program-name', default=None, help='If set, restrict results to courses linked from this Program (recommended)')
    p.add_argument('--topk', type=int, default=8, help='top-k results (default: 8)')
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    ingestion_root = repo_root / 'services' / 'ingestion-service'
    sys.path.insert(0, str(ingestion_root))

    if load_dotenv:
        load_dotenv(repo_root / '.env', override=False)

    os.environ.setdefault('CPE_DOMAIN', args.domain)

    from app.chroma_client import _embed_texts  # noqa: E402

    try:
        from neo4j import GraphDatabase  # type: ignore
    except Exception:
        GraphDatabase = None  # type: ignore

    if GraphDatabase is None:
        raise RuntimeError('neo4j python driver is not installed in this environment')

    uri = os.getenv('NEO4J_URI')
    user = os.getenv('NEO4J_USER') or os.getenv('NEO4J_USERNAME')
    password = os.getenv('NEO4J_PASSWORD')
    if not (uri and user and password):
        raise RuntimeError('Missing Neo4j env vars: NEO4J_URI, NEO4J_USERNAME/NEO4J_USER, NEO4J_PASSWORD')

    db = os.getenv('NEO4J_DATABASE')

    qvec = _embed_texts([args.query], is_query=True)[0]

    dom = str(args.domain).strip().lower()
    prog_name = (args.program_name or os.getenv('CPE_PROGRAM_NAME') or '').strip()
    program_key = f"{dom}|{prog_name}".lower() if prog_name else None

    if program_key:
        cypher = (
            "CALL db.index.vector.queryNodes('course_embedding', $k, $vec) "
            "YIELD node, score "
            "MATCH (p:Program {program_key:$program_key})-[:HAS_COURSE]->(node) "
            "WHERE node.domain = $domain "
            "RETURN node.code AS code, score AS score, substring(coalesce(node.description,''), 0, 140) AS preview "
            "ORDER BY score DESC"
        )
    else:
        cypher = (
            "CALL db.index.vector.queryNodes('course_embedding', $k, $vec) "
            "YIELD node, score "
            "WHERE node.domain = $domain "
            "RETURN node.code AS code, score AS score, substring(coalesce(node.description,''), 0, 140) AS preview "
            "ORDER BY score DESC"
        )

    drv = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with drv.session(database=db) if db else drv.session() as session:
            rows = session.run(cypher, k=int(args.topk), vec=qvec, domain=dom, program_key=program_key)
            out = list(rows)
    finally:
        try:
            drv.close()
        except Exception:
            pass

    if not out:
        print('No results (check that vector index exists and Course nodes have embeddings).')
        return

    print(f"Top {min(len(out), int(args.topk))} results for domain={args.domain}:")
    for i, r in enumerate(out, 1):
        code = r.get('code')
        score = r.get('score')
        preview = (r.get('preview') or '').replace('\n', ' ')
        print(f"{i:>2}. {code}  score={score:.4f}  {preview}…")


if __name__ == '__main__':
    main()
