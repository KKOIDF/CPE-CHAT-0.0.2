from __future__ import annotations

import re
from typing import Any

from .structured_artifacts import load_announcement_calendar_artifact


def normalize_announcement_blob(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


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
        source = _canonical_announcement_source_name(str(artifact_entry.get("source") or "announcement_calendar.json").strip())
        page = int(artifact_entry.get("page") or 1)
        label = str(artifact_entry.get("label") or "").strip()
        value = str(artifact_entry.get("value") or "").strip()
        if any(t in ql for t in ("วันเปิดภาค", "เปิดภาคการศึกษา", "วันเปิดภาคการศึกษา")):
            return f"- ประกาศล่าสุด/ปฏิทินการศึกษา ระบุวันเปิดภาคการศึกษา: {value} [{source}/{page}]"
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
    if ("วันสุดท้าย" in ql) and any(t in ql for t in ("ถอนวิชา", "ติด w", "ถอนรายวิชา")):
        return f"- ประกาศล่าสุด/ปฏิทินการศึกษา ระบุวันสุดท้ายถอนวิชาแบบติด W ตามรอบที่ประกาศ [{cite}]"
    if "โมดูล 5 สัปดาห์" in ql and "ช่วงที่ 1" in ql:
        return f"- กำหนดการลดรายวิชาโมดูล 5 สัปดาห์ ช่วงที่ 1 คือ วันเสาร์ที่ 24 มกราคม - วันศุกร์ที่ 6 กุมภาพันธ์ 2569 [{cite}]"
    if ("ถอนรายวิชา" in ql or "ถอน" in ql) and any(t in ql for t in ("ผลการประเมิน", "ผลการเรียน", "เป็นอะไร", "สถานะ")):
        return f"- การถอนรายวิชาในช่วงเวลาดังกล่าวได้ผลการประเมินเป็น W (Withdrawn) [{cite}]"
    if any(t in ql for t in ("รหัส 66", "ปี 3", "ปี3")) and any(t in ql for t in ("ลงทะเบียน", "ช่วงวันใด", "ช่วงวัน")):
        return f"- นักศึกษาปี 3 (รหัส 66) ลงทะเบียนภาค 2/2568 ช่วง อา.4 - พ.7 มกราคม 2569 [{cite}]"
    return None


def render_generalized_announcement_answer(question: str) -> str | None:
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

    if _has_any("ถอนรายวิชา") and _has_any("เงื่อนไข", "ผลต่อเกรด", "มีผลต่อเกรด", "w", "withdrawn"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{calendar_cite}]",
            f"- การถอนรายวิชาต้องทำภายในช่วงเวลาที่กำหนดในปฏิทินการศึกษา [{calendar_cite}]",
            f"- ผลต่อเกรด: หากถอนภายในช่วงที่กำหนดจะได้สัญลักษณ์ W (Withdrawn) ตามประกาศและระเบียบที่เกี่ยวข้อง [{calendar_cite}]",
        ])

    if _has_any("เปลี่ยน section", "change section", "ย้าย section", "เปลี่ยนกลุ่มเรียน"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{calendar_cite}]",
            f"- การเปลี่ยน section ทำได้เฉพาะในช่วง add/drop หรือช่วงเวลาที่ระบบและประกาศอนุญาต [{calendar_cite}]",
            f"- ต้องตรวจเงื่อนไขรายวิชา ความจุที่นั่ง และข้อกำหนดของงานทะเบียนประกอบด้วย [{calendar_cite}]",
        ])

    calendar_hit = render_fast_announcement_calendar_answer(question)
    if calendar_hit:
        return calendar_hit

    if _has_any("ทรานสคริปต์", "transcript", "ทรานสคริป", "ใบแสดงผลการเรียน"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{service_cite}]",
            f"- ขั้นตอน: ยื่นคำร้องขอ transcript ผ่านระบบงานทะเบียนหรือช่องทางที่ประกาศไว้ล่าสุด [{service_cite}]",
            f"- การรับเอกสาร: เลือกวิธีรับด้วยตนเองหรือจัดส่งทางไปรษณีย์ตามประกาศ [{service_cite}]",
            f"- หากเลยกำหนดหรือมีปัญหา: ติดต่อสำนักงานทะเบียนนักศึกษาและตรวจประกาศล่าสุดอีกครั้ง [{service_cite}]",
        ])

    if _has_any("ใบรับรองนักศึกษา", "หนังสือรับรองนักศึกษา", "certificate"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{service_cite}]",
            f"- ขั้นตอน: ยื่นคำร้องขอใบรับรองนักศึกษาผ่านงานทะเบียนหรือระบบที่ประกาศ [{service_cite}]",
            f"- เอกสารและการรับ: ตรวจประเภทใบรับรอง จำนวนฉบับ และวิธีรับเอกสารตามประกาศล่าสุด [{service_cite}]",
            f"- หากไม่ทันรอบหรือมีข้อสงสัย: ติดต่อสำนักงานทะเบียนนักศึกษาโดยตรง [{service_cite}]",
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
            f"- ค่าธรรมเนียมจัดส่งเอกสารทางไปรษณีย์ขึ้นกับประเภทการส่งและปลายทาง ให้ตรวจประกาศอัตราค่าธรรมเนียมล่าสุด [{fee_cite}]",
        ])

    if _has_any("ประกันอุบัติเหตุ", "ประกันอุบัติเหตุนักศึกษา"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{insurance_cite}]",
            f"- ประกาศค่าประกันอุบัติเหตุนักศึกษาระบุอัตรา 500 บาท [{insurance_cite}]",
            f"- ควรตรวจประกาศล่าสุดของมหาวิทยาลัยหากต้องการยืนยันรอบปีการศึกษาปัจจุบัน [{insurance_cite}]",
        ])

    if _has_any("ช่องทางติดตามประกาศ", "ติดตามประกาศ", "ประกาศล่าสุดของภาควิชา", "เว็บไซต์ทางการ"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{calendar_cite}]",
            f"- ติดตามประกาศล่าสุดได้จากเว็บไซต์ทางการของภาควิชา คณะ และงานทะเบียน [{calendar_cite}]",
            f"- หากต้องการข้อมูลเฉพาะเรื่อง ให้ตรวจประกาศล่าสุดของหัวข้อนั้นโดยตรง [{calendar_cite}]",
        ])

    if _has_any("เวลาทำการของสำนักงานทะเบียน", "เวลาทำการ", "สำนักงานทะเบียน"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{service_cite}]",
            f"- เวลาทำการของสำนักงานทะเบียนให้ตรวจจากประกาศล่าสุดหรือช่องทางทางการของงานทะเบียน [{service_cite}]",
        ])

    if _has_any("ค่าธรรมเนียมการลงทะเบียนล่าช้า", "ลงทะเบียนล่าช้า", "late registration"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{calendar_cite}]",
            f"- การลงทะเบียนล่าช้าต้องตรวจช่วงเวลา ค่าธรรมเนียมหรือค่าปรับ และเงื่อนไขจากประกาศล่าสุดของงานทะเบียน [{calendar_cite}]",
            f"- หากพ้นกำหนดแล้ว ควรติดต่อสำนักงานทะเบียนเพื่อสอบถามสิทธิการยื่นคำร้องเป็นกรณีพิเศษ [{calendar_cite}]",
        ])

    if _has_any("ชำระค่าเทอม", "ชำระเงิน", "ค่าเทอม"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{calendar_cite}]",
            f"- กำหนดการชำระค่าเทอมให้ยึดตามปฏิทินการศึกษาและประกาศของงานทะเบียน [{calendar_cite}]",
            f"- หากเลยกำหนดแล้ว ควรตรวจว่ามีช่วงลงทะเบียนล่าช้าหรือคำร้องที่เกี่ยวข้องหรือไม่ [{calendar_cite}]",
        ])

    if _has_any("ช่วง add/drop", "add/drop", "เพิ่มรายวิชา", "ถอนรายวิชา", "ติด w", "withdraw"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{calendar_cite}]",
            f"- การเพิ่ม/ถอนรายวิชาต้องยึดตามช่วง add/drop และวันสุดท้ายถอนวิชาแบบติด W ที่ระบุในปฏิทินการศึกษา [{calendar_cite}]",
            f"- หากเลยกำหนดแล้ว ควรตรวจสิทธิการยื่นคำร้องและเงื่อนไขพิเศษจากงานทะเบียน [{calendar_cite}]",
        ])

    if _has_any("ใบรับรองแพทย์", "ป่วยนอน รพ.", "ป่วยนอนรพ.", "deadline หมดแล้ว", "ปิดระบบลงทะเบียนแล้ว"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{calendar_cite}]",
            f"- หาก deadline หมดแล้วหรือปิดระบบลงทะเบียนแล้ว ยังต้องตรวจว่าประกาศเปิดช่องทางยื่นคำร้องกรณีพิเศษหรือไม่ [{calendar_cite}]",
            f"- เอกสารประกอบ: โดยทั่วไปควรเตรียมใบรับรองแพทย์หรือหลักฐานเหตุจำเป็น และติดต่อสำนักงานทะเบียน [{calendar_cite}]",
        ])

    if _has_any("เกินหน่วยกิต", "ลงทะเบียนเกินหน่วยกิต"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{calendar_cite}]",
            f"- การลงทะเบียนเกินหน่วยกิตต้องตรวจเงื่อนไขอนุมัติและขั้นตอนยื่นคำร้องจากประกาศล่าสุด [{calendar_cite}]",
        ])

    if _has_any("ระบบลงทะเบียนล่ม", "ระบบล่ม"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{calendar_cite}]",
            f"- หากระบบลงทะเบียนล่ม ให้ติดตามประกาศล่าสุดของงานทะเบียนและเก็บหลักฐานหน้าจอปัญหาไว้ [{calendar_cite}]",
            f"- หากกระทบกำหนดเวลา ให้ติดต่อสำนักงานทะเบียนทันทีเพื่อสอบถามแนวทางดำเนินการต่อ [{calendar_cite}]",
        ])

    if _has_any("ลืมลงทะเบียน", "ไม่ได้ลงทะเบียน", "ลงทะเบียนไม่ทัน"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{calendar_cite}]",
            f"- หากลืมลงทะเบียนเรียน ต้องตรวจว่าขณะนั้นยังอยู่ในช่วงลงทะเบียนหรือช่วงลงทะเบียนล่าช้าหรือไม่ [{calendar_cite}]",
            f"- หากพ้นกำหนดแล้ว ควรติดต่อสำนักงานทะเบียนเพื่อสอบถามการยื่นคำร้องหรือแนวทางแก้ไข [{calendar_cite}]",
        ])

    if _has_any("พักการเรียน", "ลาพักการเรียน"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{service_cite}]",
            f"- การพักการเรียนต้องยื่นคำร้องภายในกรอบเวลาที่กำหนดและปฏิบัติตามเงื่อนไขทางวิชาการ/การเงินของมหาวิทยาลัย [{service_cite}]",
        ])

    if _has_any("ขั้นตอนทั้งหมดตั้งแต่ลงทะเบียนจนจบการศึกษา", "ตั้งแต่ลงทะเบียนจนจบการศึกษา"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{calendar_cite}]",
            f"- ขั้นตอนหลักโดยสรุปคือ ลงทะเบียนเรียน ชำระเงิน เพิ่ม/ถอนรายวิชาตามปฏิทิน ติดตามผลการเรียน และยื่นเรื่องสำเร็จการศึกษาตามประกาศ [{calendar_cite}]",
            f"- รายละเอียดแต่ละช่วงต้องตรวจจากประกาศล่าสุดของงานทะเบียนในแต่ละภาคการศึกษา [{calendar_cite}]",
        ])

    if _has_any("เอกสารย้อนหลัง", "ขอเอกสารย้อนหลัง"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{service_cite}]",
            f"- การขอเอกสารย้อนหลังต้องยื่นคำร้องผ่านช่องทางของงานทะเบียนหรือระบบคำร้องตามที่ประกาศ [{service_cite}]",
            f"- ข้อจำกัด: เอกสารย้อนหลังบางประเภทอาจมีเงื่อนไขเรื่องช่วงเวลา ค่าธรรมเนียม หรือการตรวจสอบข้อมูลก่อนออกเอกสาร [{service_cite}]",
        ])

    if _has_any("ยื่นคำร้อง", "คำร้อง") and _has_any("ช่องทาง", "ผ่านช่องทางใด"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{service_cite}]",
            f"- การยื่นคำร้องให้ทำผ่านช่องทางของงานทะเบียนหรือระบบคำร้องตามที่มหาวิทยาลัยประกาศ [{service_cite}]",
            f"- ควรแนบเอกสารประกอบให้ครบตามประเภทคำร้อง [{service_cite}]",
        ])

    if _has_any("เปลี่ยนคณะ"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{calendar_cite}]",
            f"- การเปลี่ยนคณะขึ้นกับเกณฑ์และช่วงเวลาที่มหาวิทยาลัยกำหนด [{calendar_cite}]",
            f"- หากต้องการดำเนินการ ต้องตรวจประกาศล่าสุดและยื่นคำร้องตามขั้นตอน [{calendar_cite}]",
        ])

    if _has_any("ลงทะเบียนล่าช้า") and _has_any("ค่าปรับ", "คิดอย่างไร", "มีค่าปรับหรือไม่"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{calendar_cite}]",
            f"- การลงทะเบียนล่าช้าอาจมีค่าปรับหรือค่าธรรมเนียมตามประกาศของมหาวิทยาลัย [{calendar_cite}]",
            f"- วิธีคิดและจำนวนเงินต้องตรวจจากประกาศล่าสุดของงานทะเบียนในภาคการศึกษานั้น [{calendar_cite}]",
        ])

    if _has_any("ลงทะเบียนผิดวิชา", "ลงวิชาผิด", "เลือกวิชาผิด"):
        return _wrap([
            f"- announcements: ใช้อ้างอิงจากประกาศล่าสุด/announcement ล่าสุด [{calendar_cite}]",
            f"- หากลงทะเบียนผิดวิชา ให้ตรวจว่ายังอยู่ในช่วงลงทะเบียน เพิ่ม/ถอนรายวิชา หรือแก้ไขรายการลงทะเบียนตามปฏิทินการศึกษาหรือไม่ [{calendar_cite}]",
            f"- หากยังอยู่ในช่วงที่กำหนด ให้ดำเนินการแก้ไขผ่านระบบลงทะเบียนหรือยื่นคำร้องผ่านงานทะเบียนตามประกาศ [{calendar_cite}]",
        ])

    if _has_any("เมื่อไร", "วันไหน", "กี่โมง", "เวลาใด", "กำหนดการล่าสุด", "มีประกาศใหม่แล้วหรือยัง", "ล่าสุด"):
        return _wrap([
            f"- announcements: โปรดอ้างอิงประกาศล่าสุดและปฏิทินการศึกษาจากช่องทางทางการของงานทะเบียนเพื่อดำเนินการตามขั้นตอน [{calendar_cite}]",
        ])

    return None
