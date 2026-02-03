# การเชื่อมต่อกับ Ollama

## ขั้นตอนการติดตั้งและใช้งาน

### 1. ติดตั้ง Ollama

#### Linux
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

#### macOS
```bash
brew install ollama
```

#### Windows
ดาวน์โหลดจาก [https://ollama.com/download](https://ollama.com/download)

### 2. Pull Model ที่ต้องการใช้งาน

```bash
# Pull Typhoon 2.5 Qwen3 30B model
ollama pull scb10x/typhoon2.5-qwen3-30b-a3b
```

### 3. ตรวจสอบว่า Ollama ทำงานอยู่

```bash
# เริ่มต้น Ollama server (ถ้ายังไม่ได้เริ่ม)
ollama serve

# ทดสอบ model
ollama run scb10x/typhoon2.5-qwen3-30b-a3b "สวัสดีครับ"
```

### 4. ติดตั้ง Dependencies ของ RAG Service

```bash
cd services/rag-service
pip install -r requirements.txt
```

### 5. ตั้งค่า Environment Variables

สร้างไฟล์ `.env` ในโฟลเดอร์ root ของโปรเจค:

```bash
# เปิดใช้งาน LLM
LLM_ENABLE=1

# เลือกใช้ Ollama เป็น provider
LLM_PROVIDER=ollama

# ระบุชื่อ model
LLM_MODEL=scb10x/typhoon2.5-qwen3-30b-a3b

# Ollama URL (default: http://localhost:11434)
OLLAMA_BASE_URL=http://localhost:11434

# Timeout สำหรับ Ollama (วินาที)
OLLAMA_TIMEOUT_S=120

# LLM Parameters
LLM_MAX_TOKENS=384
LLM_TEMPERATURE=0.4
```

### 6. รัน RAG Service

```bash
cd services/rag-service
python run_server.py
```

## ตัวอย่างการใช้งาน

### ตัวอย่าง 1: ทดสอบด้วย Python Script

สร้างไฟล์ `test_ollama.py`:

```python
import os
os.environ['LLM_ENABLE'] = '1'
os.environ['LLM_PROVIDER'] = 'ollama'
os.environ['LLM_MODEL'] = 'scb10x/typhoon2.5-qwen3-30b-a3b'

from app.llm import llm_engine

# ทดสอบแบบ simple prompt
response = llm_engine.generate("อธิบายเกี่ยวกับ RAG ให้หน่อย")
print(response)

# ทดสอบแบบ chat messages
messages = [
    {"role": "system", "content": "คุณเป็น AI ผู้ช่วยตอบคำถามเกี่ยวกับมหาวิทยาลัย"},
    {"role": "user", "content": "มีกี่ภาคการศึกษาต่อปี"}
]
response = llm_engine.generate("", messages=messages)
print(response)
```

รันด้วย:
```bash
python test_ollama.py
```

### ตัวอย่าง 2: ทดสอบผ่าน API

```bash
# เริ่ม server
python run_server.py

# ส่ง request (ใน terminal อื่น)
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "อธิบายระบบ RAG",
    "domain": "curriculum"
  }'
```

### ตัวอย่าง 3: ใช้กับ Windows PowerShell

```powershell
# ตั้งค่า environment variables
$env:LLM_ENABLE="1"
$env:LLM_PROVIDER="ollama"
$env:LLM_MODEL="scb10x/typhoon2.5-qwen3-30b-a3b"

# รัน server
python run_server.py
```

## Models ที่แนะนำ

### Typhoon Models (ภาษาไทย)
- `scb10x/typhoon2.5-qwen3-30b-a3b` - Typhoon 2.5 (30B parameters) - **แนะนำ**
- `scb10x/typhoon-v1.5-8b-instruct` - Typhoon 1.5 (8B parameters)
- `scb10x/llama-3-typhoon-v1.5-8b-instruct` - Typhoon 1.5 Llama (8B)

### International Models
- `llama3.1` - Meta Llama 3.1
- `qwen2.5` - Alibaba Qwen 2.5
- `mistral` - Mistral AI
- `phi3` - Microsoft Phi-3

## การสลับระหว่าง Providers

### ใช้ Ollama
```bash
export LLM_PROVIDER=ollama
export LLM_MODEL=scb10x/typhoon2.5-qwen3-30b-a3b
```

### ใช้ Hugging Face (Local)
```bash
export LLM_PROVIDER=hf
export LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
export LLM_PIPELINE=1
export LLM_4BIT=1
```

### ใช้ OpenAI
```bash
export LLM_PROVIDER=openai
export LLM_MODEL=gpt-4
export OPENAI_API_KEY=your-api-key
```

## Troubleshooting

### ปัญหา: Connection refused
- ตรวจสอบว่า Ollama server กำลังทำงานอยู่: `ollama serve`
- ตรวจสอบ URL: `curl http://localhost:11434`

### ปัญหา: Model not found
- Pull model ก่อนใช้งาน: `ollama pull scb10x/typhoon2.5-qwen3-30b-a3b`
- ตรวจสอบ model ที่มี: `ollama list`

### ปัญหา: Timeout
- เพิ่มค่า `OLLAMA_TIMEOUT_S` เช่น `OLLAMA_TIMEOUT_S=300`

### ปัญหา: Response ช้า
- ลด `LLM_MAX_TOKENS`
- ใช้ model ขนาดเล็กกว่า เช่น `scb10x/typhoon-v1.5-8b-instruct`
- ตรวจสอบ hardware resources (CPU/GPU/RAM)

## Performance Tips

1. **GPU Acceleration**: Ollama จะใช้ GPU โดยอัตโนมัติถ้ามี
2. **Model Size**: เลือก model ให้เหมาะกับ hardware ที่มี
   - 8B models: ต้องการ RAM/VRAM ~8-16 GB
   - 30B models: ต้องการ RAM/VRAM ~30-60 GB
3. **Concurrent Requests**: Ollama รองรับ concurrent requests
4. **Context Window**: Typhoon 2.5 รองรับ context ยาวถึง 32K tokens

## เอกสารเพิ่มเติม

- [Ollama Documentation](https://github.com/ollama/ollama)
- [Typhoon Models](https://huggingface.co/scb10x)
- [Model Library](https://ollama.com/library)
