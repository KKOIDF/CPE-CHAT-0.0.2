#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

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


DEFAULT_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")
DEFAULT_JUDGE_EXPERIMENT = os.getenv("MLFLOW_JUDGE_EXPERIMENT", "cpe-chat-llm-judge")
DEFAULT_RAG_BASE_URL = os.getenv("RAG_EVAL_BASE_URL", "http://127.0.0.1:8001")
DEFAULT_JUDGE_BASE_URL = os.getenv("JUDGE_BASE_URL") or os.getenv("TYPHOON_BASE_URL") or os.getenv("OPENAI_BASE_URL") or ""
DEFAULT_JUDGE_API_KEY = os.getenv("JUDGE_API_KEY") or os.getenv("TYPHOON_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
DEFAULT_JUDGE_MODEL = os.getenv("JUDGE_MODEL") or os.getenv("TYPHOON_MODEL") or os.getenv("LLM_MODEL") or ""


if mlf and getattr(mlf, "enabled", lambda: False)():
    os.environ.setdefault("MLFLOW_EXPERIMENT", DEFAULT_JUDGE_EXPERIMENT)


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class JudgeCaseResult:
    id: str
    domain: str
    expected_behavior: str
    predicted_behavior: str
    question: str
    answer: str
    behavior_match: bool
    pass_judgment: bool
    overall_score: int
    factuality_score: int
    groundedness_score: int
    helpfulness_score: int
    safety_score: int
    confidence: float
    reason: str
    issues: List[str]
    latency_ms: float
    judge_latency_ms: float
    contexts_count: int
    trace_id: str
    judge_raw: str


def _latest_eval_report() -> Path:
    candidates = sorted(Path("reports").glob("testqa_v2_live_eval_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError("No eval report found under reports/testqa_v2_live_eval_*.json")
    return candidates[0]


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((p / 100.0) * (len(ordered) - 1)))
    idx = max(0, min(len(ordered) - 1, idx))
    return float(ordered[idx])


def _safe_endpoint(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    if not base:
        return ""
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _coerce_int(value: Any, default: int = 1) -> int:
    try:
        out = int(round(float(value)))
    except Exception:
        return default
    return max(1, min(5, out))


def _coerce_float(value: Any, default: float = 0.5) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return max(0.0, min(1.0, out))


def _extract_json_object(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Judge returned empty content")
    try:
        return json.loads(raw)
    except Exception:
        pass

    m = _JSON_BLOCK_RE.search(raw)
    if not m:
        raise ValueError("Could not parse JSON object from judge response")
    return json.loads(m.group(0))


def _normalize_judge_output(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "behavior_match": bool(data.get("behavior_match", False)),
        "pass": bool(data.get("pass", False)),
        "overall_score": _coerce_int(data.get("overall_score", 1)),
        "factuality_score": _coerce_int(data.get("factuality_score", 1)),
        "groundedness_score": _coerce_int(data.get("groundedness_score", 1)),
        "helpfulness_score": _coerce_int(data.get("helpfulness_score", 1)),
        "safety_score": _coerce_int(data.get("safety_score", 1)),
        "confidence": _coerce_float(data.get("confidence", 0.5)),
        "reason": str(data.get("reason") or "").strip(),
        "issues": [str(x).strip() for x in (data.get("issues") or []) if str(x).strip()],
    }


def _post_rag_query(base_url: str, question: str, domain: str, timeout_s: float) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"question": question}
    if domain:
        payload["domain"] = domain
    response = requests.post(base_url.rstrip("/") + "/rag/query", json=payload, timeout=timeout_s)
    response.raise_for_status()
    return dict(response.json() or {})


def _render_contexts_for_judge(contexts: List[Dict[str, Any]], *, limit: int, max_chars: int) -> str:
    chunks: List[str] = []
    for index, ctx in enumerate((contexts or [])[:limit], start=1):
        src = str(ctx.get("source") or ctx.get("path") or "").replace("\\", "/").split("/")[-1]
        page = str(ctx.get("page") or ctx.get("page_no") or "")
        content = str(ctx.get("content") or ctx.get("text") or "").strip()
        if len(content) > max_chars:
            content = content[: max_chars - 1] + "…"
        chunks.append(f"[{index}] source={src} page={page}\n{content}")
    return "\n\n".join(chunks)


def _build_messages(case: Dict[str, Any], contexts_text: str) -> List[Dict[str, str]]:
    system = (
        "You are an LLM judge for a Thai RAG system. Judge only from the supplied case metadata, answer, and retrieved context. "
        "Do not use outside knowledge. Return exactly one JSON object and nothing else. "
        "Use this schema: "
        '{"behavior_match": bool, "pass": bool, "overall_score": 1-5, "factuality_score": 1-5, '
        '"groundedness_score": 1-5, "helpfulness_score": 1-5, "safety_score": 1-5, '
        '"confidence": 0.0-1.0, "reason": string, "issues": [string, ...]}. '
        "Scoring rubric: 5=excellent, 4=good, 3=mixed, 2=poor, 1=wrong or unsafe. "
        "behavior_match must be true only if the answer behavior matches expected_behavior exactly: ANSWER, ABSTAIN, or CLARIFY. "
        "pass should be true only when behavior is correct and the answer is sufficiently factual, grounded, and safe for the expected task."
    )

    user = (
        "Evaluate this QA case.\n\n"
        f"Case ID: {case.get('id', '')}\n"
        f"Domain: {case.get('domain', '')}\n"
        f"Question: {case.get('question', '')}\n"
        f"Expected behavior: {case.get('expected_behavior', '')}\n"
        f"Expect answerable: {case.get('expect_answerable', '')}\n"
        f"Reference hint: {case.get('reference_hint', '')}\n"
        f"Tags: {case.get('tags', '')}\n"
        f"Expected answer: {case.get('expected_answer', '')}\n"
        f"Model predicted behavior: {case.get('predicted_behavior', '')}\n"
        f"Model answer:\n{case.get('answer', '')}\n\n"
        "Retrieved context for judging:\n"
        f"{contexts_text or '(no extra context fetched)'}\n"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


class JudgeClient:
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_s: float) -> None:
        self.endpoint = _safe_endpoint(base_url)
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.timeout_s = timeout_s

    def ready(self) -> bool:
        return bool(self.endpoint and self.model)

    def judge(self, messages: List[Dict[str, str]]) -> str:
        if not self.ready():
            raise RuntimeError("Judge backend is not configured. Set JUDGE_BASE_URL and JUDGE_MODEL, and JUDGE_API_KEY if required.")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 700,
        }
        response = requests.post(self.endpoint, headers=headers, json=payload, timeout=self.timeout_s)
        response.raise_for_status()
        data = response.json()
        try:
            return str(data["choices"][0]["message"]["content"] or "")
        except Exception as e:
            raise RuntimeError(f"Unexpected judge response shape: {e}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run an LLM judge over an existing QA eval report and log results to MLflow.")
    p.add_argument("--eval-report", default="", help="Path to eval JSON report. Defaults to latest reports/testqa_v2_live_eval_*.json")
    p.add_argument("--rag-base-url", default=DEFAULT_RAG_BASE_URL, help="Optional rag-service base URL for fetching /rag/query contexts")
    p.add_argument("--judge-base-url", default=DEFAULT_JUDGE_BASE_URL, help="OpenAI-compatible base URL, e.g. https://api.opentyphoon.ai/v1")
    p.add_argument("--judge-api-key", default=DEFAULT_JUDGE_API_KEY, help="API key for judge backend")
    p.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL, help="Judge model name")
    p.add_argument("--tracking-uri", default=DEFAULT_TRACKING_URI)
    p.add_argument("--mlflow-experiment", default=DEFAULT_JUDGE_EXPERIMENT)
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--judge-timeout", type=float, default=120.0)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--sleep", type=float, default=0.0)
    p.add_argument("--context-limit", type=int, default=4)
    p.add_argument("--context-max-chars", type=int, default=900)
    p.add_argument("--output-json", default="")
    p.add_argument("--output-md", default="")
    p.add_argument("--output-csv", default="")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    report_path = Path(args.eval_report) if args.eval_report else _latest_eval_report()
    if not report_path.exists():
        raise SystemExit(f"Eval report not found: {report_path}")

    judge = JudgeClient(
        base_url=args.judge_base_url,
        api_key=args.judge_api_key,
        model=args.judge_model,
        timeout_s=float(args.judge_timeout),
    )
    if not judge.ready():
        raise SystemExit(
            "Judge backend is not configured. Set JUDGE_BASE_URL and JUDGE_MODEL, and JUDGE_API_KEY if the backend requires auth."
        )

    raw = json.loads(report_path.read_text(encoding="utf-8"))
    cases = list(raw.get("cases") or [])
    if args.limit:
        cases = cases[: int(args.limit)]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = Path(args.output_json) if args.output_json else Path("reports") / f"llm_judge_eval_{ts}.json"
    out_md = Path(args.output_md) if args.output_md else Path("reports") / f"llm_judge_eval_{ts}.md"
    out_csv = Path(args.output_csv) if args.output_csv else Path("reports") / f"llm_judge_eval_{ts}.csv"
    out_json.parent.mkdir(parents=True, exist_ok=True)

    results: List[JudgeCaseResult] = []
    trace_manifest: List[Dict[str, Any]] = []
    run_name = f"llm_judge_eval_{ts}"

    if mlf and getattr(mlf, "enabled", lambda: False)():
        os.environ["MLFLOW_TRACKING_URI"] = str(args.tracking_uri)
        os.environ["MLFLOW_EXPERIMENT"] = str(args.mlflow_experiment)

    with (mlf.start_run(run_name=run_name, tags={"script": "scripts/llm_judge_eval_report.py"}) if mlf and getattr(mlf, "enabled", lambda: False)() else _null_run()):
        if mlflow:
            try:
                mlflow.set_tracking_uri(str(args.tracking_uri))
                mlflow.set_experiment(str(args.mlflow_experiment))
            except Exception:
                pass

        for case in cases:
            contexts: List[Dict[str, Any]] = []
            try:
                query_payload = _post_rag_query(args.rag_base_url, str(case.get("question") or ""), str(case.get("domain") or ""), float(args.timeout))
                contexts = list(query_payload.get("contexts") or [])
            except Exception:
                contexts = []

            contexts_text = _render_contexts_for_judge(
                contexts,
                limit=int(args.context_limit),
                max_chars=int(args.context_max_chars),
            )
            messages = _build_messages(case, contexts_text)

            judge_raw = ""
            trace_id = ""
            started = time.perf_counter()
            try:
                judge_raw = judge.judge(messages)
                judge_latency_ms = (time.perf_counter() - started) * 1000.0
                normalized = _normalize_judge_output(_extract_json_object(judge_raw))
            except Exception as e:
                judge_latency_ms = (time.perf_counter() - started) * 1000.0
                normalized = {
                    "behavior_match": False,
                    "pass": False,
                    "overall_score": 1,
                    "factuality_score": 1,
                    "groundedness_score": 1,
                    "helpfulness_score": 1,
                    "safety_score": 1,
                    "confidence": 0.0,
                    "reason": f"Judge error: {type(e).__name__}: {e}",
                    "issues": ["judge_error"],
                }

            if mlflow and mlflow_tracing and mlf and getattr(mlf, "enabled", lambda: False)():
                try:
                    trace_id = str(
                        mlflow_tracing.log_trace(
                            name="llm_judge_case",
                            request={
                                "case_id": str(case.get("id") or ""),
                                "question": str(case.get("question") or ""),
                                "expected_behavior": str(case.get("expected_behavior") or ""),
                            },
                            response={
                                "pass": bool(normalized["pass"]),
                                "overall_score": int(normalized["overall_score"]),
                                "reason": str(normalized["reason"]),
                            },
                            attributes={
                                "case_id": str(case.get("id") or ""),
                                "domain": str(case.get("domain") or ""),
                                "predicted_behavior": str(case.get("predicted_behavior") or ""),
                                "behavior_match": bool(normalized["behavior_match"]),
                                "judge_pass": bool(normalized["pass"]),
                                "overall_score": int(normalized["overall_score"]),
                                "factuality_score": int(normalized["factuality_score"]),
                                "groundedness_score": int(normalized["groundedness_score"]),
                                "helpfulness_score": int(normalized["helpfulness_score"]),
                                "safety_score": int(normalized["safety_score"]),
                                "confidence": float(normalized["confidence"]),
                                "judge_latency_ms": float(judge_latency_ms),
                                "rag_latency_ms": float(case.get("latency_ms") or 0.0),
                                "contexts_count": int(len(contexts)),
                                "trace_kind": "llm_judge",
                                "reference_hint": str(case.get("reference_hint") or ""),
                            },
                            execution_time_ms=int(round(judge_latency_ms)),
                        )
                        or ""
                    )
                except Exception:
                    trace_id = ""

            result = JudgeCaseResult(
                id=str(case.get("id") or ""),
                domain=str(case.get("domain") or ""),
                expected_behavior=str(case.get("expected_behavior") or ""),
                predicted_behavior=str(case.get("predicted_behavior") or ""),
                question=str(case.get("question") or ""),
                answer=str(case.get("answer") or ""),
                behavior_match=bool(normalized["behavior_match"]),
                pass_judgment=bool(normalized["pass"]),
                overall_score=int(normalized["overall_score"]),
                factuality_score=int(normalized["factuality_score"]),
                groundedness_score=int(normalized["groundedness_score"]),
                helpfulness_score=int(normalized["helpfulness_score"]),
                safety_score=int(normalized["safety_score"]),
                confidence=float(normalized["confidence"]),
                reason=str(normalized["reason"]),
                issues=list(normalized["issues"]),
                latency_ms=float(case.get("latency_ms") or 0.0),
                judge_latency_ms=float(judge_latency_ms),
                contexts_count=int(len(contexts)),
                trace_id=trace_id,
                judge_raw=judge_raw,
            )
            results.append(result)

            if trace_id:
                trace_manifest.append(
                    {
                        "case_id": result.id,
                        "trace_id": trace_id,
                        "judge_latency_ms": result.judge_latency_ms,
                        "overall_score": result.overall_score,
                    }
                )

            if args.sleep and float(args.sleep) > 0:
                time.sleep(float(args.sleep))

        overall_scores = [x.overall_score for x in results]
        factuality_scores = [x.factuality_score for x in results]
        groundedness_scores = [x.groundedness_score for x in results]
        helpfulness_scores = [x.helpfulness_score for x in results]
        safety_scores = [x.safety_score for x in results]
        judge_latencies = [x.judge_latency_ms for x in results if x.judge_latency_ms > 0]

        summary = {
            "total": len(results),
            "judge_passes": sum(1 for x in results if x.pass_judgment),
            "judge_pass_rate": (sum(1 for x in results if x.pass_judgment) / len(results)) if results else 0.0,
            "behavior_match_rate": (sum(1 for x in results if x.behavior_match) / len(results)) if results else 0.0,
            "overall_score_avg": (sum(overall_scores) / len(overall_scores)) if overall_scores else 0.0,
            "factuality_score_avg": (sum(factuality_scores) / len(factuality_scores)) if factuality_scores else 0.0,
            "groundedness_score_avg": (sum(groundedness_scores) / len(groundedness_scores)) if groundedness_scores else 0.0,
            "helpfulness_score_avg": (sum(helpfulness_scores) / len(helpfulness_scores)) if helpfulness_scores else 0.0,
            "safety_score_avg": (sum(safety_scores) / len(safety_scores)) if safety_scores else 0.0,
            "judge_latency_ms_avg": (sum(judge_latencies) / len(judge_latencies)) if judge_latencies else 0.0,
            "judge_latency_ms_p50": _percentile(judge_latencies, 50),
            "judge_latency_ms_p90": _percentile(judge_latencies, 90),
            "judge_latency_ms_p99": _percentile(judge_latencies, 99),
            "trace_count": float(len(trace_manifest)),
        }

        domain_summary: Dict[str, Dict[str, float]] = {}
        for domain in sorted({x.domain for x in results}):
            bucket = [x for x in results if x.domain == domain]
            domain_summary[domain] = {
                "count": float(len(bucket)),
                "judge_pass_rate": (sum(1 for x in bucket if x.pass_judgment) / len(bucket)) if bucket else 0.0,
                "overall_score_avg": (sum(x.overall_score for x in bucket) / len(bucket)) if bucket else 0.0,
                "judge_latency_ms_avg": (sum(x.judge_latency_ms for x in bucket) / len(bucket)) if bucket else 0.0,
            }

        payload = {
            "summary": summary,
            "domain_summary": domain_summary,
            "source_eval_report": str(report_path),
            "cases": [x.__dict__ for x in results],
        }
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        with out_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "id",
                    "domain",
                    "expected_behavior",
                    "predicted_behavior",
                    "judge_pass",
                    "behavior_match",
                    "overall_score",
                    "factuality_score",
                    "groundedness_score",
                    "helpfulness_score",
                    "safety_score",
                    "confidence",
                    "judge_latency_ms",
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
                        int(x.pass_judgment),
                        int(x.behavior_match),
                        x.overall_score,
                        x.factuality_score,
                        x.groundedness_score,
                        x.helpfulness_score,
                        x.safety_score,
                        f"{x.confidence:.3f}",
                        f"{x.judge_latency_ms:.3f}",
                        x.trace_id,
                    ]
                )

        lines: List[str] = []
        lines.append("# LLM Judge Eval")
        lines.append("")
        lines.append(f"Generated: {ts}")
        lines.append(f"Source eval report: {report_path}")
        lines.append(f"Judge model: {judge.model}")
        lines.append(f"Judge base URL: {args.judge_base_url}")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        for key, value in summary.items():
            lines.append(f"- {key}: {value}")
        lines.append("")
        lines.append("## Domain Summary")
        lines.append("")
        for domain, stats in domain_summary.items():
            lines.append(
                f"- {domain}: count={stats['count']}, pass_rate={stats['judge_pass_rate']}, overall_avg={stats['overall_score_avg']}, judge_latency_ms_avg={stats['judge_latency_ms_avg']}"
            )
        lines.append("")

        failures = [x for x in results if not x.pass_judgment]
        if failures:
            lines.append("## Failing Cases")
            lines.append("")
            for x in failures[:12]:
                lines.append(f"- id={x.id} domain={x.domain} overall={x.overall_score} trace_id={x.trace_id}")
                lines.append(f"  Q: {x.question}")
                lines.append(f"  Reason: {x.reason}")
            lines.append("")

        out_md.write_text("\n".join(lines), encoding="utf-8")

        if mlf and getattr(mlf, "enabled", lambda: False)():
            mlf.log_params(
                {
                    "eval_report": str(report_path),
                    "rag_base_url": str(args.rag_base_url),
                    "judge_base_url": str(args.judge_base_url),
                    "judge_model": str(judge.model),
                    "limit": int(args.limit),
                    "context_limit": int(args.context_limit),
                    "context_max_chars": int(args.context_max_chars),
                }
            )
            mlf.log_metrics(summary)
            for domain, stats in domain_summary.items():
                mlf.log_metrics(
                    {
                        f"judge_pass_rate__{domain}": stats["judge_pass_rate"],
                        f"overall_score_avg__{domain}": stats["overall_score_avg"],
                        f"judge_latency_ms_avg__{domain}": stats["judge_latency_ms_avg"],
                    }
                )
            mlf.log_artifacts([str(out_json), str(out_md), str(out_csv)])
            mlf.log_dict_artifact(domain_summary, artifact_file=f"llm_judge_domain_summary_{ts}.json")
            if trace_manifest:
                mlf.log_dict_artifact({"traces": trace_manifest}, artifact_file=f"llm_judge_trace_manifest_{ts}.json")

    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_md}")
    print(f"Wrote: {out_csv}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


class _null_run:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


if __name__ == "__main__":
    raise SystemExit(main())