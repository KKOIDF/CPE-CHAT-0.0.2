#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


KNOWN_DOMAINS = {"curriculum", "regulations", "announcements"}
CITATION_RE = re.compile(r"\[([^\[\]/]+?)/(\d+)\]")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def normalize_source_token(text: str) -> str:
    s = (text or "").strip().lower().replace("\\", "/")
    s = s.split("/")[-1]
    s = s.replace(".txt", "")
    return re.sub(r"[^a-z0-9ก-๙]+", "", s)


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((p / 100.0) * (len(ordered) - 1)))
    idx = max(0, min(idx, len(ordered) - 1))
    return float(ordered[idx])


def post_json(base_url: str, endpoint: str, payload: dict[str, Any], timeout_s: float) -> tuple[dict[str, Any], float, str]:
    url = base_url.rstrip("/") + endpoint
    started = time.perf_counter()
    try:
        response = requests.post(url, json=payload, timeout=timeout_s)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        response.raise_for_status()
        data = response.json() or {}
        return dict(data), elapsed_ms, ""
    except Exception as exc:  # pragma: no cover
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return {}, elapsed_ms, f"{type(exc).__name__}: {exc}"


def answer_keyword_stats(answer: str, expected_keywords: list[str]) -> tuple[int, int, float, bool]:
    expected = [k for k in (expected_keywords or []) if str(k).strip()]
    if not expected:
        return 0, 0, 1.0, True
    normalized_answer = normalize_text(answer)
    matched = 0
    for kw in expected:
        if normalize_text(kw) in normalized_answer:
            matched += 1
    total = len(expected)
    coverage = matched / total if total else 1.0
    return matched, total, coverage, matched == total


def must_not_contain_ok(answer: str, forbidden_list: list[str]) -> bool:
    ans = normalize_text(answer)
    for token in forbidden_list or []:
        if normalize_text(token) and normalize_text(token) in ans:
            return False
    return True


def retrieval_hit(
    contexts: list[dict[str, Any]],
    expected_domain: str | None,
    expected_domains_any: list[str],
    expected_source_contains: list[str],
) -> tuple[bool, bool, bool, list[str], list[str], float, bool]:
    domains = [str((c or {}).get("domain") or "").strip().lower() for c in contexts or []]
    domain_set = {d for d in domains if d}

    source_haystacks: list[str] = []
    for ctx in contexts or []:
        src = str((ctx or {}).get("source") or (ctx or {}).get("path") or "").strip()
        dom = str((ctx or {}).get("domain") or "").strip()
        source_haystacks.append(normalize_text(f"{src} {dom}"))

    domain_ok = True
    if (expected_domain or "").strip().lower() in KNOWN_DOMAINS:
        domain_ok = (expected_domain or "").strip().lower() in domain_set

    domains_any_ok = True
    normalized_expected_domains_any = [d.strip().lower() for d in expected_domains_any or [] if d.strip()]
    if normalized_expected_domains_any:
        domains_any_ok = all(d in domain_set for d in normalized_expected_domains_any)

    missing_source_tokens: list[str] = []
    for token in expected_source_contains or []:
        tok = normalize_text(token)
        found = any(tok in hs for hs in source_haystacks)
        if not found:
            missing_source_tokens.append(token)

    sources_ok = len(missing_source_tokens) == 0

    best_rank = 9999
    expected_toks = [normalize_text(t) for t in expected_source_contains or []]
    if expected_toks:
        for i, hs in enumerate(source_haystacks, 1):
            if all(tok in hs for tok in expected_toks):
                best_rank = i
                break
    else:
        best_rank = 1

    mrr = 1.0 / best_rank if best_rank != 9999 else 0.0
    top_1 = (best_rank == 1)

    return domain_ok and domains_any_ok and sources_ok, domain_ok, sources_ok, sorted(domain_set), missing_source_tokens, mrr, top_1


