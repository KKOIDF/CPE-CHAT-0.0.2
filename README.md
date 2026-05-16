# CPE-CHAT 0.0.2

ระบบถามตอบข้อมูลภาควิชา/มหาวิทยาลัยแบบ RAG สำหรับงานเอกสารหลายโดเมน โดยตอนนี้ในรีโปมีโดเมนหลัก 3 ส่วน:

- `announcements`
- `regulations`
- `curriculum`

โปรเจกต์นี้แยกงานเป็น 2 ส่วนหลัก:

- `rag-service` สำหรับรับคำถาม ค้นข้อมูล และตอบผ่าน API
- `ingestion-service` สำหรับแปลงเอกสารและสร้างดัชนีที่ใช้ค้น

หน้าเว็บคุยกับระบบใช้งานผ่าน OpenWebUI และ backend เปิด endpoint แบบ OpenAI-compatible ไว้ที่ `/v1`

## สิ่งที่มีในเวอร์ชันปัจจุบัน

- ค้นแบบ hybrid: vector + SQLite FTS
- รองรับหลายโดเมนในระบบเดียว
- มี deterministic path สำหรับคำถามบางประเภทเพื่อลดคำตอบเพี้ยน
- เปิดใช้ผ่าน OpenWebUI ได้
- มีชุด eval, baseline compare และ regression gate
- มี MLflow สำหรับ observability
- มี Redis สำหรับเก็บ session follow-up
- รองรับ LLM หลายแบบ เช่น `ollama`, `typhoon`, `openai`

## โครงสร้างระบบ

บริการหลักใน `docker-compose.yml` ตอนนี้มี 4 ตัว:

- `rag-service` ที่พอร์ต `8001`
- `openweb-ui` ที่พอร์ต `3000`
- `mlflow` ที่พอร์ต `5000`
- `redis` ที่พอร์ต `6379`

เส้นทางหลักของข้อมูล:

1. ผู้ใช้ส่งคำถามจาก OpenWebUI
2. OpenWebUI เรียก `rag-service` ผ่าน `/v1/chat/completions`
3. `rag-service` ดึงข้อมูลจากดัชนีใน `indexes/`
4. ระบบส่งคำตอบกลับพร้อม citation ตาม endpoint ที่เรียก

## เริ่มใช้งานแบบ Docker

### 1. เตรียม environment

```bash
cp .env.example .env
```

ค่าขั้นต่ำที่ควรตั้งใน `.env`:

```env
RAG_PORT=8001
OPENWEB_UI_PORT=3000

LLM_PROVIDER=ollama
LLM_MODEL=gemma4:26b
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_API_KEY=

LLM_AUX_PROVIDER=typhoon
LLM_AUX_MODEL=typhoon-v2.5-30b-a3b-instruct
LLM_AUX_FALLBACK_FOR_ANSWER=1
TYPHOON_API_KEY=your_typhoon_api_key_here
```

ถ้าจะใช้ `typhoon` เป็นโมเดลหลัก ให้สลับเป็น:

```env
LLM_PROVIDER=typhoon
LLM_MODEL=typhoon-v2.5-30b-a3b-instruct
TYPHOON_API_KEY=your_typhoon_api_key_here
```

หมายเหตุ:

- ค่าใน `.env.example` เป็นค่าที่อัปเดตตามสแตกปัจจุบันของรีโป
- ฝั่ง Docker รองรับทั้ง `ollama` เป็นตัวหลักและ `typhoon` เป็น fallback

### 2. เตรียมดัชนี

ต้องมีข้อมูลในโฟลเดอร์ `indexes/` ก่อนเปิดระบบ ถ้ายังไม่มีให้รัน ingestion ก่อน

```bash
make ingest
```

ถ้าจะส่งงาน ingestion ไปเครื่อง GPU:

```bash
make ingest-gpu GPU_HOST=user@remote-host
```

รายละเอียดเพิ่มดูที่ [GPU_INGEST_GUIDE.md](/home/testuser/CPE-CHAT-0.0.2/GPU_INGEST_GUIDE.md)

### 3. เปิดระบบ

```bash
docker-compose up -d
```

### 4. ตรวจสถานะ

```bash
docker-compose ps
docker-compose logs rag-service --tail=100
curl http://localhost:8001/health
```

### 5. เข้าใช้งาน

- OpenWebUI: `http://localhost:3000`
- RAG health: `http://localhost:8001/health`
- MLflow: `http://localhost:5000`

หยุดระบบ:

```bash
docker-compose down
```

## รันเฉพาะ backend แบบ local

เหมาะกับงานพัฒนา `rag-service` อย่างเดียว

```bash
./start_rag_service.sh
```

หรือ:

```bash
make run-server
```

ข้อควรรู้:

