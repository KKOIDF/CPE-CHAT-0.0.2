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
    p.add_argument('--program-name', default=None, help='Program name for (:Program) node (default: env CPE_PROGRAM_NAME or domain)')
    p.add_argument('--reset-program', action='store_true', help='Reset Program/Category/SemesterPlan links for this program_key before rebuilding course schema')
    p.add_argument('--no-course-schema', action='store_true', help='Only upsert Chunk/Course mentions graph; skip Program/Course.description+embedding upsert')
    p.add_argument('--max-codes-per-chunk', type=int, default=3, help='Heuristic: skip chunks mentioning too many course codes (default: 3)')
    p.add_argument('--min-chunk-chars', type=int, default=80, help='Heuristic: skip very short chunks for course description aggregation (default: 80)')
    p.add_argument('--max-chunks-per-course', type=int, default=4, help='Max number of chunks to concatenate into Course.description (default: 4)')
    p.add_argument('--primary-only-when-many', type=int, default=1, help='If 1, tolerate many codes by assigning chunk to a single primary code (default: 1)')
    p.add_argument('--primary-code-window', type=int, default=140, help='When tolerating many codes, primary code must appear early within this dense-char window (default: 140)')
    p.add_argument('--course-limit', type=int, default=0, help='Limit number of Course nodes to embed/upsert (0 = no limit)')
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
    from app.neo4j_graph import upsert_chunks_to_neo4j, upsert_program_courses_to_neo4j_from_chunks, reset_program_schema_in_neo4j

    data = read_toon(str(toon_path))
    chunks = data.get('chunks') if isinstance(data, dict) else data
    chunks = chunks if isinstance(chunks, list) else []

    n_chunks = upsert_chunks_to_neo4j(chunks, domain=args.domain)
    print(f"✅ Upserted {n_chunks} chunks to Neo4j for domain={args.domain}")

    if not args.no_course_schema:
        if args.reset_program:
            reset_program_schema_in_neo4j(domain=args.domain, program_name=args.program_name)
        n_courses = upsert_program_courses_to_neo4j_from_chunks(
            chunks,
            domain=args.domain,
            program_name=args.program_name,
            max_codes_per_chunk=int(args.max_codes_per_chunk),
            min_chunk_chars=int(args.min_chunk_chars),
            max_chunks_per_course=int(args.max_chunks_per_course),
            primary_only_when_many=bool(int(args.primary_only_when_many)),
            primary_code_window=int(args.primary_code_window),
            course_limit=int(args.course_limit),
        )
        print(f"✅ Upserted {n_courses} Course nodes (Program+description+embedding) for domain={args.domain}")


if __name__ == '__main__':
    main()
