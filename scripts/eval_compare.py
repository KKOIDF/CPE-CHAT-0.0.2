#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid report format: {p}")
    return data


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _counts(report: dict[str, Any]) -> dict[str, int]:
    s = (report.get("summary") or {}).get("error_tag_counts") or {}
    return {
        "incomplete": int(s.get("retrieve_found_but_answer_incomplete") or 0),
        "not_found": int(s.get("retrieve_not_found") or 0),
        "runtime_error": int(s.get("runtime_error") or 0),
    }


def _case_tags(report: dict[str, Any]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for c in report.get("cases") or []:
        cid = str((c or {}).get("id") or "").strip()
        if not cid:
            continue
        tags = [str(x).strip() for x in ((c or {}).get("error_tags") or []) if str(x).strip()]
        out[cid] = set(tags)
    return out


def _headline(report: dict[str, Any]) -> dict[str, float]:
    s = report.get("summary") or {}
    return {
        "overall": _num(s.get("overall_pass_rate")),
        "answer": _num(s.get("answer_hit_rate")),
        "retrieval": _num(s.get("retrieval_hit_rate")),
        "citation": _num(s.get("citation_validity_rate")),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare two eval_runner JSON reports")
    ap.add_argument("--baseline", required=True, help="Path to baseline report JSON")
    ap.add_argument("--candidate", required=True, help="Path to candidate report JSON")
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--out", default="", help="Optional output JSON path")
    args = ap.parse_args()

    base = _load(args.baseline)
    cand = _load(args.candidate)

    base_h = _headline(base)
    cand_h = _headline(cand)
    base_c = _counts(base)
    cand_c = _counts(cand)

    base_tags = _case_tags(base)
    cand_tags = _case_tags(cand)
    all_ids = sorted(set(base_tags.keys()) | set(cand_tags.keys()))

    fixed_incomplete: list[str] = []
    new_incomplete: list[str] = []
    fixed_not_found: list[str] = []
    new_not_found: list[str] = []
    regressed_runtime: list[str] = []

    for cid in all_ids:
        b = base_tags.get(cid, set())
        c = cand_tags.get(cid, set())
        if "retrieve_found_but_answer_incomplete" in b and "retrieve_found_but_answer_incomplete" not in c:
            fixed_incomplete.append(cid)
        if "retrieve_found_but_answer_incomplete" not in b and "retrieve_found_but_answer_incomplete" in c:
            new_incomplete.append(cid)
        if "retrieve_not_found" in b and "retrieve_not_found" not in c:
            fixed_not_found.append(cid)
        if "retrieve_not_found" not in b and "retrieve_not_found" in c:
            new_not_found.append(cid)
        if "runtime_error" not in b and "runtime_error" in c:
            regressed_runtime.append(cid)

    report = {
        "baseline": args.baseline,
        "candidate": args.candidate,
        "delta": {
            "overall_pass_rate": cand_h["overall"] - base_h["overall"],
            "answer_hit_rate": cand_h["answer"] - base_h["answer"],
            "retrieval_hit_rate": cand_h["retrieval"] - base_h["retrieval"],
            "citation_validity_rate": cand_h["citation"] - base_h["citation"],
            "incomplete": cand_c["incomplete"] - base_c["incomplete"],
            "not_found": cand_c["not_found"] - base_c["not_found"],
            "runtime_error": cand_c["runtime_error"] - base_c["runtime_error"],
        },
        "swaps": {
            "fixed_incomplete": fixed_incomplete,
            "new_incomplete": new_incomplete,
            "fixed_not_found": fixed_not_found,
            "new_not_found": new_not_found,
            "new_runtime_error": regressed_runtime,
        },
    }

    print("== Headline Delta ==")
    print(f"overall_pass_rate: {report['delta']['overall_pass_rate']:+.4f}")
    print(f"answer_hit_rate: {report['delta']['answer_hit_rate']:+.4f}")
    print(f"retrieval_hit_rate: {report['delta']['retrieval_hit_rate']:+.4f}")
    print(f"citation_validity_rate: {report['delta']['citation_validity_rate']:+.4f}")
    print(f"retrieve_found_but_answer_incomplete: {report['delta']['incomplete']:+d}")
    print(f"retrieve_not_found: {report['delta']['not_found']:+d}")
    print(f"runtime_error: {report['delta']['runtime_error']:+d}")

    n = max(1, int(args.top_n))
    print("\n== Swap Summary ==")
    print(f"fixed_incomplete: {len(fixed_incomplete)}")
    print(f"new_incomplete: {len(new_incomplete)}")
    print(f"fixed_not_found: {len(fixed_not_found)}")
    print(f"new_not_found: {len(new_not_found)}")
    print(f"new_runtime_error: {len(regressed_runtime)}")

    if fixed_incomplete:
        print("\nfixed_incomplete sample:")
        for cid in fixed_incomplete[:n]:
            print(f"- {cid}")
    if new_incomplete:
        print("\nnew_incomplete sample:")
        for cid in new_incomplete[:n]:
            print(f"- {cid}")

    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nWrote: {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
