import argparse
import os
import sqlite3
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore


def main():
    p = argparse.ArgumentParser(description='Upsert curriculum graph into Neo4j from per-domain SQLite (indexes/<domain>/vector/sqlite/ingestion.db)')
    p.add_argument('--domain', default='curriculum', help='domain name (default: curriculum)')
    p.add_argument('--limit', type=int, default=0, help='optional limit for quick testing (0 = no limit)')
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    ingestion_root = repo_root / 'services' / 'ingestion-service'
    sys.path.insert(0, str(ingestion_root))

    if load_dotenv:
        load_dotenv(repo_root / '.env', override=False)

    # Make config resolve to indexes/<domain>/...
    os.environ.setdefault('CPE_DOMAIN', args.domain)
    os.environ.setdefault('CPE_INDEX_ROOT', str(repo_root / 'indexes'))

    from app.config import SQLITE_PATH  # noqa: E402
    from app.neo4j_graph import upsert_chunks_to_neo4j  # noqa: E402

    sqlite_path = Path(SQLITE_PATH)
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite not found: {sqlite_path}. Run ingestion first.")

    conn = sqlite3.connect(str(sqlite_path))
    cur = conn.cursor()

    q = "SELECT doc_id, path, page_start, page_end, text FROM documents"
    if args.limit and args.limit > 0:
        q += f" LIMIT {int(args.limit)}"

    rows = cur.execute(q).fetchall()
    conn.close()

    chunks = [
        {
            'doc_id': r[0],
            'path': r[1],
            'page_start': r[2],
            'page_end': r[3],
            'text': r[4],
        }
        for r in rows
        if r and r[0]
    ]

    n = upsert_chunks_to_neo4j(chunks, domain=args.domain)
    print(f"✅ Upserted {n} chunks to Neo4j for domain={args.domain} (from SQLite)")


if __name__ == '__main__':
    main()
