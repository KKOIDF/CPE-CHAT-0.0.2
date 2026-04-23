# CPE-CHAT 0.0.2

ระบบแชตบอท RAG สำหรับงานข้อมูลภาควิชา/มหาวิทยาลัย โดยรองรับการสืบค้นหลายโดเมน เช่น announcements, regulations และ curriculum พร้อมเชื่อมต่อ LLM ผ่าน Typhoon API หรือ Ollama และใช้งานผ่าน OpenWeb-UI ได้

## Features

- Multi-domain RAG: announcements, regulations, curriculum
- Hybrid retrieval: vector + keyword (SQLite FTS)
- OpenAI-compatible API ผ่าน RAG service
- ใช้งานผ่าน OpenWeb-UI ได้ทันที
- มีชุด evaluation และ regression gate สำหรับเช็กคุณภาพก่อน deploy
- รองรับ ingestion ทั้ง local และ offload ไป GPU host

## Architecture

บริการหลักใน docker-compose:

- rag-service: FastAPI backend + retrieval + Typhoon/Ollama LLM integration
- openweb-ui: web chat interface
- mlflow: tracking/observability (optional แต่เปิดไว้โดยค่าเริ่มต้น)

พอร์ตค่าเริ่มต้น:

- RAG API: 8001
- OpenWeb-UI: 3000
- MLflow: 5000

## Quick Start (Docker Compose)

1. เตรียมไฟล์ environment

```bash
cp .env.example .env
```

2. ตั้งค่าอย่างน้อยในไฟล์ `.env`

```env
LLM_PROVIDER=typhoon
LLM_MODEL=typhoon-v2.5-30b-a3b-instruct
TYPHOON_API_KEY=your_real_api_key
RAG_PORT=8001
OPENWEB_UI_PORT=3000
```

ตัวอย่างสำหรับ Ollama บน GPU host:

```env
LLM_PROVIDER=ollama
LLM_MODEL=gemma4:26b
OLLAMA_BASE_URL=http://gpu06.slurm.cpe.kmutt.ac.th:11434
OLLAMA_API_KEY=sk-ollama-dummy
RAG_PORT=8001
OPENWEB_UI_PORT=3000
```

ตัวอย่างที่แนะนำสำหรับใช้งานสองโมเดลพร้อมกัน:

```env
LLM_PROVIDER=typhoon
LLM_MODEL=typhoon-v2.5-30b-a3b-instruct
LLM_AUX_PROVIDER=ollama
LLM_AUX_MODEL=gemma4:26b
OLLAMA_BASE_URL=http://gpu06.slurm.cpe.kmutt.ac.th:11434
OLLAMA_API_KEY=sk-ollama-dummy
OLLAMA_THINK=0
```

แนวทางนี้ให้ Typhoon เป็นโมเดลหลักสำหรับคำตอบสุดท้าย และให้ Ollama ช่วยงาน rewrite/routing/multi-query รวมถึงรับช่วง fallback เวลาตัวหลักมีปัญหา

3. ตรวจว่ามีดัชนีแล้วในโฟลเดอร์ `indexes/`

- ถ้ายังไม่มี ให้รัน ingestion ก่อน (ดูหัวข้อ Ingestion)

4. สตาร์ตระบบ

```bash
docker-compose up -d
```

5. ตรวจสถานะ

```bash
docker-compose ps
docker-compose logs rag-service --tail=100
curl http://localhost:8001/health
```

6. เปิดใช้งาน

- OpenWeb-UI: http://localhost:3000
- RAG health: http://localhost:8001/health

หยุดระบบ:

```bash
docker-compose down
```

## Quick Start (Local RAG Service)

เหมาะกับการพัฒนาเฉพาะ backend โดยไม่เปิด OpenWeb-UI ใน Docker

1. เปิด virtual environment (ถ้ามี)

```bash
source venv/bin/activate
```

2. ตั้งค่า `.env` ให้ตรงกับ provider ที่จะใช้ เช่น `TYPHOON_API_KEY` หรือ `OLLAMA_BASE_URL`

3. รัน service

```bash
./start_rag_service.sh
```

หรือใช้ Makefile:

```bash
make run-server
```

## Ingestion

### Local ingestion (all domains)

