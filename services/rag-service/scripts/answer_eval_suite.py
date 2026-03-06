import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import sys

# Allow running from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from fastapi.testclient import TestClient
from app.main import app

try:
    import mlflow_utils as mlf
except Exception:  # pragma: no cover
    mlf = None  # type: ignore


FALLBACK = "ไม่พบข้อมูลในเอกสาร"
CITE_RE = re.compile(r"\[([^\]]+?/\d+)\]")
BRACKET_RE = re.compile(r"\[[^\]]*\]")


def _truthy_env(v: str) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y"}


@dataclass
class AnswerEvalQuery:
    domain: str
    question: str
    expect_answerable: bool = True


DEFAULT_QUERIES: List[AnswerEvalQuery] = [
    # announcements (30)
    AnswerEvalQuery("announcements", "ประกาศสอบซ้อนทำอย่างไร"),
    AnswerEvalQuery("announcements", "ขั้นตอนการขอสอบซ้อนต้องใช้เอกสารอะไร"),
    AnswerEvalQuery("announcements", "นักศึกษาขอจัดสอบซ้อนในรายวิชาเลือกได้ไหม"),
    AnswerEvalQuery("announcements", "ขอสอบซ้อนได้ไม่เกินกี่วิชาต่อวัน"),
    AnswerEvalQuery("announcements", "ประกาศผลการพิจารณาการสอบซ้อนแจ้งนักศึกษาล่วงหน้ากี่วัน"),
    AnswerEvalQuery("announcements", "รายวิชาเลือกเสรีสามารถขอจัดสอบซ้อนได้หรือไม่"),
    AnswerEvalQuery("announcements", "ใครเป็นผู้อนุมัติการจัดสอบซ้อน"),
    AnswerEvalQuery("announcements", "คำร้องสอบซ้อนชื่อแบบฟอร์มอะไร"),
    AnswerEvalQuery("announcements", "ต้องมีเหตุผลแบบใดถึงจะขอสอบซ้อนได้"),
    AnswerEvalQuery("announcements", "ถ้ามีชั่วโมงสอบซ้อน มหาวิทยาลัยจะประกาศรายชื่ออย่างไร"),
    AnswerEvalQuery("announcements", "การสอบซ้อนเกี่ยวข้องกับสอบกลางภาคและปลายภาคหรือไม่"),
    AnswerEvalQuery("announcements", "การยกเลิกการอนุมัติสอบซ้อนเกิดได้ในกรณีใด"),
    AnswerEvalQuery("announcements", "เงื่อนไขรายวิชาที่อนุมัติให้สอบซ้อนได้ต้องเป็นรายวิชาแบบไหน"),
    AnswerEvalQuery("announcements", "หากนักศึกษามีสอบซ้อนมากกว่า 2 วิชาในวันเดียวทำอย่างไร", expect_answerable=False),
    AnswerEvalQuery("announcements", "การขอสอบซ้อนต้องทำก่อนวันสอบหรือหลังวันสอบ", expect_answerable=False),
    AnswerEvalQuery("announcements", "ขอสอบซ้อนได้สำหรับวิชาที่ไม่จำเป็นต่อการสำเร็จการศึกษาหรือไม่"),
    AnswerEvalQuery("announcements", "ประกาศสอบซ้อนเป็นของหน่วยงาน/ภาควิชาใด", expect_answerable=False),
    AnswerEvalQuery("announcements", "มีข้อกำหนดเกี่ยวกับสถานที่หรือรูปแบบการสอบซ้อนหรือไม่", expect_answerable=False),
    AnswerEvalQuery("announcements", "สอบซ้อนหมายถึงอะไรตามประกาศ", expect_answerable=False),
    AnswerEvalQuery("announcements", "ถ้านักศึกษายื่นคำร้องแล้วจะรู้ผลจากช่องทางใด"),
    AnswerEvalQuery("announcements", "มีช่วงเวลาโดยประมาณที่ประกาศผลก่อนสอบเท่าไร"),
    AnswerEvalQuery("announcements", "การสอบซ้อนจัดเพื่อแก้ปัญหาอะไร"),
    AnswerEvalQuery("announcements", "ถ้าไม่ได้รับอนุมัติสอบซ้อนต้องทำอย่างไร", expect_answerable=False),
    AnswerEvalQuery("announcements", "ข้อกำหนดเรื่องรายวิชาบังคับเลือกเกี่ยวข้องกับสอบซ้อนอย่างไร"),
    AnswerEvalQuery("announcements", "การสอบซ้อนอนุมัติเป็นรายกรณีโดยใครร่วมกับใคร"),
    AnswerEvalQuery("announcements", "การสอบซ้อนมีหลักเกณฑ์ต่างจากการเลื่อนสอบหรือไม่", expect_answerable=False),
    AnswerEvalQuery("announcements", "ถ้าเป็นรายวิชาบังคับในหลักสูตรแต่ไม่จำเป็นต่อสำเร็จการศึกษาจะขอได้ไหม", expect_answerable=False),
    AnswerEvalQuery("announcements", "เอกสารประกาศสอบซ้อนมีเลขที่/ปีใด", expect_answerable=False),
    AnswerEvalQuery("announcements", "ผู้ที่เกี่ยวข้องกับการจัดตารางสอบซ้อนมีตำแหน่งอะไรบ้าง"),

    # regulations (30)
    AnswerEvalQuery("regulations", "ได้คะแนน 0 ในการสอบเกิดจากกรณีใดบ้าง"),
    AnswerEvalQuery("regulations", "ได้คะแนน 0 ในการทดสอบย่อยหมายถึงอะไร"),
    AnswerEvalQuery("regulations", "ถ้ามีปัญหาในการปฏิบัติตามระเบียบต้องทำอย่างไร"),
    AnswerEvalQuery("regulations", "ระเบียบการคุ้มครองข้อมูลส่วนบุคคลเกี่ยวข้องกับบทบาท DPO อย่างไร"),
    AnswerEvalQuery("regulations", "ต้องแจ้งเหตุการณ์ละเมิดข้อมูลส่วนบุคคลเมื่อใด"),
    AnswerEvalQuery("regulations", "ข้อกำหนดเรื่องการเก็บรวบรวม ใช้ หรือเปิดเผยข้อมูลส่วนบุคคลมีอะไรบ้าง", expect_answerable=False),
    AnswerEvalQuery("regulations", "ถ้าผู้ปฏิบัติงานมีข้อสงสัยต้องปรึกษาใคร"),
    AnswerEvalQuery("regulations", "เอกสารระเบียบ/ข้อบังคับฉบับปี 2563 กล่าวถึงอะไรโดยสรุป", expect_answerable=False),
    AnswerEvalQuery("regulations", "ในระเบียบมีการระบุขั้นตอนการรายงานเหตุข้อมูลรั่วไหลหรือไม่"),
    AnswerEvalQuery("regulations", "การได้คะแนน 0 ในการสอบเกี่ยวข้องกับการทุจริตหรือไม่", expect_answerable=False),
    AnswerEvalQuery("regulations", "การได้คะแนน 0 ในการทดสอบย่อยเกิดจากอะไรบ้าง (ตามเอกสาร)"),
    AnswerEvalQuery("regulations", "ระเบียบเกี่ยวกับการสอบมีเอกสารชื่ออะไร"),
    AnswerEvalQuery("regulations", "มีข้อกำหนดเกี่ยวกับการประเมินผลหรือคะแนนขั้นต่ำหรือไม่", expect_answerable=False),
    AnswerEvalQuery("regulations", "ถ้าผลสอบเป็น 0 จะมีผลต่อเกรดอย่างไร", expect_answerable=False),
    AnswerEvalQuery("regulations", "ระเบียบ/ข้อบังคับมีการกำหนดผู้รับผิดชอบข้อมูลส่วนบุคคลหรือไม่"),
    AnswerEvalQuery("regulations", "ข้อ 13.7 และ 13.8 กล่าวถึงอะไร"),
    AnswerEvalQuery("regulations", "คำว่า DPO ย่อมาจากอะไร (ตามเอกสาร)", expect_answerable=False),
    AnswerEvalQuery("regulations", "มีแนวทางปฏิบัติเมื่อเกิดเหตุละเมิดข้อมูลส่วนบุคคลอย่างไร"),
    AnswerEvalQuery("regulations", "ระเบียบเกี่ยวกับการเป็นอาจารย์ที่ปรึกษาวิทยานิพนธ์ร่วมมีไหม", expect_answerable=False),
    AnswerEvalQuery("regulations", "เอกสารระเบียบปี 2560 ระบุเรื่องคะแนน 0 อย่างไร"),
    AnswerEvalQuery("regulations", "เอกสารระเบียบปี 2568 ระบุเรื่องคะแนน 0 อย่างไร", expect_answerable=False),
    AnswerEvalQuery("regulations", "ถ้าต้องการยกเว้นตามระเบียบ ต้องยื่นคำร้องหรือไม่", expect_answerable=False),
    AnswerEvalQuery("regulations", "มีข้อกำหนดเรื่องการเก็บรักษาข้อมูลและการเข้าถึงหรือไม่", expect_answerable=False),
    AnswerEvalQuery("regulations", "กรณีเกิดเหตุข้อมูลรั่วไหลต้องทำโดยไม่ชักช้าใช่ไหม"),
    AnswerEvalQuery("regulations", "ระเบียบกำหนดให้ต้องปฏิบัติตามขั้นตอนที่มหาวิทยาลัยกำหนดหรือไม่"),
    AnswerEvalQuery("regulations", "ข้อบังคับเกี่ยวกับข้อมูลส่วนบุคคลฉบับนี้บังคับใช้กับใคร", expect_answerable=False),
    AnswerEvalQuery("regulations", "มีข้อกำหนดเกี่ยวกับการถ่ายโอนข้อมูลไปต่างประเทศหรือไม่", expect_answerable=False),
    AnswerEvalQuery("regulations", "หากไม่ปฏิบัติตามระเบียบจะมีบทลงโทษหรือไม่", expect_answerable=False),
    AnswerEvalQuery("regulations", "ในเอกสารมีคำแนะนำให้ปรึกษา DPO เมื่อมีข้อสงสัยหรือไม่"),

    # curriculum (30)
    AnswerEvalQuery("curriculum", "เกณฑ์การสำเร็จการศึกษา หลักสูตรวิศวกรรมคอมพิวเตอร์"),
    AnswerEvalQuery("curriculum", "โครงสร้างหมวดวิชาและหน่วยกิตของหลักสูตร"),
    AnswerEvalQuery("curriculum", "ผลลัพธ์การเรียนรู้ของหลักสูตร (PLO/LO) คืออะไร", expect_answerable=False),
    AnswerEvalQuery("curriculum", "คุณสมบัติผู้เข้าศึกษา/การรับเข้าศึกษา"),
    AnswerEvalQuery("curriculum", "หมวดวิชาแกนทางวิศวกรรมมีอะไรบ้าง"),
    AnswerEvalQuery("curriculum", "กลุ่มวิชาโครงสร้างพื้นฐานของระบบหมายถึงอะไร", expect_answerable=False),
    AnswerEvalQuery("curriculum", "กลุ่มวิชาฮาร์ดแวร์และสถาปัตยกรรมคอมพิวเตอร์มีอะไรบ้าง", expect_answerable=False),
    AnswerEvalQuery("curriculum", "หลักสูตรปรับปรุง 64 ระบุโครงสร้างหลักสูตรอย่างไร"),
    AnswerEvalQuery("curriculum", "Year-LO 645 เกี่ยวกับอะไร"),
    AnswerEvalQuery("curriculum", "หลักสูตรระบุทักษะการออกแบบและพัฒนาซอฟต์แวร์/ฮาร์ดแวร์อย่างไร"),
    AnswerEvalQuery("curriculum", "หลักสูตรกล่าวถึงการแก้ปัญหาปลายเปิดอย่างไร"),
    AnswerEvalQuery("curriculum", "หลักสูตรกล่าวถึงการสร้างนวัตกรรมอย่างไร"),
    AnswerEvalQuery("curriculum", "มีการแบ่งหมวดวิชาเป็นกลุ่มอะไรบ้าง"),
    AnswerEvalQuery("curriculum", "หน่วยกิตรวมของหลักสูตรคือเท่าไร", expect_answerable=False),
    AnswerEvalQuery("curriculum", "รายวิชาบังคับเลือกเกี่ยวข้องกับหมวดใด", expect_answerable=False),
    AnswerEvalQuery("curriculum", "หลักสูตรกำหนดคุณสมบัติผู้เข้าศึกษาเป็นสายใดบ้าง"),
    AnswerEvalQuery("curriculum", "หลักสูตรกล่าวถึงการประเมินประสิทธิภาพของวิธีการและเครื่องมืออย่างไร"),
    AnswerEvalQuery("curriculum", "เอกสารหลักสูตรกล่าวถึงกลุ่มวิชาแกนทางวิศวกรรมในหน้าใด", expect_answerable=False),
    AnswerEvalQuery("curriculum", "หลักสูตรกล่าวถึงกลุ่มวิชาโครงสร้างพื้นฐานของระบบในหน้าใด", expect_answerable=False),
    AnswerEvalQuery("curriculum", "หลักสูตรกล่าวถึงกลุ่มวิชาฮาร์ดแวร์และสถาปัตยกรรมคอมพิวเตอร์ในหน้าใด", expect_answerable=False),
    AnswerEvalQuery("curriculum", "มีการพูดถึงวิชาศึกษาทั่วไปหรือไม่", expect_answerable=False),
    AnswerEvalQuery("curriculum", "โครงสร้างหลักสูตรแบ่งเป็นหมวด/กลุ่มวิชาอะไรบ้าง"),
    AnswerEvalQuery("curriculum", "หลักสูตรกล่าวถึงการสื่อสาร (communication) อย่างไร"),
    AnswerEvalQuery("curriculum", "หลักสูตรกล่าวถึงการทำงานเป็นทีมอย่างไร", expect_answerable=False),
    AnswerEvalQuery("curriculum", "หลักสูตรกล่าวถึงจริยธรรม/ความรับผิดชอบทางวิชาชีพอย่างไร", expect_answerable=False),
    AnswerEvalQuery("curriculum", "มีการกำหนดเงื่อนไขการสำเร็จการศึกษานอกเหนือจากหน่วยกิตหรือไม่", expect_answerable=False),
    AnswerEvalQuery("curriculum", "รายละเอียดเกณฑ์สำเร็จการศึกษามีหัวข้ออะไรบ้าง"),
    AnswerEvalQuery("curriculum", "คุณสมบัติการรับเข้าศึกษามีเงื่อนไขอย่างไร"),
    AnswerEvalQuery("curriculum", "สรุปภาพรวมหลักสูตรวิศวกรรมคอมพิวเตอร์ใน 3-5 bullet"),
]


