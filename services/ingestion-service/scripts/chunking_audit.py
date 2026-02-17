#!/usr/bin/env python3
"""Audit chunk token distributions + inspect frequently retrieved chunks.

Reads per-domain SQLite DBs under `indexes/<domain>/vector/sqlite/ingestion.db`
and (optionally) retrieval evaluation reports in `reports/retrieval_eval_*.json`.

Outputs a short markdown report with:
- tokens_est distribution stats per domain
- top retrieved doc_ids per domain + sample text snippets
- crude OCR noise indicators

This script is read-only (no DB writes).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


# This file lives at: services/ingestion-service/scripts/chunking_audit.py
# parents[0]=scripts, [1]=ingestion-service, [2]=services, [3]=<repo-root>
REPO_ROOT = Path(__file__).resolve().parents[3]
INDEXES_DIR = REPO_ROOT / "indexes"
REPORTS_DIR = REPO_ROOT / "reports"

KNOWN_DOMAINS = ("announcements", "regulations", "curriculum")


@dataclass(frozen=True)
class DistStats:
    n: int
    min_: int
    p5: int
    p10: int
    p25: int
    p50: int
    p75: int
    p90: int
    p95: int
    p99: int
    max_: int
    mean: float


def percentile(sorted_vals: list[int], p: float) -> int:
    if not sorted_vals:
        return 0
    if p <= 0:
        return sorted_vals[0]
    if p >= 100:
        return sorted_vals[-1]
    # Linear index, nearest-rank-ish.
    idx = int(round((p / 100.0) * (len(sorted_vals) - 1)))
    idx = max(0, min(idx, len(sorted_vals) - 1))
    return int(sorted_vals[idx])


def compute_dist_stats(vals: Iterable[int]) -> DistStats:
    arr = [int(v) for v in vals if v is not None]
    arr.sort()
    n = len(arr)
    if n == 0:
        return DistStats(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0)
    mean = float(sum(arr)) / float(n)
    return DistStats(
        n=n,
        min_=arr[0],
        p5=percentile(arr, 5),
        p10=percentile(arr, 10),
        p25=percentile(arr, 25),
        p50=percentile(arr, 50),
        p75=percentile(arr, 75),
        p90=percentile(arr, 90),
        p95=percentile(arr, 95),
        p99=percentile(arr, 99),
        max_=arr[-1],
        mean=mean,
    )


def open_db(domain: str) -> Path:
    # Prefer per-domain isolated indexes
    p = INDEXES_DIR / domain / "vector" / "sqlite" / "ingestion.db"
    if p.exists():
        return p
    # Fallback: service-local DB (rare)
    p2 = REPO_ROOT / "services" / "ingestion-service" / "data" / "db" / "ingestion.db"
    return p2


def fetch_tokens_est(db_path: Path) -> list[int]:
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT tokens_est FROM documents WHERE tokens_est IS NOT NULL")
    vals = [int(r[0]) for r in cur.fetchall() if r and r[0] is not None]
    conn.close()
    return vals


def fetch_docs_by_id(db_path: Path, doc_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not doc_ids:
        return {}
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in doc_ids)
    cur.execute(
        f"SELECT doc_id, source, path, page_start, page_end, tokens_est, text FROM documents WHERE doc_id IN ({placeholders})",
        doc_ids,
    )
    rows = cur.fetchall()
    conn.close()
    out: dict[str, dict[str, Any]] = {}
    for doc_id, source, path, page_start, page_end, tokens_est, text in rows:
        out[str(doc_id)] = {
            "doc_id": str(doc_id),
            "source": source,
            "path": path,
            "page_start": page_start,
            "page_end": page_end,
            "tokens_est": tokens_est,
            "text": text or "",
        }
    return out


def fetch_docs_fallback(
    db_path: Path,
    *,
    source: str | None,
    page_start: int | None,
    snippet: str | None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Best-effort mapping when doc_id changed (e.g., after re-ingest).

    Tries to find rows by source + page_start and optionally a snippet substring.
    """
    if not source and page_start is None:
        return []
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    clauses: list[str] = []
    params: list[Any] = []
    if source:
        clauses.append("source = ?")
        params.append(source)
    if page_start is not None:
        clauses.append("page_start = ?")
        params.append(int(page_start))

    like = ""
    like_params: list[Any] = []
    if snippet:
        frag = " ".join(str(snippet).split())
        frag = frag[:40]
        if len(frag) >= 8:
            like = " AND text LIKE ?"
            like_params.append(f"%{frag}%")

    where = " AND ".join(clauses) if clauses else "1=1"
    cur.execute(
        "SELECT doc_id, source, path, page_start, page_end, tokens_est, text "
        f"FROM documents WHERE {where}{like} LIMIT ?",
        params + like_params + [limit],
    )
    rows = cur.fetchall()
    conn.close()
    out: list[dict[str, Any]] = []
    for doc_id, src, path, ps, pe, te, text in rows:
        out.append(
            {
                "doc_id": str(doc_id),
                "source": src,
                "path": path,
                "page_start": ps,
                "page_end": pe,
                "tokens_est": te,
                "text": text or "",
            }
        )
    return out


