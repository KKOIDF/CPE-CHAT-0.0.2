#!/usr/bin/env python3
"""Generate per-domain (announcements/regulations/curriculum) test Q&A CSV.

Goal:
- 30 Q&As per domain (90 total)
- Expected answers are grounded in the corpus (quotes / extracted clause text)
- CSV layout is compatible with existing `testQA1.csv` blocks

This script is intentionally deterministic and avoids LLM usage.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = ROOT / "testQA_domains_30.csv"


@dataclass(frozen=True)
class QA:
    domain: str
    question: str
    expected: str
    source: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _iter_lines(text: str) -> Iterator[str]:
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Normalize OCR artifacts lightly
        line = re.sub(r"\s+", " ", line)
        yield line


def _extract_numbered_clauses(text: str) -> list[str]:
    """Extract lines that look like 'ข้อ X ...' or markdown '**ข้อ X** ...'."""
    clauses: list[str] = []
    for line in _iter_lines(text):
        if re.match(r"^(\*\*\s*)?ข้อ\s*\d+\b", line):
            # Remove markdown ** ... ** around 'ข้อ ...'
            line = re.sub(r"\*\*", "", line).strip()
            clauses.append(line)
    return clauses


def _extract_bullets_with_money(text: str) -> list[str]:
    bullets: list[str] = []
    for line in _iter_lines(text):
        if "บาท" in line and re.search(r"\d", line):
            # keep bullet-like lines or subclauses
            if re.match(r"^(\*\s+)?\d+(\.\d+)?\b", line) or "ครั้งละ" in line or "ปีการศึกษาละ" in line:
                bullets.append(re.sub(r"^\*\s*", "", line).strip())
    return bullets


def _dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        key = it.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def generate_announcements() -> list[QA]:
    """Build 30 QAs from announcement-like official notifications."""

    paths = [
        ROOT / "data/announcements/insurance-std.txt",
        ROOT / "data/announcements/t_fee.txt",
        ROOT / "data/announcements/price.txt",
        ROOT / "data/announcements/fee2567update.txt",
        ROOT / "data/announcements/ปฏิทินการศึกษา 2568.txt",
    ]

    items: list[tuple[str, str]] = []  # (source, line)
    for p in paths:
        if not p.exists():
            continue
        text = _read_text(p)
        for c in _extract_numbered_clauses(text):
            items.append((p.name, c))
        for b in _extract_bullets_with_money(text):
            items.append((p.name, b))

        # Add a few schedule / system lines (calendar file is short and clear)
        if "ปฏิทินการศึกษา" in p.name:
            for line in _iter_lines(text):
                if any(k in line for k in ["วันลงทะเบียน", "วันสุดท้าย", "ระบบเปิดให้บริการ", "เข้าสู่ระบบลงทะเบียน", "ถอนรายวิชา", "ลดรายวิชา"]):
                    # Skip section headers without details
                    if re.match(r"^[^:]+:\s*$", line) or re.match(r"^🔸วันลงทะเบียนเรียน\b", line):
                        continue
                    # Prefer lines with concrete details
                    if not (re.search(r"\d", line) or "http" in line.lower()):
                        continue
                    items.append((p.name, line))

    # Prefer content-rich unique lines (keep first source that introduced the line)
    first_src_by_line: dict[str, str] = {}
    for src, line in items:
        if line not in first_src_by_line:
            first_src_by_line[line] = src
    unique_lines = list(first_src_by_line.keys())

    qas: list[QA] = []
    for line in unique_lines:
        src = first_src_by_line[line]

        # Heuristic question generation
        q: str
        expected = line

        if "ประกันภัย" in line and "บาท" in line:
            q = "ค่าประกันภัยอุบัติเหตุสำหรับนักศึกษาเก็บเท่าไรต่อปีการศึกษา?"
        elif "ไปรษณีย์" in line and "ครั้งละ" in line and "บาท" in line:
            q = "ค่าธรรมเนียมจัดส่งเอกสารสำคัญทางการศึกษาทางไปรษณีย์ (ตามที่ระบุ) เท่าไร?"
        elif "ค่าประกันทรัพย์สินเสียหาย" in line:
            if "บาท" in line and re.search(r"\d", line):
                q = "นักศึกษาแบบบุคคลภายนอกต้องจ่ายค่าประกันทรัพย์สินเสียหายเท่าไรต่อภาคการศึกษา?"
            else:
                q = "เงินค่าประกันทรัพย์สินเสียหายคืนให้เมื่อไร/อย่างไร?"
        elif re.match(r"^ข้อ\s*2\b", line) and "มีผล" in line:
            q = "ประกาศนี้มีผลใช้บังคับตั้งแต่เมื่อไร (ตามข้อ 2)?"
        elif "วันสุดท้ายของการชำระเงิน" in line:
            q = "วันสุดท้ายของการชำระเงินค่าลงทะเบียนคือวันไหน?"
        elif "วันลงทะเบียนเรียน" in line:
            q = "กำหนดวันลงทะเบียนเรียน (ตามที่ประกาศ) คือช่วงไหน?"
        elif "เข้าสู่ระบบลงทะเบียนเรียน" in line and "http" in line.lower():
            q = "เข้าสู่ระบบลงทะเบียนเรียนได้ที่ลิงก์ไหน?"
        elif "ระบบเปิดให้บริการ" in line and ("เวลา" in line or "07" in line):
            q = "ระบบลงทะเบียนเปิดให้บริการเวลาใดถึงเวลาใด?"
        elif re.match(r"^\d+\.\d+\.\d+\b", line) and "บาท" in line:
            q = "ค่าธรรมเนียมตามรายการนี้คิดเท่าไร?"
        elif line.startswith("ข้อ "):
            # Use clause header as the question seed
            m = re.match(r"^ข้อ\s*(\d+)\s*(.*)$", line)
            clause_no = m.group(1) if m else ""
            rest = m.group(2).strip() if m else line
            if rest:
                q = f"ตามประกาศ ข้อ {clause_no} ระบุเรื่องอะไร/มีใจความว่าอย่างไร?"
            else:
                q = f"ตามประกาศ ข้อ {clause_no} ระบุว่าอย่างไร?"
        else:
            # Fallback: ask to repeat/confirm the stated detail
            q = "ตามประกาศ ระบุรายละเอียดนี้ว่าอย่างไร?"

        qas.append(QA(domain="announcements", question=q, expected=expected, source=src))
        if len(qas) >= 30:
            break

    if len(qas) < 30:
        raise SystemExit(f"announcements: not enough QA candidates ({len(qas)}/30)")

    # Ensure questions are varied: if duplicates, slightly rewrite deterministically
    seen_q: dict[str, int] = {}
    final: list[QA] = []
    for qa in qas:
        n = seen_q.get(qa.question, 0)
        seen_q[qa.question] = n + 1
        if n == 0:
            final.append(qa)
        else:
            final.append(
                QA(
                    domain=qa.domain,
                    question=f"{qa.question} (อ้างอิง: {qa.source})",
                    expected=qa.expected,
                    source=qa.source,
                )
            )
    return final[:30]


def generate_regulations() -> list[QA]:
    """Build 30 QAs from exam and discipline regulations."""

    sources = [
        ROOT / "data/regulations/rule_exam2560.txt",
        ROOT / "data/regulations/discipline2566_fulltext.txt",
    ]

    candidates: list[tuple[str, str]] = []
    for p in sources:
        if not p.exists():
            continue
        text = _read_text(p)
        for c in _extract_numbered_clauses(text):
            candidates.append((p.name, c))

    # Keep only clauses with actionable guidance
    filtered: list[tuple[str, str]] = []
    for src, line in candidates:
        if any(k in line for k in ["ห้าม", "ต้อง", "ไม่", "ให้", "อุทธรณ์", "โทษ", "หมดสิทธิ์", "บัตรนักศึกษา", "เครื่องมือสื่อสาร", "ทุจริต"]):
            filtered.append((src, line))

    # Deduplicate while keeping order
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for src, line in filtered:
        key = f"{src}|{line}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append((src, line))

    qas: list[QA] = []
    for src, line in deduped:
        m = re.match(r"^ข้อ\s*(\d+)\s*(.*)$", line)
        clause_no = m.group(1) if m else ""
        rest = m.group(2).strip() if m else line

        if "ห้าม" in rest:
            q = f"ระเบียบ ข้อ {clause_no} ห้ามอะไร?"
        elif "ต้อง" in rest:
            q = f"ระเบียบ ข้อ {clause_no} กำหนดให้นักศึกษาต้องทำอะไร?"
        elif "อุทธรณ์" in rest:
            q = f"การอุทธรณ์คำสั่งลงโทษทำอย่างไรตามข้อ {clause_no}?"
        elif "โทษ" in rest or "ลงโทษ" in rest:
            q = f"บทลงโทษ/อำนาจลงโทษในข้อ {clause_no} ระบุว่าอย่างไร?"
        else:
            q = f"ข้อ {clause_no} มีใจความสำคัญว่าอย่างไร?"

        qas.append(QA(domain="regulations", question=q, expected=line, source=src))
        if len(qas) >= 30:
            break

    if len(qas) < 30:
        raise SystemExit(f"regulations: not enough QA candidates ({len(qas)}/30)")

    return qas[:30]


@dataclass
class Course:
    code: str
    thai: str
    eng: str | None
    credits: int
    detail: str


def _parse_curriculum_courses(text: str) -> list[Course]:
    courses: list[Course] = []
    lines = list(_iter_lines(text))
    i = 0
    course_re = re.compile(
        r"^(?P<prefix>[A-Z]{3})\s*(?P<num>\d{3})\s+(?P<thai>.+?)\s+(?P<cr>\d+)\s*\((?P<detail>[^)]+)\)\s*$"
    )
    while i < len(lines):
        line = lines[i]
        m = course_re.match(line)
        if not m:
            i += 1
            continue
        code = f"{m.group('prefix')} {m.group('num')}"
        thai = m.group("thai").strip()
        credits = int(m.group("cr"))
        detail = m.group("detail").strip()
        eng = None
        if i + 1 < len(lines):
            nxt = lines[i + 1]
            m2 = re.match(r"^\((.+)\)\s*$", nxt)
            if m2:
                eng = m2.group(1).strip()
        courses.append(Course(code=code, thai=thai, eng=eng, credits=credits, detail=detail))
        i += 1
    return courses


def generate_curriculum() -> list[QA]:
    p = ROOT / "data/curriculum/FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt"
    if not p.exists():
        raise SystemExit("curriculum source file missing")

    text = _read_text(p)
    qas: list[QA] = []

    # Program structure facts
    structure_patterns = [
        (r"หมวดวิชาศึกษาทั่วไป\s+(\d+)\s+หน่วยกิต", "หมวดวิชาศึกษาทั่วไปกำหนดกี่หน่วยกิต?"),
        (r"หมวดวิชาเฉพาะ\s+(\d+)\s+หน่วยกิต", "หมวดวิชาเฉพาะกำหนดกี่หน่วยกิต?"),
        (r"จำนวนหน่วยกิตรวมตลอดหลักสูตร\s+(\d+)\s+หน่วยกิต", "หลักสูตรวิศวกรรมคอมพิวเตอร์กำหนดหน่วยกิตรวมเท่าไร?"),
    ]
    for pat, q in structure_patterns:
        m = re.search(pat, text)
        if m:
            expected = re.sub(r"\s+", " ", m.group(0)).strip()
            qas.append(QA(domain="curriculum", question=q, expected=expected, source=p.name))

    # Course facts
    courses = _parse_curriculum_courses(text)
    # Deterministic: pick the first many courses in the plan
    for c in courses:
        if len(qas) >= 30:
            break
        if c.eng:
            q = f"วิชา {c.code} ชื่อภาษาอังกฤษว่าอะไร และมีหน่วยกิตเท่าไร?"
            expected = f"{c.code} {c.thai} {c.credits} หน่วยกิต ({c.detail}) — {c.eng}"
        else:
            q = f"วิชา {c.code} ({c.thai}) มีหน่วยกิตเท่าไร?"
            expected = f"{c.code} {c.thai} {c.credits} หน่วยกิต ({c.detail})"
        qas.append(QA(domain="curriculum", question=q, expected=expected, source=p.name))

    if len(qas) < 30:
        raise SystemExit(f"curriculum: not enough QA candidates ({len(qas)}/30)")

    return qas[:30]


def write_csv(blocks: dict[str, list[QA]]) -> None:
    # CSV layout compatible with existing file
    header = [
        "ลำดับ",
        "คำถาม",
        "คำตอบที่คาดว่าจะตอบ",
        "คำตอบที่ระบบตอบ\nรอบที่1",
        "คำตอบที่ระบบตอบ\nรอบที่2",
        "คำตอบที่ระบบตอบ\nรอบที่3",
    ]

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)

        def write_block(title: str, qas: list[QA]) -> None:
            # Title row + spacer
            w.writerow([title, "", "", "", "", ""])
            w.writerow(["", "", "", "", "", ""])
            w.writerow(header)
            for i, qa in enumerate(qas, start=1):
                w.writerow([i, qa.question, qa.expected, "", "", ""])
            w.writerow(["", "", "", "", "", ""])
            w.writerow(["", "", "", "", "", ""])

        write_block(
            "Announcements — คำถาม (นักศึกษาจะถาม) และคำตอบที่คาดว่าจะตอบ",
            blocks["announcements"],
        )
        write_block(
            "Regulations — คำถาม (นักศึกษาจะถาม) และคำตอบที่คาดว่าจะตอบ",
            blocks["regulations"],
        )
        write_block(
            "Curriculum — คำถาม (นักศึกษาจะถาม) และคำตอบที่คาดว่าจะตอบ",
            blocks["curriculum"],
        )


def main() -> None:
    blocks = {
        "announcements": generate_announcements(),
        "regulations": generate_regulations(),
        "curriculum": generate_curriculum(),
    }
    write_csv(blocks)
    print(f"Wrote: {OUT_CSV} (rows: {sum(len(v) for v in blocks.values())})")


if __name__ == "__main__":
    main()
