#!/usr/bin/env python3
"""Evaluate QA dataset v2 CSV against the *running* rag-service.

This is a v2 companion to scripts/eval_testqa_csv_live.py.

What it adds:
- explicit labels: expected_behavior + expect_answerable
- computes abstention / hallucination rates for unanswerable cases
- keeps the same lightweight heuristics (stdlib + requests)

Usage:
  python3 scripts/eval_testqa_csv_live_v2.py \
    --input scripts/testqa_v2_template.csv \
    --base-url http://127.0.0.1:8001

CSV columns:
  id, domain, question, expected_behavior, expect_answerable,
  expected_answer, reference_hint, tags, notes
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Allow running from anywhere (so repo-root helpers like mlflow_utils are importable).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import mlflow_utils as mlf
except Exception:  # pragma: no cover
    mlf = None  # type: ignore

try:
    import mlflow
    import mlflow.tracing.fluent as mlflow_tracing
except Exception:  # pragma: no cover
    mlflow = None  # type: ignore
    mlflow_tracing = None  # type: ignore


if mlf and getattr(mlf, "enabled", lambda: False)():
    os.environ.setdefault("MLFLOW_EXPERIMENT", os.getenv("MLFLOW_EVAL_EXPERIMENT", "cpe-chat-eval"))


FALLBACK = "ไม่พบข้อมูลในเอกสาร"


def _normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s)
    return s


_NUM_RE = re.compile(r"\d+(?:[\.,]\d+)?")
_YEAR_RE = re.compile(r"\b(25\d{2})\b")
_MONEY_RE = re.compile(r"(\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?\s*บาท")


def _extract_numbers(s: str) -> List[str]:
    s = _normalize_text(s)
    nums = _NUM_RE.findall(s)
    return [n.replace(",", "") for n in nums]


def _extract_years(s: str) -> List[str]:
    return _YEAR_RE.findall(_normalize_text(s))


def _extract_money_amounts(s: str) -> List[str]:
    txt = _normalize_text(s)
    out: List[str] = []
    for m in _MONEY_RE.finditer(txt):
        n = (m.group(1) or "").replace(",", "").strip()
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


def _truthy(s: str) -> bool:
    return str(s or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _infer_behavior_from_thai_row(question_type: str, expected_answer: str) -> str:
    _ = question_type  # Currently informational; behavior is inferred mostly from expected answer text.
    txt = (expected_answer or "").strip()
    if not txt:
        return "ANSWER"

    abstain_markers = [
        "ไม่สามารถยืนยัน",
        "เอกสารที่มีไม่ได้ระบุ",
        "ไม่มีข้อมูลนี้ในเอกสาร",
        "เอกสารไม่ได้ระบุ",
        "ไม่สามารถสรุป",
    ]
    if any(m in txt for m in abstain_markers):
        return "ABSTAIN"
    return "ANSWER"


def _normalize_input_rows(rows: List[Dict[str, Any]], default_domain: str) -> tuple[List[Dict[str, Any]], str]:
    if not rows:
        return [], "empty"

    first = rows[0]
    if "question" in first:
        normalized: List[Dict[str, Any]] = []
        for r in rows:
            expected_behavior = (r.get("expected_behavior") or "").strip().upper() or "ANSWER"
            expect_answerable = _truthy(str(r.get("expect_answerable") or ""))
            normalized.append(
                {
                    "id": (r.get("id") or "").strip(),
                    "domain": (r.get("domain") or "").strip(),
                    "question": (r.get("question") or "").strip(),
                    "expected_behavior": expected_behavior,
                    "expect_answerable": expect_answerable,
                    "expected_answer": (r.get("expected_answer") or "").strip(),
                    "reference_hint": (r.get("reference_hint") or "").strip(),
                    "tags": (r.get("tags") or "").strip(),
                }
            )
        return normalized, "v2"

    # Thai CSV format support, e.g. kmutt_cpe_questions_1_100.csv
    if "คำถาม" in first:
        normalized = []
        for r in rows:
            expected_answer = (r.get("คำตอบที่คาดหวัง") or "").strip()
            question_type = (r.get("ประเภทคำถาม") or "").strip()
            expected_behavior = _infer_behavior_from_thai_row(question_type, expected_answer)
            normalized.append(
                {
                    "id": (r.get("ข้อ") or "").strip(),
                    "domain": default_domain,
                    "question": (r.get("คำถาม") or "").strip(),
                    "expected_behavior": expected_behavior,
                    "expect_answerable": expected_behavior == "ANSWER",
                    "expected_answer": expected_answer,
                    "reference_hint": "",
                    "tags": question_type,
                }
            )
        return normalized, "thai_qa"

    # Unknown schema; pass through with best-effort fallback keys.
    normalized = []
    for r in rows:
        normalized.append(
            {
                "id": (r.get("id") or r.get("ข้อ") or "").strip(),
                "domain": (r.get("domain") or default_domain or "").strip(),
                "question": (r.get("question") or r.get("คำถาม") or "").strip(),
                "expected_behavior": (r.get("expected_behavior") or "ANSWER").strip().upper() or "ANSWER",
                "expect_answerable": _truthy(str(r.get("expect_answerable") or "1")),
                "expected_answer": (r.get("expected_answer") or r.get("คำตอบที่คาดหวัง") or "").strip(),
                "reference_hint": (r.get("reference_hint") or "").strip(),
                "tags": (r.get("tags") or r.get("ประเภทคำถาม") or "").strip(),
            }
        )
    return normalized, "unknown"


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((p / 100.0) * (len(ordered) - 1)))
    idx = max(0, min(len(ordered) - 1, idx))
    return float(ordered[idx])


def _get_json(url: str, timeout_s: float) -> Dict[str, Any]:
    r = requests.get(url, timeout=timeout_s)
    r.raise_for_status()
    return dict(r.json() or {})


def _sources_from_contexts(contexts: List[Dict[str, Any]]) -> List[str]:
    sources: List[str] = []
    for c in contexts or []:
        src = (c.get("source") or c.get("path") or "").strip()
        if not src:
            continue
        src = src.replace("\\", "/").split("/")[-1]
        sources.append(src)
    return sources


_ABSTAIN_RE = re.compile(
    r"ไม่พบข้อมูล|ไม่มีข้อมูล|ไม่ปรากฏ|เอกสารไม่ได้ระบุ|เอกสารไม่ระบุ|"
    r"ไม่พบข้อความยืนยันโดยตรง|ไม่มีข้อความยืนยันโดยตรง|ไม่ได้กล่าวตรง\s*ๆ"
)
_CLARIFY_RE = re.compile(r"ช่วยระบุ|ขอรายละเอียด|หมายถึง|ต้องการ.*(ปี|ภาค|รหัส)|พิมพ์รหัสเต็ม")
_CITATION_RE = re.compile(r"\[([^\[\]]+?)/(\d+)\]")


def _is_abstain(answer: str) -> bool:
    a = (answer or "").strip()
    if not a:
        return True
    if a == FALLBACK:
        return True
    return bool(_ABSTAIN_RE.search(a))


def _is_clarify(answer: str) -> bool:
    a = (answer or "").strip()
    if not a:
        return False
    return bool(_CLARIFY_RE.search(a))


def _normalize_source_name(src: str) -> str:
    s = (src or "").strip().replace("\\", "/").split("/")[-1].lower()
    return s


def _relaxed_source_token(src: str) -> str:
    # Relax matching so minor punctuation/underscore variations still map.
    return re.sub(r"[\W_]+", "", _normalize_source_name(src), flags=re.UNICODE)


def _extract_citation_sources(answer: str) -> List[str]:
    return [m.group(1).strip() for m in _CITATION_RE.finditer(answer or "")]


def _infer_eval_group(row: Dict[str, Any]) -> str:
    grp = (row.get("eval_group") or row.get("group") or "").strip().lower()
    if grp:
        return grp
    tags = (row.get("tags") or "").strip().lower()
    domain = (row.get("domain") or "").strip().lower()
    q = (row.get("question") or "").strip().lower()
    if "calendar" in tags or "schedule" in tags or "ปฏิทิน" in q:
        return "announcement_schedule"
    if "prerequisite" in tags or "course-code" in tags or "รหัส" in q:
        return "prerequisite_course_code"
    if "clause" in tags or domain == "regulations":
        return "regulations_clause_query"
    if "multi_doc" in tags or "multi-intent" in tags:
        return "multi_doc_multi_intent"
    if domain == "curriculum":
        return "curriculum_fact_lookup"
    return "uncategorized"


@dataclass
class CaseResult:
    id: str
    domain: str
    question: str
    expected_behavior: str
    expect_answerable: bool
    expected_answer: str
    reference_hint: str
    tags: str
    answer: str
    sources_top: List[str]
    contexts_count: int
    latency_ms: float
    similarity: float
    years_jaccard: float
    money_jaccard: float
    abstained: bool
    clarified: bool
    predicted_behavior: str
    behavior_match: bool
    hallucination: bool
    false_negative: bool
    eval_group: str
    citations_found: int
    citations_valid: bool
    error: str
    trace_id: str


def _predicted_behavior(answer: str, *, clarified: bool, abstained: bool, error: str) -> str:
    if (error or "").strip():
        return "ERROR"
    if clarified:
        return "CLARIFY"
    if abstained:
        return "ABSTAIN"
    return "ANSWER"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="scripts/testqa_v2_template.csv")
    ap.add_argument("--base-url", default="http://127.0.0.1:8001")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--sleep", type=float, default=0.0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sim-threshold", type=float, default=0.55)
    ap.add_argument("--default-domain", default="curriculum")
    ap.add_argument("--require-citations", action="store_true")
    ap.add_argument("--gate-min-exactness", type=float, default=-1.0)
    ap.add_argument("--gate-min-citation-validity", type=float, default=-1.0)
    ap.add_argument("--gate-max-latency-p95", type=float, default=-1.0)
    ap.add_argument("--gate-required-groups", default="")
    ap.add_argument("--gate-min-cases-per-group", type=int, default=0)
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        raise SystemExit(f"Input not found: {in_path}")

    with in_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader]

    normalized_rows, input_format = _normalize_input_rows(rows, default_domain=str(args.default_domain or "").strip())

    results: List[CaseResult] = []
    total = 0

    for r in normalized_rows:
        if args.limit and total >= int(args.limit):
            break
        q = (r.get("question") or "").strip()
        if not q:
            continue

        total += 1

        cid = (r.get("id") or "").strip()
        domain = (r.get("domain") or "").strip() or None
        expected_behavior = (r.get("expected_behavior") or "").strip().upper() or "ANSWER"
        expect_answerable = bool(r.get("expect_answerable"))
        expected_answer = (r.get("expected_answer") or "").strip()
        reference_hint = (r.get("reference_hint") or "").strip()
        tags = (r.get("tags") or "").strip()
        eval_group = _infer_eval_group(r)

        answer = ""
        contexts: List[Dict[str, Any]] = []
        err = ""
        latency_ms = 0.0
        try:
            started = time.perf_counter()
            data = _post_answer(args.base_url, q, domain, timeout_s=float(args.timeout))
            latency_ms = (time.perf_counter() - started) * 1000.0
            answer = str(data.get("answer") or "").strip()
            contexts = list(data.get("contexts") or [])
        except Exception as e:
            latency_ms = (time.perf_counter() - started) * 1000.0 if 'started' in locals() else 0.0
            err = f"{type(e).__name__}: {e}"

        sources = _sources_from_contexts(contexts)
        sources_top = sources[:8]
        context_src_strict = {_normalize_source_name(x) for x in sources_top}
        context_src_relaxed = {_relaxed_source_token(x) for x in sources_top}

        citation_srcs = _extract_citation_sources(answer)
        citation_srcs_strict = [_normalize_source_name(x) for x in citation_srcs]
        citation_srcs_relaxed = [_relaxed_source_token(x) for x in citation_srcs]
        has_citations = len(citation_srcs) > 0
        valid_citations = False
        if has_citations:
            valid_citations = all(
                (src in context_src_strict) or (r_src in context_src_relaxed)
                for src, r_src in zip(citation_srcs_strict, citation_srcs_relaxed)
            )

        sim = _seq_ratio(expected_answer, answer) if (expected_answer and answer) else 0.0
        years_j = _jaccard(_extract_years(expected_answer), _extract_years(answer)) if (expected_answer and answer) else 0.0
        money_j = _jaccard(_extract_money_amounts(expected_answer), _extract_money_amounts(answer)) if (expected_answer and answer) else 0.0

        abstained = _is_abstain(answer)
        clarified = _is_clarify(answer)

        predicted = _predicted_behavior(answer, clarified=clarified, abstained=abstained, error=err)
        behavior_match = bool(predicted == expected_behavior)

        # Hallucination heuristic: should abstain/clarify but answered.
        should_not_answer = (expected_behavior in {"ABSTAIN", "CLARIFY"}) or (not expect_answerable)
        hallucination = bool(
            should_not_answer
            and predicted == "ANSWER"
            and (answer or "").strip()
            and not (err or "").strip()
        )

        # False-negative: should answer but abstained/clarified.
        should_answer = (expected_behavior == "ANSWER") and expect_answerable
        false_negative = bool(should_answer and (predicted in {"ABSTAIN", "CLARIFY"}))

        results.append(
            CaseResult(
                id=cid,
                domain=str(domain or ""),
                question=q,
                expected_behavior=expected_behavior,
                expect_answerable=expect_answerable,
                expected_answer=expected_answer,
                reference_hint=reference_hint,
                tags=tags,
                answer=answer,
                sources_top=sources_top,
                contexts_count=len(contexts),
                latency_ms=latency_ms,
                similarity=sim,
                years_jaccard=years_j,
                money_jaccard=money_j,
                abstained=abstained,
                clarified=clarified,
                predicted_behavior=predicted,
                behavior_match=behavior_match,
                hallucination=hallucination,
                false_negative=false_negative,
                eval_group=eval_group,
                citations_found=len(citation_srcs),
                citations_valid=(valid_citations and has_citations),
                error=err,
                trace_id="",
            )
        )

        if args.sleep and args.sleep > 0:
            time.sleep(float(args.sleep))

    # Summaries
    n_total = len(results)
    n_unans = sum(1 for x in results if (x.expected_behavior in {"ABSTAIN", "CLARIFY"}) or (not x.expect_answerable))
    n_ans = sum(1 for x in results if (x.expected_behavior == "ANSWER") and x.expect_answerable)

    hallucinations = sum(1 for x in results if x.hallucination)
    false_negs = sum(1 for x in results if x.false_negative)

    # Behavior accuracy (ANSWER/CLARIFY/ABSTAIN/ERROR).
    behavior_correct = sum(1 for x in results if x.behavior_match)

    # Confusion matrix: expected_behavior -> predicted_behavior counts.
    behavior_confusion: Dict[str, Dict[str, int]] = {}
    for x in results:
        behavior_confusion.setdefault(x.expected_behavior, {})
        behavior_confusion[x.expected_behavior][x.predicted_behavior] = (
            behavior_confusion[x.expected_behavior].get(x.predicted_behavior, 0) + 1
        )

    # Heuristic "correct" for answerable: only meaningful when expected_answer is provided.
    correct_ans = 0
    n_ans_with_expected = 0
    for x in results:
        if not ((x.expected_behavior == "ANSWER") and x.expect_answerable):
            continue
        if not x.expected_answer:
            continue
        n_ans_with_expected += 1
        ok_sim = x.similarity >= float(args.sim_threshold)
        ok_num = True
        if x.answer:
            exp_nums = set(_extract_numbers(x.expected_answer))
            ans_nums = set(_extract_numbers(x.answer))
            # If expected includes numbers, require at least one to match.
            if exp_nums:
                ok_num = bool(exp_nums & ans_nums)
        if ok_sim and ok_num:
            correct_ans += 1

    answered_cases = [x for x in results if x.predicted_behavior == "ANSWER" and not (x.error or "").strip()]
    if args.require_citations:
        citation_valid_cases = [x for x in answered_cases if x.citations_valid]
    else:
        # If citations are optional, treat non-citation answers as valid and only reject invalid citation references.
        citation_valid_cases = [x for x in answered_cases if (x.citations_found == 0) or x.citations_valid]
    citation_validity_rate = (len(citation_valid_cases) / len(answered_cases)) if answered_cases else 0.0

    group_counts: Dict[str, int] = {}
    group_exact_numer: Dict[str, int] = {}
    group_exact_denom: Dict[str, int] = {}
    group_cite_numer: Dict[str, int] = {}
    group_cite_denom: Dict[str, int] = {}
    for x in results:
        g = x.eval_group or "uncategorized"
        group_counts[g] = group_counts.get(g, 0) + 1
        if (x.expected_behavior == "ANSWER") and x.expect_answerable and x.expected_answer:
            group_exact_denom[g] = group_exact_denom.get(g, 0) + 1
            ok_sim = x.similarity >= float(args.sim_threshold)
            ok_num = True
            if x.answer:
                exp_nums = set(_extract_numbers(x.expected_answer))
                ans_nums = set(_extract_numbers(x.answer))
                if exp_nums:
                    ok_num = bool(exp_nums & ans_nums)
            if ok_sim and ok_num:
                group_exact_numer[g] = group_exact_numer.get(g, 0) + 1

        if x.predicted_behavior == "ANSWER" and not (x.error or "").strip():
            group_cite_denom[g] = group_cite_denom.get(g, 0) + 1
            if args.require_citations:
                cite_ok = x.citations_valid
            else:
                cite_ok = (x.citations_found == 0) or x.citations_valid
            if cite_ok:
                group_cite_numer[g] = group_cite_numer.get(g, 0) + 1

    group_metrics: Dict[str, Dict[str, float]] = {}
    for g in sorted(group_counts.keys()):
        ex_d = group_exact_denom.get(g, 0)
        ct_d = group_cite_denom.get(g, 0)
        group_metrics[g] = {
            "cases": float(group_counts.get(g, 0)),
            "exactness": (group_exact_numer.get(g, 0) / ex_d) if ex_d else 0.0,
            "exactness_denom": float(ex_d),
            "citation_validity": (group_cite_numer.get(g, 0) / ct_d) if ct_d else 0.0,
            "citation_denom": float(ct_d),
        }

    abstain_correct = sum(
        1
        for x in results
        if ((x.expected_behavior in {"ABSTAIN", "CLARIFY"}) or (not x.expect_answerable))
        and (x.abstained or x.clarified)
    )

    latency_values = [x.latency_ms for x in results if x.latency_ms > 0]
    latency_by_domain: Dict[str, List[float]] = {}
    for x in results:
        if x.latency_ms <= 0:
            continue
        latency_by_domain.setdefault(x.domain or "unknown", []).append(x.latency_ms)

    summary = {
        "input_format": input_format,
        "total": n_total,
        "answerable_cases": n_ans,
        "unanswerable_cases": n_unans,
        "behavior_correct": behavior_correct,
        "behavior_accuracy": (behavior_correct / n_total) if n_total else 0.0,
        "hallucinations": hallucinations,
        "hallucination_rate": (hallucinations / n_unans) if n_unans else 0.0,
        "false_negatives": false_negs,
        "false_negative_rate": (false_negs / n_ans) if n_ans else 0.0,
        "answerable_correct_heur": correct_ans,
        "answerable_accuracy_heur": (correct_ans / n_ans_with_expected) if n_ans_with_expected else 0.0,
        "exactness": (correct_ans / n_ans_with_expected) if n_ans_with_expected else 0.0,
        "answerable_cases_with_expected": n_ans_with_expected,
        "abstain_correct": abstain_correct,
        "abstain_accuracy": (abstain_correct / n_unans) if n_unans else 0.0,
        "latency_ms_avg": (sum(latency_values) / len(latency_values)) if latency_values else 0.0,
        "latency_ms_p50": _percentile(latency_values, 50),
        "latency_ms_p90": _percentile(latency_values, 90),
        "latency_ms_p95": _percentile(latency_values, 95),
        "latency_ms_p99": _percentile(latency_values, 99),
        "latency_ms_max": max(latency_values) if latency_values else 0.0,
        "contexts_count_avg": (sum(x.contexts_count for x in results) / n_total) if n_total else 0.0,
        "citation_validity_rate": citation_validity_rate,
        "answered_cases_for_citation": len(answered_cases),
        "require_citations": bool(args.require_citations),
        "sim_threshold": float(args.sim_threshold),
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = Path("reports") / f"testqa_v2_live_eval_{ts}.json"
    out_md = Path("reports") / f"testqa_v2_live_eval_{ts}.md"
    out_latency_csv = Path("reports") / f"testqa_v2_live_eval_latency_{ts}.csv"
    out_json.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "summary": summary,
        "behavior_confusion": behavior_confusion,
        "group_metrics": group_metrics,
        "cases": [
            {
                **x.__dict__,
            }
            for x in results
        ],
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with out_latency_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "id",
                "domain",
                "expected_behavior",
                "predicted_behavior",
                "latency_ms",
                "contexts_count",
                "behavior_match",
                "hallucination",
                "false_negative",
                "trace_id",
            ]
        )
        for x in results:
            writer.writerow(
                [
                    x.id,
                    x.domain,
                    x.expected_behavior,
                    x.predicted_behavior,
                    f"{x.latency_ms:.3f}",
                    x.contexts_count,
                    int(x.behavior_match),
                    int(x.hallucination),
                    int(x.false_negative),
                    x.trace_id,
                ]
            )

    lines: List[str] = []
    lines.append("# TestQA v2 Live Eval")
    lines.append("")
    lines.append(f"Generated: {ts}")
    lines.append(f"Input: {in_path}")
    lines.append(f"Base URL: {args.base_url}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    for k, v in summary.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## Latency By Domain")
    lines.append("")
    for domain_key in sorted(latency_by_domain.keys()):
        domain_values = latency_by_domain[domain_key]
        lines.append(
            f"- {domain_key}: avg={sum(domain_values) / len(domain_values):.2f} ms, "
            f"p90={_percentile(domain_values, 90):.2f} ms, max={max(domain_values):.2f} ms"
        )
    lines.append("")

    lines.append("## Behavior confusion (expected -> predicted)")
    lines.append("")
    for exp in sorted(behavior_confusion.keys()):
        preds = behavior_confusion.get(exp, {})
        rendered = ", ".join(f"{k}={preds[k]}" for k in sorted(preds.keys()))
        lines.append(f"- {exp}: {rendered}")
    lines.append("")

    lines.append("## Group Metrics")
    lines.append("")
    for g in sorted(group_metrics.keys()):
        gm = group_metrics[g]
        lines.append(
            f"- {g}: cases={int(gm.get('cases', 0))}, "
            f"exactness={gm.get('exactness', 0.0):.4f} (n={int(gm.get('exactness_denom', 0))}), "
            f"citation_validity={gm.get('citation_validity', 0.0):.4f} (n={int(gm.get('citation_denom', 0))})"
        )
    lines.append("")

    # Show top hallucination examples
    hall = [x for x in results if x.hallucination]
    if hall:
        lines.append("## Hallucination examples (should abstain)")
        lines.append("")
        for x in hall[:8]:
            lines.append(f"- id={x.id} domain={x.domain} tags={x.tags}")
            lines.append(f"  Q: {x.question}")
            lines.append(f"  A: {x.answer[:280]}")
        lines.append("")

    # Show false-negative examples
    fn = [x for x in results if x.false_negative]
    if fn:
        lines.append("## False-negative examples (should answer)")
        lines.append("")
        for x in fn[:8]:
            lines.append(f"- id={x.id} domain={x.domain} tags={x.tags}")
            lines.append(f"  Q: {x.question}")
            lines.append(f"  Expected: {x.expected_answer[:220]}")
            lines.append(f"  A: {x.answer[:220]}")
        lines.append("")

    mismatches = [x for x in results if (not x.behavior_match) and not (x.error or "").strip()]
    if mismatches:
        lines.append("## Behavior mismatches")
        lines.append("")
        for x in mismatches[:10]:
            lines.append(
                f"- id={x.id} exp={x.expected_behavior} pred={x.predicted_behavior} domain={x.domain} tags={x.tags}"
            )
            lines.append(f"  Q: {x.question}")
            lines.append(f"  A: {x.answer[:220]}")
        lines.append("")

    if mlf and getattr(mlf, "enabled", lambda: False)():
        with mlf.start_run(
            run_name=f"testqa_v2_live_eval_{ts}",
            tags={"script": "scripts/eval_testqa_csv_live_v2.py"},
        ):
            trace_manifest: List[Dict[str, Any]] = []
            if mlflow and mlflow_tracing:
                try:
                    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
                    mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT", os.getenv("MLFLOW_EVAL_EXPERIMENT", "cpe-chat-eval")))
                    for x in results:
                        trace_id = mlflow_tracing.log_trace(
                            name="eval_case",
                            request={
                                "case_id": x.id,
                                "domain": x.domain,
                                "question": x.question,
                                "expected_behavior": x.expected_behavior,
                            },
                            response={
                                "answer": x.answer,
                                "predicted_behavior": x.predicted_behavior,
                                "error": x.error,
                            },
                            attributes={
                                "case_id": x.id,
                                "domain": x.domain,
                                "expected_behavior": x.expected_behavior,
                                "predicted_behavior": x.predicted_behavior,
                                "expect_answerable": x.expect_answerable,
                                "behavior_match": x.behavior_match,
                                "hallucination": x.hallucination,
                                "false_negative": x.false_negative,
                                "latency_ms": x.latency_ms,
                                "contexts_count": x.contexts_count,
                                "trace_kind": "evaluation",
                                "trace_script": "eval_testqa_csv_live_v2.py",
                                "reference_hint": x.reference_hint,
                                "tags": x.tags,
                                "sources_top": "|".join(x.sources_top[:8]),
                            },
                            execution_time_ms=int(round(x.latency_ms)),
                        )
                        x.trace_id = str(trace_id or "")
                        trace_manifest.append(
                            {
                                "case_id": x.id,
                                "domain": x.domain,
                                "trace_id": x.trace_id,
                                "latency_ms": x.latency_ms,
                            }
                        )
                except Exception:
                    trace_manifest = []

            payload = {
                "summary": summary,
                "behavior_confusion": behavior_confusion,
                "group_metrics": group_metrics,
                "cases": [
                    {
                        **x.__dict__,
                    }
                    for x in results
                ],
            }
            out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            with out_latency_csv.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "id",
                        "domain",
                        "expected_behavior",
                        "predicted_behavior",
                        "latency_ms",
                        "contexts_count",
                        "behavior_match",
                        "hallucination",
                        "false_negative",
                        "trace_id",
                    ]
                )
                for x in results:
                    writer.writerow(
                        [
                            x.id,
                            x.domain,
                            x.expected_behavior,
                            x.predicted_behavior,
                            f"{x.latency_ms:.3f}",
                            x.contexts_count,
                            int(x.behavior_match),
                            int(x.hallucination),
                            int(x.false_negative),
                            x.trace_id,
                        ]
                    )

            out_md.write_text("\n".join(lines), encoding="utf-8")

            mlf.log_params(
                {
                    "input": str(in_path),
                    "input_format": input_format,
                    "base_url": str(args.base_url),
                    "timeout_s": float(args.timeout),
                    "sleep_s": float(args.sleep),
                    "limit": int(args.limit),
                    "sim_threshold": float(args.sim_threshold),
                    "default_domain": str(args.default_domain),
                }
            )
            mlf.log_metrics(summary)
            for domain_key in sorted(latency_by_domain.keys()):
                domain_values = latency_by_domain[domain_key]
                mlf.log_metrics(
                    {
                        f"latency_ms_avg__{domain_key}": sum(domain_values) / len(domain_values),
                        f"latency_ms_p90__{domain_key}": _percentile(domain_values, 90),
                        f"latency_ms_max__{domain_key}": max(domain_values),
                    }
                )
            mlf.log_metrics({"trace_count": float(len(trace_manifest))})
            mlf.log_artifacts([str(out_json), str(out_md), str(out_latency_csv)])

            # Log confusion matrix as artifact for MLflow UI browsing.
            mlf.log_dict_artifact(behavior_confusion, artifact_file=f"behavior_confusion_{ts}.json")
            if trace_manifest:
                mlf.log_dict_artifact({"traces": trace_manifest}, artifact_file=f"trace_manifest_{ts}.json")

            ctx: Dict[str, Any] = {
                "generated": ts,
                "input": str(in_path),
                "base_url": str(args.base_url),
                "env": mlf.env_snapshot(),
            }
            # Best-effort: capture running service config (disabled by default in service).
            try:
                ctx["rag_service_health"] = _get_json(args.base_url.rstrip("/") + "/health", timeout_s=3.0)
            except Exception as e:
                ctx["rag_service_health_error"] = f"{type(e).__name__}: {e}"
            try:
                ctx["rag_service_config"] = _get_json(args.base_url.rstrip("/") + "/debug/config", timeout_s=3.0)
            except Exception as e:
                ctx["rag_service_config_error"] = f"{type(e).__name__}: {e}"

            mlf.log_dict_artifact(ctx, artifact_file=f"run_context_{ts}.json")

    else:
        out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_md}")
    print(f"Wrote: {out_latency_csv}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    gate_failures: List[str] = []
    req_groups = [x.strip().lower() for x in str(args.gate_required_groups or "").split(",") if x.strip()]
    if req_groups:
        for g in req_groups:
            if g not in group_counts:
                gate_failures.append(f"missing_required_group={g}")
            elif args.gate_min_cases_per_group > 0 and group_counts.get(g, 0) < int(args.gate_min_cases_per_group):
                gate_failures.append(
                    f"insufficient_cases_group={g} have={group_counts.get(g, 0)} need>={int(args.gate_min_cases_per_group)}"
                )

    exactness_val = float(summary.get("exactness", 0.0))
    citation_val = float(summary.get("citation_validity_rate", 0.0))
    p95_val = float(summary.get("latency_ms_p95", 0.0))

    if args.gate_min_exactness >= 0 and exactness_val < float(args.gate_min_exactness):
        gate_failures.append(
            f"exactness_below_threshold value={exactness_val:.4f} need>={float(args.gate_min_exactness):.4f}"
        )
    if args.gate_min_citation_validity >= 0 and citation_val < float(args.gate_min_citation_validity):
        gate_failures.append(
            f"citation_validity_below_threshold value={citation_val:.4f} need>={float(args.gate_min_citation_validity):.4f}"
        )
    if args.gate_max_latency_p95 >= 0 and p95_val > float(args.gate_max_latency_p95):
        gate_failures.append(
            f"latency_p95_above_threshold value={p95_val:.2f} need<={float(args.gate_max_latency_p95):.2f}"
        )

    if gate_failures:
        print("GATE_STATUS: FAIL")
        for f in gate_failures:
            print(f"GATE_FAIL: {f}")
        return 2

    has_gate = any(
        [
            args.gate_min_exactness >= 0,
            args.gate_min_citation_validity >= 0,
            args.gate_max_latency_p95 >= 0,
            bool(req_groups),
        ]
    )
    if has_gate:
        print("GATE_STATUS: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
