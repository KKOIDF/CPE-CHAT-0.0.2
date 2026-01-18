import argparse
import os
import sys
from pathlib import Path
import re

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore


def main():
    p = argparse.ArgumentParser(description='Summarize curriculum semester plans in Neo4j (courses per term)')
    p.add_argument('--domain', default='curriculum', help='domain name (default: curriculum)')
    p.add_argument('--program-name', default=None, help='Program name (default: env CPE_PROGRAM_NAME or domain)')
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    ingestion_root = repo_root / 'services' / 'ingestion-service'
    sys.path.insert(0, str(ingestion_root))

    if load_dotenv:
        load_dotenv(repo_root / '.env', override=False)

    try:
        from neo4j import GraphDatabase  # type: ignore
    except Exception:
        GraphDatabase = None  # type: ignore

    if GraphDatabase is None:
        raise RuntimeError('neo4j python driver is not installed')

    uri = os.getenv('NEO4J_URI')
    user = os.getenv('NEO4J_USER') or os.getenv('NEO4J_USERNAME')
    password = os.getenv('NEO4J_PASSWORD')
    if not (uri and user and password):
        raise RuntimeError('Missing Neo4j env vars: NEO4J_URI, NEO4J_USERNAME/NEO4J_USER, NEO4J_PASSWORD')

    db = os.getenv('NEO4J_DATABASE')

    dom = str(args.domain).strip().lower() or 'curriculum'
    prog_name = (args.program_name or os.getenv('CPE_PROGRAM_NAME') or dom).strip() or dom
    program_key = f"{dom}|{prog_name}".lower()

    cypher = """
    MATCH (p:Program {program_key:$pk})-[:HAS_SEMESTER_PLAN]->(s:SemesterPlan)
    OPTIONAL MATCH (s)-[:HAS_COURSE]->(c:Course)
    RETURN s.semester_key AS key,
           s.label AS label,
           count(DISTINCT c) AS courses,
           collect(DISTINCT c.code)[0..12] AS sample
    ORDER BY key
    """

    drv = GraphDatabase.driver(uri, auth=(user, password))
    try:
        session = drv.session(database=db) if db else drv.session()
        try:
            rows = list(session.run(cypher, pk=program_key))
        finally:
            session.close()
    finally:
        try:
            drv.close()
        except Exception:
            pass

    print(f"Program: {prog_name} (domain={dom})")
    print(f"Semester plans: {len(rows)}")
    for r in rows:
        label = r.get('label') or r.get('key')
        n = int(r.get('courses') or 0)
        sample = r.get('sample') or []
        cleaned = []
        for s in sample:
            if not s:
                continue
            cs = re.sub(r'[^A-Z0-9]', '', str(s).upper())
            if cs:
                cleaned.append(cs)

        print(f"- {label}: {n} วิชา")
        if cleaned:
            print(f"  เช่น: {', '.join(cleaned)}")
        print()


if __name__ == '__main__':
    main()
