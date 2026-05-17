#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "http://localhost:8001"
DEFAULT_MODEL = "gemma4:26b"
DEFAULT_TIMEOUT = 120
DEFAULT_RUNS = 3
DEFAULT_CONTAINER = "cpe-chat-rag"
DEFAULT_REPORT_DIR = Path("reports/latency_benchmarks")
DEFAULT_QUESTIONS = [
    "เงื่อนไขการสำเร็จหลักสูตรมีอะไรบ้าง",
    "ใบลา",
    "หากนักศึกษาเข้าสอบสาย จะมีระเบียบหรือแนวทางปฏิบัติอย่างไร",
    "วิชาบังคับของภาควิชาคือวิชาอะไรบ้าง",
    "วิชาบังครับของภาควิชาคือวิชาอะไรบ้าง",
]
TIMING_KEYS = [
    "total",
    "langchain_rag",
    "rag_query",
    "vector_search",
    "embed_query_ms",
    "chroma_query_ms",
    "llm_generate",
    "top_k_rerank",
    "embedding_fetch_ms",
    "structured_regulations",
    "structured_curriculum",
]
METRIC_KEYS = [
    "path_langchain_used",
    "path_nonstructured_used",
    "retrieval_fallback_all_domains_triggered",
    "retrieval_adaptive_retry_triggered",
    "retrieval_cache_hit",
    "embed_query_cache_hit",
    "auto_evidence_verifier_skipped",
    "routing_domain_final",
    "intent_primary",
    "ctx_n",
    "structured_path_hit",
    "structured_regulations_shortcut_preferred",
    "structured_curriculum_shortcut_preferred",
]


@dataclass
class RunResult:
    endpoint: str
    question: str
    run_index: int
    session_id: str
    ok: bool
    status: int | None
    elapsed_s: float
    answer_preview: str
    error: str | None
    timings: dict[str, float]
    metrics: dict[str, Any]
    response_meta: dict[str, Any]


@dataclass
class QuestionSummary:
    endpoint: str
    question: str
    runs: int
    success_runs: int
    min_s: float | None
    median_s: float | None
    avg_s: float | None
    max_s: float | None
    timing_medians_ms: dict[str, float]
    timing_max_ms: dict[str, float]
    metric_last: dict[str, Any]
    cache_hits: dict[str, int]



def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")



def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            elapsed = time.perf_counter() - started
            return {
                "ok": True,
                "status": resp.status,
                "elapsed": elapsed,
                "raw": raw,
                "json": json.loads(raw),
                "error": None,
            }
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - started
        raw = e.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status": e.code,
            "elapsed": elapsed,
            "raw": raw,
            "json": None,
            "error": str(e),
        }
    except Exception as e:
        elapsed = time.perf_counter() - started
        return {
            "ok": False,
            "status": None,
            "elapsed": elapsed,
            "raw": "",
            "json": None,
            "error": repr(e),
        }



