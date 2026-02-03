# การตั้งค่าตำแหน่งข้อมูลสำหรับ RAG Service (รองรับแยกโดเมน)

## ภาพรวม

RAG Service อ่านข้อมูลจาก **indexes/<domain>/** (แนะนำ) หรือ fallback ไปยังโครงสร้างแบบเดิมของ ingestion-service/data

## โครงสร้างข้อมูล (แนะนำ)

```
indexes/
├── announcements/
│   └── vector/
│       ├── chroma/
│       └── sqlite/ingestion.db
├── regulations/
│   └── vector/
│       ├── chroma/
│       └── sqlite/ingestion.db
└── curriculum/
  └── vector/
    ├── chroma/
    └── sqlite/ingestion.db
```

## การกำหนดค่าใน RAG Service

### ไฟล์: `services/rag-service/app/config.py`

RAG Service จะเลือก path ตามโดเมนโดยดูจาก:
1) request body field `domain` (แนะนำ)
2) หรือ env `CPE_DOMAIN`
3) ถ้าไม่ระบุ จะ fallback ไป `DATA_DIR` แบบเดิม

### การปรับแต่งตำแหน่ง (ถ้าต้องการ)

สามารถกำหนดตำแหน่งใหม่ผ่าน environment variable:

```bash
# Windows PowerShell
$env:CPE_INDEX_ROOT = "C:\path\to\indexes"   # (default = <repo>/indexes)
$env:CPE_DOMAIN = "announcements"             # optional default domain

# Legacy fallback
$env:DATA_DIR = "C:\path\to\legacy\ingestion-service\data"
```

## การตรวจสอบการเชื่อมต่อ

### 1. รันสคริปต์ทดสอบ

```bash
cd services/rag-service
python test_data_connection.py --domain announcements
python test_data_connection.py --domain regulations
python test_data_connection.py --domain curriculum
```

### 2. ผลลัพธ์ที่คาดหวัง

```
✓ DATA_DIR exists:    True
✓ CHROMA_DIR exists:  True  
✓ SQLITE_PATH exists: True
✅ SQLite connection: OK (พบ X documents)
✅ Chroma connection: OK
✅ Keyword search: OK
```

## ข้อมูลที่ RAG Service ต้องการ

### จาก SQLite (`ingestion.db`)

- **Table `documents`**: เอกสารทั้งหมดพร้อม metadata
  - doc_id, source, path, file_type
  - page_start, page_end
  - owner, sensitivity, updated_at
  - tokens_est, text

- **Table `docs_fts`**: Full-text search index
  - รองรับการค้นหาด้วย keyword (Thai + English)

### จาก Chroma (`chroma/`)

- **Vector embeddings**: สำหรับ semantic search
- **Collection `documents`**: 
  - IDs, embeddings, metadata, documents

## Workflow การใช้ข้อมูล

```
1. Ingestion Service ประมวลผล → บันทึกลงใน data/
2. RAG Service อ่านจาก data/ โดยตรง
3. Hybrid Search:
   - Semantic search ผ่าน Chroma
   - Keyword search ผ่าน SQLite FTS
4. Reciprocal Rank Fusion (RRF) รวมผลลัพธ์
5. Context packing ตาม token budget
```

## ข้อควรระวัง

### ✅ ทำ
- ตรวจสอบว่า `ingestion.db` และ `chroma/` มีข้อมูลก่อนเริ่ม RAG
- ใช้ environment variable เมื่อต้องการเปลี่ยน path
- รันทดสอบหลังจาก ingest ข้อมูลใหม่

### ❌ ไม่ควรทำ
- ย้ายไฟล์ `chroma/` หรือ `ingestion.db` โดยตรง
- แก้ไข database ด้วยตนเอง
- ลบไฟล์ใน `data/` ขณะ service กำลังทำงาน

## การตรวจสอบข้อมูลใน Database

### เช็คจำนวนเอกสาร

```python
import sqlite3
conn = sqlite3.connect('services/ingestion-service/data/db/ingestion.db')
cur = conn.execute("SELECT COUNT(*) FROM documents")
print(f"Total documents: {cur.fetchone()[0]}")
```

### ดูตัวอย่างเอกสาร

```python
cur = conn.execute("""
    SELECT doc_id, source, page_start, tokens_est 
    FROM documents LIMIT 5
""")
for row in cur.fetchall():
    print(row)
```

## Troubleshooting

### ปัญหา: SQLite ไม่พบไฟล์

```
Solution: ตรวจสอบว่า ingestion service ทำงานแล้ว และมีการสร้าง ingestion.db
```

### ปัญหา: Chroma ไม่มีข้อมูล

```
Solution: รัน ingestion pipeline อีกครั้งเพื่อสร้าง embeddings
```

### ปัญหา: Path ไม่ถูกต้อง

```
Solution: ตั้งค่า DATA_DIR environment variable ให้ชี้ไปที่ตำแหน่งที่ถูกต้อง
```

## ข้อมูลเพิ่มเติม

- **Embedding Model**: `BAAI/bge-m3` (ค่าเริ่มต้น)
- **Token Budget**: 1200 tokens (ปรับได้ผ่าน `TOKEN_BUDGET`)
- **Max Contexts**: 8 chunks (ปรับได้ผ่าน `MAX_CONTEXTS`)
- **RRF K**: 60 (ปรับได้ผ่าน `RRF_K`)

---

**อัพเดต**: 21 พฤศจิกายน 2025  
**สถานะ**: ✅ ทดสอบแล้ว - ระบบพร้อมใช้งาน (1186 documents)
