#!/usr/bin/env python3
"""Fill a QA CSV with system answers from the running RAG service.

Reads the CSV, detects section (announcements/curriculum/regulations), and for each
row with a question, calls the RAG API:
    POST <base-url>/rag/answer  {"domain": <domain>, "question": <question>}

Writes answers into the "คำตอบที่ระบบตอบ\nรอบที่1/2/3" columns.

Usage:
    python scripts/fill_testqa_round1.py --in testQA_domains_30_revised.csv --rounds 3

By default, creates a .bak backup and overwrites the input file.
"""

import argparse
import csv
import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional


def _is_int(s: str) -> bool:
    try:
        int(s.strip())
        return True
    except Exception:
        return False


def _detect_domain_from_section_line(line0: str) -> Optional[str]:
    s = (line0 or "").strip().lower()
    if s.startswith("announcements"):
        return "announcements"
    if s.startswith("curriculum"):
        return "curriculum"
    if s.startswith("regulations"):
        return "regulations"
    return None


def _find_round_col(header_row: list[str], round_num: int) -> Optional[int]:
    # Header cell may contain a literal newline, or may be split depending on CSV authoring.
    needle = f"รอบที่{round_num}"
    for i, cell in enumerate(header_row):
        c = (cell or "").replace("\r", "")
        if "คำตอบที่ระบบตอบ" in c and needle in c:
            return i
        if c.strip() == "คำตอบที่ระบบตอบ" and i + 1 < len(header_row) and needle in (header_row[i + 1] or ""):
            return i
    return None


def _ensure_round_header(header_row: list[str], round_num: int) -> int:
    """Ensure the header row has a column for the given round.

    Returns the column index for that round after ensuring it exists.
    """
    existing = _find_round_col(header_row, round_num)
    if existing is not None:
        return existing

    # Append a new single-cell header like existing format: "คำตอบที่ระบบตอบ\nรอบที่N"
    header_row.append(f"คำตอบที่ระบบตอบ\nรอบที่{round_num}")
    return len(header_row) - 1


