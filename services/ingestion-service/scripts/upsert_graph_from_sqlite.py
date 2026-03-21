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
    p.add_argument('--focus-code', default=None, help='Optional course code (e.g., LNG120) to only upsert chunks whose text mentions this code')
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

    repo_root = Path(__file__).resolve().parents[3]
    ingestion_root = repo_root / 'services' / 'ingestion-service'
    sys.path.insert(0, str(ingestion_root))

    if load_dotenv:
        load_dotenv(repo_root / '.env', override=False)

    # Make config resolve to indexes/<domain>/...
    os.environ.setdefault('CPE_DOMAIN', args.domain)
    os.environ.setdefault('CPE_INDEX_ROOT', str(repo_root / 'indexes'))

    from app.config import SQLITE_PATH  # noqa: E402
    from app.neo4j_graph import upsert_chunks_to_neo4j, upsert_program_courses_to_neo4j_from_chunks, reset_program_schema_in_neo4j  # noqa: E402

    sqlite_path = Path(SQLITE_PATH)
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite not found: {sqlite_path}. Run ingestion first.")

    conn = sqlite3.connect(str(sqlite_path))
    cur = conn.cursor()

    # Use rowid as a stable per-row ordering key (works even if schema has no explicit id)
    q = "SELECT rowid as chunk_id, doc_id, path, page_start, page_end, text FROM documents"
    params: list[str] = []
    if args.focus_code:
        # Best-effort LIKE filter for quick testing. We include both dense and spaced variants.
        code = str(args.focus_code).strip().upper().replace('-', '')
        if code:
            spaced = code
            if len(code) >= 6 and code[:3].isalpha() and code[3:].isdigit():
                spaced = f"{code[:3]} {code[3:]}"
            q += " WHERE text LIKE ? OR text LIKE ?"
            params = [f"%{code}%", f"%{spaced}%"]
    q += " ORDER BY rowid ASC"
    if args.limit and args.limit > 0:
        q += f" LIMIT {int(args.limit)}"

    rows = cur.execute(q, params).fetchall() if params else cur.execute(q).fetchall()
    conn.close()

    chunks = [
        {
            'chunk_id': r[0],
            'doc_id': r[1],
            'path': r[2],
            'page_start': r[3],
            'page_end': r[4],
            'text': r[5],
        }
        for r in rows
        if r and r[1]
    ]

    n_chunks = upsert_chunks_to_neo4j(chunks, domain=args.domain)
    print(f"✅ Upserted {n_chunks} chunks to Neo4j for domain={args.domain} (from SQLite)")

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
