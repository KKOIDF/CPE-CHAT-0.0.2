# QA Dataset v2 (CPE Chat) — แนวทางออกแบบคำถามให้หลากหลาย + Metrics

เอกสารนี้ตั้งใจให้ทีมใช้ “ออกแบบชุดคำถาม” เพื่อวัด RAG ให้ครบหลายระดับ ไม่ใช่แค่วัดคำตอบตายตัว

## 1) Taxonomy: ระดับ/ชนิดคำถามที่ควรมี

> เป้าหมาย: ครอบคลุมทั้ง *ตอบได้จากเอกสาร*, *ตอบไม่ได้*, *กำกวมต้องถามกลับ*, และ *คำถามหลอก/ตั้งใจทำให้พลาด*

### A. Answerable (มีคำตอบในฐานข้อมูล/เอกสาร)
1) **Exact fact**: ข้อ/เงื่อนไข/จำนวนเงิน/วัน/เส้นตาย (ตอบสั้น แม่น)
2) **Paraphrase**: ถามแบบภาษาพูด/ย่อ/สลับคำ แต่ความหมายเดิม
3) **Numeric extraction**: ตัวเลขจากตาราง/หลายบรรทัด (ปี, บาท, จำนวนครั้ง, สัปดาห์)
4) **Constraint / condition**: “ถ้า…ต้อง…/ยกเว้นกรณี…”
5) **Multi-hop (within doc)**: ต้องรวม 2–3 ส่วนในเอกสารเดียว
6) **Compare & contrast**: “ต่างกันอย่างไร” ระหว่าง 2 กระบวนการ/2 ประกาศ
7) **Temporal compare**: ปี/ฉบับ A vs B ต่างกันอะไร (เปลี่ยนเงื่อนไข/ตัวเลข)
8) **List synthesis**: “มีอะไรบ้าง” แต่ในเอกสารกระจายหลายช่วง
9) **Cross-domain but answerable**: คำถามโยง 2 โดเมน แต่ยังมีข้อมูลรองรับ

### B. Unanswerable (ไม่มีคำตอบในเอกสาร) — ใช้วัด Hallucination/Abstention
1) **Missing detail**: ถาม “เลขที่ประกาศ/ปี/หน่วยงาน” ที่เอกสารไม่ได้ระบุ
2) **Over-specific**: ถามชื่อบุคคล/อีเมล/ห้อง/สถานที่สอบ ที่ไม่มีในเอกสาร
3) **Out-of-scope**: คำถามนอกขอบเขตโดเมนทั้งหมด
4) **Counterfactual**: ตั้งสมมติฐานที่เอกสารไม่พูดถึง (“ถ้าสอบซ้อนเกิน 2 วิชา…”) 

### C. Ambiguous (กำกวม) — ต้องถามกลับ (Clarification)
1) **Underspecified entity**: ไม่ระบุปีการศึกษา/หลักสูตร/รหัสวิชาเต็ม (เช่น “LNGxxx”)
2) **Multi-intent**: ถาม 2 เรื่องในประโยคเดียว
3) **Term ambiguity**: ใช้คำที่ตีความได้หลายแบบ (เช่น “รหัสวิชา” vs “section”)

### D. Adversarial / Trap (คำถามหลอก)
1) **Wrong premise**: ใส่ข้อเท็จจริงผิดในคำถาม แล้วดูว่าระบบ “แก้” หรือ “เชื่อตาม”
2) **Leading question**: บีบให้ตอบยืนยัน (“สรุปคือ…ใช่ไหม”) ทั้งที่เอกสารไม่ยืนยัน
3) **Instruction injection**: สั่งให้ข้ามบริบท/แต่งคำตอบ/ให้คำตอบมั่นใจ 100%

## 2) พฤติกรรมที่คาดหวัง (Expected behavior)