def extract_answer(endpoint: str, payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    if endpoint == "/rag/answer":
        return str(payload.get("answer") or "")
    try:
        return str(payload["choices"][0]["message"]["content"] or "")
    except Exception:
        return ""



def extract_meta(endpoint: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    if endpoint == "/rag/answer":
        return dict(payload.get("meta") or {})
    return {}



def docker_logs_since(container: str, since_iso: str) -> str:
    try:
        proc = subprocess.run(
            ["docker", "logs", "--since", since_iso, container],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return ""
    return (proc.stdout or "") + "\n" + (proc.stderr or "")



def parse_timing_line(line: str) -> tuple[dict[str, float], dict[str, Any]]:
    timings: dict[str, float] = {}
    metrics: dict[str, Any] = {}
    body = line.strip()
    if "|" in body:
        timing_part, metric_part = body.split("|", 1)
    else:
        timing_part, metric_part = body, ""
    for token in timing_part.split():
        if "=" not in token or not token.endswith("ms"):
            continue
        key, value = token.split("=", 1)
        try:
            timings[key.strip()] = float(value[:-2])
        except Exception:
            continue
    for key in METRIC_KEYS:
        needle = f"{key}="
        idx = metric_part.find(needle)
        if idx < 0:
            continue
        start = idx + len(needle)
        end = metric_part.find(" ", start)
        raw = metric_part[start:] if end < 0 else metric_part[start:end]
        raw = raw.strip()
        if raw in ("0", "1"):
            metrics[key] = int(raw)
            continue
        try:
            if "." in raw:
                metrics[key] = float(raw)
            else:
                metrics[key] = int(raw)
        except Exception:
            metrics[key] = raw
    return timings, metrics



def find_timing_for_session(log_text: str, session_id: str, request_name: str) -> tuple[dict[str, float], dict[str, Any]]:
    target = f"[TIMING][{request_name}]"
    matched: list[str] = []
    for line in log_text.splitlines():
        if target not in line:
            continue
        if f"session_id={session_id}" not in line:
            continue
        matched.append(line)
    if not matched:
        return {}, {}
    return parse_timing_line(matched[-1])



def build_payload(endpoint: str, question: str, session_id: str, model: str) -> dict[str, Any]:
    if endpoint == "/rag/answer":
        return {
            "question": question,
            "domain": "auto",
            "session_id": session_id,
        }
    if endpoint == "/v1/chat/completions":
        return {
            "model": model,
            "messages": [{"role": "user", "content": question}],
            "session_id": session_id,
        }
    raise ValueError(f"Unsupported endpoint: {endpoint}")



def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    values = sorted(values)
    k = (len(values) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return float(values[f])
    d0 = values[f] * (c - k)
    d1 = values[c] * (k - f)
    return float(d0 + d1)



def summarize_question(endpoint: str, question: str, rows: list[RunResult]) -> QuestionSummary:
    success = [r for r in rows if r.ok]
    elapsed = [r.elapsed_s for r in success]
    timing_medians: dict[str, float] = {}
    timing_max: dict[str, float] = {}
    for key in TIMING_KEYS:
        vals = [r.timings[key] for r in success if key in r.timings]
        if vals:
            timing_medians[key] = round(statistics.median(vals), 1)
            timing_max[key] = round(max(vals), 1)
    metric_last = dict(success[-1].metrics if success else {})
    cache_hits = {
        "retrieval_cache_hit_runs": sum(int((r.metrics.get("retrieval_cache_hit") or 0) == 1) for r in success),
        "embed_query_cache_hit_runs": sum(int((r.metrics.get("embed_query_cache_hit") or 0) == 1) for r in success),
    }
    return QuestionSummary(
        endpoint=endpoint,
        question=question,
        runs=len(rows),
        success_runs=len(success),
        min_s=round(min(elapsed), 3) if elapsed else None,
        median_s=round(statistics.median(elapsed), 3) if elapsed else None,
        avg_s=round(statistics.mean(elapsed), 3) if elapsed else None,
        max_s=round(max(elapsed), 3) if elapsed else None,
        timing_medians_ms=timing_medians,
        timing_max_ms=timing_max,
        metric_last=metric_last,
        cache_hits=cache_hits,
    )



def render_markdown(results: list[RunResult], summaries: list[QuestionSummary], args: argparse.Namespace) -> str:
    lines: list[str] = []
    lines.append("# Post-fix RAG Latency Benchmark")
    lines.append("")
    lines.append(f"- Base URL: `{args.base_url}`")
    lines.append(f"- Endpoints: `{', '.join(args.endpoints)}`")
    lines.append(f"- Runs per question: `{args.runs}`")
    lines.append(f"- Timestamp: `{utc_now_iso()}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    for summary in summaries:
        lines.append(f"### {summary.endpoint} :: {summary.question}")
        lines.append(f"- success: `{summary.success_runs}/{summary.runs}`")
        lines.append(f"- client latency s: min=`{summary.min_s}` median=`{summary.median_s}` avg=`{summary.avg_s}` max=`{summary.max_s}`")
        if summary.timing_medians_ms:
            timing_bits = ", ".join(f"{k}={v}ms" for k, v in summary.timing_medians_ms.items())
            lines.append(f"- timing median: {timing_bits}")
        if summary.cache_hits:
            lines.append(
                f"- cache hits: retrieval=`{summary.cache_hits.get('retrieval_cache_hit_runs', 0)}` embed_query=`{summary.cache_hits.get('embed_query_cache_hit_runs', 0)}`"
            )
        if summary.metric_last:
            interesting = []
            for key in (
                "routing_domain_final",
                "intent_primary",
                "path_langchain_used",
                "path_nonstructured_used",
                "retrieval_fallback_all_domains_triggered",
                "auto_evidence_verifier_skipped",
                "ctx_n",
                "structured_path_hit",
                "structured_regulations_shortcut_preferred",
                "structured_curriculum_shortcut_preferred",
            ):
                if key in summary.metric_last:
                    interesting.append(f"{key}={summary.metric_last[key]}")
            if interesting:
                lines.append(f"- last-run metrics: {', '.join(interesting)}")
        lines.append("")

    lines.append("## Per-run")
    lines.append("")
    for row in results:
        lines.append(f"### {row.endpoint} :: {row.question} :: run {row.run_index}")
        lines.append(f"- session_id: `{row.session_id}`")
        lines.append(f"- status: `{row.status}` ok=`{row.ok}` elapsed=`{row.elapsed_s:.3f}s`")
        if row.error:
            lines.append(f"- error: `{row.error}`")
        if row.timings:
            lines.append("- timings: " + ", ".join(f"{k}={v}ms" for k, v in sorted(row.timings.items())))
        if row.metrics:
            lines.append("- metrics: " + ", ".join(f"{k}={row.metrics[k]}" for k in sorted(row.metrics.keys())))
        if row.answer_preview:
            lines.append("- answer preview:")
            lines.append("")
            lines.append(f"```text\n{row.answer_preview}\n```")
        lines.append("")
    return "\n".join(lines)



def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Benchmark post-fix RAG latency and cache behavior")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--container", default=DEFAULT_CONTAINER)
    ap.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    ap.add_argument("--questions-file", default="")
    ap.add_argument("--endpoint", dest="endpoints", action="append", choices=["/rag/answer", "/v1/chat/completions"])
    ap.add_argument("--no-log-parse", action="store_true", help="Skip docker log parsing and only measure client-side latency")
    return ap.parse_args()



def load_questions(path_str: str) -> list[str]:
    if not path_str:
        return list(DEFAULT_QUESTIONS)
    path = Path(path_str)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("questions") or []
    if not isinstance(raw, list):
        raise ValueError("questions file must be a JSON list or {questions:[...]}")
    return [str(x).strip() for x in raw if str(x).strip()]



def main() -> int:
    args = parse_args()
    questions = load_questions(args.questions_file)
    endpoints = args.endpoints or ["/rag/answer"]
    request_name_map = {
        "/rag/answer": "rag_answer",
        "/v1/chat/completions": "v1_chat_completions",
    }
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    all_rows: list[RunResult] = []

    print("=" * 88)
    print("Post-fix RAG latency benchmark")
    print(f"Base URL: {args.base_url}")
    print(f"Endpoints: {', '.join(endpoints)}")
    print(f"Questions: {len(questions)}")
    print(f"Runs/question: {args.runs}")
    print("=" * 88)

    for endpoint in endpoints:
        url = f"{args.base_url}{endpoint}"
        for q_idx, question in enumerate(questions, start=1):
            print(f"\n[{endpoint}] Q{q_idx}/{len(questions)}: {question}")
            for run_idx in range(1, args.runs + 1):
                session_id = f"bench-{stamp}-{q_idx:02d}-{run_idx:02d}-{uuid.uuid4().hex[:8]}"
                payload = build_payload(endpoint, question, session_id, args.model)
                since_iso = utc_now_iso()
                result = post_json(url, payload, timeout=args.timeout)
                time.sleep(0.4)
                timings: dict[str, float] = {}
                metrics: dict[str, Any] = {}
                if not args.no_log_parse:
                    logs = docker_logs_since(args.container, since_iso)
                    timings, metrics = find_timing_for_session(logs, session_id, request_name_map[endpoint])
                answer = extract_answer(endpoint, result.get("json"))
                meta = extract_meta(endpoint, result.get("json"))
                row = RunResult(
                    endpoint=endpoint,
                    question=question,
                    run_index=run_idx,
                    session_id=session_id,
                    ok=bool(result["ok"]),
                    status=result["status"],
                    elapsed_s=float(result["elapsed"]),
                    answer_preview=(answer or result.get("raw") or "")[:400],
                    error=result.get("error"),
                    timings=timings,
                    metrics=metrics,
                    response_meta=meta,
                )
                all_rows.append(row)
                summary_bits = [f"status={row.status}", f"elapsed={row.elapsed_s:.3f}s"]
                if "embed_query_ms" in row.timings:
                    summary_bits.append(f"embed={row.timings['embed_query_ms']:.1f}ms")
                if "retrieval_cache_hit" in row.metrics:
                    summary_bits.append(f"retrieval_cache_hit={row.metrics['retrieval_cache_hit']}")
                if "embed_query_cache_hit" in row.metrics:
                    summary_bits.append(f"embed_cache_hit={row.metrics['embed_query_cache_hit']}")
                if "path_langchain_used" in row.metrics:
                    summary_bits.append(f"lc={row.metrics['path_langchain_used']}")
                if "path_nonstructured_used" in row.metrics:
                    summary_bits.append(f"nonstructured={row.metrics['path_nonstructured_used']}")
                print("  - run", run_idx, "::", ", ".join(summary_bits))

    grouped: dict[tuple[str, str], list[RunResult]] = {}
    for row in all_rows:
        grouped.setdefault((row.endpoint, row.question), []).append(row)
    summaries = [summarize_question(endpoint, question, rows) for (endpoint, question), rows in grouped.items()]

    json_path = report_dir / f"post_fix_latency_{stamp}.json"
    md_path = report_dir / f"post_fix_latency_{stamp}.md"
    payload = {
        "generated_at": utc_now_iso(),
        "base_url": args.base_url,
        "endpoints": endpoints,
        "questions": questions,
        "runs": args.runs,
        "results": [asdict(r) for r in all_rows],
        "summaries": [asdict(s) for s in summaries],
        "p95_client_latency_s": {
            endpoint: percentile([r.elapsed_s for r in all_rows if r.endpoint == endpoint and r.ok], 95)
            for endpoint in endpoints
        },
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(all_rows, summaries, args), encoding="utf-8")

    print("\n" + "=" * 88)
    print("Summary")
    print("=" * 88)
    for summary in summaries:
        print(f"[{summary.endpoint}] {summary.question}")
        print(f"  success={summary.success_runs}/{summary.runs} median={summary.median_s}s max={summary.max_s}s")
        if summary.timing_medians_ms:
            print("  timings:", ", ".join(f"{k}={v}ms" for k, v in summary.timing_medians_ms.items()))
        if summary.cache_hits:
            print("  cache:", ", ".join(f"{k}={v}" for k, v in summary.cache_hits.items()))
    print(f"\nJSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
