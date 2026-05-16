from __future__ import annotations

import os
import re
from typing import Dict, List


_SYSTEM_PROMPT = """คุณเป็นผู้ช่วยตอบคำถามจากเอกสารของมหาวิทยาลัย/หลักสูตร
หน้าที่ของคุณคือสังเคราะห์คำตอบจาก CONTEXT ที่ระบบค้นมาให้เท่านั้น

แนวทางการตอบ:
1. ตอบคำถามโดยตรงก่อนเสมอ
2. ถ้าคำถามเป็นคำสั้นหรือวลี ให้ตีความว่า user ต้องการคำอธิบายเกี่ยวกับเรื่องนั้นจากเอกสาร
3. ถ้า CONTEXT มีข้อมูลเพียงพอ ให้สรุปคำตอบเป็นภาษาไทยที่อ่านง่ายและเป็นธรรมชาติ
4. ถ้า CONTEXT มีข้อมูลจากหลาย source ให้รวมเป็นคำตอบเดียว โดยจัดหมวดหมู่ให้เข้าใจง่าย
5. ถ้า CONTEXT มีข้อมูลบางส่วน ให้ตอบเฉพาะส่วนที่พบ และระบุว่าส่วนใดไม่พบในเอกสาร
6. ถ้า CONTEXT ไม่มีข้อมูลที่เกี่ยวข้องเลย ให้ตอบว่า "ไม่พบข้อมูลนี้ในเอกสารที่ค้นได้"
7. ห้ามใช้ความรู้ภายนอก CONTEXT
8. ห้ามสร้าง citation ที่ไม่มีอยู่จริง
9. ใช้ citation แบบตัวเลข เช่น [1], [2] ต่อท้ายประโยคหรือ bullet ที่อ้างอิงข้อมูล
10. ท้ายคำตอบให้ใส่ References โดย map หมายเลข citation ไปยัง source จริงเท่านั้น
11. ถ้าคำถามเป็นภาษาไทย ให้ตอบภาษาไทยด้วยน้ำเสียงสุภาพ เป็นธรรมชาติ และใช้คำว่า "ครับ" ได้
12. ถ้าคำถามเกี่ยวกับระเบียบ ขั้นตอน หรือเงื่อนไข ให้จัดคำตอบเป็นหัวข้อและ bullet
13. ถ้าคำถามเกี่ยวกับความหมายของคำหรือสัญลักษณ์ ให้ให้คำนิยามก่อน แล้วค่อยขยายบริบทการใช้งาน
14. ถ้ามีข้อมูลเพียงบางส่วน ห้ามตอบว่าไม่พบทั้งหมด

รูปแบบคำตอบที่ต้องการ:
- คำตอบหลักที่ตอบตรงคำถามก่อน
- รายละเอียดหรือหัวข้อย่อยเท่าที่จำเป็น
- References
"""


def _format_ref(source_name: str, page: str = "", section: str = "") -> str:
    if page:
        return f"{source_name}, หน้า {page}"
    if section:
        return f"{source_name}, section {section}"
    return source_name


def _extract_citation_map(formatted_context: str) -> Dict[int, str]:
    current_num: int | None = None
    current_name = ""
    current_page = ""
    current_section = ""
    mapping: dict[int, str] = {}
    for raw_line in (formatted_context or "").splitlines():
        line = raw_line.strip()
        match = re.fullmatch(r"\[(\d+)\]", line)
        if match:
            if current_num is not None and current_name:
                mapping[current_num] = _format_ref(current_name, current_page, current_section)
            current_num = int(match.group(1))
            current_name = ""
            current_page = ""
            current_section = ""
            continue
        if line.startswith("source_name:"):
            current_name = line.split(":", 1)[1].strip()
        elif line.startswith("page:"):
            current_page = line.split(":", 1)[1].strip()
        elif line.startswith("section:"):
            current_section = line.split(":", 1)[1].strip()
    if current_num is not None and current_name:
        mapping[current_num] = _format_ref(current_name, current_page, current_section)
    return mapping


def build_prompt(question: str, formatted_context: str, cites: Dict[int, str] | None = None, intent: str = "general") -> str:
    citation_map = dict(sorted((cites or _extract_citation_map(formatted_context)).items()))
    reference_block = "\n".join([f"[{idx}] - source:{label}" for idx, label in citation_map.items()]) or "(ไม่มีแหล่งอ้างอิง)"
    prompt_style = (os.getenv("RAG_PROMPT_STYLE", "open_notebook_like") or "open_notebook_like").strip().lower()
    answer_style = (os.getenv("RAG_ANSWER_STYLE", "thai_academic_friendly") or "thai_academic_friendly").strip().lower()
    citation_style = (os.getenv("RAG_CITATION_STYLE", "numeric_sources") or "numeric_sources").strip().lower()
    include_refs = (os.getenv("RAG_INCLUDE_REFERENCES_BLOCK", "true") or "true").strip().lower() in ("1", "true", "yes", "on")
    return (
        f"{_SYSTEM_PROMPT}\n\n"
        f"Prompt style: {prompt_style}\n"
        f"Answer style: {answer_style}\n"
        f"Citation style: {citation_style}\n"
        f"ต้องใช้เลขอ้างอิงเฉพาะชุดนี้เท่านั้น: {', '.join(f'[{n}]' for n in citation_map) or '(ไม่มี)'}\n\n"
        f"CONTEXT:\n{formatted_context}\n\n"
        f"QUESTION:\n{question}\n\n"
        f"References ที่ใช้ได้:\n{reference_block if include_refs else ''}\n\n"
        "ANSWER:\n"
    )


def build_answer_messages(question: str, formatted_context: str, cites: Dict[int, str] | None = None) -> List[Dict[str, str]]:
    prompt = build_prompt(question, formatted_context, cites=cites)
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt.split("\n\n", 1)[1] if "\n\n" in prompt else prompt},
    ]


def finalize_answer(answer: str, citation_map: Dict[int, str] | None = None) -> str:
    text = str(answer or "").strip()
    if not text:
        return "ไม่พบข้อมูลนี้ในเอกสารที่ค้นได้"
    if text == "ไม่พบข้อมูลนี้ในเอกสารที่ค้นได้":
        return text

    citation_map = dict(sorted((citation_map or {}).items()))
    found = [int(m.group(1)) for m in re.finditer(r"\[(\d+)\]", text) if int(m.group(1)) in citation_map]
    ordered_cites: list[int] = []
    seen: set[int] = set()
    for num in found or list(citation_map.keys()):
        if num in citation_map and num not in seen:
            seen.add(num)
            ordered_cites.append(num)

    if ordered_cites and not found:
        lines = [line.rstrip() for line in text.splitlines()]
        for idx, line in enumerate(lines):
            if line.strip() and not line.strip().startswith("References:"):
                suffix = f" [{ordered_cites[0]}]"
                if suffix.strip() not in line:
                    lines[idx] = line.rstrip(" .") + suffix
                break
        text = "\n".join(lines).strip()

    ref_lines = [f"[{num}] - source:{citation_map[num]}" for num in ordered_cites if num in citation_map]
    if ref_lines:
        text = re.sub(r"(?:\n+References:?\n(?:\[[^\n]+\n?)+)\s*$", "", text, flags=re.MULTILINE).strip()
        text = f"{text}\n\nReferences:\n" + "\n".join(ref_lines)
    return text.strip()
