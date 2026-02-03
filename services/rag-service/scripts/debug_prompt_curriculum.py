import re
import sys
from pathlib import Path

# Ensure local imports work when running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag_logic import rag_query_domain

QUESTION = "โครงสร้างหลักสูตรวิศวกรรมคอมพิวเตอร์มีหน่วยกิตรวมกี่หน่วยกิต"

def main():
    r = rag_query_domain(QUESTION, "curriculum")
    p = r["prompt"]
    print("prompt_len:", len(p))
    print("has_หน่วยกิต:", "หน่วยกิต" in p)

    blocks = []
    # Extract packed blocks like: [src/page] text
    for m in re.finditer(r"\[([^\]]+?/\d+)\]\s*", p):
        cite = m.group(1)
        start = m.end()
        next_m = re.search(r"\n\n\[[^\]]+?/\d+\]\s*", p[start:])
        end = start + (next_m.start() if next_m else len(p[start:]))
        text = (p[start:end] or "").strip()
        if text:
            blocks.append((cite, text))

    print("ctx_blocks:", len(blocks))

    pat = re.compile(r"(รวม(?:ทั้งสิ้น)?|รวมไม่น้อยกว่า|ไม่น้อยกว่า)[^\d]{0,30}(\d{2,3})\s*หน่วยกิต")
    hits = []
    for cite, text in blocks:
        for mm in pat.finditer(text):
            hits.append((mm.group(0), cite))

    print("credit_hits:", len(hits))
    for h, cite in hits[:10]:
        print("-", h, "[", cite, "]")

    pat2 = re.compile(r"(\d{2,3})\s*หน่วยกิต")
    hits2 = []
    for cite, text in blocks:
        for mm in pat2.finditer(text):
            hits2.append((mm.group(0), cite))

    uniq = []
    seen = set()
    for h, cite in hits2:
        key = (h, cite)
        if key not in seen:
            uniq.append((h, cite))
            seen.add(key)

    print("any_credit_snippets:", len(uniq))
    for h, cite in uniq[:20]:
        print("-", h, "[", cite, "]")


if __name__ == "__main__":
    main()
