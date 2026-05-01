#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def fmt_ms(v: Any) -> str:
    return f"{float(v):.2f}"


def build_domain_markdown(data: dict[str, Any], source: Path) -> str:
    domains = data.get('domains', [])
    totals = data.get('totals', {})
    lines = [f"# Ingestion Timing Report ({data.get('mode','')})", "", f"Generated from `{source}`.", ""]
    lines += [
        "## Domain Breakdown",
        "",
        "| Domain | Files | Records | Chunks | Embedded | Extract ms | Chunking ms | DB ms | Embedding ms | Total ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in domains:
        counts = row.get('counts', {})
        phase = row.get('phase_ms', {})
        lines.append(
            f"| `{row.get('domain','')}` | {counts.get('files',0)} | {counts.get('records',0)} | {counts.get('chunks',0)} | "
            f"{counts.get('embedded_chunks',0)} | {fmt_ms(phase.get('extract_total_ms',0.0))} | {fmt_ms(phase.get('chunking_ms',0.0))} | "
            f"{fmt_ms(phase.get('db_store_ms',0.0))} | {fmt_ms(phase.get('embedding_ms',0.0))} | {fmt_ms(row.get('total_ms',0.0))} |"
        )
    lines += ["", "## Totals", "", "| Metric | Value |", "|---|---:|"]
    for key, value in totals.items():
        if isinstance(value, float):
            lines.append(f"| `{key}` | {fmt_ms(value)} |")
        else:
            lines.append(f"| `{key}` | {value} |")
    return "\n".join(lines) + "\n"


def build_transfer_markdown(data: dict[str, Any], source: Path) -> str:
    phase = data.get('phase_ms', {})
    lines = [f"# GPU Host Transfer Timing Report", "", f"Generated from `{source}`.", ""]
    lines += ["| Phase | Time (ms) |", "|---|---:|"]
    for key, value in phase.items():
        lines.append(f"| `{key}` | {fmt_ms(value)} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export ingestion timing JSON to Markdown.")
    parser.add_argument("--input", required=True, help="Input timing JSON path.")
    parser.add_argument("--output", required=True, help="Output Markdown path.")
    args = parser.parse_args()

    input_path = Path(args.input)
    data = json.loads(input_path.read_text(encoding='utf-8'))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if 'domains' in data:
        md = build_domain_markdown(data, input_path)
    else:
        md = build_transfer_markdown(data, input_path)
    output.write_text(md, encoding='utf-8')
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
