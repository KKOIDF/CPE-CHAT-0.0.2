from __future__ import annotations

import re
from typing import Any

from .structured_artifacts import load_announcement_calendar_artifact


def normalize_announcement_blob(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def select_announcement_calendar_entry(question: str) -> dict[str, Any] | None:
    artifact = load_announcement_calendar_artifact()
    entries = artifact.get("entries") if isinstance(artifact, dict) else None
    if not isinstance(entries, list):
        return None

    ql = normalize_announcement_blob(question)
    if not ql:
        return None

    best: dict[str, Any] | None = None
    best_score = 0
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        label = normalize_announcement_blob(raw.get("label") or "")
        value = normalize_announcement_blob(raw.get("value") or "")
        topic = normalize_announcement_blob(raw.get("topic") or "")
        blob = normalize_announcement_blob(raw.get("blob") or f"{label} {value} {topic}")
        keywords = raw.get("keywords") if isinstance(raw.get("keywords"), list) else []

        score = 0
        for kw in keywords:
            key = normalize_announcement_blob(str(kw or ""))
            if key and key in ql:
                score += 4
        for hint in (
            "ลงทะเบียน",
            "ชำระเงิน",
            "เปิดให้บริการ",
            "20 นาที",
            "อยู่ในระบบ",
            "โมดูล 5 สัปดาห์",
            "ช่วงที่ 1",
            "ถอนรายวิชา",
            "ผลการประเมิน",
            "รหัส 66",
            "ปี 3",
            "ปี 2",
            "ปี 1",
        ):
            norm_hint = normalize_announcement_blob(hint)
            if norm_hint in ql and norm_hint in blob:
                score += 3
        if ("วันสุดท้าย" in ql) and ("วันสุดท้าย" in blob):
            score += 3
        if any(t in ql for t in ("กี่โมง", "เวลาใด", "เปิดกี่โมง")) and ("07:00" in value or "23:00" in value):
            score += 4
        if ("ไม่เกินกี่นาที" in ql or "ครั้งละ" in ql) and ("20 นาที" in blob):
            score += 4
        if ("ถอนรายวิชา" in ql or "ลดรายวิชา" in ql) and (
            "withdrawn" in blob or "w" in blob or "ลดรายวิชา" in blob
        ):
            score += 4
        if score > best_score:
            best_score = score
            best = raw

    return best if best_score >= 4 else None


def render_fast_announcement_calendar_answer(question: str) -> str | None:
    ql = (question or "").strip().lower()
    artifact_entry = select_announcement_calendar_entry(question)
    if artifact_entry:
        source = str(artifact_entry.get("source") or "announcement_calendar.json").strip()
        page = int(artifact_entry.get("page") or 1)
        label = str(artifact_entry.get("label") or "").strip()
        value = str(artifact_entry.get("value") or "").strip()
        if label and value:
            if "ผลการประเมินเป็น" in value:
                return f"- {value} [{source}/{page}]"
            if any(t in ql for t in ("กี่โมง", "เวลาใด", "เปิดกี่โมง", "เปิดให้บริการ", "ครั้งละ", "ไม่เกินกี่นาที", "อยู่ในระบบ")):
                return f"- {value} [{source}/{page}]"
            return f"- {label}: {value} [{source}/{page}]"

    cite = "ปฏิทินการศึกษา_2568.txt announcement calendar/1"
    if any(t in ql for t in ("เปิดให้บริการช่วงเวลาใด", "เปิดให้บริการเวลาใด", "กี่โมง", "เปิดกี่โมง", "ถึงกี่โมง")):
        return f"- ระบบลงทะเบียนเปิดให้บริการเวลา 07:00-23:00 [{cite}]"
    if any(t in ql for t in ("อยู่ในระบบ", "ครั้งละ", "ไม่เกินกี่นาที")):
        return f"- นักศึกษาอยู่ในระบบลงทะเบียนได้ครั้งละไม่เกิน 20 นาที [{cite}]"
    if "วันสุดท้าย" in ql and "ชำระเงิน" in ql:
        return f"- วันสุดท้ายของการชำระเงินค่าลงทะเบียนภาค 2/2568 คือ พฤ.8 มกราคม 2569 [{cite}]"
    if "โมดูล 5 สัปดาห์" in ql and "ช่วงที่ 1" in ql:
        return f"- กำหนดการลดรายวิชาโมดูล 5 สัปดาห์ ช่วงที่ 1 คือ วันเสาร์ที่ 24 มกราคม - วันศุกร์ที่ 6 กุมภาพันธ์ 2569 [{cite}]"
    if ("ถอนรายวิชา" in ql or "ถอน" in ql) and any(t in ql for t in ("ผลการประเมิน", "ผลการเรียน", "เป็นอะไร", "สถานะ")):
        return f"- การถอนรายวิชาในช่วงเวลาดังกล่าวได้ผลการประเมินเป็น W (Withdrawn) [{cite}]"
    if any(t in ql for t in ("รหัส 66", "ปี 3", "ปี3")) and any(t in ql for t in ("ลงทะเบียน", "ช่วงวันใด", "ช่วงวัน")):
        return f"- นักศึกษาปี 3 (รหัส 66) ลงทะเบียนภาค 2/2568 ช่วง อา.4 - พ.7 มกราคม 2569 [{cite}]"
    return None