def _post_json(
    url: str,
    payload: Dict[str, Any],
    *,
    connect_timeout_s: float,
    read_timeout_s: float,
    retries: int,
    session: Any | None = None,
) -> Dict[str, Any]:
    last_err: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            try:
                import requests  # type: ignore

                sess = session or requests
                resp = sess.post(
                    url,
                    json=payload,
                    timeout=(float(connect_timeout_s), float(read_timeout_s)),
                )
                if resp.status_code >= 400:
                    # Keep a short body snippet for debugging.
                    body = (resp.text or "").strip().replace("\n", " ")
                    body = body[:400]
                    raise RuntimeError(f"HTTP {resp.status_code}: {body}")
                return resp.json()
            except ModuleNotFoundError:
                import urllib.request

                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=float(read_timeout_s)) as r:
                    body = r.read().decode("utf-8", errors="replace")
                return json.loads(body)
        except Exception as e:
            last_err = e
            if attempt < retries:
                # simple backoff
                time.sleep(1.0 * (attempt + 1))
                continue
            raise
    raise RuntimeError(str(last_err))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="in_path", default="testQA_domains_30_revised.csv")
    p.add_argument("--base-url", default="http://localhost:8001", help="RAG service base URL")
    p.add_argument("--rounds", type=int, default=1, help="How many rounds to fill (1-3)")
    p.add_argument("--timeout", type=int, default=60, help="HTTP read timeout seconds")
    p.add_argument("--connect-timeout", type=float, default=5.0, help="HTTP connect timeout seconds")
    p.add_argument("--retries", type=int, default=2, help="HTTP retries per call")
    p.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between requests")
    p.add_argument("--overwrite", action="store_true", help="Overwrite already-filled answer cells")
    p.add_argument(
        "--retry-exceptions",
        action="store_true",
        help="Treat cells starting with '(exception)' as empty and re-run them",
    )
    p.add_argument("--flush-every", type=int, default=5, help="Write CSV every N questions")
    p.add_argument("--no-backup", action="store_true", help="Do not create .bak")
    args = p.parse_args()

    in_path = Path(args.in_path)
    if not in_path.exists():
        raise SystemExit(f"Input not found: {in_path}")

    base_url = str(args.base_url).rstrip("/")
    answer_url = base_url + "/rag/answer"

    rounds = int(args.rounds)
    if rounds < 1 or rounds > 4:
        raise SystemExit("--rounds must be 1..4")

    # Backup before mutating the input file.
    if not args.no_backup:
        backup = in_path.with_suffix(in_path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(in_path, backup)

    # Read all rows first (preserve structure)
    rows: list[list[str]] = []
    with in_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for r in reader:
            rows.append(r)

    # Walk rows, track section/domain and header mapping.
    current_domain: Optional[str] = None
    round_cols: dict[int, Optional[int]] = {1: None, 2: None, 3: None, 4: None}
    # Default column guess: [ลำดับ, คำถาม, คำตอบที่คาดว่าจะตอบ, r1, r2, r3]
    QUESTION_COL = 1

    filled_cells = 0
    skipped = 0
    errors = 0
    questions_seen = 0

    def _write_now() -> None:
        with in_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

    try:
        import requests  # type: ignore

        http_session: Any | None = requests.Session()
    except Exception:
        http_session = None

    try:
        for idx, r in enumerate(rows):
            if not r:
                continue

            # Detect section markers
            dom = _detect_domain_from_section_line(r[0])
            if dom:
                current_domain = dom
                round_cols = {1: None, 2: None, 3: None, 4: None}
                continue

            # Detect header row for a section
            if (r[0] or "").strip() == "ลำดับ" and len(r) >= 4:
                for rn in (1, 2, 3):
                    round_cols[rn] = _find_round_col(r, rn)
                # Add round 4 header if requested.
                if rounds >= 4:
                    round_cols[4] = _ensure_round_header(r, 4)
                if round_cols[1] is None:
                    round_cols[1] = 3 if len(r) > 3 else None
                if round_cols[2] is None:
                    round_cols[2] = 4 if len(r) > 4 else None
                if round_cols[3] is None:
                    round_cols[3] = 5 if len(r) > 5 else None
                if rounds >= 4 and round_cols[4] is None:
                    round_cols[4] = 6 if len(r) > 6 else _ensure_round_header(r, 4)
                continue

            # Fill for any known domain where a question is present.
            if current_domain not in ("announcements", "curriculum", "regulations"):
                continue

            if not _is_int(r[0] or ""):
                continue

            if round_cols[1] is None:
                round_cols[1] = 3
            if round_cols[2] is None:
                round_cols[2] = 4
            if round_cols[3] is None:
                round_cols[3] = 5
            if rounds >= 4 and round_cols[4] is None:
                round_cols[4] = 6

            question = (r[QUESTION_COL] if len(r) > QUESTION_COL else "").strip()
            if not question:
                skipped += 1
                continue

            questions_seen += 1
            payload = {"domain": current_domain, "question": question}

            for rn in range(1, rounds + 1):
                col = round_cols[rn]
                if col is None:
                    continue
                if len(r) <= col:
                    r.extend([""] * (col + 1 - len(r)))

                cell = (r[col] or "").strip()
                if cell and not args.overwrite:
                    if args.retry_exceptions and cell.startswith("(exception)"):
                        pass
                    else:
                        continue

                try:
                    data = _post_json(
                        answer_url,
                        payload,
                        connect_timeout_s=float(args.connect_timeout),
                        read_timeout_s=float(args.timeout),
                        retries=int(args.retries),
                        session=http_session,
                    )
                    ans = str(data.get("answer") or "").strip()
                    if not ans:
                        ans = json.dumps(data, ensure_ascii=False)
                    r[col] = ans
                    filled_cells += 1
                except Exception as e:
                    errors += 1
                    r[col] = f"(exception) {type(e).__name__}: {e}"

                if args.sleep and args.sleep > 0:
                    time.sleep(float(args.sleep))

            if args.flush_every and args.flush_every > 0 and questions_seen % int(args.flush_every) == 0:
                _write_now()
                print(f"progress: {questions_seen} questions (filled cells={filled_cells}, errors={errors})")

        _write_now()

        print(f"Questions: {questions_seen}, filled cells: {filled_cells}, skipped: {skipped}, errors: {errors}")
        print(f"Wrote: {in_path}")
        return 0
    except KeyboardInterrupt:
        # Ensure the latest progress is written.
        _write_now()
        print(
            f"Interrupted. Questions: {questions_seen}, filled cells: {filled_cells}, skipped: {skipped}, errors: {errors}"
        )
        print(f"Wrote partial results: {in_path}")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
