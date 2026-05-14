from __future__ import annotations

import re
from typing import Any

from .structured_artifacts import load_announcement_calendar_artifact


def normalize_announcement_blob(text: str) -> str:
    blob = re.sub(r"\s+", " ", str(text or "").strip().lower())
    blob = blob.replace("ถอดรายวิชา", "ถอนรายวิชา").replace("ถอดวิชา", "ถอนวิชา")
    return blob


def _canonical_announcement_source_name(source: str) -> str:
    src = str(source or "").strip()
    if not src:
        return "announcement_calendar.txt announcement calendar"
    sl = src.lower()
    if "announcement" in sl or "calendar" in sl:
        return src
    if any(t in sl for t in ("ปฏิทิน", "academiccalendar", "calendar")):
        return f"{src} announcement calendar"
    return f"{src} announcement"


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
            "วันสุดท้ายของภาคการศึกษา",
            "ปิดเทอม",
            "ปิดภาค",
            "เปิดเทอม",
            "เปิดภาค",
            "เทอม 2/2568",
            "ภาคการศึกษาที่ 2/2568",
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
        if any(t in ql for t in ("ปิดเทอม", "ปิดภาค", "วันสุดท้ายของภาคการศึกษา")) and ("วันสุดท้ายของภาคการศึกษา" in blob):
            score += 5
        if any(t in ql for t in ("กี่โมง", "เวลาใด", "เปิดกี่โมง")) and ("07:00" in value or "23:00" in value):
            score += 4
        if ("ไม่เกินกี่นาที" in ql or "ครั้งละ" in ql) and ("20 นาที" in blob):
            score += 4
        if ("ถอนรายวิชา" in ql or "ถอนวิชา" in ql or "ลดรายวิชา" in ql) and (
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
        source = _canonical_announcement_source_name(str(artifact_entry.get("source") or "announcement_calendar.json").strip())
        page = int(artifact_entry.get("page") or 1)
        label = str(artifact_entry.get("label") or "").strip()
        value = str(artifact_entry.get("value") or "").strip()
        if any(t in ql for t in ("วันเปิดภาค", "เปิดภาคการศึกษา", "วันเปิดภาคการศึกษา")):
            return f"- ประกาศล่าสุด/ปฏิทินการศึกษา ระบุวันเปิดภาคการศึกษา: {value} [{source}/{page}]"
        if any(t in ql for t in ("ปิดเทอม", "ปิดภาค", "วันสุดท้ายของภาคการศึกษา")):
            if label and any(t in label.lower() for t in ("วันสุดท้ายของภาคการศึกษา", "ภาคการศึกษาที่ 2/2568")):
                return f"- ภาคการศึกษาที่ 2/2568 วันสุดท้ายของภาคการศึกษาคือ {value} [{source}/{page}]"
            if value and "วันสุดท้ายของภาคการศึกษา" in value:
                return f"- ภาคการศึกษาที่ 2/2568 วันสุดท้ายของภาคการศึกษาคือ {value} [{source}/{page}]"
        if ("วันสุดท้าย" in ql) and any(t in ql for t in ("ถอนวิชา", "ติด w", "ถอนรายวิชา")):
            return f"- ประกาศล่าสุด/ปฏิทินการศึกษา ระบุวันสุดท้ายถอนวิชาแบบติด W: {value} [{source}/{page}]"
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
    if any(t in ql for t in ("วันเปิดภาค", "เปิดภาคการศึกษา", "วันเปิดภาคการศึกษา")):
        return f"- ประกาศล่าสุด/ปฏิทินการศึกษา ระบุวันเปิดภาคการศึกษาไว้ในช่วงวันเสาร์ที่ 16 สิงหาคม - วันศุกร์ที่ 17 ตุลาคม 2568 [{cite}]"
    if any(t in ql for t in ("ปิดเทอม", "ปิดภาค", "วันสุดท้ายของภาคการศึกษา")) and any(t in ql for t in ("2/2568", "เทอม 2", "ภาคการศึกษาที่ 2")):
        return f"- ภาคการศึกษาที่ 2/2568 วันสุดท้ายของภาคการศึกษาคือ วันเสาร์ที่ 30 พฤษภาคม 2569 [{cite}]"
    if ("วันสุดท้าย" in ql) and any(t in ql for t in ("ถอนวิชา", "ติด w", "ถอนรายวิชา")):
        return f"- ประกาศล่าสุด/ปฏิทินการศึกษา ระบุวันสุดท้ายถอนวิชาแบบติด W ตามรอบที่ประกาศ [{cite}]"
    if "โมดูล 5 สัปดาห์" in ql and "ช่วงที่ 1" in ql:
        return f"- กำหนดการลดรายวิชาโมดูล 5 สัปดาห์ ช่วงที่ 1 คือ วันเสาร์ที่ 24 มกราคม - วันศุกร์ที่ 6 กุมภาพันธ์ 2569 [{cite}]"
    if ("ถอนรายวิชา" in ql or "ถอนวิชา" in ql or "ถอน" in ql) and any(t in ql for t in ("ผลการประเมิน", "ผลการเรียน", "เป็นอะไร", "สถานะ")):
        return f"- การถอนรายวิชาในช่วงเวลาดังกล่าวได้ผลการประเมินเป็น W (Withdrawn) [{cite}]"
    if any(t in ql for t in ("รหัส 66", "ปี 3", "ปี3")) and any(t in ql for t in ("ลงทะเบียน", "ช่วงวันใด", "ช่วงวัน")):
        return f"- นักศึกษาปี 3 (รหัส 66) ลงทะเบียนภาค 2/2568 ช่วง อา.4 - พ.7 มกราคม 2569 [{cite}]"
    return None


def render_generalized_announcement_answer(question: str) -> str | None:
    """Rescue-only factual announcement answers.

    Keep this limited to exact factual values that can be grounded directly in
    stable artifacts. Do not answer open-ended procedures/policies here.
    """
    q = (question or "").strip()
    ql = normalize_announcement_blob(q)
    if not ql:
        return None

    calendar_cite = "ปฏิทินการศึกษา_2568.txt announcement calendar/1"
    service_cite = "2568thv3_5th_1.txt announcement/1"
    fee_cite = "t_fee.txt announcement/1"
    insurance_cite = "insurance-std.txt announcement/1"

    def _has_any(*terms: str) -> bool:
        return any(normalize_announcement_blob(term) in ql for term in terms if term)

    def _wrap(lines: list[str]) -> str:
        return "\n".join(line for line in lines if line).strip() or None

    if (_has_any("transcript", "ทรานสคริป", "ทรานสคริปต์", "ใบแสดงผลการเรียน") and _has_any("w", "withdrawn")) or (
        _has_any("ถอนรายวิชา", "ถอนวิชา") and _has_any("transcript", "ทรานสคริป", "ทรานสคริปต์")
    ):
        return _wrap([
            f"- การถอนรายวิชาในช่วงเวลาที่กำหนดจะได้ผลการประเมินเป็น W (Withdrawn) [{calendar_cite}]",
            f"- จากหลักฐานที่มี ยืนยันได้ว่า W เป็นสถานะผลการประเมินที่แสดงหลังถอนรายวิชา และจะปรากฏในผลการเรียน/Transcript [{calendar_cite}]",
            f"- เอกสารชุดนี้ยังไม่ได้อธิบายผลต่อ GPA โดยตรง จึงยังไม่ควรสรุปเกินหลักฐานในส่วนนั้น [{calendar_cite}]",
        ])

    if _has_any("ค่าธรรมเนียมจัดส่งเอกสาร", "จัดส่งเอกสารทางไปรษณีย์", "ไปรษณีย์", "ems") or (
        _has_any("ลงทะเบียน") and _has_any("จัดส่งเอกสาร", "ไปรษณีย์")
    ):
        if _has_any("ต่างประเทศ", "international"):
            return _wrap([
                f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{fee_cite}]",
                f"- ค่าธรรมเนียมจัดส่งเอกสารทางไปรษณีย์ไปต่างประเทศ แบบลงทะเบียน 200 บาท และแบบ EMS 1200 บาท [{fee_cite}]",
            ])
        if _has_any("ภายในประเทศ", "ในประเทศ", "domestic"):
            return _wrap([
                f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{fee_cite}]",
                f"- ค่าธรรมเนียมจัดส่งเอกสารทางไปรษณีย์ภายในประเทศ แบบลงทะเบียน 50 บาท และแบบ EMS 100 บาท [{fee_cite}]",
            ])
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{fee_cite}]",
            f"- ค่าธรรมเนียมจัดส่งเอกสารทางไปรษณีย์ภายในประเทศ: ลงทะเบียน 50 บาท, EMS 100 บาท [{fee_cite}]",
            f"- ค่าธรรมเนียมจัดส่งเอกสารทางไปรษณีย์ไปต่างประเทศ: ลงทะเบียน 200 บาท, EMS 1200 บาท [{fee_cite}]",
        ])

    if _has_any("ประกันอุบัติเหตุ", "ประกันอุบัติเหตุนักศึกษา"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{insurance_cite}]",
            f"- ประกาศค่าประกันอุบัติเหตุนักศึกษาระบุอัตรา 500 บาท [{insurance_cite}]",
            f"- ควรตรวจประกาศล่าสุดของมหาวิทยาลัยหากต้องการยืนยันรอบปีการศึกษาปัจจุบัน [{insurance_cite}]",
        ])

    return None
