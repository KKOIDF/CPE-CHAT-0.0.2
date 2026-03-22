#!/usr/bin/env python3
"""Evaluate retrieval quality against a CSV QA sheet.

This script runs retrieval only (no LLM calls) via `app.rag_logic.rag_query`.
It computes hit@k based on the referenced filename(s) embedded in the question
(e.g. "(อ้างอิง: insurance-std.txt)").

Usage:
  /path/to/.venv/bin/python eval_retrieval_csv.py \
      --csv testQA_domains_30_revised.csv \
      --k 10

Outputs:
  - reports/retrieval_eval_<timestamp>.json
  - reports/retrieval_eval_<timestamp>.md
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parent
RAG_SERVICE_DIR = REPO_ROOT / "services" / "rag-service"


def _normalize_filename(name: str) -> str:
    s = (name or "").strip().lower()
    if not s:
        return ""
    s = s.replace("\\", "/")
    s = s.split("/")[-1]
    s = s.replace(" ", "")
    # dataset often uses '-' while indexed sources may use '_'
    s = s.replace("-", "_")
    return s


def _expected_refs_from_question(question: str) -> list[str]:
    q = question or ""
    # Most rows use: (อ้างอิง: <file>)
    m = re.search(r"อ้างอิง\s*:\s*([^\)]+)", q)
    if not m:
        return []
    raw = m.group(1).strip()

    # Split on common separators
    parts = re.split(r"[;,/]|\s+และ\s+|\s+หรือ\s+", raw)
    refs: list[str] = []
    for p in parts:
        p = (p or "").strip().strip("\"")
        if not p:
            continue
        refs.append(p)
    return refs


def _expected_refs_from_text(text: str) -> list[str]:
    t = text or ""
    # fallback: capture [file/page] patterns if present
    hits = re.findall(r"\[\s*([^\]/\s]+\.(?:txt|pdf))\s*/\s*\d+\s*\]", t, flags=re.IGNORECASE)
    return [h.strip() for h in hits]


def _find_header_row(rows: list[list[str]]) -> tuple[int, list[str]]:
    for i, row in enumerate(rows):
        if len(row) >= 2 and row[0].strip() == "ลำดับ" and row[1].strip() == "คำถาม":
            return i, row
    raise RuntimeError("Could not find header row (expected a row starting with 'ลำดับ,คำถาม').")


def _section_from_title_cell(cell0: str) -> str | None:
    s = (cell0 or "").strip().lower()
    if s.startswith("announcements"):
        return "announcements"
    if s.startswith("regulations"):
        return "regulations"
    if s.startswith("curriculum"):
        return "curriculum"
    return None


def _load_sections(csv_path: Path) -> dict[str, list[dict[str, str]]]:
    """Parse a multi-section CSV sheet.

    The file is structured as:
      <Section title row>
      <blank rows>
      <header row>
      <data rows>
      ... repeat for next section ...
    """
    sections: dict[str, list[dict[str, str]]] = defaultdict(list)
    current_section: str | None = None
    current_header: list[str] | None = None

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            cell0 = (row[0] or "").strip()
            sec = _section_from_title_cell(cell0)
            if sec:
                current_section = sec
                current_header = None
                continue

            if current_section is None:
                continue

            if len(row) >= 2 and row[0].strip() == "ลำดับ" and row[1].strip() == "คำถาม":
                current_header = row
                continue

            if current_header is None:
                continue

            if not any((c or "").strip() for c in row):
                continue

            rec: dict[str, str] = {}
            for j, key in enumerate(current_header):
                rec[key] = row[j] if j < len(row) else ""
            sections[current_section].append(rec)

    return dict(sections)


def _safe_int(s: str) -> int | None:
    try:
        return int((s or "").strip())
    except Exception:
        return None


def _top_sources(contexts: list[dict], n: int) -> list[str]:
    out: list[str] = []
    for c in contexts[:n]:
        p = c.get("path") or c.get("source") or ""
        p = str(p)
        if not p:
            continue
        out.append(_normalize_filename(p))
    return out


def _first_hit_rank(
    retrieved: list[str],
    expected: Iterable[str],
    *,
    max_rank: int,
) -> int | None:
    exp = {_normalize_filename(e) for e in expected if (e or "").strip()}
    exp.discard("")
    if not exp:
        return None

    for i, r in enumerate(retrieved[:max_rank], start=1):
        if not r:
            continue
        if r in exp:
            return i
        # allow loose matching: if one is substring of the other
        for e in exp:
            if e and (e in r or r in e):
                return i
    return None


@dataclass
class RowResult:
    qid: int
    section: str
    question: str
    inferred_domain: str | None
    top1_domain: str | None
    top5_domain_counts: dict[str, int]
    top1_section_match: bool
    top5_majority_section_match: bool
    expected_refs: list[str]
    expected_refs_norm: list[str]
    hit_rank: int | None
    hit_at_5: bool
    hit_at_10: bool
    top_5: list[str]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to CSV sheet")
    ap.add_argument("--k", type=int, default=10, help="Max rank to evaluate")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of questions (0 = all)")
    args = ap.parse_args()

    csv_path = (REPO_ROOT / args.csv).resolve() if not os.path.isabs(args.csv) else Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    # Ensure we can import the rag-service package as `app.*`
    sys.path.insert(0, str(RAG_SERVICE_DIR))

    from app.rag_logic import infer_domain, normalize_question, rag_query  # type: ignore

    sections = _load_sections(csv_path)

    results: list[RowResult] = []
    evaluated = 0

    for section_name, sheet in sections.items():
        for rec in sheet:
            qid = _safe_int(rec.get("ลำดับ", ""))
            question = (rec.get("คำถาม", "") or "").strip()
            if not qid or not question:
                continue

            expected = _expected_refs_from_question(question)
            if not expected:
                expected = _expected_refs_from_text(rec.get("คำตอบที่คาดว่าจะตอบ", ""))

            expected_norm = [_normalize_filename(e) for e in expected if (e or "").strip()]

            q_display = normalize_question(question)
            dom = infer_domain(q_display)

            out = rag_query(question)
            contexts = out.get("contexts") or []

            top1_domain = None
            if contexts:
                top1_domain = contexts[0].get("domain")

            top5_domains = [((c.get("domain") or "") or "").strip().lower() for c in contexts[:5]]
            top5_counts = Counter(d for d in top5_domains if d)
            top1_match = bool(top1_domain) and (str(top1_domain).strip().lower() == section_name)
            top5_majority_match = False
            if top5_counts:
                top_dom, top_cnt = top5_counts.most_common(1)[0]
                top5_majority_match = (top_dom == section_name) and (top_cnt >= 3)

            retrieved_norm = [_normalize_filename(c.get("path") or c.get("source") or "") for c in contexts]

            hit_rank = _first_hit_rank(retrieved_norm, expected_norm, max_rank=max(10, int(args.k)))
            hit_at_5 = hit_rank is not None and hit_rank <= 5
            hit_at_10 = hit_rank is not None and hit_rank <= 10

            results.append(
                RowResult(
                    qid=qid,
                    section=section_name,
                    question=question,
                    inferred_domain=dom,
                    top1_domain=(str(top1_domain).strip().lower() if top1_domain else None),
                    top5_domain_counts=dict(top5_counts),
                    top1_section_match=top1_match,
                    top5_majority_section_match=top5_majority_match,
                    expected_refs=expected,
                    expected_refs_norm=expected_norm,
                    hit_rank=hit_rank,
                    hit_at_5=hit_at_5,
                    hit_at_10=hit_at_10,
                    top_5=_top_sources(contexts, 5),
                )
            )

            evaluated += 1
            if args.limit and evaluated >= args.limit:
                break
        if args.limit and evaluated >= args.limit:
            break

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / f"retrieval_eval_{ts}.json"
    md_path = reports_dir / f"retrieval_eval_{ts}.md"

    # summary stats
    total = len(results)

    # Only compute doc hit@k for rows where we could parse an expected reference.
    with_gt = [r for r in results if r.expected_refs_norm]
    gt_total = len(with_gt)
    hit5 = sum(1 for r in with_gt if r.hit_at_5)
    hit10 = sum(1 for r in with_gt if r.hit_at_10)

    hit_ranks = [r.hit_rank for r in with_gt if r.hit_rank is not None]
    avg_rank = (sum(hit_ranks) / len(hit_ranks)) if hit_ranks else None

    # domain alignment for all rows
    top1_dom_acc = sum(1 for r in results if r.top1_section_match)
    top5_dom_acc = sum(1 for r in results if r.top5_majority_section_match)

    miss_by_domain = Counter((r.inferred_domain or "") for r in with_gt if not r.hit_at_10)
    miss_by_section = Counter(r.section for r in with_gt if not r.hit_at_10)

    payload = {
        "csv": str(csv_path),
        "evaluated": total,
        "doc_eval_rows": gt_total,
        "hit@5": hit5,
        "hit@10": hit10,
        "avg_hit_rank": avg_rank,
        "domain_top1_accuracy": top1_dom_acc,
        "domain_top5_majority_accuracy": top5_dom_acc,
        "miss_by_inferred_domain": dict(miss_by_domain),
        "miss_by_section": dict(miss_by_section),
        "results": [
            {
                "qid": r.qid,
                "section": r.section,
                "question": r.question,
                "inferred_domain": r.inferred_domain,
                "top1_domain": r.top1_domain,
                "top5_domain_counts": r.top5_domain_counts,
                "top1_section_match": r.top1_section_match,
                "top5_majority_section_match": r.top5_majority_section_match,
                "expected_refs": r.expected_refs,
                "expected_refs_norm": r.expected_refs_norm,
                "hit_rank": r.hit_rank,
                "hit@5": r.hit_at_5,
                "hit@10": r.hit_at_10,
                "top_5": r.top_5,
            }
            for r in results
        ],
    }

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append(f"# Retrieval Eval ({ts})")
    lines.append("")
    lines.append(f"- CSV: {csv_path}")
    lines.append(f"- Evaluated: {total}")
    lines.append(f"- Doc-eval rows (has expected ref): {gt_total}")
    lines.append(f"- hit@5 (doc-eval only): {hit5}/{gt_total}")
    lines.append(f"- hit@10 (doc-eval only): {hit10}/{gt_total}")
    lines.append(f"- Domain top1 accuracy (all rows): {top1_dom_acc}/{total}")
    lines.append(f"- Domain top5-majority accuracy (all rows): {top5_dom_acc}/{total}")
    if avg_rank is not None:
        lines.append(f"- avg_hit_rank (hits only): {avg_rank:.2f}")
    lines.append("")

    lines.append("## By section")
    for sec in ("announcements", "regulations", "curriculum"):
        sec_rows = [r for r in results if r.section == sec]
        if not sec_rows:
            continue

        sec_gt = [r for r in sec_rows if r.expected_refs_norm]
        sec_gt_total = len(sec_gt)
        sec_hit10 = sum(1 for r in sec_gt if r.hit_at_10)
        sec_top1 = sum(1 for r in sec_rows if r.top1_section_match)
        sec_top5 = sum(1 for r in sec_rows if r.top5_majority_section_match)

        lines.append(
            f"- {sec}: rows={len(sec_rows)} | doc_eval={sec_gt_total} | "
            f"hit@10={sec_hit10}/{sec_gt_total} | top1={sec_top1}/{len(sec_rows)} | "
            f"top5maj={sec_top5}/{len(sec_rows)}"
        )

    lines.append("")
    lines.append("## Domain mismatches (top1 != section)")
    mismatches = [r for r in results if not r.top1_section_match]
    if not mismatches:
        lines.append("(none)")
    else:
        for r in sorted(mismatches, key=lambda x: (x.section, x.qid)):
            top5 = ",".join([f"{k}:{v}" for k, v in sorted(r.top5_domain_counts.items())])
            lines.append(
                f"- [{r.section}] {r.qid}: top1={r.top1_domain or 'n/a'} | top5_counts={top5 or 'n/a'} | top5_src={', '.join(r.top_5)}"
            )

    lines.append("## Misses (doc-eval only; hit@10 = false)")

    misses = [r for r in with_gt if not r.hit_at_10]
    if not misses:
        lines.append("(none)")
    else:
        for r in sorted(misses, key=lambda x: (x.section, x.qid)):
            exp = ", ".join(r.expected_refs_norm) if r.expected_refs_norm else "(no expected ref parsed)"
            lines.append(
                f"- [{r.section}] {r.qid}: {exp} | top1_dom={r.top1_domain or 'n/a'} | top5={', '.join(r.top_5)}"
            )

    lines.append("")
    lines.append("## Per-question")
    for r in sorted(results, key=lambda x: (x.section, x.qid)):
        exp = ", ".join(r.expected_refs_norm) if r.expected_refs_norm else "(no expected ref parsed)"
        lines.append(
            f"- [{r.section}] {r.qid}: top1_dom={r.top1_domain or 'n/a'} | top5_majority={r.top5_majority_section_match} | hit_rank={r.hit_rank} | exp={exp}"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    print(
        f"doc_hit@5={hit5}/{gt_total} doc_hit@10={hit10}/{gt_total} "
        f"domain_top1={top1_dom_acc}/{total} domain_top5maj={top5_dom_acc}/{total} avg_rank={avg_rank}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
