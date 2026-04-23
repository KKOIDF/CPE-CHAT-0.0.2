#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


EXACT_RATE_KEYS = {
    "mrr",
    "precision",
    "recall",
}

SUFFIX_RATE_KEYS = (
    "_rate",
    "_ratio",
    "_precision",
    "_recall",
    "_mrr",
)


def _to_float(value: object) -> float | None:
    try:
        out = float(str(value))
    except Exception:
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def _looks_like_rate(name: str) -> bool:
    ln = (name or "").strip().lower()
    if ln in EXACT_RATE_KEYS:
        return True
    if any(ln.endswith(suffix) for suffix in SUFFIX_RATE_KEYS):
        return True
    if ln.startswith("retrieval_top_") and ln.endswith("_rate"):
        return True
    return False


def _check_dict_values(prefix: str, row: dict[str, object], failures: list[str]) -> None:
    for key, raw in row.items():
        if not _looks_like_rate(str(key)):
            continue
        val = _to_float(raw)
        if val is None:
            failures.append(f"{prefix}.{key}: non-finite or non-numeric value={raw!r}")
            continue
        if val < 0.0 or val > 1.0:
            failures.append(f"{prefix}.{key}: out-of-range value={val:.6f}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate eval metric sanity for report JSON")
    ap.add_argument("--report-json", default="qball_canary_guard.json")
    args = ap.parse_args()

    path = Path(args.report_json)
    if not path.exists():
        print(f"METRIC SANITY FAILED: report not found: {path}", file=sys.stderr)
        return 3

    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if not isinstance(summary, dict):
        print("METRIC SANITY FAILED: missing summary object", file=sys.stderr)
        return 3

    failures: list[str] = []

    _check_dict_values("summary", summary, failures)

    by_category = summary.get("by_category")
    if isinstance(by_category, dict):
        for category, row in by_category.items():
            if isinstance(row, dict):
                _check_dict_values(f"summary.by_category.{category}", row, failures)

    by_domain = summary.get("by_domain")
    if isinstance(by_domain, dict):
        for domain, row in by_domain.items():
            if isinstance(row, dict):
                _check_dict_values(f"summary.by_domain.{domain}", row, failures)

    if failures:
        print("METRIC SANITY FAILED")
        for f in failures:
            print(f"- {f}")
        return 2

    print("METRIC SANITY PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
