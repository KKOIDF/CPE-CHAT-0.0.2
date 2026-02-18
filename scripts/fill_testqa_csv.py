#!/usr/bin/env python3
import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _detect_domain(cell0: str) -> Optional[str]:
    s = (cell0 or '').lower()
    if 'announcement' in s:
        return 'announcements'
    if 'regulation' in s:
        return 'regulations'
    if 'curriculum' in s:
        return 'curriculum'
    return None


def _post_json(url: str, payload: Dict[str, Any], timeout_s: int = 120, retries: int = 2) -> Dict[str, Any]:
    # Use requests if available; fall back to urllib.
    last_err: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            try:
                import requests  # type: ignore

                resp = requests.post(url, json=payload, timeout=timeout_s)
                resp.raise_for_status()
                return resp.json()
            except ModuleNotFoundError:
                import urllib.request

                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST',
                )
                with urllib.request.urlopen(req, timeout=timeout_s) as r:
                    body = r.read().decode('utf-8', errors='replace')
                return json.loads(body)
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            raise
    raise RuntimeError(str(last_err))


def _is_question_row(row: List[str]) -> bool:
    if not row:
        return False
    first = (row[0] or '').strip()
    if not first:
        return False
    try:
        int(first)
        return True
    except Exception:
        return False


def _ensure_len(row: List[str], n: int) -> List[str]:
    if len(row) >= n:
        return row
    return row + [''] * (n - len(row))


def main() -> int:
    ap = argparse.ArgumentParser(description='Fill QA CSV with answers from running rag-service.')
    ap.add_argument('--input', default='testQA_domains_30_revised.csv', help='Input CSV path')
    ap.add_argument('--output', default='', help='Output CSV path (default: timestamped next to input)')
    ap.add_argument('--base-url', default='http://localhost:8001', help='RAG service base URL')
    ap.add_argument('--rounds', type=int, default=3, help='How many times to answer each question (fills round columns)')
    ap.add_argument('--timeout', type=int, default=120, help='HTTP timeout seconds')
    ap.add_argument('--sleep', type=float, default=0.0, help='Sleep seconds between requests')
    ap.add_argument('--overwrite', action='store_true', help='Overwrite existing round columns even if already filled')
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"[ERROR] Input not found: {in_path}", file=sys.stderr)
        return 2

    out_path = Path(args.output) if args.output else in_path.with_name(
        f"{in_path.stem}_answered_{datetime.now().strftime('%Y%m%d_%H%M%S')}{in_path.suffix}"
    )

    answer_url = args.base_url.rstrip('/') + '/rag/answer'

    # Read entire CSV (it contains section headers + blank rows).
    with in_path.open('r', encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        rows = [list(r) for r in reader]

    current_domain: Optional[str] = None
    filled = 0
    total_q = 0

    # Heuristic column indices (this file format is consistent across sections)
    COL_NO = 0
    COL_Q = 1
    COL_EXPECT = 2
    COL_R1 = 3

    for i, row in enumerate(rows):
        row0 = (row[0] if row else '')
        dom = _detect_domain(row0)
        if dom:
            current_domain = dom
            continue

        if not _is_question_row(row):
            continue
        row = _ensure_len(row, COL_R1 + max(args.rounds, 3))
        rows[i] = row

        q = (row[COL_Q] if len(row) > COL_Q else '').strip()
        if not q:
            continue
        if not current_domain:
            # If domain header missing, skip to avoid misrouting.
            continue

        total_q += 1

        payload = {'domain': current_domain, 'question': q}

        for r in range(args.rounds):
            col = COL_R1 + r
            if col >= len(row):
                row.extend([''] * (col + 1 - len(row)))
            if (row[col] or '').strip() and not args.overwrite:
                continue

            try:
                data = _post_json(answer_url, payload, timeout_s=int(args.timeout))
                ans = str(data.get('answer') or '').strip()
                if not ans:
                    # Some builds return prompt+answer together; keep diagnostic JSON.
                    ans = json.dumps(data, ensure_ascii=False)
                row[col] = ans
                filled += 1
            except Exception as e:
                row[col] = f"(ERROR) {type(e).__name__}: {e}"

            if args.sleep and args.sleep > 0:
                time.sleep(float(args.sleep))

        # progress
        if total_q % 5 == 0:
            print(f"progress: {total_q} questions processed (filled cells={filled})")

    with out_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    print(f"Wrote: {out_path}")
    print(f"Questions seen: {total_q}; answer cells filled: {filled}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
