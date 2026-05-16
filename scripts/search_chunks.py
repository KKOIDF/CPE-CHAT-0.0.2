from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = REPO_ROOT / 'services' / 'rag-service'
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.config import RAG_GLOBAL_SQLITE_PATH  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--keyword', required=True)
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()

    conn = sqlite3.connect(str(Path(RAG_GLOBAL_SQLITE_PATH).resolve()))
    conn.row_factory = sqlite3.Row
    like = f"%{args.keyword}%"
    rows = conn.execute(
        'SELECT stable_chunk_id, domain, source_name, section_heading, page, substr(text,1,220) AS preview FROM rag_chunks WHERE text LIKE ? OR title LIKE ? OR source_name LIKE ? OR section_heading LIKE ? LIMIT ?',
        (like, like, like, like, args.limit),
    ).fetchall()
    print(f"sqlite_path: {Path(RAG_GLOBAL_SQLITE_PATH).resolve()}")
    print(f"matches: {len(rows)}")
    for row in rows:
        print(
            f"- {row['stable_chunk_id']} domain={row['domain']} source={row['source_name']} page={row['page']} section={row['section_heading'] or '-'} preview={row['preview']}"
        )
    conn.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