```bash
make ingest
```

สคริปต์ที่ใช้จริงคือ [scripts/ingest_all_domains.sh](scripts/ingest_all_domains.sh)

### GPU ingestion (remote host)

```bash
make ingest-gpu GPU_HOST=user@remote-host
```

ดูรายละเอียดเพิ่มที่ [GPU_INGEST_GUIDE.md](GPU_INGEST_GUIDE.md)

## Evaluation และ Regression Gate

### รัน evaluation พื้นฐาน

```bash
make eval-regression
```

### รันชุด qball

```bash
make eval-qball
```

### เปรียบเทียบกับ baseline

```bash
make eval-qball-gate
```

### รัน canary guard

```bash
make eval-canary-guard
```

เอกสารเต็มอยู่ที่ [EVAL_GUIDE.md](EVAL_GUIDE.md)

## API ที่ใช้บ่อย

### Health check

```bash
curl http://localhost:8001/health
```

### RAG query

```bash
curl -X POST http://localhost:8001/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "หลักสูตรต้องมีหน่วยกิตกี่หน่วย",
    "domain": "curriculum"
  }'
```

### RAG answer for your own backend

แนะนำสำหรับเว็บ/backend ของคุณเอง เพราะจะได้ทั้ง `answer`, `contexts`, และ `token_est` กลับมาในครั้งเดียว

```bash
curl -X POST http://localhost:8001/rag/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "อาจารย์ผู้รับผิดชอบวิชา CPE101 มีใครบ้าง",
    "domain": "curriculum"
  }'
```

ถ้าต้องการบังคับโมเดลต่อ request:

```bash
curl -X POST http://localhost:8001/rag/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "หลักสูตรต้องมีหน่วยกิตกี่หน่วย",
    "domain": "curriculum",
    "model": "gemma4:26b"
  }'
```

ถ้าไม่ส่ง `model` ระบบจะใช้โหมดแนะนำอัตโนมัติ:
- `Typhoon` เป็นโมเดลหลักสำหรับคำตอบสุดท้าย
- `gemma4:26b` ช่วยงาน rewrite/routing/multi-query และ fallback เมื่อโมเดลหลักมีปัญหา

### OpenAI-compatible endpoint

```bash
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "typhoon-rag",
    "messages": [
      {"role": "user", "content": "หลักสูตรต้องมีหน่วยกิตกี่หน่วย"}
    ]
  }'
```

## โครงสร้างที่ควรรู้

- [docker-compose.yml](docker-compose.yml): orchestration หลัก
- [Makefile](Makefile): คำสั่งหลักสำหรับ run/ingest/eval
- [start_rag_service.sh](start_rag_service.sh): รัน RAG service แบบ local
- [scripts](scripts): utility scripts สำหรับ ingestion/evaluation/gates
- [services/rag-service](services/rag-service): โค้ด backend RAG
- [services/ingestion-service](services/ingestion-service): โค้ด ingestion pipeline
- [README_DOMAINS.md](README_DOMAINS.md): รายละเอียดแยกโดเมน
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md): คู่มือ deploy บน VM

## Troubleshooting

- RAG ไม่ขึ้น:
  - เช็กค่า provider ใน `.env` ว่าตรงกับ `LLM_PROVIDER`
  - ถ้าใช้ Typhoon ให้เช็ก `TYPHOON_API_KEY`
  - ถ้าใช้ Ollama ให้เช็ก `OLLAMA_BASE_URL` และให้ container เข้าถึง host ปลายทางได้
  - ดู log: `docker-compose logs rag-service`
- OpenWeb-UI คุยกับ RAG ไม่ได้:
  - เช็ก health endpoint `http://localhost:8001/health`
  - เช็ก network/ports ใน [docker-compose.yml](docker-compose.yml)
- ตอบไม่ได้เรื่อง curriculum:
  - เช็กว่ามี index ใน `indexes/curriculum/...`
  - รัน ingestion ใหม่

## Notes

- ไฟล์ index และ data ที่ generate ระหว่าง ingestion อาจมีขนาดใหญ่และไม่ควรถูก commit
- ควรใช้ regression/eval ทุกครั้งก่อนปล่อยขึ้นสภาพแวดล้อมใช้งานจริง