def _snip(text: str, n: int = 260) -> str:
    s = (text or "").strip().replace("\n", " ")
    s = " ".join(s.split())
    return s[:n] + ("…" if len(s) > n else "")


def _extract_allowed_cites(prompt: str) -> List[str]:
    # Prefer a dedicated allowed list section if present.
    # Otherwise, fall back to citations embedded in the context blocks.
    p = prompt or ""
    marker = "รายชื่ออ้างอิงที่อนุญาต"
    after = ""
    if marker in p:
        after = p.split(marker, 1)[1]
        if "\n\nคำตอบ:" in after:
            after = after.split("\n\nคำตอบ:", 1)[0]
    else:
        # Typical prompt format: ... "บริบท:\n{ctx}\n\nคำตอบ:".
        if "\n\nบริบท:\n" in p and "\n\nคำตอบ:" in p:
            after = p.split("\n\nบริบท:\n", 1)[1].split("\n\nคำตอบ:", 1)[0]
        else:
            after = p

    found = CITE_RE.findall(after)
    # De-dup preserve order
    seen = set()
    ordered: List[str] = []
    for c in found:
        if c and c not in seen:
            ordered.append(c)
            seen.add(c)
    return ordered


def _split_bullets(answer: str) -> List[str]:
    # Handle wrapped lines: treat a bullet as starting at a line whose trimmed form starts with "- ".
    lines = (answer or "").splitlines()
    bullets: List[str] = []
    current: List[str] = []
    for ln in lines:
        if ln.lstrip().startswith("- "):
            if current:
                bullets.append("\n".join(current).strip())
                current = []
            current.append(ln.strip())
        else:
            if current:
                current.append(ln.rstrip())
    if current:
        bullets.append("\n".join(current).strip())
    # If model returned a single paragraph without '-' bullets, treat as one block.
    if not bullets and (answer or "").strip():
        bullets = [(answer or "").strip()]
    return bullets


