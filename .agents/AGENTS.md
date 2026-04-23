# AGENTS Workspace Rules

เอกสารนี้คือกติกากลางที่ AI ทุกตัวต้องอ่านก่อนเริ่มทำงานใน repo นี้

## เป้าหมาย
- แก้ปัญหาให้จบครบวงจรในรอบเดียวเมื่อทำได้
- เปลี่ยนให้น้อยที่สุดเท่าที่จำเป็น และไม่แตะส่วนที่ไม่เกี่ยวข้อง
- เน้นความถูกต้องของระบบ RAG, ingestion และ evaluation gate เป็นหลัก

## ลำดับการอ่านก่อนลงมือ
1. README.md
2. README_DOMAINS.md
3. EVAL_GUIDE.md
4. DEPLOYMENT_GUIDE.md
5. Makefile

## Working Rules
- อ่าน requirement ให้ครบก่อนแก้ไฟล์
- ก่อนแก้โค้ด ให้หาไฟล์ที่เกี่ยวข้องและอ่าน context รอบจุดแก้
- หลังแก้ ให้รันการตรวจสอบที่เล็กและตรงจุดก่อนเสมอ
- ห้าม revert การเปลี่ยนแปลงที่ผู้ใช้ทำไว้แล้วถ้าไม่ได้สั่ง
- ถ้าเจอความเสี่ยงต่อพฤติกรรมเดิม ให้ระบุเป็น finding ชัดเจน

## Validation Defaults
- Python changes: รัน test/unit ที่เกี่ยวข้องอย่างน้อย 1 ชุด
- Retrieval/RAG changes: รัน smoke query หรือ eval ชุดย่อย
- Script/CLI changes: รันทดสอบคำสั่งตัวอย่าง 1 ครั้ง

## .agents Contract
- อัปเดต active.md ทุกครั้งเมื่อเริ่ม/จบงาน
- เก็บ checkpoint เป็นรายรอบใน sessions/
- เก็บโน้ตข้ามงานหรือเชิงสถาปัตย์ใน topics/
- ห้าม commit เนื้อหาใน private/
- อัปเดต index/repo-tree.md เมื่อโครงสร้าง repo เปลี่ยนอย่างมีนัยสำคัญ

## Communication Style
- สรุปสั้น ชัดเจน วัดผลได้
- ระบุไฟล์ที่แก้และผลตรวจสอบเสมอ
- ถ้าติด blocker ให้ระบุทางเลือกถัดไป 1-3 ทาง