def citation_validity(answer: str, contexts: list[dict[str, Any]]) -> tuple[bool, int, int, list[str]]:
    citations = [(m.group(1).strip(), int(m.group(2))) for m in CITATION_RE.finditer(answer or "")]
    if not citations:
        return False, 0, 0, ["missing_citations"]

    context_entries: list[dict[str, Any]] = []
    for ctx in contexts or []:
        src = str((ctx or {}).get("source") or (ctx or {}).get("path") or "")
        pstart = (ctx or {}).get("page_start")
        pend = (ctx or {}).get("page_end")
        try:
            ps = int(pstart) if pstart is not None else None
        except Exception:
            ps = None
        try:
            pe = int(pend) if pend is not None else ps
        except Exception:
            pe = ps
        context_entries.append(
            {
                "source_token": normalize_source_token(src),
                "page_start": ps,
                "page_end": pe,
                "raw_source": src,
            }
        )

    valid_count = 0
    issues: list[str] = []
    for src, page in citations:
        src_tok = normalize_source_token(src)
        candidates = [e for e in context_entries if e["source_token"] == src_tok]
        if not candidates:
            issues.append(f"citation_source_not_found:{src}/{page}")
            continue

        match_page = False
        for c in candidates:
            ps = c["page_start"]
            pe = c["page_end"]
            if ps is None and pe is None:
                continue
            if ps is None:
                ps = pe
            if pe is None:
                pe = ps
            if ps is not None and pe is not None and ps <= page <= pe:
                match_page = True
                break

        if not match_page:
            issues.append(f"citation_page_not_found:{src}/{page}")
            continue

        valid_count += 1

    total = len(citations)
    return valid_count == total, total, valid_count, issues


@dataclass
class CaseResult:
    id: str
    category: str
    question: str
    expected_domain: str | None
    expected_domains_any: list[str]
    answer: str
    answer_hit_pass: bool
    answer_hit_coverage: float
    answer_keywords_matched: int
    answer_keywords_total: int
    retrieval_hit_pass: bool
    retrieval_domain_pass: bool
    retrieval_source_pass: bool
    retrieval_domains_found: list[str]
    retrieval_missing_source_tokens: list[str]
    retrieval_mrr: float
    retrieval_top_1_pass: bool
    citation_validity_pass: bool
    citation_total: int
    citation_valid_count: int
    citation_issues: list[str]
    must_not_contain_pass: bool
    total_pass: bool
    total_latency_ms: float
    retrieval_latency_ms: float
    contexts_count: int
    error: str
    adaptive: dict[str, Any]


def default_adaptive() -> dict[str, float]:
    return {
        "retrieval_adaptive_retry_triggered": 0.0,
        "retrieval_adaptive_retry_succeeded": 0.0,
        "retrieval_fallback_all_domains_triggered": 0.0,
        "retrieval_fallback_all_domains_succeeded": 0.0,
        "structured_rescue_triggered": 0.0,
        "structured_rescue_succeeded": 0.0,
        "curriculum_bypass_vector_triggered": 0.0,
        "low_confidence_detected": 0.0,
        "initial_retrieval_doc_count": 0.0,
        "retry_retrieval_doc_count": 0.0,
        "initial_top_score": 0.0,
        "retry_top_score": 0.0,
    }