def evaluate_one(client: TestClient, domain: str, question: str, citations_mode: str) -> Dict[str, Any]:
    q_payload = {"domain": domain, "question": question}

    q = client.post("/rag/query", json=q_payload)
    q.raise_for_status()
    qdata = q.json()

    contexts = qdata.get("contexts") or []
    ctx_n = len(contexts)
    prompt = qdata.get("prompt") or ""
    allowed = _extract_allowed_cites(prompt)
    allowed_set = set(allowed)

    a = client.post("/rag/answer", json=q_payload)
    a.raise_for_status()
    adata = a.json()

    answer = (adata.get("answer") or "").strip()
    answer_cites = CITE_RE.findall(answer)
    answer_cite_set = set(answer_cites)

    non_cite_brackets = [b for b in BRACKET_RE.findall(answer or "") if not re.fullmatch(r"\[[^\]]+?/\d+\]", b)]

    bullets = _split_bullets(answer)
    bullet_cite_ok = True
    for b in bullets:
        if not CITE_RE.search(b or ""):
            bullet_cite_ok = False
            break

    violations: List[str] = []

    # When LLM is disabled/unavailable, main.py returns diagnostic strings starting with '('.
    if answer.startswith("("):
        violations.append("LLM_DIAGNOSTIC")
        passed = False
    elif citations_mode == "off":
        # Lightweight health-check mode for systems that do not emit citations.
        if ctx_n == 0:
            # Accept either strict fallback token or a clear "not found" statement.
            if answer == FALLBACK or "ไม่พบข้อมูล" in answer:
                passed = True
            else:
                violations.append("NO_CONTEXTS_BUT_NOT_FALLBACK")
                passed = False
        else:
            # We mainly want to ensure the system produced a non-empty answer.
            passed = bool((answer or "").strip())
            if not passed:
                violations.append("EMPTY_ANSWER")
    else:
        # Strict citation/guardrail mode.
        if ctx_n == 0:
            if answer != FALLBACK:
                violations.append("NO_CONTEXTS_BUT_NOT_FALLBACK")
            passed = (answer == FALLBACK)
        else:
            if answer == FALLBACK:
                passed = True
            else:
                if not answer_cites:
                    violations.append("NO_CITATIONS")
                if not bullet_cite_ok:
                    violations.append("BULLET_MISSING_CITATION")
                if non_cite_brackets:
                    violations.append("NON_CITATION_BRACKETS")
                if answer_cite_set and not answer_cite_set.issubset(allowed_set):
                    violations.append("CITES_NOT_IN_ALLOWED_LIST")

                passed = (
                    bool(answer_cites)
                    and bullet_cite_ok
                    and not non_cite_brackets
                    and (not answer_cite_set or answer_cite_set.issubset(allowed_set))
                )

    return {
        "domain": domain,
        "question": question,
        "contexts": ctx_n,
        "allowed_citations": allowed,
        "answer": answer,
        "answer_snippet": _snip(answer),
        "answer_citations": sorted(answer_cite_set),
        "bullet_count": len([b for b in bullets if b.strip()]),
        "passed": passed,
        "violations": violations,
    }


