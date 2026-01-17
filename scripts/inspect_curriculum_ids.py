import re
import sqlite3
from pathlib import Path

DB = Path('indexes/curriculum/vector/sqlite/ingestion.db')


def main():
    if not DB.exists():
        raise SystemExit(f"Missing {DB}")

    conn = sqlite3.connect(str(DB))
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    print('tables', tables)

    def show(table: str):
        try:
            rows = conn.execute(f"SELECT doc_id FROM {table} WHERE doc_id IS NOT NULL LIMIT 10").fetchall()
        except Exception as e:
            print(f"{table}: error {e}")
            return
        ids = [r[0] for r in rows if r and r[0]]
        print(f"{table}: sample_doc_ids", ids)
        if ids:
            suffix = sum(1 for d in ids if re.search(r"-\d+$", str(d)))
            print(f"{table}: sample_suffix_dash_number", suffix, '/', len(ids))

    for t in ('documents', 'chunks', 'docs_fts'):
        if t in tables:
            show(t)

    # distribution check on documents.doc_id
    if 'documents' in tables:
        try:
            c_total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            c_dash = conn.execute("SELECT COUNT(*) FROM documents WHERE doc_id GLOB '*-[0-9][0-9]*'").fetchone()[0]
            print('documents_count', c_total)
            print('documents_doc_id_like_*-[digits]*', c_dash)
        except Exception as e:
            print('documents stats error', e)

    conn.close()


if __name__ == '__main__':
    main()