def coerce_adaptive(meta: dict[str, Any]) -> dict[str, float]:
    out = default_adaptive()
    raw = (meta or {}).get("adaptive") if isinstance(meta, dict) else None
    if not isinstance(raw, dict):
        return out
    for k in out:
        try:
            out[k] = float(raw.get(k, out[k]))
        except Exception:
            out[k] = out[k]
    return out


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    total = len(results)
    lat_total = [r.total_latency_ms for r in results if r.total_latency_ms > 0]
    lat_ret = [r.retrieval_latency_ms for r in results if r.retrieval_latency_ms > 0]

    answer_hit_rate = sum(1 for r in results if r.answer_hit_pass) / total if total else 0.0
    retrieval_hit_rate = sum(1 for r in results if r.retrieval_hit_pass) / total if total else 0.0
    retrieval_mrr = statistics.mean([r.retrieval_mrr for r in results]) if total else 0.0
    retrieval_top_1_rate = sum(1 for r in results if r.retrieval_top_1_pass) / total if total else 0.0
    citation_validity_rate = sum(1 for r in results if r.citation_validity_pass) / total if total else 0.0
    must_not_pass_rate = sum(1 for r in results if r.must_not_contain_pass) / total if total else 0.0
    overall_pass_rate = sum(1 for r in results if r.total_pass) / total if total else 0.0

    by_category: dict[str, dict[str, Any]] = {}
    for r in results:
        cat = r.category
        bucket = by_category.setdefault(
            cat,
            {
                "total": 0,
                "overall_pass": 0,
                "answer_hit_pass": 0,
                "retrieval_hit_pass": 0,
                "citation_validity_pass": 0,
            },
        )
        bucket["total"] += 1
        bucket["overall_pass"] += int(r.total_pass)
        bucket["answer_hit_pass"] += int(r.answer_hit_pass)
        bucket["retrieval_hit_pass"] += int(r.retrieval_hit_pass)
        bucket["retrieval_mrr_sum"] = bucket.get("retrieval_mrr_sum", 0.0) + r.retrieval_mrr
        bucket["retrieval_top_1_pass"] = bucket.get("retrieval_top_1_pass", 0) + int(r.retrieval_top_1_pass)
        bucket["citation_validity_pass"] += int(r.citation_validity_pass)

    by_category_rates: dict[str, dict[str, float]] = {}
    for cat, m in by_category.items():
        n = max(1, int(m["total"]))
        by_category_rates[cat] = {
            "total": float(m["total"]),
            "overall_pass_rate": float(m["overall_pass"]) / n,
            "answer_hit_rate": float(m["answer_hit_pass"]) / n,
            "retrieval_hit_rate": float(m["retrieval_hit_pass"]) / n,
            "retrieval_mrr": float(m["retrieval_mrr_sum"]) / n,
            "retrieval_top_1_rate": float(m["retrieval_top_1_pass"]) / n,
            "citation_validity_rate": float(m["citation_validity_pass"]) / n,
        }

    adaptive_acc = default_adaptive()
    for r in results:
        for k in adaptive_acc:
            try:
                adaptive_acc[k] += float(r.adaptive.get(k, 0.0))
            except Exception:
                pass
    adaptive_avg = {
        k: (v / total if total else 0.0)
        for k, v in adaptive_acc.items()
    }

    failures = [r for r in results if not r.total_pass]
    failures_sorted = sorted(
        failures,
        key=lambda x: (
            0 if x.error else 1,
            x.answer_hit_coverage,
            0 if x.citation_validity_pass else 1,
            x.total_latency_ms,
        ),
    )

    top_failed = []
    for f in failures_sorted[:10]:
        top_failed.append(
            {
                "id": f.id,
                "category": f.category,
                "question": f.question,
                "error": f.error,
                "answer_hit_coverage": f.answer_hit_coverage,
                "retrieval_hit_pass": f.retrieval_hit_pass,
                "citation_validity_pass": f.citation_validity_pass,
                "must_not_contain_pass": f.must_not_contain_pass,
                "total_latency_ms": f.total_latency_ms,
            }
        )

    return {
        "total_cases": total,
        "overall_pass_rate": overall_pass_rate,
        "answer_hit_rate": answer_hit_rate,
        "retrieval_hit_rate": retrieval_hit_rate,
        "retrieval_mrr": retrieval_mrr,
        "retrieval_top_1_rate": retrieval_top_1_rate,
        "citation_validity_rate": citation_validity_rate,
        "must_not_contain_pass_rate": must_not_pass_rate,
        "avg_latency_ms": statistics.mean(lat_total) if lat_total else 0.0,
        "p95_latency_ms": percentile(lat_total, 95),
        "avg_retrieval_latency_ms": statistics.mean(lat_ret) if lat_ret else 0.0,
        "p95_retrieval_latency_ms": percentile(lat_ret, 95),
        "by_category": by_category_rates,
        "adaptive_metrics_avg": adaptive_avg,
        "failed_cases_top10": top_failed,
    }


