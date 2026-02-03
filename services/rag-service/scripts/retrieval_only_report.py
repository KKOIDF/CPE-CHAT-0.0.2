import argparse
import textwrap
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag_logic import retrieve_by_domain


def _snip(s: str, n: int = 220) -> str:
    s = (s or "").strip().replace("\n", " ")
    s = " ".join(s.split())
    return s[:n] + ("…" if len(s) > n else "")


def main() -> None:
    p = argparse.ArgumentParser(description="Retrieval-only report (no LLM)")
    p.add_argument("--top", type=int, default=5, help="how many contexts to print per query")
    args = p.parse_args()

    queries = [
        ("announcements", "ประกาศสอบซ้อนทำอย่างไร"),
        ("regulations", "เกณฑ์ได้คะแนน 0 ทำอย่างไร"),
        ("curriculum", "เกณฑ์การสำเร็จการศึกษา หลักสูตรวิศวกรรมคอมพิวเตอร์"),
    ]

    for dom, q in queries:
        ctxs = retrieve_by_domain(q, dom)
        print("\n" + "=" * 90)
        print(f"DOMAIN: {dom}")
        print(f"Q: {q}")
        print(f"contexts={len(ctxs)}")
        for i, c in enumerate(ctxs[: args.top], 1):
            src = c.get("source") or c.get("path")
            page = c.get("page_start")
            score = c.get("score_rrf")
            print("-" * 90)
            print(f"[{i}] src={src} page={page} score_rrf={score}")
            print(textwrap.fill(_snip(c.get('text') or ''), width=100))


if __name__ == "__main__":
    main()
