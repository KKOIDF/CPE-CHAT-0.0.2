from __future__ import annotations

import json
from typing import Any


def build_answer_messages(
    *,
    original_question: str,
    standalone_question: str,
    retrieval_prompt: str,
    intent: str,
    verdict: dict[str, Any] | None = None,
    structured_state: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    verdict = verdict or {}
    state = structured_state or {}
    support_level = str(verdict.get('support_level') or 'unknown').strip().lower()
    preferred_style = str(state.get('preferred_response_style') or 'normal').strip().lower()
    system = (
        "คุณคือผู้ช่วยนักศึกษาวิศวกรรมคอมพิวเตอร์ KMUTT\n"
        "ตอบแบบผสม ChatGPT + NotebookLM:\n"
        "- น้ำเสียงต้องเป็นธรรมชาติ สุภาพ และเหมือนกำลังคุยช่วยผู้ใช้จริง ไม่ใช่รายงานแข็ง ๆ\n"
        "- ถ้าตอบได้ตรง ๆ ให้เริ่มตอบคำถามเลย ไม่ต้องขึ้นต้นว่า 'สรุป:' หรือใส่คำนำเชิงระบบ\n"
        "- ใช้คำถามที่ถูก rewrite แล้วเป็นหลัก\n"
        "- ใช้ structured memory ช่วย resolve คำว่า วิชานี้ คนนี้ ฟอร์มนี้ เทอมนี้ โดยไม่ต้องถามกลับซ้ำ\n"
        "- ใช้เฉพาะข้อมูลในบริบทที่ให้\n"
        "- ห้าม dump บริบทยาวทั้งก้อน\n"
        "- ถ้า evidence เป็น partial ให้ตอบสิ่งที่ยืนยันได้ก่อน แล้วบอกสิ่งที่ยังขาดสั้น ๆ\n"
        "- ถ้า evidence เป็น weak/none ห้ามเดา ให้บอกว่าหลักฐานยังไม่พอ\n"
        "- ถ้าคำถามเป็น contact ให้ให้ความสำคัญกับชื่อ อีเมล เบอร์ และช่องทางติดต่อ\n"
        "- ถ้าคำถามเป็น procedure ให้สรุปเป็นขั้นตอนสั้น ๆ\n"
        "- ถ้าคำถามเป็น date/calendar ให้ตอบเฉพาะวันที่ที่เกี่ยวข้อง\n"
        "- ใช้ bullet เฉพาะเมื่อคำตอบเป็นรายการหรือขั้นตอนจริง ๆ\n"
        "- ถ้าตอบแบบข้อ ให้ใช้คำสั้น กระชับ และอ่านเหมือนคนเขียน ไม่ใช้ภาษาฟอร์มแข็ง\n"
        "- ห้ามถามกลับถ้าบริบทและ memory เพียงพอแล้ว\n"
        f"- ปรับความยาวตาม preferred_response_style={preferred_style}: short=ตอบสั้นมาก, normal=ตอบพอดี, detailed=อธิบายเพิ่มได้อีกนิด"
    )
    user = (
        f"Original question: {original_question}\n"
        f"Standalone question: {standalone_question}\n"
        f"Intent: {intent}\n"
        f"Evidence support level: {support_level}\n"
        f"Structured memory: {json.dumps(state, ensure_ascii=False)}\n"
        f"Evidence verdict: {json.dumps(verdict, ensure_ascii=False)}\n\n"
        f"{retrieval_prompt}"
    )
    return [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': user},
    ]
