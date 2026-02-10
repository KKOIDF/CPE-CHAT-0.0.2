# Ingestion Service (OCR + Chunk + Index)

บริการสำหรับ batch ingest เอกสาร (PDF/TXT/Excel/CSV/TSV):

* ดึงข้อความด้วย PyMuPDF และ fallback เป็น OCR (pdf2image + Tesseract) เมื่อคุณภาพต่ำ
* รองรับข้อความไทย/อังกฤษ + normalization
* chunking แบบ paragraph/sentence-aware (อิงช่วง token) พร้อม overlap
* เก็บ keyword index ด้วย SQLite (FTS5)
* เก็บ vector embeddings + metadata ใน ChromaDB
* (Curriculum) อัปเดทกราฟ Neo4j แบบ optional ถ้าติดตั้ง dependency และตั้งค่าไว้

## โครงสร้างไดเรกทอรี

```text
services/ingestion-service/
  app/                         # source code
  data/                        # service-local data (ใช้เมื่อไม่พบ workspace data/ หรือบังคับใช้)

Workspace (แนะนำ):
  data/<domain>/               # ไฟล์ input (announcements/regulations/curriculum)
  indexes/<domain>/vector/
    chroma/                    # Chroma per domain
    sqlite/ingestion.db        # SQLite FTS per domain
    review/flagged_*.jsonl     # review file (เมื่อ EMBED_FLAGGED=false)
```

หมายเหตุ: ค่าเริ่มต้นจะพยายามใช้ `data/` และ `indexes/` ที่ระดับ repo ก่อน (workspace) ถ้ามีอยู่จริง

## การใช้งาน (CLI)

จากโฟลเดอร์ `services/ingestion-service/`:

```bash
python -m app.main --input <input_dir> [--domain announcements|regulations|curriculum] [--output <output_base>] [--no-store] [--no-embed]
```

Flags ที่ใช้บ่อย:

* `--domain` แยก index/DB ออกจากกันเป็นรายโดเมน (แนะนำ)
* `--output` กำหนด base path ของไฟล์ TOON ที่สร้าง (default: `data/db/data`)
* `--no-store` ไม่เขียน SQLite
* `--no-embed` ไม่ทำ embedding/upsert Chroma

## Quick Start (Local)

```powershell
cd services/ingestion-service

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# ตัวอย่าง ingest แบบแยกโดเมน (แนะนำ)
python -m app.main --domain announcements --input ..\..\data\announcements
python -m app.main --domain regulations   --input ..\..\data\regulations
python -m app.main --domain curriculum    --input ..\..\data\curriculum
```

### ไฟล์/ผลลัพธ์ที่ได้

* TOON outputs (ขึ้นกับ `--output`):
  * `<output_base>_records.toon` (ต่อหน้า/ชีท)
  * `<output_base>_chunks.toon`
* Storage paths:
  * เมื่อมี `--domain`:
    * SQLite: `indexes/<domain>/vector/sqlite/ingestion.db`
    * Chroma: `indexes/<domain>/vector/chroma/`
    * Review (flagged): `indexes/<domain>/vector/review/flagged_*.jsonl`
  * เมื่อไม่มี `--domain` (legacy / single-index):
    * SQLite: `data/db/ingestion.db`
    * Chroma: `data/chroma/`
    * Review (flagged): `data/db/review/flagged_*.jsonl`

## Docker

Build:

```bash
cd services/ingestion-service
docker build -t ingestion-service .
```

Run (แนะนำให้ mount index ออกมาด้วย เพื่อให้ผลลัพธ์ไม่หาย):

```bash
# Linux/macOS
docker run --rm \
  -v $(pwd)/../../data/announcements:/input \
  -v $(pwd)/../../indexes:/indexes \
  ingestion-service --domain announcements --input /input
```

```powershell
# Windows PowerShell (ตัวอย่าง)
docker run --rm `
  -v ${PWD}\..\..\data\announcements:/input `
  -v ${PWD}\..\..\indexes:/indexes `
  ingestion-service --domain announcements --input /input
```

หมายเหตุ: ใน container ค่า default ของ `CPE_INDEX_ROOT` จะเป็น `/indexes` ดังนั้นการ mount `indexes/` ไปที่ `/indexes` จะทำให้ DB/Chroma ถูกเก็บ persist บนเครื่อง host

## Environment Variables

ตัวแปรหลัก:

| Variable | Purpose | Default |
| -------- | ------- | ------- |
| `CPE_DOMAIN` | โดเมน (ตั้งได้ผ่าน `--domain` ด้วย) | (unset) |
| `CPE_INDEX_ROOT` | โฟลเดอร์รากของ `indexes/` | `<repo>/indexes` (local) / `/indexes` (docker) |
| `CPE_USE_SERVICE_DATA` | บังคับใช้ `services/ingestion-service/data/` แทน workspace `data/` | false |
| `OCR_ENGINE` | `auto`\|`poppler`\|`tesseract` | auto |
| `OCR_LANG` | ภาษา OCR (`tha` หรือ `tha+eng`) | tha |
| `OCR_DPI` | DPI สำหรับ OCR image | 450 |
| `MIN_QUALITY_SCORE` | threshold คุณภาพเพื่อ fallback OCR | 0.2 |
| `MIN_LENGTH` | ความยาวขั้นต่ำที่ยอมรับ MuPDF text | 50 |
| `MUPDF_ONLY` | ข้าม OCR ทั้งหมด (fast path) | false |
| `CHUNK_MIN_TOKENS` | เป้าต่ำสุดของ chunk | 400 |
| `CHUNK_MAX_TOKENS` | เป้าสูงสุดของ chunk | 800 |
| `CHUNK_OVERLAP_RATIO` | overlap ratio | 0.12 |
| `CHAR_PER_TOKEN` | heuristic แปลง chars→tokens | 4.0 |
| `EMBEDDING_MODEL` | SentenceTransformer model | `BAAI/bge-m3` |
| `EMBED_BATCH` | batch size ตอน embed | 32 |
| `EMBEDDING_API_BASE` / `EMBEDDING_API_KEY` | เรียก external embedding API (ถ้ามี) | (unset) |
| `EMBED_FLAGGED` | embed chunk ที่ flagged หรือไม่ | false |
| `POPPLER_PATH` | path ไปยัง Poppler (Windows) | (unset) |
| `TESSERACT_PATH` | path ไปยัง Tesseract (Windows) | (unset) |
| `THAI_WORD_TOKENIZER` | `newmm`\|`attacut`\|`longest`\|`deepcut` | attacut |
| `THAI_SENT_TOKENIZER` | `crfcut`\|`tltk` | crfcut |

### Flagged chunk handling

ถ้า chunk คุณภาพต่ำ จะถูกตั้ง `status=flagged`.
เมื่อ `EMBED_FLAGGED=false` ระบบจะไม่ embed chunk เหล่านี้ และจะเขียนไฟล์ review เป็น `flagged_*.jsonl` ไว้ในโฟลเดอร์ `review/` ของโดเมนนั้น

## Keyword / Semantic Search (ตัวอย่างสั้น)

```python
from app.db import keyword_search
print(keyword_search('หลักเกณฑ์', limit=5))
```

```python
from app.chroma_client import semantic_search
print(semantic_search('หลักเกณฑ์การรับสมัคร', n_results=3))
```