def write_markdown(out_path: Path, results: List[Dict[str, Any]], started_at: float) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dur_ms = int((time.time() - started_at) * 1000)
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))

    lines: List[str] = []
    lines.append("# Answer Evaluation Report (LLM + Guardrails)")
    lines.append("")
    lines.append(f"Generated: {ts}")
    lines.append(f"Duration: {dur_ms} ms")
    lines.append(f"Pass: {passed}/{total}")
    lines.append("")

    # Include evaluation mode hint (if present)
    citations_mode = results[0].get("citations_mode") if results else None
    if citations_mode:
        lines.append(f"Citations mode: {citations_mode}")
        lines.append("")

    by_domain: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        by_domain.setdefault(r["domain"], []).append(r)

    for dom in ("announcements", "regulations", "curriculum"):
        rows = by_domain.get(dom, [])
        if not rows:
            continue
        dom_total = len(rows)
        dom_pass = sum(1 for r in rows if r.get("passed"))
        dom_fail = dom_total - dom_pass
        dom_fallback = sum(1 for r in rows if (r.get('answer') or '').strip() == FALLBACK)
        dom_nonfallback = dom_total - dom_fallback

        lines.append(f"## Domain: {dom}")
        lines.append("")
        lines.append(f"pass: {dom_pass}/{dom_total} | fail: {dom_fail} | fallback: {dom_fallback} | non-fallback: {dom_nonfallback}")
        lines.append("")

        # Show a few fail examples up-front
        fail_examples = [r for r in rows if not r.get('passed')]
        if fail_examples:
            lines.append("### Fail examples")
            lines.append("")
            for r in fail_examples[:3]:
                v = r.get('violations') or []
                lines.append(f"- Q: {r['question']}")
                lines.append(f"  - violations: {', '.join(v) if v else '-'}")
                lines.append(f"  - snippet: {r.get('answer_snippet')}")
            lines.append("")

        lines.append("### Details")
        lines.append("")
        for r in rows:
            status = "PASS" if r.get("passed") else "FAIL"
            lines.append(f"### {status}: {r['question']}")
            lines.append("")
            lines.append(
                f"contexts: {r['contexts']} | bullets: {r['bullet_count']} | cites: {len(r.get('answer_citations') or [])}"
            )
            v = r.get("violations") or []
            if v:
                lines.append(f"violations: {', '.join(v)}")
            lines.append(f"answer_snippet: {r.get('answer_snippet')}")
            lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="Run answer evaluation suite via /rag/answer (OpenAI or other LLM)")
    p.add_argument("--out", type=str, default="", help="markdown report path (default: reports/answer_eval_<ts>.md)")
    p.add_argument("--json", type=str, default="", help="optional JSON output path")
    p.add_argument("--debug", action="store_true", help="enable OpenAI debug logging")
    p.add_argument("--n-per-domain", type=int, default=30, help="max questions per domain to run")
    p.add_argument("--domains", type=str, default="announcements,regulations,curriculum", help="comma-separated domain list")
    p.add_argument(
        "--citations",
        type=str,
        default="strict",
        choices=["strict", "off"],
        help="evaluation mode: strict=enforce per-bullet citations, off=do not require citations",
    )
    args = p.parse_args()

    # Improve Windows console output
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    if args.debug:
        os.environ["OPENAI_DEBUG"] = "1"

    started = time.time()
    client = TestClient(app)

    want_domains = [d.strip().lower() for d in (args.domains or '').split(',') if d.strip()]
    n_per = max(1, int(args.n_per_domain))

    # Stable ordering + slice per domain to control cost
    by_dom: Dict[str, List[AnswerEvalQuery]] = {"announcements": [], "regulations": [], "curriculum": []}
    for q in DEFAULT_QUERIES:
        dom = (q.domain or '').strip().lower()
        if dom in by_dom:
            by_dom[dom].append(q)

    suite: List[AnswerEvalQuery] = []
    for dom in ("announcements", "regulations", "curriculum"):
        if dom not in want_domains:
            continue
        suite.extend(by_dom.get(dom, [])[:n_per])
    results: List[Dict[str, Any]] = []

    for q in suite:
        r = evaluate_one(client, q.domain, q.question, citations_mode=args.citations)
        r["expect_answerable"] = bool(q.expect_answerable)
        r["citations_mode"] = args.citations
        results.append(r)

    repo_root = Path(__file__).resolve().parents[3]
    ts_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_md = Path(args.out) if args.out else (repo_root / "reports" / f"answer_eval_{ts_slug}.md")
    out_json = Path(args.json) if args.json else (repo_root / "reports" / f"answer_eval_{ts_slug}.json")

    write_markdown(out_md, results, started)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    print(f"✅ Wrote report: {out_md}")
    print(f"✅ Wrote data:   {out_json}")
    print(f"✅ Pass: {passed}/{total}")

    if mlf and getattr(mlf, "enabled", lambda: False)():
        with mlf.start_run(
            run_name=f"answer_eval_{ts_slug}",
            tags={"script": "services/rag-service/scripts/answer_eval_suite.py"},
        ):
            mlf.log_params(
                {
                    "n_per_domain": int(args.n_per_domain),
                    "domains": str(args.domains),
                    "citations": str(args.citations),
                    "debug": bool(args.debug),
                }
            )
            mlf.log_metrics(
                {
                    "total": total,
                    "passed": passed,
                    "pass_rate": (passed / total) if total else 0.0,
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
