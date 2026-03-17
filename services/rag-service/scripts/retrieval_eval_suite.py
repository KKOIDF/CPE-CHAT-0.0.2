import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import sys

# Allow running from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.rag_logic import retrieve_by_domain

try:
    import mlflow_utils as mlf
except Exception:  # pragma: no cover
    mlf = None  # type: ignore


if mlf and getattr(mlf, "enabled", lambda: False)():
    os.environ.setdefault("MLFLOW_EXPERIMENT", os.getenv("MLFLOW_RETRIEVAL_EXPERIMENT", "cpe-chat-retrieval-regression"))


@dataclass
class EvalQuery:
    domain: str
    question: str
    expected_keywords: List[str]


DEFAULT_QUERIES: List[EvalQuery] = [
    # announcements
    EvalQuery("announcements", "ประกาศสอบซ้อนทำอย่างไร", ["สอบซ้อน", "คำร้อง", "อนุมัติ"]),
    EvalQuery("announcements", "ขั้นตอนการขอสอบซ้อนต้องใช้เอกสารอะไร", ["สอบซ้อน", "คำร้อง", "แบบฟอร์ม"]),
    EvalQuery("announcements", "ประกาศเกี่ยวกับการสอบซ้อนใช้ตั้งแต่เมื่อไร", ["ประกาศ", "ภาคการศึกษา", "ปีการศึกษา"]),
    EvalQuery("announcements", "นักศึกษาขอจัดสอบซ้อนในรายวิชาเลือกได้ไหม", ["รายวิชา", "บังคับ", "สำเร็จการศึกษา"]),
    # regulations
    EvalQuery("regulations", "ได้คะแนน 0 ในการสอบเกิดจากกรณีใดบ้าง", ["คะแนน", "0", "สอบ"]),
    EvalQuery("regulations", "ได้คะแนน 0 ในการทดสอบย่อยหมายถึงอะไร", ["คะแนน", "0", "ทดสอบ"]),
    EvalQuery("regulations", "ระเบียบเกี่ยวกับอาจารย์ที่ปรึกษาวิทยานิพนธ์ร่วม (ถ้ามี)", ["อาจารย์", "ที่ปรึกษ", "วิทยานิพนธ์"]),
    EvalQuery("regulations", "ถ้ามีปัญหาในการปฏิบัติตามระเบียบต้องทำอย่างไร", ["ปัญหา", "พิจารณา", "อนุมัติ"]),
    # curriculum
    EvalQuery("curriculum", "เกณฑ์การสำเร็จการศึกษา หลักสูตรวิศวกรรมคอมพิวเตอร์", ["สำเร็จ", "การศึกษา", "หลักสูตร"]),
    EvalQuery("curriculum", "ผลลัพธ์การเรียนรู้ของหลักสูตร (PLO/LO) คืออะไร", ["ผลลัพธ์", "การเรียนรู้", "PLO"]),
    EvalQuery("curriculum", "โครงสร้างหมวดวิชาและหน่วยกิตของหลักสูตร", ["หน่วยกิต", "หมวด", "วิชา"]),
    EvalQuery("curriculum", "คุณสมบัติผู้เข้าศึกษา/การรับเข้าศึกษา", ["คุณสมบัติ", "รับเข้าศึกษา", "สายวิทยาศาสตร์"]),
]


def _snip(text: str, n: int = 240) -> str:
    s = (text or "").strip().replace("\n", " ")
    s = " ".join(s.split())
    return s[:n] + ("…" if len(s) > n else "")


def _count_hits(text: str, keywords: List[str]) -> int:
    if not text:
        return 0
    t = text
    hits = 0
    for kw in keywords:
        if not kw:
            continue
        if kw in t:
            hits += 1
    return hits


def run_query(dom: str, question: str, top_k: int) -> List[Dict[str, Any]]:
    # retrieve_by_domain returns at most MAX_CONTEXTS; we want more for inspection
    # so call with larger k_vec/k_kw but still capped by MAX_CONTEXTS inside.
    # For suite purposes, we keep default MAX_CONTEXTS; report top_k <= that.
    return retrieve_by_domain(question, dom)[:top_k]


