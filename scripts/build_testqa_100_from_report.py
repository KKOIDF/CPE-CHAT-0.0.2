#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Build 100-case TestQA CSV from an existing eval report JSON.")
    ap.add_argument(
        "--source",
        default="reports/testqa_v2_live_eval_20260310_210644.json",
        help="Source report JSON that contains `cases`.",
    )
    ap.add_argument(
        "--out",
        default="scripts/testqa_100_from_report.csv",
        help="Output CSV path for harness input.",
    )
    ap.add_argument("--limit", type=int, default=100, help="Number of cases to export.")
    ap.add_argument(
        "--domain",
        default="",
        help="Optional domain filter (e.g. curriculum). Empty means keep all domains.",
    )
    args = ap.parse_args()

    src = Path(args.source)
    if not src.exists():
        raise SystemExit(f"Source file not found: {src}")

    payload = json.loads(src.read_text(encoding="utf-8"))
    cases = list(payload.get("cases") or [])
    if not cases:
        raise SystemExit(f"No `cases` found in: {src}")

    out_rows = []
    for c in cases:
        domain = str(c.get("domain") or "").strip()
        if args.domain and domain != args.domain:
            continue

        out_rows.append(
            {
                "id": str(c.get("id") or "").strip(),
                "domain": domain,
                "question": str(c.get("question") or "").strip(),
                "expected_behavior": str(c.get("expected_behavior") or "ANSWER").strip(),
                "expect_answerable": str(bool(c.get("expect_answerable"))).lower(),
                "expected_answer": str(c.get("expected_answer") or "").strip(),
                "reference_hint": str(c.get("reference_hint") or "").strip(),
                "tags": str(c.get("tags") or "").strip(),
                "notes": "",
            }
        )

        if args.limit > 0 and len(out_rows) >= args.limit:
            break

    if not out_rows:
        raise SystemExit("No rows selected. Try removing --domain filter.")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "id",
        "domain",
        "question",
        "expected_behavior",
        "expect_answerable",
        "expected_answer",
        "reference_hint",
        "tags",
        "notes",
    ]
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)

    print(f"Wrote {len(out_rows)} rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
