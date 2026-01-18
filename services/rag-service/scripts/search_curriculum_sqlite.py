import argparse
import sqlite3
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--sqlite', default=str(Path('indexes/curriculum/vector/sqlite/ingestion.db')))
    p.add_argument('--needle', default='130')
    p.add_argument('--limit', type=int, default=20)
    args = p.parse_args()

    conn = sqlite3.connect(args.sqlite)
    try:
        cur = conn.execute(
            "SELECT doc_id, path, page_start, substr(text, 1, 200) as snippet FROM documents WHERE text LIKE ? LIMIT ?",
            (f"%{args.needle}%", args.limit),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    print('matches:', len(rows))
    for doc_id, path, page, snippet in rows:
        print('---')
        print(f"{doc_id} | {path}/{page}")
        print(snippet.replace('\n',' '))


if __name__ == '__main__':
    main()
