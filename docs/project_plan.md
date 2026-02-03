# แผนงาน Chatbot ภาควิชา (ประกาศ / ระเบียบ / โครงสร้างรายวิชา)

## สถานะปัจจุบันจากโค้ด
- มีโครงสร้าง RAG แยกโดเมน 3 หมวด และระบุวิธี ingest/query ไว้แล้ว (announcements, regulations, curriculum). 
- Backend ฝั่ง RAG มี API `/rag/query` และ `/rag/answer` พร้อมการบังคับอ้างอิงในคำตอบ (citations guardrails).
- Frontend ปัจจุบันเรียก API `/chat` และ `/upload-pdf` ซึ่งยังไม่ตรงกับ endpoint ของ RAG service.

## ช่องว่างที่ต้องแก้ไข (สิ่งที่ควรทำต่อทันที)
1. **เชื่อมต่อ Frontend กับ Backend ให้ตรงกัน**
   - เปลี่ยนจาก `/chat` ไปเป็น `/rag/answer` (และส่ง `domain`).
   - เพิ่มตัวเลือกหมวด (ประกาศ/ระเบียบ/โครงสร้างรายวิชา) ใน UI.
2. **ตรวจสอบ data/indexes สำหรับทั้ง 3 หมวด**
   - Ensure `indexes/<domain>/vector/...` มีข้อมูลครบเพื่อให้ตอบได้ตามหมวด.
3. **เตรียม Deploy บน server มหาวิทยาลัย**
   - สคริปต์/เอกสารสำหรับการตั้งค่า env เช่น `CPE_INDEX_ROOT`, `CPE_DOMAIN`.
   - จัดทำ Health check และ monitoring ขั้นต่ำ.
4. **Prototype ภายใน 4 อาทิตย์**
   - สรุป prototype scope: ตอบคำถาม 3 หมวดด้วย citations, หน้าเว็บใช้งานได้, deploy บน server.

## แบ่งงาน 4 คน (3 สายงานหลัก + ผู้ประสาน/QA)
- **Model (1 คน)**
  - โฟกัส ingest/embedding/การปรับคุณภาพการค้นคืน (RAG) และชุดทดสอบ Q&A.
- **Backend (1 คน)**
  - API, CORS/auth, logging, deploy script, health checks.
- **Frontend (1 คน)**
  - UI/UX, domain selector, call `/rag/answer`, history.
- **Integration/QA/PM (1 คน)**
  - รวมงาน, ทดสอบ end-to-end, เช็ค deploy, เก็บ feedback ผู้ใช้.

## Timeline 4 สัปดาห์ (เสนอ)
### สัปดาห์ที่ 1 — Baseline & Alignment
- Model: ทำ ingest ครบ 3 หมวด + verify index structure.
- Backend: ยืนยัน API `/rag/answer` พร้อมใช้งาน, CORS สำหรับ frontend.
- Frontend: ปรับ endpoint ให้ตรง, เพิ่ม dropdown หมวด, แสดง citation.
- QA/PM: ทำ checklist prototype + test plan.

### สัปดาห์ที่ 2 — Prototype Feature Complete
- Model: สร้างชุดคำถามทดสอบแต่ละหมวด + วัดคุณภาพคำตอบ.
- Backend: เพิ่ม logging/metrics พื้นฐาน, error handling.
- Frontend: ปรับ UI สรุปคำตอบเป็น bullet ตาม requirement.
- QA/PM: end-to-end test รอบแรก, บันทึกปัญหา.

### สัปดาห์ที่ 3 — Harden & Deploy Readiness
- Model: ปรับ prompt/guardrail ตามปัญหาจริง.
- Backend: เตรียม config สำหรับ server มหาวิทยาลัย + document deploy.
- Frontend: รองรับ loading/error state, polish UI.
- QA/PM: ทดลอง deploy บน staging หรือ server จริง.

### สัปดาห์ที่ 4 — Prototype Freeze & Hand-off
- Model: Final tuning + freeze dataset.
- Backend: deploy production + backup instructions.
- Frontend: finalize UI, bug fixes.
- QA/PM: ทำรายงานสรุป, demo, ส่งมอบ.

## นิยาม Prototype ที่ต้องเสร็จภายใน 4 อาทิตย์
- ระบบตอบคำถามได้ครบ 3 หมวด (ประกาศ/ระเบียบ/โครงสร้างรายวิชา).
- คำตอบมี citations ถูกต้อง.
- UI ใช้งานได้จริงและเชื่อมกับ backend.
- Deploy สำเร็จบน server มหาวิทยาลัย.