กำหนดต่อเคสว่าควรเป็นหนึ่งในนี้:
- **ANSWER**: ตอบตรงจากเอกสาร
- **ABSTAIN**: ตอบว่าไม่พบข้อมูลในเอกสาร (หรือระบุชัดว่าเอกสารไม่ยืนยัน)
- **CLARIFY**: ถามกลับเพื่อขอรายละเอียดเพิ่มก่อนตอบ

คำแนะนำสำหรับ Unanswerable:
- ไม่ควร “เดา” หรือเติมรายละเอียดเฉพาะเจาะจง
- ควรตอบ ABSTAIN และถ้าเป็นไปได้ ชี้ว่าขาดข้อมูลส่วนไหน

## 3) Metrics ที่ควรเก็บเพิ่ม

### Core
- **Answer accuracy** (เฉพาะเคส ANSWER): similarity/keyword overlap/ตัวเลขสำคัญตรงกัน
- **Abstention accuracy** (เฉพาะเคส ABSTAIN): ไม่ตอบมั่วเมื่อไม่มีข้อมูล
- **Clarification rate** (เฉพาะเคส CLARIFY): ถามกลับถูกจุด ไม่ถามมั่ว

### Hallucination
- **Hallucination rate (Unanswerable)**: สัดส่วนเคสที่ควร ABSTAIN แต่ระบบกลับ “ให้คำตอบเชิงข้อเท็จจริง”
- **Unsupported claim rate (Answerable)**: ในเคส ANSWER แต่มีรายละเอียดที่ไม่ควรมี (เช่น ตัวเลข/ปี/ชื่อหน่วยงานที่ไม่มี)

### Retrieval / Evidence
- **Reference-hint hit rate**: ถ้ามี “(อ้างอิง: X)” ในคำถาม แหล่งที่ดึงมามี X ใน top-k ไหม
- **Cross-doc contamination**: เคสที่คำถามกำหนดเอกสาร แต่ไปตอบจากเอกสารอื่น

### Calibration (ความมั่นใจ)
> ต้องมี “confidence” ต่อเคส (0–1) เพื่อคำนวณจริงจัง
- **Brier score**: วัดความแม่นของความมั่นใจ
- **ECE (Expected Calibration Error)**: วัดการ over/under-confident
- **Selective accuracy / risk-coverage**: ถ้าตั้ง policy ว่า ตอบเฉพาะ confidence ≥ t จะได้ความแม่นเท่าไร

หมายเหตุ: ถ้า production ไม่อยากโชว์ confidence ให้ทำใน “eval mode” หรือทำ pass ที่สอง (LLM-judge) เพื่อให้คะแนน confidence เฉพาะงานประเมิน

## 4) โครง CSV แนะนำ (สำหรับ v2)

ดูไฟล์ template: `scripts/testqa_v2_template.csv`

คอลัมน์หลักที่ช่วยให้วัดได้ครบ:
- `id`, `domain`, `question`
- `expected_behavior` = ANSWER | ABSTAIN | CLARIFY
- `expect_answerable` = true/false (สำหรับคำนวณ hallucination/false-negative)
- `expected_answer` (ใส่เมื่อ expected_behavior=ANSWER)
- `reference_hint` (optional: ชื่อไฟล์/เอกสารที่ควรยึด)
- `tags` (เช่น exact_fact, multi_hop, trap_wrong_premise)

## 5) ตัวอย่างไอเดียคำถาม (ยกตัวอย่างรูปแบบ ไม่ผูกกับเอกสารจริง)

- Exact fact: “ต้องยื่นคำร้องภายในกี่สัปดาห์แรกของภาคการศึกษา?”
- Multi-hop: “ขั้นตอนสอบซ้อน + ใครต้องลงนามบ้าง (สรุปเป็นลำดับ)”
- Wrong premise: “สอบซ้อนได้ไม่จำกัดจำนวนวิชาใช่ไหม?”
- Unanswerable detail: “ประกาศฉบับนี้มีเลขที่ประกาศอะไร?” (ถ้าเอกสารไม่ระบุ)
- Ambiguous: “รหัสวิชาภาษาเลือกมีอะไรบ้าง” (ไม่ระบุปี/หลักสูตร/ระดับ)

