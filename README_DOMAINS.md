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
