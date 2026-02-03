import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag_logic import rag_query_domain


def main() -> None:
    qs = [
        ("announcements", "ประกาศสอบซ้อนทำอย่างไร"),
        ("regulations", "เกณฑ์ได้คะแนน 0 ทำอย่างไร"),
        ("curriculum", "เกณฑ์การสำเร็จการศึกษา หลักสูตรวิศวกรรมคอมพิวเตอร์"),
    ]

    for dom, q in qs:
        r = rag_query_domain(q, dom)
        ctxs = r.get("contexts") or []
        print("\n===", dom, "===")
        print("contexts", len(ctxs), "token_est", r.get("token_est"))
        print(
            "top_sources",
            [
                ((c.get("source") or c.get("path")), c.get("page_start"), c.get("score_rrf"))
                for c in ctxs[:5]
            ],
        )


if __name__ == "__main__":
    main()
