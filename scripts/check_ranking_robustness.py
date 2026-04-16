#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value))
    except Exception:
        return default


def main() -> int:
    ap = argparse.ArgumentParser(description="Ranking robustness checks for eval_runner output JSON")
    ap.add_argument("--report-json", default="qball_canary_guard.json")
    ap.add_argument("--min-top1", type=float, default=0.60)
    ap.add_argument("--min-top3", type=float, default=0.70)
    ap.add_argument("--min-top5", type=float, default=0.70)
    ap.add_argument("--min-mrr", type=float, default=0.65)
    ap.add_argument("--exclude-domains", default="multi")
    args = ap.parse_args()

    report_path = Path(args.report_json)
    if not report_path.exists():
        print(f"ROBUSTNESS CHECK FAILED: report not found: {report_path}", file=sys.stderr)
        return 3

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    summary = payload.get("summary") or {}
    by_domain = (summary.get("by_domain") or {}) if isinstance(summary, dict) else {}

    excluded = {x.strip().lower() for x in str(args.exclude_domains or "").split(",") if x.strip()}

    failures: list[str] = []
    checked = 0
    for dom, row in sorted((by_domain or {}).items()):
        dom_key = str(dom or "").strip().lower()
        if not dom_key or dom_key in excluded:
            continue

        checked += 1
        top1 = _to_float((row or {}).get("retrieval_top_1_rate"))
        top3 = _to_float((row or {}).get("retrieval_top_3_rate"))
        top5 = _to_float((row or {}).get("retrieval_top_5_rate"))
        mrr = _to_float((row or {}).get("retrieval_mrr"))

        if top1 < float(args.min_top1):
            failures.append(
                f"{dom_key} top1 below threshold: current={top1:.4f}, threshold={float(args.min_top1):.4f}"
            )
        if top3 < float(args.min_top3):
            failures.append(
                f"{dom_key} top3 below threshold: current={top3:.4f}, threshold={float(args.min_top3):.4f}"
            )
        if top5 < float(args.min_top5):
            failures.append(
                f"{dom_key} top5 below threshold: current={top5:.4f}, threshold={float(args.min_top5):.4f}"
            )
        if mrr < float(args.min_mrr):
            failures.append(
                f"{dom_key} mrr below threshold: current={mrr:.4f}, threshold={float(args.min_mrr):.4f}"
            )

    if checked == 0:
        print("ROBUSTNESS CHECK FAILED: no domains were checked", file=sys.stderr)
        return 3

    if failures:
        print("RANKING ROBUSTNESS FAILED")
        for line in failures:
            print(f"- {line}")
        return 2

    print("RANKING ROBUSTNESS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
