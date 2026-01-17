import re
import sqlite3
from pathlib import Path

DB = Path('indexes/curriculum/vector/sqlite/ingestion.db')


def main():
    if not DB.exists():
        raise SystemExit(f"Missing {DB}. Run ingestion first.")

    conn = sqlite3.connect(str(DB))
    rows = conn.execute("SELECT text FROM documents LIMIT 300").fetchall()
    sample = conn.execute("SELECT text FROM documents WHERE text LIKE ? LIMIT 1", ("%รหัส%",)).fetchone()
    conn.close()

    text = "\n".join(r[0] for r in rows if r and r[0])
    ascii_digits = len(re.findall(r"[0-9]", text))
    thai_digits = len(re.findall(r"[\u0E50-\u0E59]", text))
    any_digits = len(re.findall(r"[0-9\u0E50-\u0E59]", text))

    print(f"DB: {DB}")
    print(f"ascii_digits={ascii_digits}")
    print(f"thai_digits={thai_digits}")
    print(f"any_digits={any_digits}")

    print("\n--- sample chunk with 'รหัส' ---")
    if sample and sample[0]:
        print(sample[0][:1200])
    else:
        print("no_chunk_with_รหัส")


if __name__ == '__main__':
    main()
