#!/usr/bin/env python3
"""Run test questions against the live rag-service and write answers back to CSV.

Reads `testQA_domains_30.csv` (block-structured like testQA1.csv).
Calls POST /rag/answer with explicit domain per block.
Writes `testQA_domains_30_round1.csv` with column "คำตอบที่ระบบตอบ\nรอบที่1" filled.

Usage:
  python3 scripts/run_testqa_csv_round1.py --base http://127.0.0.1:8001 \
    --in testQA_domains_30.csv --out testQA_domains_30_round1.csv
"""

from __future__ import annotations

import argparse
import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests


DOMAIN_TITLES = {
    "announcements": "Announcements — คำถาม (นักศึกษาจะถาม) และคำตอบที่คาดว่าจะตอบ",
    "regulations": "Regulations — คำถาม (นักศึกษาจะถาม) และคำตอบที่คาดว่าจะตอบ",
    "curriculum": "Curriculum — คำถาม (นักศึกษาจะถาม) และคำตอบที่คาดว่าจะตอบ",
}


@dataclass
class Row:
    raw: list[str]
    domain: Optional[str] = None
    is_header: bool = False


def detect_domain(row: list[str]) -> Optional[str]:
    if not row:
        return None
    first = (row[0] or "").strip()
    for dom, title in DOMAIN_TITLES.items():
        if first.startswith(title):
            return dom
    return None


def is_table_header(row: list[str]) -> bool:
    return len(row) >= 3 and (row[0] or "").strip() == "ลำดับ" and (row[1] or "").strip() == "คำถาม"


def call_answer(base: str, question: str, domain: str, timeout_s: float = 120.0) -> str:
    url = base.rstrip("/") + "/rag/answer"
    payload = {"question": question, "domain": domain}
    r = requests.post(url, json=payload, timeout=timeout_s)
    r.raise_for_status()
    data = r.json()
    ans = (data.get("answer") or "").strip()
    return ans


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--in", dest="inp", default="testQA_domains_30.csv")
    ap.add_argument("--out", dest="out", default="testQA_domains_30_round1.csv")
    ap.add_argument("--sleep", type=float, default=0.0, help="Optional delay between requests")
    args = ap.parse_args()

    inp = Path(args.inp)
    out = Path(args.out)

    with inp.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        rows = [r for r in reader]

    current_domain: Optional[str] = None
    wrote = []
    answered = 0

    for row in rows:
        dom = detect_domain(row)
        if dom:
            current_domain = dom
            wrote.append(row)
            continue

        if is_table_header(row):
            wrote.append(row)
            continue

        # Question rows: first col is an integer index
        if current_domain and len(row) >= 3 and (row[0] or "").strip().isdigit():
            q = (row[1] or "").strip()
            if q:
                try:
                    ans = call_answer(args.base, q, current_domain)
                except Exception as e:
                    ans = f"(error: {e})"
                # Ensure 6 columns
                while len(row) < 6:
                    row.append("")
                row[3] = ans
                answered += 1
                if args.sleep:
                    time.sleep(args.sleep)
            wrote.append(row)
            continue

        wrote.append(row)

    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(wrote)

    print(f"Wrote {out} with {answered} answers.")


if __name__ == "__main__":
    main()