def to_markdown(summary: dict[str, Any], input_path: Path, base_url: str) -> str:
    lines: list[str] = []
    lines.append("# Regression Eval Summary")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append(f"Input: {input_path}")
    lines.append(f"Base URL: {base_url}")
    lines.append("")

    lines.append("## Headline")
    lines.append("")
    lines.append(f"- total cases: {summary['total_cases']}")
    lines.append(f"- overall pass rate: {summary['overall_pass_rate']:.4f}")
    lines.append("")
    lines.append("### Retrieval Metrics")
    lines.append(f"- top-1 hit rate: {summary['retrieval_top_1_rate']:.4f}")
    lines.append(f"- top-K hit rate: {summary.get('retrieval_hit_rate', 0.0):.4f}")
    lines.append(f"- mean reciprocal rank (mrr): {summary.get('retrieval_mrr', 0.0):.4f}")
    lines.append("")
    lines.append("### Answer Quality Metrics")
    lines.append(f"- answer keyword hit rate: {summary['answer_hit_rate']:.4f}")
    lines.append(f"- citation validity (groundedness): {summary['citation_validity_rate']:.4f}")
    lines.append(f"- must-not contain pass rate: {summary.get('must_not_contain_pass_rate', 0.0):.4f}")
    lines.append("")
    lines.append("### Latency Metrics")
    lines.append(f"- avg total latency ms: {summary['avg_latency_ms']:.2f}")
    lines.append(f"- p95 total latency ms: {summary['p95_latency_ms']:.2f}")
    lines.append(f"- avg retrieval latency ms: {summary['avg_retrieval_latency_ms']:.2f}")
    lines.append(f"- p95 retrieval latency ms: {summary['p95_retrieval_latency_ms']:.2f}")
    lines.append("")

    lines.append("## By Category")
    lines.append("")
    for cat in sorted(summary["by_category"].keys()):
        row = summary["by_category"][cat]
        lines.append(
            f"- {cat}: total={int(row['total'])}, overall={row['overall_pass_rate']:.4f}, "
            f"answer={row['answer_hit_rate']:.4f}, retrieval={row['retrieval_hit_rate']:.4f}, "
            f"citation={row['citation_validity_rate']:.4f}"
        )
    lines.append("")

    lines.append("## Adaptive Metrics")
    lines.append("")
    for k, v in summary["adaptive_metrics_avg"].items():
        lines.append(f"- {k}: {v:.4f}")
    lines.append("")

    lines.append("## Failed Cases Top 10")
    lines.append("")
    top_failed = summary.get("failed_cases_top10") or []
    if not top_failed:
        lines.append("- none")
    else:
        for f in top_failed:
            lines.append(
                f"- {f['id']} ({f['category']}): coverage={f['answer_hit_coverage']:.2f}, "
                f"retrieval={f['retrieval_hit_pass']}, citation={f['citation_validity_pass']}, "
                f"must_not={f['must_not_contain_pass']}, latency_ms={f['total_latency_ms']:.1f}, "
                f"error={f['error'] or 'none'}"
            )
    lines.append("")

    return "\n".join(lines)


def build_baseline(summary: dict[str, Any], commit_sha: str) -> dict[str, Any]:
    by_cat = summary.get("by_category") or {}
    adaptive = summary.get("adaptive_metrics_avg") or {}
    return {
        "commit": commit_sha,
        "overall_pass_rate": summary.get("overall_pass_rate", 0.0),
        "per_category_pass_rate": {
            k: (v.get("overall_pass_rate", 0.0) if isinstance(v, dict) else 0.0)
            for k, v in by_cat.items()
        },
        "citation_validity_rate": summary.get("citation_validity_rate", 0.0),
        "avg_latency_ms": summary.get("avg_latency_ms", 0.0),
        "p95_latency_ms": summary.get("p95_latency_ms", 0.0),
        "adaptive_retry_rate": adaptive.get("retrieval_adaptive_retry_triggered", 0.0),
        "fallback_rate": adaptive.get("retrieval_fallback_all_domains_triggered", 0.0),
        "structured_rescue_rate": adaptive.get("structured_rescue_triggered", 0.0),
    }


def baseline_markdown(baseline: dict[str, Any]) -> str:
    lines = ["# Baseline Snapshot", ""]
    for k, v in baseline.items():
        if isinstance(v, dict):
            lines.append(f"- {k}:")
            for sk, sv in sorted(v.items()):
                lines.append(f"  - {sk}: {sv}")
        else:
            lines.append(f"- {k}: {v}")
    lines.append("")
    return "\n".join(lines)


