# Ollama Integration - Quick Start Guide

เชื่อมต่อกับ Ollama โดยใช้ model **scb10x/typhoon2.5-qwen3-30b-a3b** สำหรับ RAG service

## 🎯 Quick Start (3 ขั้นตอน)

### 1. ติดตั้ง Ollama

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**macOS:**
```bash
brew install ollama
```

**Windows:** ดาวน์โหลดจาก [ollama.com/download](https://ollama.com/download)

### 2. Pull Model และติดตั้ง Dependencies

**Linux/macOS:**
```bash
cd services/rag-service
./setup_ollama.sh
```

**Windows (PowerShell):**
```powershell
cd services/rag-service
.\setup_ollama.ps1
```

หรือทำด้วยตัวเอง:
```bash
# Pull model
ollama pull scb10x/typhoon2.5-qwen3-30b-a3b

# ติดตั้ง dependencies
cd services/rag-service
pip install -r requirements.txt
```

### 3. รัน Service

```bash
export LLM_ENABLE=1
export LLM_PROVIDER=ollama
export LLM_MODEL=scb10x/typhoon2.5-qwen3-30b-a3b

python run_server.py
```

**Windows (PowerShell):**
```powershell
$env:LLM_ENABLE="1"
$env:LLM_PROVIDER="ollama"
$env:LLM_MODEL="scb10x/typhoon2.5-qwen3-30b-a3b"

python run_server.py
```

## 🧪 ทดสอบการเชื่อมต่อ

```bash
cd services/rag-service
python test_ollama_typhoon.py
```

## 📋 Files ที่เพิ่ม/แก้ไข

### ไฟล์ใหม่:
- `services/rag-service/OLLAMA_SETUP.md` - คู่มือการใช้งานแบบละเอียด
- `services/rag-service/test_ollama_typhoon.py` - script ทดสอบ
- `services/rag-service/setup_ollama.sh` - setup script สำหรับ Linux/macOS
- `services/rag-service/setup_ollama.ps1` - setup script สำหรับ Windows

### ไฟล์ที่แก้ไข:
- `services/rag-service/requirements.txt` - เพิ่ม `ollama` package
- `services/rag-service/app/config.py` - เพิ่มการตั้งค่า Ollama
- `services/rag-service/app/llm.py` - เพิ่มฟังก์ชัน `_generate_ollama()`

## 🔧 การตั้งค่า Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_ENABLE` | `0` | เปิด/ปิดการใช้งาน LLM (ตั้งเป็น `1` เพื่อเปิด) |
| `LLM_PROVIDER` | `""` | `ollama`, `openai`, หรือ `hf` |
| `LLM_MODEL` | `Qwen/Qwen2.5-7B-Instruct` | ชื่อ model ที่จะใช้ |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL ของ Ollama server |
| `OLLAMA_TIMEOUT_S` | `120` | Timeout (วินาที) |
| `LLM_MAX_TOKENS` | `384` | จำนวน tokens สูงสุดที่จะ generate |
| `LLM_TEMPERATURE` | `0.4` | Temperature สำหรับการ generate |

## 📝 ตัวอย่างการใช้งาน

### ตัวอย่าง 1: Python Code

```python
import os
os.environ['LLM_ENABLE'] = '1'
os.environ['LLM_PROVIDER'] = 'ollama'
os.environ['LLM_MODEL'] = 'scb10x/typhoon2.5-qwen3-30b-a3b'

from app.llm import llm_engine

# Simple prompt
response = llm_engine.generate("อธิบายเกี่ยวกับ RAG")
print(response)

# Chat messages
messages = [
    {"role": "system", "content": "คุณเป็น AI ผู้ช่วย"},
    {"role": "user", "content": "สวัสดีครับ"}
]
response = llm_engine.generate("", messages=messages)
print(response)
```

### ตัวอย่าง 2: API Request

```bash
# Start server
python run_server.py

# Send request
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "อธิบาย RAG", "domain": "curriculum"}'
```

## 🔄 การสลับระหว่าง Providers

### Ollama (Recommended for Thai)
```bash
export LLM_PROVIDER=ollama
export LLM_MODEL=scb10x/typhoon2.5-qwen3-30b-a3b
```

### Hugging Face (Local, requires GPU)
```bash
export LLM_PROVIDER=hf
export LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
export LLM_PIPELINE=1
export LLM_4BIT=1
```

### OpenAI (Cloud)
```bash
export LLM_PROVIDER=openai
export LLM_MODEL=gpt-4
export OPENAI_API_KEY=your-key-here
```

## ⚙️ Models ที่แนะนำ

### Typhoon (ภาษาไทย) - แนะนำ
- `scb10x/typhoon2.5-qwen3-30b-a3b` ⭐ - Typhoon 2.5, 30B params
- `scb10x/typhoon-v1.5-8b-instruct` - Typhoon 1.5, 8B params
- `scb10x/llama-3-typhoon-v1.5-8b-instruct` - Typhoon 1.5 Llama

### International Models
- `llama3.1` - Meta Llama 3.1
- `qwen2.5` - Alibaba Qwen 2.5
- `mistral` - Mistral AI
- `phi3` - Microsoft Phi-3

ดู models ทั้งหมดได้ที่: [ollama.com/library](https://ollama.com/library)

## 🐛 Troubleshooting

### Ollama server ไม่ทำงาน
```bash
# Start manually
ollama serve
```

### Model ไม่พบ
```bash
# Pull model
ollama pull scb10x/typhoon2.5-qwen3-30b-a3b

# ดู models ที่มี
ollama list
```

### Response ช้า
- ลด `LLM_MAX_TOKENS`
- ใช้ model เล็กกว่า (8B แทน 30B)
- เช็ค hardware resources

### Connection timeout
- เพิ่ม `OLLAMA_TIMEOUT_S=300`
- ตรวจสอบว่า Ollama server ทำงานอยู่

## 📚 เอกสารเพิ่มเติม

- [OLLAMA_SETUP.md](./OLLAMA_SETUP.md) - คู่มือการใช้งานแบบละเอียด
- [Ollama Documentation](https://github.com/ollama/ollama)
- [Typhoon Models on HuggingFace](https://huggingface.co/scb10x)

## 💡 Tips

1. **GPU**: Ollama จะใช้ GPU อัตโนมัติถ้ามี (NVIDIA CUDA, Apple Metal, AMD ROCm)
2. **Memory**: 30B model ต้องการ RAM/VRAM ~30-60 GB
3. **Concurrent**: Ollama รองรับหลาย requests พร้อมกัน
4. **Context**: Typhoon 2.5 รองรับ context window ยาวถึง 32K tokens

---

**สร้างเมื่อ:** 3 Feb 2026  
**Model:** scb10x/typhoon2.5-qwen3-30b-a3b  
**Provider:** Ollama
