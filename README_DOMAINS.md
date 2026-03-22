# Domain-separated RAG (announcements / regulations / curriculum)

## Folders
- `data/announcements` → RAG แบบ vector (ธรรมดา)
- `data/regulations` → RAG แบบ vector (ธรรมดา)
- `data/curriculum` → Hybrid RAG (vector + Neo4j graph expansion)

Indexes are stored under:
- `indexes/<domain>/vector/chroma`
- `indexes/<domain>/vector/sqlite/ingestion.db`
- `indexes/curriculum/graph` (Neo4j is external; this folder is kept for local graph artifacts if needed)

## Ingest (สร้างดัชนี)
ใช้ PowerShell:
- `./scripts/ingest_domain.ps1 -Domain announcements -Input data/announcements`
- `./scripts/ingest_domain.ps1 -Domain regulations -Input data/regulations`
- `./scripts/ingest_domain.ps1 -Domain curriculum -Input data/curriculum`

หรือรันรวดเดียวทุกโดเมน (ข้ามโดเมนที่ไม่มีไฟล์):
- `./scripts/ingest_all_domains.ps1`

> Curriculum ingestion จะพยายาม upsert graph เข้า Neo4j แบบ best-effort ถ้าตั้งค่า `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD` ไว้

ถ้าต้องการรัน upsert กราฟซ้ำ (แนะนำให้ใช้ SQLite เป็นแหล่งข้อมูล):
- `C:/Users/KritChaJ/CPE-CHAT-0.0.2/.venv/Scripts/python.exe services/ingestion-service/scripts/upsert_graph_from_sqlite.py --domain curriculum`

## Query (ผ่าน API)
รัน RAG service:
- `./scripts/run_rag_service.ps1`

เรียก API:
- POST `/rag/query` body: `{ "question": "...", "domain": "announcements" }`
- POST `/rag/query` body: `{ "question": "...", "domain": "regulations" }`
- POST `/rag/query` body: `{ "question": "...", "domain": "curriculum" }`

Notes:
- announcements/regulations → vector+keyword (SQLite FTS) + RRF merge
- curriculum → vector+keyword (SQLite FTS) + Neo4j graph expansion (ถ้ามี course code ในคำถาม)

## Regression Gate ก่อน Merge

มี regression set ถาวรสำหรับ merge gate อยู่ที่:
- `scripts/regression_gate_50.csv`

แบ่งหมวดครบ 5 กลุ่ม:
- curriculum_fact_lookup
- prerequisite_course_code
- regulations_clause_query
- multi_doc_multi_intent
- announcement_schedule

รัน gate แบบ local (ต้องมี rag-service ทำงานที่ `http://127.0.0.1:8001`):
- `bash scripts/run_regression_gate.sh`

ค่า gate เริ่มต้น:
- exactness >= 0.70
- citation_validity >= 0.90
- latency p95 <= 12000 ms
- แต่ละกลุ่มต้องมีอย่างน้อย 8 เคส

ปรับ threshold ได้ผ่าน environment variables:
- `GATE_MIN_EXACTNESS`
- `GATE_MIN_CITATION_VALIDITY`
- `GATE_MAX_LATENCY_P95`
- `GATE_MIN_CASES_PER_GROUP`

ใน CI มี workflow:
- `.github/workflows/regression-gate.yml`

ตัว eval (`scripts/eval_testqa_csv_live_v2.py`) รองรับ gate flags โดยตรง และจะ exit code = 2 เมื่อไม่ผ่านเกณฑ์
