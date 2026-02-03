import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag_logic import rag_query_domain


def main():
    r = rag_query_domain("ประกาศสอบซ้อนทำอย่างไร", "announcements")
    lines = (r.get("prompt") or "").splitlines()
    for ln in lines[:35]:
        print(ln)


if __name__ == "__main__":
    main()
