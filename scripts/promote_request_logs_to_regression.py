#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _norm_question(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or '').strip().lower())


def _iter_events(patterns: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_files: set[str] = set()
    for pattern in patterns:
        for path_str in glob.glob(pattern, recursive=True):
            path = Path(path_str)
            if not path.is_file():
                continue
            norm_path = str(path.resolve())
            if norm_path in seen_files:
                continue
            seen_files.add(norm_path)
            try:
                for line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    if isinstance(item, dict) and item.get('question'):
                        rows.append(item)
            except Exception:
                continue
    return rows


def _parse_tracking_uri(uri: str) -> Path | None:
    raw = str(uri or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme in ("", "file"):
        if parsed.scheme == "file":
            path = parsed.path or ""
            if os.name == "nt" and path.startswith("/"):
                path = path[1:]
            return Path(path).expanduser().resolve()
        return Path(raw).expanduser().resolve()
    return None


def _mlflow_local_globs(tracking_uri: str, request_dir: str) -> list[str]:
    root = _parse_tracking_uri(tracking_uri)
    if root is None:
        return []

    req = str(request_dir or "requests").strip().strip("/") or "requests"
    roots = [root]
    if root.name == "mlruns":
        roots.append(root.parent / "mlartifacts")
    if root.name == "mlartifacts":
        roots.append(root.parent / "mlruns")

    patterns: list[str] = []
    seen: set[str] = set()
    for base in roots:
        for pat in (
            base / "**" / "artifacts" / req / "*.jsonl",
            base / "**" / req / "*.jsonl",
        ):
            key = str(pat)
            if key in seen:
                continue
            seen.add(key)
            patterns.append(key)
    return patterns


def _expand_input_dirs(input_dirs: list[str], request_dir: str) -> list[str]:
    patterns: list[str] = []
    seen: set[str] = set()
    req = str(request_dir or "requests").strip().strip("/") or "requests"
    for item in input_dirs:
        base = Path(str(item or "").strip()).expanduser()
        if not str(base):
            continue
        for pat in (
            base / "**" / "*.jsonl",
            base / "**" / req / "*.jsonl",
            base / "**" / "artifacts" / req / "*.jsonl",
        ):
            key = str(pat)
            if key in seen:
                continue
            seen.add(key)
            patterns.append(key)
    return patterns


def _looks_bad(evt: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    answer = str(evt.get('answer') or '')
    if bool(evt.get('error')):
        reasons.append('error')
    if int(evt.get('ctx_n') or 0) == 0:
        reasons.append('no_context')
    if 'timeout' in answer.lower() or 'empty response' in answer.lower():
        reasons.append('timeout_or_empty')
    if int(evt.get('answer_chars') or 0) < 24:
        reasons.append('short_answer')
    if str(evt.get('structured_path_miss_reason') or '').strip():
        reasons.append('structured_miss')
    if int(evt.get('path_nonstructured_used') or 0) and not int(evt.get('structured_path_hit') or 0):
        reasons.append('nonstructured_fallback')
    if int(evt.get('guardrail_triggered') or 0):
        reasons.append('guardrail')
    return bool(reasons), reasons


def _priority(count: int, bad_count: int) -> str:
    rate = (bad_count / count) if count else 0.0
    if count >= 3 and rate >= 0.5:
        return 'P0'
    if count >= 2 and rate >= 0.4:
        return 'P1'
    return 'P2'


def main() -> int:
    ap = argparse.ArgumentParser(description='Promote request-log events into regression candidates.')
    ap.add_argument(
        '--input-glob',
        action='append',
        default=[
            'mlruns/**/artifacts/requests/*.jsonl',
            'mlartifacts/**/artifacts/requests/*.jsonl',
            'reports/requests/*.jsonl',
            'requests/*.jsonl',
        ],
        help='Glob for request-log JSONL artifacts. Can be repeated.',
    )
    ap.add_argument(
        '--input-dir',
        action='append',
        default=[],
        help='Directory containing exported request logs or MLflow artifact trees. Can be repeated.',
    )
    ap.add_argument(
        '--tracking-uri',
        default=(os.getenv('MLFLOW_TRACKING_URI') or '').strip(),
        help='Optional MLflow tracking URI. Local file/file:// URIs are expanded into artifact globs automatically.',
    )
    ap.add_argument(
        '--request-log-dir',
        default=(os.getenv('MLFLOW_OBS_REQUEST_LOG_DIR') or 'requests').strip() or 'requests',
        help='Artifact subdirectory name used by request logs (default: requests).',
    )
    ap.add_argument('--top-k', type=int, default=200)
    ap.add_argument('--out-dir', default='reports')
    args = ap.parse_args()

    patterns: list[str] = list(args.input_glob or [])
    patterns.extend(_expand_input_dirs(list(args.input_dir or []), str(args.request_log_dir or 'requests')))
    if args.tracking_uri:
        patterns.extend(_mlflow_local_globs(str(args.tracking_uri), str(args.request_log_dir or 'requests')))

    uniq_patterns: list[str] = []
    seen_patterns: set[str] = set()
    for pat in patterns:
        key = str(pat or '').strip()
        if not key or key in seen_patterns:
            continue
        seen_patterns.add(key)
        uniq_patterns.append(key)

    events = _iter_events(uniq_patterns)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for evt in events:
        key = _norm_question(str(evt.get('question') or ''))
        if key:
            grouped[key].append(evt)

    ranked: list[dict[str, Any]] = []
    for key, rows in grouped.items():
        bad_rows = []
        reason_counts: dict[str, int] = defaultdict(int)
        domains: dict[str, int] = defaultdict(int)
        intents: dict[str, int] = defaultdict(int)
        latencies: list[float] = []
        for row in rows:
            bad, reasons = _looks_bad(row)
            if bad:
                bad_rows.append(row)
                for reason in reasons:
                    reason_counts[reason] += 1
            domains[str(row.get('domain') or row.get('requested_domain') or 'unknown')] += 1
            intents[str(row.get('intent_primary') or row.get('failure_intent') or 'unknown')] += 1
            try:
                latencies.append(float(row.get('total_ms') or 0.0))
            except Exception:
                pass
        if not bad_rows:
            continue
        sample = rows[-1]
        ranked.append(
            {
                'priority': _priority(len(rows), len(bad_rows)),
                'question': str(sample.get('question') or key),
                'count': len(rows),
                'bad_count': len(bad_rows),
                'bad_rate': round(len(bad_rows) / len(rows), 4),
                'avg_latency_ms': round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
                'domain': max(domains.items(), key=lambda x: x[1])[0] if domains else 'unknown',
                'intent': max(intents.items(), key=lambda x: x[1])[0] if intents else 'unknown',
                'reasons': sorted(reason_counts.items(), key=lambda x: (-x[1], x[0])),
                'latest_answer': str(sample.get('answer') or ''),
                'latest_ctx_sources': str(sample.get('ctx_sources') or ''),
            }
        )

    ranked.sort(key=lambda row: (row['priority'], -int(row['bad_count']), -int(row['count'])))
    ranked = ranked[: max(1, int(args.top_k or 1))]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_json = out_dir / f'promoted_regression_candidates_{stamp}.json'
    out_csv = out_dir / f'promoted_regression_candidates_{stamp}.csv'
    out_json.write_text(json.dumps({'candidates': ranked}, ensure_ascii=False, indent=2), encoding='utf-8')

    with out_csv.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                'priority', 'question', 'count', 'bad_count', 'bad_rate',
                'avg_latency_ms', 'domain', 'intent', 'reasons',
                'latest_answer', 'latest_ctx_sources',
            ],
        )
        writer.writeheader()
        for row in ranked:
            flat = dict(row)
            flat['reasons'] = '; '.join([f'{k}:{v}' for k, v in row.get('reasons', [])])
            writer.writerow(flat)

    print(f'scanned_patterns={len(uniq_patterns)}')
    print(f'events_total={len(events)}')
    print(f'candidates_total={len(ranked)}')
    print(f'wrote {out_json}')
    print(f'wrote {out_csv}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