_NOISE_GIBBERISH_RE = re.compile(r"[«»◊�]|\b[0-9A-Za-z]{1}[ก-๙]{1}\b")


def noise_score(text: str) -> float:
    """Crude OCR noise indicator: higher = noisier."""
    if not text:
        return 0.0
    t = text.strip()
    if not t:
        return 0.0
    # Non-printables / replacement chars
    bad = len(re.findall(r"[\uFFFD\x00-\x08\x0B\x0C\x0E-\x1F]", t))
    # Weird symbols often from OCR
    bad += len(_NOISE_GIBBERISH_RE.findall(t))
    # Overly high punctuation density
    punct = len(re.findall(r"[^\w\sก-๙]", t))
    denom = max(1, len(t))
    return (bad / denom) * 10.0 + (punct / denom)


def safe_snippet(text: str, max_chars: int = 260) -> str:
    s = " ".join((text or "").split())
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1] + "…"


def to_int_or_none(val: Any) -> int | None:
    try:
        if val is None:
            return None
        return int(val)
    except Exception:
        return None


def load_retrieval_eval_reports(report_glob: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for p in sorted(REPORTS_DIR.glob(report_glob)):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, list):
            items.extend([x for x in data if isinstance(x, dict)])
    return items


def count_retrieved_doc_ids(eval_items: list[dict[str, Any]], top_field: str = "top") -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = {d: Counter() for d in KNOWN_DOMAINS}
    for it in eval_items:
        dom = str(it.get("domain") or "").strip().lower()
        if dom not in counts:
            continue
        top = it.get(top_field)
        if not isinstance(top, list):
            continue
        for row in top:
            if isinstance(row, dict) and row.get("doc_id"):
                counts[dom][str(row["doc_id"])] += 1
    return counts