- สคริปต์ [start_rag_service.sh](/home/testuser/CPE-CHAT-0.0.2/start_rag_service.sh) ตั้ง `LLM_PROVIDER=typhoon` เป็นค่าเริ่มต้น
- ถ้ามีไฟล์ `.env` สคริปต์จะพยายามโหลด `LLM_MODEL` และ `TYPHOON_API_KEY` ให้
- ถ้าจะใช้ provider อื่นแบบ local ควร export ค่า env เองก่อนรัน

## Ingestion

คำสั่งหลัก:

```bash
make ingest
```

สคริปต์ที่เรียกจริงคือ [scripts/ingest_all_domains.sh](/home/testuser/CPE-CHAT-0.0.2/scripts/ingest_all_domains.sh)

ไฟล์ต้นทางที่ระบบใช้อ่านโดยทั่วไปอยู่ใน:

- `data/raw/announcements`
- `data/raw/regulations`
- `data/raw/curriculum`

ผลลัพธ์หลักที่ใช้ตอน runtime จะอยู่ใน:

- `indexes/<domain>/vector/chroma`
- `indexes/<domain>/vector/sqlite/ingestion.db`
- `indexes/global/chroma`
- `indexes/global/sqlite/ingestion.db`

RAG flow แบบ global cross-domain และ source-labeled context ดูเพิ่มที่ [docs/RAG_OPEN_NOTEBOOK_STYLE.md](/home/testuser/CPE-CHAT-0.0.2/docs/RAG_OPEN_NOTEBOOK_STYLE.md)

## Evaluation และ gate

คำสั่งที่ใช้บ่อย:

```bash
make eval-regression
make eval-qball
make eval-qball-gate
make eval-canary-guard
make eval-domain-monitor
make eval-week3-gates
```

เอกสารเพิ่ม:

- [EVAL_GUIDE.md](/home/testuser/CPE-CHAT-0.0.2/EVAL_GUIDE.md)
- [docs/system_reference.md](/home/testuser/CPE-CHAT-0.0.2/docs/system_reference.md)

## API ที่ใช้บ่อย

### Health check

```bash
curl http://localhost:8001/health
```

### Query แบบ retrieval

```bash
curl -X POST http://localhost:8001/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "หลักสูตรต้องมีหน่วยกิตกี่หน่วย",
    "domain": "curriculum"
  }'
```

### Answer สำหรับ backend อื่น

```bash
curl -X POST http://localhost:8001/rag/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "อาจารย์ผู้รับผิดชอบวิชา CPE101 มีใครบ้าง",
    "domain": "curriculum"
  }'
```

### OpenAI-compatible endpoint

```bash
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma4:26b",
    "messages": [
      {"role": "user", "content": "หลักสูตรต้องมีหน่วยกิตกี่หน่วย"}
    ]
  }'
```

endpoint ที่มีตอนนี้:

- `POST /rag/query`
- `POST /rag/answer`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `GET /health`
- `GET /debug/config` เมื่อเปิด `RAG_EXPOSE_CONFIG=1`

## ไฟล์ที่ควรรู้

- [docker-compose.yml](/home/testuser/CPE-CHAT-0.0.2/docker-compose.yml) สแตกหลักตอนรันจริง
- [Makefile](/home/testuser/CPE-CHAT-0.0.2/Makefile) รวมคำสั่งใช้งานบ่อย
- [services/rag-service](/home/testuser/CPE-CHAT-0.0.2/services/rag-service) โค้ดของ backend
- [services/ingestion-service](/home/testuser/CPE-CHAT-0.0.2/services/ingestion-service) โค้ดของ ingestion pipeline
- [README_DOMAINS.md](/home/testuser/CPE-CHAT-0.0.2/README_DOMAINS.md) รายละเอียดรายโดเมน
- [DEPLOYMENT_GUIDE.md](/home/testuser/CPE-CHAT-0.0.2/DEPLOYMENT_GUIDE.md) คู่มือ deploy เพิ่มเติม

## ปัญหาที่เจอบ่อย

- `rag-service` ไม่ขึ้น
  - เช็ก `.env` ว่าตั้ง `LLM_PROVIDER` และ key ที่เกี่ยวข้องครบ
  - เช็กว่ามีดัชนีใน `indexes/`
  - ดู log ด้วย `docker-compose logs rag-service`

- OpenWebUI เรียก RAG ไม่ได้
  - เช็ก `http://localhost:8001/health`
  - เช็กว่า `rag-service` ผ่าน healthcheck แล้ว
  - เช็กพอร์ตใน `docker-compose.yml`

- คำตอบของบางโดเมนไม่ขึ้น
  - เช็กว่ามีข้อมูลใน `indexes/<domain>/...`
  - รัน ingestion ใหม่

## หมายเหตุ

- ไฟล์ใน `indexes/`, `chroma/`, `data/db/` และไฟล์ที่ generate ระหว่าง eval มีขนาดใหญ่ ควรระวังเรื่องการ commit
- ถ้าจะปรับค่า retrieval หรือ routing ให้เริ่มจาก `.env.example` เพราะตอนนี้รวมตัวแปรหลักไว้ค่อนข้างครบแล้ว