def write_markdown(
    out_path: Path,
    results: List[Dict[str, Any]],
    started_at: float,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dur_ms = int((time.time() - started_at) * 1000)
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    lines: List[str] = []
    lines.append(f"# Retrieval-only Evaluation Report")
    lines.append("")
    lines.append(f"Generated: {ts}")
    lines.append(f"Duration: {dur_ms} ms")
    lines.append("")

    by_domain: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        by_domain.setdefault(r["domain"], []).append(r)

    for dom in ("announcements", "regulations", "curriculum"):
        rows = by_domain.get(dom, [])
        if not rows:
            continue
        lines.append(f"## Domain: {dom}")
        lines.append("")
        for r in rows:
            lines.append(f"### Q: {r['question']}")
            lines.append("")
            lines.append(f"contexts: {r['contexts']} | keyword_hits_in_top1: {r['top1_keyword_hits']}/{r['expected_keywords_count']}")
            if r.get("notes"):
                lines.append(f"notes: {r['notes']}")
            lines.append("")
            for i, c in enumerate(r.get("top") or [], 1):
                lines.append(f"- [{i}] src={c.get('source')} page={c.get('page_start')} score_rrf={c.get('score_rrf')}")
                lines.append(f"  - snippet: {c.get('snippet')}")
            lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="Run retrieval-only evaluation suite (no LLM)")
    p.add_argument("--top", type=int, default=5, help="contexts to print per query")
    p.add_argument("--out", type=str, default="", help="markdown report path (default: reports/retrieval_eval_<ts>.md)")
    p.add_argument("--json", type=str, default="", help="optional JSON output path")
    args = p.parse_args()

    top_k = max(1, int(args.top))
    started = time.time()

    suite: List[EvalQuery] = DEFAULT_QUERIES

    results: List[Dict[str, Any]] = []

    for q in suite:
        top = run_query(q.domain, q.question, top_k=top_k)
        ctx_count = len(top)

        top_items: List[Dict[str, Any]] = []
        for c in top:
            top_items.append(
                {
                    "doc_id": c.get("doc_id"),
                    "source": c.get("source") or c.get("path"),
                    "page_start": c.get("page_start"),
                    "page_end": c.get("page_end"),
                    "score_rrf": c.get("score_rrf"),
                    "snippet": _snip(c.get("text") or ""),
                }
            )

        top1_text = (top[0].get("text") if top else "") or ""
        hits = _count_hits(top1_text, q.expected_keywords)

        notes: Optional[str] = None
        if ctx_count == 0:
            notes = "NO_CONTEXTS"
        elif hits == 0 and q.expected_keywords:
            notes = "TOP1_HAS_NO_EXPECTED_KEYWORDS"

        results.append(
            {
                "domain": q.domain,
                "question": q.question,
                "expected_keywords": q.expected_keywords,
                "expected_keywords_count": len(q.expected_keywords),
                "contexts": ctx_count,
                "top1_keyword_hits": hits,
                "notes": notes,
                "top": top_items,
            }
        )

    # Default outputs at repo root
    repo_root = Path(__file__).resolve().parents[3]
    ts_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_md = Path(args.out) if args.out else (repo_root / "reports" / f"retrieval_eval_{ts_slug}.md")
    out_json = Path(args.json) if args.json else (repo_root / "reports" / f"retrieval_eval_{ts_slug}.json")

    write_markdown(out_md, results, started)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Wrote report: {out_md}")
    print(f"✅ Wrote data:   {out_json}")

    if mlf and getattr(mlf, "enabled", lambda: False)():
        total = len(results)
        no_contexts = sum(1 for r in results if int(r.get("contexts") or 0) == 0)
        flagged = sum(1 for r in results if r.get("notes"))
        avg_contexts = (sum(int(r.get("contexts") or 0) for r in results) / total) if total else 0.0

        with mlf.start_run(
            run_name=f"retrieval_eval_{ts_slug}",
            tags={"script": "services/rag-service/scripts/retrieval_eval_suite.py"},
        ):
            mlf.log_params({"top": int(args.top)})
            mlf.log_metrics(
                {
                    "total": total,
                    "no_contexts": no_contexts,
                    "flagged": flagged,
                    "avg_contexts": avg_contexts,
                }
            )
            mlf.log_artifacts([str(out_md), str(out_json)])

            try:
                from app import config as cfg  # type: ignore

                ctx = {
                    "generated": ts_slug,
                    "env": mlf.env_snapshot(),
                    "resolved": {
                        "ROOT_DIR": str(getattr(cfg, "ROOT_DIR", "")),
                        "DATA_DIR": str(getattr(cfg, "DATA_DIR", "")),
                        "CHROMA_DIR": str(getattr(cfg, "CHROMA_DIR", "")),
                        "SQLITE_PATH": str(getattr(cfg, "SQLITE_PATH", "")),
                        "EMBEDDING_MODEL": getattr(cfg, "EMBEDDING_MODEL", ""),
                        "EMBED_BATCH": getattr(cfg, "EMBED_BATCH", None),
                        "EMBEDDING_DIM": getattr(cfg, "EMBEDDING_DIM", None),
                        "TOKEN_BUDGET": getattr(cfg, "TOKEN_BUDGET", None),
                        "RRF_K": getattr(cfg, "RRF_K", None),
                        "MAX_CONTEXTS": getattr(cfg, "MAX_CONTEXTS", None),
                        "LLM_ENABLE": getattr(cfg, "LLM_ENABLE", None),
                        "LLM_PROVIDER": getattr(cfg, "LLM_PROVIDER", ""),
                        "LLM_MODEL": getattr(cfg, "LLM_MODEL", ""),
                        "LLM_MAX_TOKENS": getattr(cfg, "LLM_MAX_TOKENS", None),
                        "LLM_TEMPERATURE": getattr(cfg, "LLM_TEMPERATURE", None),
                    },
                }
                mlf.log_dict_artifact(ctx, artifact_file=f"run_context_{ts_slug}.json")
            except Exception:
                pass


if __name__ == "__main__":
    main()
