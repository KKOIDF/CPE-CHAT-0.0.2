#!/usr/bin/env python3
"""Evaluate testQA CSV against the *running* rag-service.

- Reads testQA_domains_30_revised.csv (sectioned by domain headers).
- For each question row:
  - calls POST /rag/answer with {domain, question}
  - collects answer + contexts (sources)
  - computes lightweight heuristics vs expected answer (string similarity + number overlap)
  - checks reference-hint strictness (if question has "(อ้างอิง: X)")
- Writes timestamped JSON + Markdown reports under ./reports/

This is intentionally dependency-light (stdlib + requests).

Usage:
  python3 scripts/eval_testqa_csv_live.py \
    --input testQA_domains_30_revised.csv \
    --base-url http://127.0.0.1:8001

Notes:
- Scores are heuristics; treat them as a triage signal.
- The report includes top retrieved sources to debug cross-doc contamination.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


DOMAIN_TITLES = {
    "announcements": "Announcements — คำถาม (นักศึกษาจะถาม) และคำตอบที่คาดว่าจะตอบ",
    "regulations": "Regulations — คำถาม (นักศึกษาจะถาม) และคำตอบที่คาดว่าจะตอบ",
    "curriculum": "Curriculum — คำถาม (นักศึกษาจะถาม) และคำตอบที่คาดว่าจะตอบ",
}


def _detect_domain_from_row0(cell0: str) -> Optional[str]:
    first = (cell0 or "").strip()
    for dom, title in DOMAIN_TITLES.items():
        if first.startswith(title):
            return dom
    return None


def _is_question_row(row: List[str]) -> bool:
    if not row:
        return False
    first = (row[0] or "").strip()
    if not first:
        return False
    try:
        int(first)
        return True
    except Exception:
        return False


_REF_RE = re.compile(r"\(\s*อ้างอิง\s*:\s*([^\)]+)\)")


def _extract_reference_hint(question: str) -> Optional[str]:
    m = _REF_RE.search(question or "")
    if not m:
        return None
    ref = (m.group(1) or "").strip()
    if not ref:
        return None
    # normalize: keep basename-ish
    ref = ref.replace("\\", "/")
    ref = ref.split("/")[-1]
    return ref


def _canon_source_name(name: str) -> str:
    """Canonicalize a source filename for loose comparisons.

    Normalizes basename + strips extension + removes separators so that
    insurance-std.txt and insurance_std.txt are considered equivalent.
    """
    s = (name or '').strip().lower().replace('\\', '/')
    s = s.split('/')[-1]
    # strip common extension
    s = re.sub(r"\.(txt|pdf)$", "", s)
    # remove separators/punctuation
    s = re.sub(r"[^a-z0-9\u0E00-\u0E7F]+", "", s)
    return s


def _normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s)
    return s


_NUM_RE = re.compile(r"\d+(?:[\.,]\d+)?")


def _extract_numbers(s: str) -> List[str]:
    s = _normalize_text(s)
    nums = _NUM_RE.findall(s)
    # normalize commas
    out: List[str] = []
    for n in nums:
        n2 = n.replace(",", "")
        out.append(n2)
    return out


_YEAR_RE = re.compile(r"\b(25\d{2})\b")
_MONEY_RE = re.compile(r"(\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?\s*บาท")


def _extract_years(s: str) -> List[str]:
    return _YEAR_RE.findall(_normalize_text(s))


def _extract_money_amounts(s: str) -> List[str]:
    txt = _normalize_text(s)
    out: List[str] = []
    for m in _MONEY_RE.finditer(txt):
        n = (m.group(1) or '').replace(',', '').strip()
        if n:
            out.append(n)
    return out


def _jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _seq_ratio(a: str, b: str) -> float:
    # stdlib-only similarity
    import difflib

    return difflib.SequenceMatcher(None, _normalize_text(a), _normalize_text(b)).ratio()


def _post_answer(base_url: str, question: str, domain: Optional[str], timeout_s: float) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/rag/answer"
    payload: Dict[str, Any] = {"question": question}
    if domain:
        payload["domain"] = domain
    r = requests.post(url, json=payload, timeout=timeout_s)
    r.raise_for_status()
    return r.json()


def _sources_from_contexts(contexts: List[Dict[str, Any]]) -> List[str]:
    sources: List[str] = []
    for c in contexts or []:
        src = (c.get("source") or c.get("path") or "").strip()
        if not src:
            continue
        src = src.replace("\\", "/")
        src = src.split("/")[-1]
        sources.append(src)
    return sources


@dataclass
class CaseResult:
    idx: int
    domain: str
    question: str
    expected: str
    answer: str
    error: Optional[str]
    reference_hint: Optional[str]
    sources_top: List[str]
    sources_unique: List[str]
    similarity: float
    years_expected: List[str]
    years_answer: List[str]
    money_expected: List[str]
    money_answer: List[str]
    years_jaccard: float
    money_jaccard: float
    ref_leak: bool


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="testQA_domains_30_revised.csv")
    ap.add_argument("--base-url", default="http://127.0.0.1:8001")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--sleep", type=float, default=0.0)
    ap.add_argument("--limit", type=int, default=0, help="Limit number of questions (0 = all)")
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        raise SystemExit(f"Input not found: {in_path}")

    # Read CSV fully (handles embedded newlines in quoted fields).
    with in_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))

    current_domain: Optional[str] = None
    results: List[CaseResult] = []
    total_q = 0
    errors = 0

    # Column mapping: [ลำดับ, คำถาม, คำตอบที่คาดว่าจะตอบ, ...]
    COL_Q = 1
    COL_EXPECT = 2

    for row in rows:
        if row and (dom := _detect_domain_from_row0(row[0])):
            current_domain = dom
            continue

        if not current_domain:
            continue

        if not _is_question_row(row):
            continue

        idx = int((row[0] or "0").strip() or "0")
        q = (row[COL_Q] if len(row) > COL_Q else "").strip()
        expected = (row[COL_EXPECT] if len(row) > COL_EXPECT else "").strip()
        if not q:
            continue

        total_q += 1
        if args.limit and total_q > int(args.limit):
            break

        ref = _extract_reference_hint(q)

        answer = ""
        contexts: List[Dict[str, Any]] = []
        err: Optional[str] = None
        try:
            data = _post_answer(args.base_url, q, current_domain, timeout_s=float(args.timeout))
            answer = str(data.get("answer") or "").strip()
            contexts = list(data.get("contexts") or [])
        except Exception as e:
            errors += 1
            err = f"{type(e).__name__}: {e}"

        sources = _sources_from_contexts(contexts)
        sources_top = sources[:8]
        sources_unique = sorted(set(sources))

        sim = _seq_ratio(expected, answer) if (expected and answer) else 0.0
        years_e = _extract_years(expected)
        years_a = _extract_years(answer)
        money_e = _extract_money_amounts(expected)
        money_a = _extract_money_amounts(answer)
        years_j = _jaccard(years_e, years_a)
        money_j = _jaccard(money_e, money_a)

        ref_leak = False
        if ref:
            # If any retrieved context source isn't the hinted ref, flag it.
            # (In strict mode we expect *only* that doc.)
            ref_canon = _canon_source_name(ref)
            if sources_unique:
                src_canons = {_canon_source_name(s) for s in sources_unique}
                if src_canons and any(c != ref_canon for c in src_canons):
                    ref_leak = True

        results.append(
            CaseResult(
                idx=idx,
                domain=current_domain,
                question=q,
                expected=expected,
                answer=answer,
                error=err,
                reference_hint=ref,
                sources_top=sources_top,
                sources_unique=sources_unique,
                similarity=sim,
                years_expected=years_e,
                years_answer=years_a,
                money_expected=money_e,
                money_answer=money_a,
                years_jaccard=years_j,
                money_jaccard=money_j,
                ref_leak=ref_leak,
            )
        )

        if args.sleep and args.sleep > 0:
            time.sleep(float(args.sleep))

        if total_q % 5 == 0:
            print(f"progress: {total_q} questions")

    # Aggregate
    ref_cases = [r for r in results if r.reference_hint]
    ref_leaks = [r for r in ref_cases if r.ref_leak]
    numeric_mismatches = [
        r
        for r in results
        if (r.years_expected and r.years_jaccard < 1.0) or (r.money_expected and r.money_jaccard < 1.0)
    ]

    # Heuristic pass/fail
    # - If expected has numbers, require perfect number match.
    # - Otherwise require moderate similarity.
    def is_pass(r: CaseResult) -> bool:
        if r.error:
            return False
        if r.years_expected and r.years_jaccard < 1.0:
            return False
        if r.money_expected and r.money_jaccard < 1.0:
            return False
        if r.years_expected or r.money_expected:
            return True
        return r.similarity >= 0.25

    passes = [r for r in results if is_pass(r)]
    fails = [r for r in results if not is_pass(r)]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_json = reports_dir / f"testqa_csv_live_eval_{ts}.json"
    out_md = reports_dir / f"testqa_csv_live_eval_{ts}.md"

    payload = {
        "generated_at": ts,
        "input": str(in_path),
        "base_url": args.base_url,
        "total_questions": len(results),
        "errors": errors,
        "passes_heuristic": len(passes),
        "fails_heuristic": len(fails),
        "ref_hint_questions": len(ref_cases),
        "ref_leaks": len(ref_leaks),
        "numeric_mismatches": len(numeric_mismatches),
        "results": [
            {
                "idx": r.idx,
                "domain": r.domain,
                "question": r.question,
                "expected": r.expected,
                "answer": r.answer,
                "error": r.error,
                "reference_hint": r.reference_hint,
                "sources_unique": r.sources_unique,
                "sources_top": r.sources_top,
                "similarity": r.similarity,
                "years_expected": r.years_expected,
                "years_answer": r.years_answer,
                "money_expected": r.money_expected,
                "money_answer": r.money_answer,
                "years_jaccard": r.years_jaccard,
                "money_jaccard": r.money_jaccard,
                "ref_leak": r.ref_leak,
            }
            for r in results
        ],
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _short(s: str, n: int = 220) -> str:
        s = (s or "").strip().replace("\r", " ").replace("\n", " ")
        s = re.sub(r"\s+", " ", s)
        if len(s) <= n:
            return s
        return s[: n - 3] + "..."

    lines: List[str] = []
    lines.append(f"# Live CSV Eval Report ({ts})")
    lines.append("")
    lines.append(f"- input: {in_path}")
    lines.append(f"- base_url: {args.base_url}")
    lines.append(f"- questions: {len(results)}")
    lines.append(f"- errors: {errors}")
    lines.append(f"- heuristic passes: {len(passes)}")
    lines.append(f"- heuristic fails: {len(fails)}")
    lines.append(f"- ref-hint questions: {len(ref_cases)}")
    lines.append(f"- ref leaks (should be 0 in strict mode): {len(ref_leaks)}")
    lines.append(f"- numeric mismatches (expected numbers not all present in answer): {len(numeric_mismatches)}")

    if ref_leaks:
        lines.append("")
        lines.append("## Reference-leak cases (top)")
        for r in ref_leaks[:12]:
            lines.append(f"- [{r.domain} #{r.idx}] ref={r.reference_hint} sources={', '.join(r.sources_top) or '(none)'}")

    if numeric_mismatches:
        lines.append("")
        lines.append("## Numeric-mismatch cases (top)")
        def _worst(r: CaseResult) -> float:
            parts: List[float] = []
            if r.years_expected:
                parts.append(r.years_jaccard)
            if r.money_expected:
                parts.append(r.money_jaccard)
            return min(parts) if parts else 1.0

        for r in sorted(numeric_mismatches, key=_worst)[:12]:
            lines.append(
                f"- [{r.domain} #{r.idx}] years(exp={r.years_expected}, ans={r.years_answer}, j={r.years_jaccard:.2f}) "
                f"money(exp={r.money_expected}, ans={r.money_answer}, j={r.money_jaccard:.2f})"
            )

    if fails:
        lines.append("")
        lines.append("## Heuristic fails (top)")
        for r in fails[:12]:
            lines.append(f"### {r.domain} #{r.idx}")
            if r.reference_hint:
                lines.append(f"ref: {r.reference_hint} | ref_leak={r.ref_leak}")
            if r.error:
                lines.append(f"error: {r.error}")
            lines.append(f"q: {_short(r.question, 240)}")
            lines.append(f"expected: {_short(r.expected, 260)}")
            lines.append(f"answer: {_short(r.answer, 260)}")
            if r.sources_top:
                lines.append(f"sources: {', '.join(r.sources_top)}")
            lines.append("")

    out_md.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
