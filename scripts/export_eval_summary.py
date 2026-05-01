#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def f4(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.4f}"
    return str(value)


def f2(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.2f}"
    return str(value)


def build_markdown(input_path: Path, payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    coverage = summary.get("coverage", {})
    by_domain = summary.get("by_domain", {})
    errors = summary.get("error_tag_counts", {})

    lines: list[str] = []
    lines.append("# Evaluation Summary")
    lines.append("")
    lines.append(f"Generated from `{input_path}`.")
    lines.append("")
    lines.append("## Headline Metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    for label, key in [
        ("Total cases", "total_cases"),
        ("Overall pass rate", "overall_pass_rate"),
        ("Answer hit rate", "answer_hit_rate"),
        ("Retrieval hit rate", "retrieval_hit_rate"),
        ("Top-1 hit rate", "retrieval_top_1_rate"),
        ("Top-3 hit rate", "retrieval_top_3_rate"),
        ("Top-5 hit rate", "retrieval_top_5_rate"),
        ("MRR", "retrieval_mrr"),
        ("Citation validity", "citation_validity_rate"),
        ("% correct answers", "pct_correct_answers"),
        ("% hallucination", "pct_hallucination"),
        ("% answerable handled correctly", "pct_answerable_handled_correctly"),
        ("Runtime error count", "runtime_error_count"),
    ]:
        value = summary.get(key, "")
        lines.append(f"| {label} | {f4(value) if isinstance(value, float) else value} |")
    lines.append("")

    lines.append("## Latency")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    for label, key in [
        ("Average total latency (ms)", "avg_latency_ms"),
        ("Median total latency (ms)", "median_latency_ms"),
        ("P95 total latency (ms)", "p95_latency_ms"),
        ("Average retrieval latency (ms)", "avg_retrieval_latency_ms"),
        ("Median retrieval latency (ms)", "median_retrieval_latency_ms"),
        ("P95 retrieval latency (ms)", "p95_retrieval_latency_ms"),
        ("Average generation latency (ms)", "avg_generation_latency_ms"),
        ("Median generation latency (ms)", "median_generation_latency_ms"),
        ("P95 generation latency (ms)", "p95_generation_latency_ms"),
    ]:
        lines.append(f"| {label} | {f2(summary.get(key, ''))} |")
    lines.append("")

    lines.append("## Coverage")
    lines.append("")
    lines.append("| Dimension | Distribution |")
    lines.append("|---|---|")
    domain_dist = ", ".join(f"`{k}` {v}" for k, v in coverage.get("questions_by_domain", {}).items())
    diff_dist = ", ".join(f"`{k}` {v}" for k, v in coverage.get("questions_by_difficulty", {}).items())
    type_dist = ", ".join(f"`{k}` {v}" for k, v in coverage.get("questions_by_question_type", {}).items())
    lines.append(f"| Total questions | {coverage.get('total_questions', '')} |")
    lines.append(f"| By domain | {domain_dist} |")
    lines.append(f"| By difficulty | {diff_dist} |")
    lines.append(f"| By question type | {type_dist} |")
    lines.append("")

    lines.append("## Domain Breakdown")
    lines.append("")
    lines.append("| Domain | Total | Overall | Top-1 | Top-5 | MRR | Answer | Citation |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for domain, stats in by_domain.items():
        lines.append(
            f"| `{domain}` | {int(stats.get('total', 0))} | {f4(stats.get('overall_pass_rate', 0.0))} | "
            f"{f4(stats.get('retrieval_top_1_rate', 0.0))} | {f4(stats.get('retrieval_top_5_rate', 0.0))} | "
            f"{f4(stats.get('retrieval_mrr', 0.0))} | {f4(stats.get('answer_hit_rate', 0.0))} | "
            f"{f4(stats.get('citation_validity_rate', 0.0))} |"
        )
    lines.append("")

    lines.append("## Error Analysis")
    lines.append("")
    lines.append("| Error Tag | Count |")
    lines.append("|---|---:|")
    for key, value in sorted(errors.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| `{key}` | {value} |")
    lines.append("")

    lines.append("## Strong Cases")
    lines.append("")
    schema = summary.get("answer_schema_metrics_by_task", {})
    lines.append("| Task | Cases | Success | Attempted |")
    lines.append("|---|---:|---:|---:|")
    for task, stats in sorted(schema.items(), key=lambda kv: (-float(kv[1].get("repair_success", 0)), kv[0])):
        cases = int(stats.get("cases", 0))
        success = int(stats.get("repair_success", 0))
        attempted = int(stats.get("repair_attempted", 0))
        if cases <= 0:
            continue
        lines.append(f"| `{task}` | {cases} | {success} | {attempted} |")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export eval summary JSON to Markdown tables.")
    parser.add_argument("--input", default="qball_ci.json", help="Input eval JSON path.")
    parser.add_argument("--output", default="out/eval_summary.md", help="Output Markdown path.")
    args = parser.parse_args()

    input_path = Path(args.input)
    payload = json.loads(input_path.read_text(encoding="utf-8"))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_markdown(input_path, payload), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
