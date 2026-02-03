# BGE-M3 Embedding Model Migration Guide

## ✅ สิ่งที่เสร็จแล้ว

1. **อัปเดต Configuration**
   - เปลี่ยน `EMBEDDING_MODEL` เป็น `BAAI/bge-m3`
   - รองรับ embedding dimension 1024

2. **อัปเดต Embedding Functions**
   - เพิ่ม query instruction: `"Represent this sentence for searching relevant passages: "`
   - แยก query embedding (มี instruction) จาก document embedding (ไม่มี instruction)
   - รองรับ Thai spell correction ก่อน embedding

3. **อัปเดตทั้งสอง Services**
   - ✅ `ingestion-service/app/chroma_client.py`
   - ✅ `rag-service/app/chroma_client.py`

4. **สร้าง Test Scripts**
   - ✅ `scripts/test_bge_m3.py` - ทดสอบคุณภาพ embedding
   - ✅ `scripts/migrate_to_bge_m3.py` - re-embed ข้อมูลเดิม

## 🧪 ผลการทดสอบ

### BGE-M3 Test Results
```
✅ Embedding dimension: 1024 (correct)
✅ Query instruction: Working (vectors differ by 20%)
✅ Semantic similarity: Excellent (0.63-0.71 for correct matches)
✅ Typo robustness: Good (0.86-0.96 with spell correction)
✅ Cross-lingual: Excellent (Thai-English mixed queries work well)
```

## 📋 ขั้นตอนถัดไป

### 1. ทดสอบ BGE-M3 (เสร็จแล้ว ✅)

```powershell
cd "c:\Users\KritChaJ\OneDrive\Documents\CPE CHAT 0.0.3\services\ingestion-service"
& "C:/Users/KritChaJ/OneDrive/Documents/CPE CHAT 0.0.3/.venv/Scripts/python.exe" "scripts/test_bge_m3.py"
```

### 2. Re-embed ข้อมูลเดิมด้วย BGE-M3

⚠️ **คำเตือน**: จะลบ Chroma collection เดิมและสร้างใหม่

```powershell
cd "c:\Users\KritChaJ\OneDrive\Documents\CPE CHAT 0.0.3\services\ingestion-service"
& "C:/Users/KritChaJ/OneDrive/Documents/CPE CHAT 0.0.3/.venv/Scripts/python.exe" "scripts/migrate_to_bge_m3.py"
```

### 3. หรือทำ Ingestion ใหม่ทั้งหมด

```powershell
cd "c:\Users\KritChaJ\OneDrive\Documents\CPE CHAT 0.0.3\services\ingestion-service"
$env:THAI_WORD_TOKENIZER = "attacut"
$env:THAI_SENT_TOKENIZER = "crfcut"
$env:EMBEDDING_MODEL = "BAAI/bge-m3"

& "C:/Users/KritChaJ/OneDrive/Documents/CPE CHAT 0.0.3/.venv/Scripts/python.exe" -m app.main `
  --input "data/raw_files" `
  --output "data/db/data"
```

### 4. ทดสอบ RAG Service

```powershell
cd "c:\Users\KritChaJ\OneDrive\Documents\CPE CHAT 0.0.3\services\rag-service"
$env:EMBEDDING_MODEL = "BAAI/bge-m3"

& "C:/Users/KritChaJ/OneDrive/Documents/CPE CHAT 0.0.3/.venv/Scripts/python.exe" run_server.py
```

### 5. รัน Benchmark (ถ้ามี)

```powershell
cd "c:\Users\KritChaJ\OneDrive\Documents\CPE CHAT 0.0.3\services\ingestion-service"

# Baseline with BGE-M3
& "C:/Users/KritChaJ/OneDrive/Documents/CPE CHAT 0.0.3/.venv/Scripts/python.exe" "scripts/benchmark_rag_system.py" `
  --queries "data/benchmark_queries.json" `
  --spell-correction `
  --output "results/bge_m3_baseline.json"
```

## 🔧 Configuration

### Environment Variables

```bash
# Embedding Model
EMBEDDING_MODEL=BAAI/bge-m3
EMBED_BATCH=32
EMBED_DEVICE=cuda  # or 'cpu'

# Thai NLP
THAI_WORD_TOKENIZER=attacut
THAI_SENT_TOKENIZER=crfcut
```

### Config Files Updated

- `services/ingestion-service/app/config.py` ✅
- `services/rag-service/app/config.py` ✅

## 📊 BGE-M3 vs. Previous Model

### ข้อดี ✅
- **Better multilingual**: รองรับภาษาไทยดีกว่า
- **Larger dimension**: 1024 มิติ (vs 768) → semantic information มากกว่า
- **Query instruction**: ปรับ embedding สำหรับ query โดยเฉพาะ
- **Better zero-shot**: สำหรับ domain-specific queries
- **Hybrid retrieval**: รองรับ dense + sparse retrieval

### Trade-offs ⚖️
- **Memory**: ใช้ RAM มากกว่า (~1.5x)
- **Speed**: Embedding time ช้ากว่าเล็กน้อย
- **Storage**: Chroma DB ใช้พื้นที่มากกว่า

## 🎯 Expected Improvements

จากการทดสอบ BGE-M3 น่าจะให้ผลดีกว่าโมเดลเดิม:

1. **Retrieval Quality**
   - Hit Rate: คาดว่าจะเพิ่ม 5-10%
   - MRR: คาดว่าจะเพิ่ม 10-15%
   - NDCG@5: คาดว่าจะเพิ่ม 5-12%

2. **Robustness**
   - Typo handling: ดีขึ้นเมื่อใช้ร่วมกับ Thai spell correction
   - Cross-lingual: รองรับ Thai-English mixed ได้ดีมาก

3. **Domain Adaptation**
   - Academic/Technical Thai: ดีขึ้นอย่างชัดเจน
   - CPE-specific queries: แม่นยำมากขึ้น

## 📝 Notes

- BGE-M3 ต้องการ sentence-transformers >= 2.3.1
- Query instruction จะถูกเพิ่มอัตโนมัติเมื่อ `is_query=True`
- Document embedding ไม่มี instruction (ตามคำแนะนำของ BGE)
- Thai spell correction ยังทำงานก่อน embedding เหมือนเดิม

## 🆘 Troubleshooting

### Model ไม่โหลด
```bash
pip install sentence-transformers --upgrade
pip install transformers torch --upgrade
```

### Out of Memory
```bash
# ใช้ CPU แทน GPU สำหรับ embedding
export EMBED_DEVICE=cpu
```

### Dimension Mismatch
```bash
# ต้อง re-embed ทั้งหมด เพราะ dimension เปลี่ยนจาก 768 → 1024
python scripts/migrate_to_bge_m3.py
```

## ✅ Checklist

- [x] อัปเดต config ทั้งสอง services
- [x] เพิ่ม BGE-M3 query instruction support
- [x] เพิ่ม Thai spell correction integration
- [x] สร้าง test script
- [x] สร้าง migration script
- [ ] Re-embed ข้อมูลเดิม (รอผู้ใช้ confirm)
- [ ] รัน benchmark เปรียบเทียบ
- [ ] Deploy to production

## 📚 References

- BGE-M3 Paper: [arXiv:2402.03216](https://arxiv.org/abs/2402.03216)
- Model: [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)
- BGE GitHub: [FlagOpen/FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding)
