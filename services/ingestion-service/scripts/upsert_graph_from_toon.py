import argparse
import os
from pathlib import Path
import sys

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore


def main():
    p = argparse.ArgumentParser(description='Upsert curriculum graph into Neo4j from a TOON chunks file')
    p.add_argument('--domain', default='curriculum', help='domain name (default: curriculum)')
    p.add_argument('--toon', default=None, help='Path to chunks TOON file (default: data/db/<domain>_chunks.toon in repo root)')
    args = p.parse_args()

    # __file__ = .../services/ingestion-service/scripts/upsert_graph_from_toon.py
    # parents[3] = repo root (..../CPE-CHAT-0.0.2)
    repo_root = Path(__file__).resolve().parents[3]
    ingestion_root = repo_root / 'services' / 'ingestion-service'
    sys.path.insert(0, str(ingestion_root))

    # Load env vars (Neo4j credentials, etc.)
    if load_dotenv:
        load_dotenv(repo_root / '.env', override=False)
    default_toon = repo_root / 'data' / 'db' / f"{args.domain}_chunks.toon"
    toon_path = Path(args.toon) if args.toon else default_toon

    if not toon_path.exists():
        raise FileNotFoundError(f"TOON not found: {toon_path}")

    os.environ.setdefault('CPE_DOMAIN', args.domain)

    from app.toon_converter import read_toon
    from app.neo4j_graph import upsert_chunks_to_neo4j

    data = read_toon(str(toon_path))
    chunks = data.get('chunks') if isinstance(data, dict) else data
    chunks = chunks if isinstance(chunks, list) else []

    n = upsert_chunks_to_neo4j(chunks, domain=args.domain)
    print(f"✅ Upserted {n} chunks to Neo4j for domain={args.domain}")


if __name__ == '__main__':
    main()