def build_retrieval_lookup(eval_items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map doc_id -> retrieval row fields (domain/source/page_start/page_end/snippet)."""
    out: dict[str, dict[str, Any]] = {}
    for it in eval_items:
        dom = str(it.get("domain") or "").strip().lower()
        top = it.get("top")
        if not isinstance(top, list):
            continue
        for row in top:
            if not isinstance(row, dict) or not row.get("doc_id"):
                continue
            doc_id = str(row.get("doc_id"))
            if doc_id in out:
                continue
            out[doc_id] = {
                "domain": dom,
                "source": row.get("source"),
                "page_start": row.get("page_start"),
                "page_end": row.get("page_end"),
                "snippet": row.get("snippet"),
            }
    return out


def recommend_settings(dist: DistStats, domain: str) -> dict[str, Any]:
    """Heuristic recommendations based on observed distribution.

    Goal: make heading-boundary flush realistic for sentence/structure strategies,
    while keeping max near where most chunks already sit.
    """

    if dist.n == 0:
        return {"min": None, "max": None, "overlap": None}

    # Choose max to cover most chunks, but cap to keep retrieval focused.
    # (Curriculum chunks often need to be larger.)
    if domain == "curriculum":
        target_max = int(max(650, min(dist.p95, 950)))
        target_min = int(max(250, min(dist.p25, int(target_max * 0.6))))
        overlap = 0.10
    elif domain == "regulations":
        target_max = int(max(320, min(dist.p95, 520)))
        target_min = int(max(120, min(dist.p25, int(target_max * 0.6))))
        overlap = 0.08
    else:  # announcements
        target_max = int(max(320, min(dist.p95, 520)))
        target_min = int(max(140, min(dist.p25, int(target_max * 0.6))))
        overlap = 0.12

    # Ensure min < max
    if target_min >= target_max:
        target_min = max(80, target_max - 80)

    return {"min": target_min, "max": target_max, "overlap": overlap}


def write_report(
    *,
    out_path: Path,
    dist_by_domain: dict[str, DistStats],
    rec_by_domain: dict[str, dict[str, Any]],
    top_docs_by_domain: dict[str, list[dict[str, Any]]],
) -> None:
    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"# Chunking audit\n\nGenerated: {now}\n")

    lines.append("## Token distribution (tokens_est)\n")
    for dom in KNOWN_DOMAINS:
        st = dist_by_domain.get(dom) or DistStats(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0)
        rec = rec_by_domain.get(dom, {})
        lines.append(f"### {dom}\n")
        if st.n == 0:
            lines.append("No chunks found.\n")
            continue
        lines.append(
            "- "
            + f"n={st.n}, min={st.min_}, p25={st.p25}, p50={st.p50}, p75={st.p75}, p90={st.p90}, p95={st.p95}, max={st.max_}, mean={st.mean:.1f}\n"
        )
        lines.append(
            "- "
            + f"recommended defaults: CHUNK_MIN_TOKENS={rec.get('min')}, CHUNK_MAX_TOKENS={rec.get('max')}, CHUNK_OVERLAP_RATIO={rec.get('overlap')}\n"
        )

    lines.append("\n## Frequently retrieved chunks (from retrieval_eval reports)\n")
    for dom in KNOWN_DOMAINS:
        rows = top_docs_by_domain.get(dom, [])
        lines.append(f"### {dom}\n")
        if not rows:
            lines.append("No retrieval samples found.\n")
            continue
        for r in rows:
            lines.append(
                "- "
                + f"doc_id={r.get('doc_id')} source={r.get('source')} pages={r.get('page_start')}-{r.get('page_end')} tokens_est={r.get('tokens_est')} noise={r.get('noise'):.3f}\n"
                + f"  - snippet: {r.get('snippet')}\n"
            )

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--domains",
        default=",".join(KNOWN_DOMAINS),
        help="Comma-separated domains to audit (announcements,regulations,curriculum)",
    )
    ap.add_argument(
        "--retrieval-reports",
        default="retrieval_eval_*.json",
        help="Glob under reports/ to parse retrieved doc_ids",
    )
    ap.add_argument("--topk", type=int, default=12, help="How many doc_ids per domain to inspect")
    ap.add_argument(
        "--out",
        default="",
        help="Output markdown path (default: reports/chunking_audit_<timestamp>.md)",
    )
    args = ap.parse_args()

    domains = [d.strip().lower() for d in str(args.domains).split(",") if d.strip()]
    domains = [d for d in domains if d in KNOWN_DOMAINS]
    if not domains:
        domains = list(KNOWN_DOMAINS)

    # Distributions
    dist_by_domain: dict[str, DistStats] = {}
    rec_by_domain: dict[str, dict[str, Any]] = {}
    for dom in domains:
        db = open_db(dom)
        toks = fetch_tokens_est(db)
        dist = compute_dist_stats(toks)
        dist_by_domain[dom] = dist
        rec_by_domain[dom] = recommend_settings(dist, dom)

    # Retrieval-based inspection
    eval_items = load_retrieval_eval_reports(args.retrieval_reports)
    retrieved_counts = count_retrieved_doc_ids(eval_items)
    retrieval_lookup = build_retrieval_lookup(eval_items)

    top_docs_by_domain: dict[str, list[dict[str, Any]]] = {}
    for dom in domains:
        db = open_db(dom)
        top_ids = [doc_id for doc_id, _ in retrieved_counts.get(dom, Counter()).most_common(args.topk)]
        docs = fetch_docs_by_id(db, top_ids)
        rows: list[dict[str, Any]] = []
        for doc_id in top_ids:
            d = docs.get(doc_id)
            if d:
                txt = d.get("text", "")
                rows.append(
                    {
                        "doc_id": doc_id,
                        "source": d.get("source"),
                        "page_start": d.get("page_start"),
                        "page_end": d.get("page_end"),
                        "tokens_est": d.get("tokens_est"),
                        "noise": float(noise_score(txt)),
                        "snippet": safe_snippet(txt),
                    }
                )
                continue

            # Fallback mapping using retrieval report metadata.
            lk = retrieval_lookup.get(doc_id, {})
            fb = fetch_docs_fallback(
                db,
                source=str(lk.get("source") or "") or None,
                page_start=to_int_or_none(lk.get("page_start")),
                snippet=str(lk.get("snippet") or "") or None,
                limit=1,
            )
            if fb:
                txt = fb[0].get("text", "")
                rows.append(
                    {
                        "doc_id": fb[0].get("doc_id") or doc_id,
                        "source": fb[0].get("source") or lk.get("source"),
                        "page_start": fb[0].get("page_start") or lk.get("page_start"),
                        "page_end": fb[0].get("page_end") or lk.get("page_end"),
                        "tokens_est": fb[0].get("tokens_est"),
                        "noise": float(noise_score(txt)),
                        "snippet": safe_snippet(txt),
                    }
                )
            elif lk:
                # Still include retrieval snippet for manual inspection.
                sn = str(lk.get("snippet") or "")
                rows.append(
                    {
                        "doc_id": doc_id,
                        "source": lk.get("source"),
                        "page_start": lk.get("page_start"),
                        "page_end": lk.get("page_end"),
                        "tokens_est": None,
                        "noise": float(noise_score(sn)),
                        "snippet": safe_snippet(sn),
                    }
                )
        top_docs_by_domain[dom] = rows

    out = str(args.out).strip()
    if out:
        out_path = (REPO_ROOT / out).resolve() if not out.startswith("/") else Path(out)
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = REPORTS_DIR / f"chunking_audit_{ts}.md"

    write_report(
        out_path=out_path,
        dist_by_domain=dist_by_domain,
        rec_by_domain=rec_by_domain,
        top_docs_by_domain=top_docs_by_domain,
    )

    print(f"Wrote report: {out_path}")
    for dom in domains:
        rec = rec_by_domain.get(dom, {})
        print(f"{dom}: recommend CHUNK_MIN_TOKENS={rec.get('min')} CHUNK_MAX_TOKENS={rec.get('max')} CHUNK_OVERLAP_RATIO={rec.get('overlap')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