def apply_gate(
    summary: dict[str, Any],
    baseline: dict[str, Any],
    *,
    overall_drop_pct: float,
    citation_drop_pct: float,
    p95_increase_pct: float,
    protected_categories: list[str],
) -> list[str]:
    failures: list[str] = []

    current_overall = float(summary.get("overall_pass_rate", 0.0))
    base_overall = float(baseline.get("overall_pass_rate", 0.0))
    if current_overall < (base_overall - (overall_drop_pct / 100.0)):
        failures.append(
            f"overall pass rate dropped too much: current={current_overall:.4f}, baseline={base_overall:.4f}, allowed_drop={overall_drop_pct:.2f}%"
        )

    current_citation = float(summary.get("citation_validity_rate", 0.0))
    base_citation = float(baseline.get("citation_validity_rate", 0.0))
    if current_citation < (base_citation - (citation_drop_pct / 100.0)):
        failures.append(
            f"citation validity dropped: current={current_citation:.4f}, baseline={base_citation:.4f}, allowed_drop={citation_drop_pct:.2f}%"
        )

    current_p95 = float(summary.get("p95_latency_ms", 0.0))
    base_p95 = float(baseline.get("p95_latency_ms", 0.0))
    allowed_p95 = base_p95 * (1.0 + p95_increase_pct / 100.0)
    if base_p95 > 0 and current_p95 > allowed_p95:
        failures.append(
            f"p95 latency exceeded threshold: current={current_p95:.2f} ms, baseline={base_p95:.2f} ms, allowed={allowed_p95:.2f} ms"
        )

    current_cat = summary.get("by_category") or {}
    base_cat = baseline.get("per_category_pass_rate") or {}
    for cat in protected_categories:
        cur = float(((current_cat.get(cat) or {}).get("overall_pass_rate", 0.0)))
        base = float(base_cat.get(cat, 0.0))
        if cur < base:
            failures.append(
                f"protected category dropped: {cat} current={cur:.4f}, baseline={base:.4f}"
            )

    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description="Persistent regression evaluator for RAG")
    ap.add_argument("--input", default="eval_cases.json")
    ap.add_argument("--base-url", default="http://127.0.0.1:8001")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--output-prefix", default="")
    ap.add_argument("--baseline-commit", default="")
    ap.add_argument("--compare-baseline", default="")
    ap.add_argument("--gate-overall-drop-pct", type=float, default=3.0)
    ap.add_argument("--gate-citation-drop-pct", type=float, default=0.0)
    ap.add_argument("--gate-p95-increase-pct", type=float, default=25.0)
    ap.add_argument(
        "--gate-protected-categories",
        default="curriculum_fact_lookup,regulations",
    )
    args = ap.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 2

    cases = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        print("Input must be a JSON array", file=sys.stderr)
        return 2

    results: list[CaseResult] = []
    total = 0
    planned_cases = [c for c in cases if isinstance(c, dict)]
    if args.limit:
        planned_cases = planned_cases[: int(args.limit)]
    planned_total = len(planned_cases)

    print(
        f"[heartbeat] start total_cases={planned_total} base_url={args.base_url} timeout_s={float(args.timeout):.1f}",
        flush=True,
    )

    for case in cases:
        if args.limit and total >= int(args.limit):
            break
        if not isinstance(case, dict):
            continue

        total += 1

        cid = str(case.get("id") or f"case_{total:03d}")
        category = str(case.get("category") or "uncategorized")
        question = str(case.get("question") or "").strip()
        expected_domain_raw = str(case.get("expected_domain") or "").strip().lower()
        expected_domain = expected_domain_raw if expected_domain_raw else None
        expected_domains_any = [
            str(x).strip().lower()
            for x in (case.get("expected_domains_any") or [])
            if str(x).strip()
        ]

        payload: dict[str, Any] = {"question": question}
        if expected_domain in KNOWN_DOMAINS:
            payload["domain"] = expected_domain

        case_t0 = time.perf_counter()
        print(
            f"[heartbeat] case_start idx={total}/{planned_total or total} id={cid} category={category} domain={expected_domain or 'auto'}",
            flush=True,
        )

        retrieval_data, retrieval_ms, retrieval_err = post_json(
            args.base_url, "/rag/query", payload, timeout_s=float(args.timeout)
        )
        answer_data, total_ms, answer_err = post_json(
            args.base_url, "/rag/answer", payload, timeout_s=float(args.timeout)
        )

        answer = str(answer_data.get("answer") or "").strip()

        retrieval_contexts = retrieval_data.get("contexts") or []
        answer_contexts = answer_data.get("contexts") or []
        contexts = answer_contexts if answer_contexts else retrieval_contexts

        answer_matched, answer_total, answer_coverage, answer_pass = answer_keyword_stats(
            answer,
            list(case.get("expected_answer_keywords") or []),
        )

        retrieval_pass, retrieval_domain_pass, retrieval_source_pass, domains_found, missing_source, mrr, top1 = retrieval_hit(
            contexts,
            expected_domain,
            expected_domains_any,
            list(case.get("expected_source_contains") or []),
        )

        citation_pass, citation_total, citation_valid, citation_issues = citation_validity(answer, contexts)
        must_not_pass = must_not_contain_ok(answer, list(case.get("must_not_contain") or []))

        err = answer_err or retrieval_err
        total_pass = bool(answer_pass and retrieval_pass and citation_pass and must_not_pass and not err)

        meta = answer_data.get("meta") if isinstance(answer_data, dict) else None
        if not isinstance(meta, dict):
            meta = retrieval_data.get("meta") if isinstance(retrieval_data, dict) else {}
        adaptive = coerce_adaptive(meta or {})

        results.append(
            CaseResult(
                id=cid,
                category=category,
                question=question,
                expected_domain=expected_domain,
                expected_domains_any=expected_domains_any,
                answer=answer,
                answer_hit_pass=answer_pass,
                answer_hit_coverage=answer_coverage,
                answer_keywords_matched=answer_matched,
                answer_keywords_total=answer_total,
                retrieval_hit_pass=retrieval_pass,
                retrieval_domain_pass=retrieval_domain_pass,
                retrieval_source_pass=retrieval_source_pass,
                retrieval_domains_found=domains_found,
                retrieval_missing_source_tokens=missing_source,
                retrieval_mrr=mrr,
                retrieval_top_1_pass=top1,
                citation_validity_pass=citation_pass,
                citation_total=citation_total,
                citation_valid_count=citation_valid,
                citation_issues=citation_issues,
                must_not_contain_pass=must_not_pass,
                total_pass=total_pass,
                total_latency_ms=total_ms,
                retrieval_latency_ms=retrieval_ms,
                contexts_count=len(contexts or []),
                error=err,
                adaptive=adaptive,
            )
        )

        case_ms = (time.perf_counter() - case_t0) * 1000.0
        print(
            (
                f"[heartbeat] case_done idx={total}/{planned_total or total} id={cid} "
                f"pass={int(total_pass)} err={int(bool(err))} "
                f"latency_ms={total_ms:.1f} case_ms={case_ms:.1f}"
            ),
            flush=True,
        )

    summary = summarize(results)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.output_prefix:
        out_json = Path(f"{args.output_prefix}.json")
        out_md = Path(f"{args.output_prefix}.md")
    else:
        out_json = Path("reports") / f"eval_runner_{ts}.json"
        out_md = Path("reports") / f"eval_runner_{ts}.md"

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "summary": summary,
        "cases": [asdict(r) for r in results],
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(to_markdown(summary, input_path, args.base_url), encoding="utf-8")

    print(f"Wrote JSON: {out_json}", flush=True)
    print(f"Wrote MD:   {out_md}", flush=True)

    if args.baseline_commit:
        short = (args.baseline_commit or "").strip()[:7]
        baseline = build_baseline(summary, args.baseline_commit)
        b_json = Path("reports") / f"baseline_{short}.json"
        b_md = Path("reports") / f"baseline_{short}.md"
        b_json.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
        b_md.write_text(baseline_markdown(baseline), encoding="utf-8")
        print(f"Wrote baseline JSON: {b_json}", flush=True)
        print(f"Wrote baseline MD:   {b_md}", flush=True)

    if args.compare_baseline:
        baseline_path = Path(args.compare_baseline)
        if not baseline_path.exists():
            print(f"Baseline file not found: {baseline_path}", file=sys.stderr)
            return 3

        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        protected = [
            x.strip()
            for x in str(args.gate_protected_categories).split(",")
            if x.strip()
        ]
        gate_failures = apply_gate(
            summary,
            baseline,
            overall_drop_pct=float(args.gate_overall_drop_pct),
            citation_drop_pct=float(args.gate_citation_drop_pct),
            p95_increase_pct=float(args.gate_p95_increase_pct),
            protected_categories=protected,
        )
        if gate_failures:
            print("GATE FAILED", flush=True)
            for line in gate_failures:
                print(f"- {line}", flush=True)
            return 1
        print("GATE PASSED", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
