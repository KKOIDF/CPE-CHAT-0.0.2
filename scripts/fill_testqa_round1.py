#!/usr/bin/env python3
"""Fill `testQA1.csv` with system answers (round 1).

Reads the CSV, detects section (announcements/curriculum/regulations), and for each
row with a question, calls the local RAG FastAPI app via TestClient:
  POST /rag/answer  {"domain": <domain>, "question": <question>}

Writes answers into the "คำตอบที่ระบบตอบ\nรอบที่1" column.

Usage:
  python scripts/fill_testqa_round1.py --in testQA1.csv

By default, creates a .bak backup and overwrites the input file.
"""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path
from typing import Optional


def _is_int(s: str) -> bool:
    try:
        int(s.strip())
        return True
    except Exception:
        return False


def _detect_domain_from_section_line(line0: str) -> Optional[str]:
    s = (line0 or "").strip().lower()
    if s.startswith("announcements"):
        return "announcements"
    if s.startswith("curriculum"):
        return "curriculum"
    if s.startswith("regulations"):
        return "regulations"
    return None


def _find_round1_col(header_row: list[str]) -> Optional[int]:
    # Header cell may contain a literal newline, or may be split depending on CSV authoring.
    for i, cell in enumerate(header_row):
        c = (cell or "").replace("\r", "")
        if "คำตอบที่ระบบตอบ" in c and "รอบที่1" in c:
            return i
        if c.strip() == "คำตอบที่ระบบตอบ" and i + 1 < len(header_row) and "รอบที่1" in (header_row[i + 1] or ""):
            return i
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="in_path", default="testQA1.csv")
    p.add_argument("--overwrite", action="store_true", help="Overwrite input (default: yes)")
    p.add_argument("--no-backup", action="store_true", help="Do not create .bak")
    args = p.parse_args()

    in_path = Path(args.in_path)
    if not in_path.exists():
        raise SystemExit(f"Input not found: {in_path}")

    # Import FastAPI app via service path.
    repo_root = Path(__file__).resolve().parents[1]
    service_dir = repo_root / "services" / "rag-service"
    app_dir = service_dir / "app"

    import sys

    sys.path.insert(0, str(service_dir))
    sys.path.insert(0, str(app_dir))

    from fastapi.testclient import TestClient  # type: ignore
    from app.main import app  # type: ignore

    client = TestClient(app)

    # Read all rows first (preserve structure)
    rows: list[list[str]] = []
    with in_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for r in reader:
            rows.append(r)

    # Walk rows, track section/domain and header mapping.
    current_domain: Optional[str] = None
    round1_col: Optional[int] = None
    # Default column guess: [ลำดับ, คำถาม, คำตอบที่คาดว่าจะตอบ, r1, r2, r3]
    QUESTION_COL = 1

    filled = 0
    skipped = 0
    errors = 0

    for idx, r in enumerate(rows):
        if not r:
            continue

        # Detect section markers
        dom = _detect_domain_from_section_line(r[0])
        if dom:
            current_domain = dom
            round1_col = None
            continue

        # Detect header row for a section
        if (r[0] or "").strip() == "ลำดับ" and len(r) >= 4:
            round1_col = _find_round1_col(r)
            if round1_col is None:
                # Fallback to 4th column
                round1_col = 3 if len(r) > 3 else None
            continue

        # Fill for any known domain where a question is present.
        if current_domain not in ("announcements", "curriculum", "regulations"):
            continue

        if not _is_int(r[0] or ""):
            continue

        if round1_col is None:
            # If we didn't see a header row, assume column 3 is round1.
            round1_col = 3

        # Ensure row has enough columns
        if len(r) <= round1_col:
            r.extend([""] * (round1_col + 1 - len(r)))

        question = (r[QUESTION_COL] if len(r) > QUESTION_COL else "").strip()
        if not question:
            skipped += 1
            continue

        # If already filled, skip
        if (r[round1_col] or "").strip():
            skipped += 1
            continue

        payload = {"domain": current_domain, "question": question}
        try:
            resp = client.post("/rag/answer", json=payload)
            if resp.status_code != 200:
                errors += 1
                r[round1_col] = f"(error {resp.status_code}) {resp.text[:200]}"
                continue
            data = resp.json()
            ans = (data.get("answer") or "").strip()
            r[round1_col] = ans
            filled += 1
        except Exception as e:
            errors += 1
            r[round1_col] = f"(exception) {e}"

    if not args.no_backup:
        backup = in_path.with_suffix(in_path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(in_path, backup)

    # Overwrite in place (default)
    out_path = in_path
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    print(f"Filled: {filled}, skipped: {skipped}, errors: {errors}")
    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
