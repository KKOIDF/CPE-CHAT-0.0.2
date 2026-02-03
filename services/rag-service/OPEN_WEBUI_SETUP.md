# Open WebUI + Ollama Setup Guide

Open WebUI เป็น web interface สำหรับ Ollama ที่ให้คุณใช้งาน AI models ผ่านหน้าเว็บแบบ ChatGPT

## 🚀 Quick Start (แนะนำ - ใช้ Docker)

### 1. ติดตั้ง Docker (ถ้ายังไม่มี)

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# หรือติดตั้งด้วย apt
sudo apt update
sudo apt install docker.io docker-compose -y
sudo systemctl start docker
sudo systemctl enable docker
```

### 2. รัน Open WebUI ด้วย Docker (แนะนำ)

```bash
# รัน Open WebUI พร้อมเชื่อมต่อกับ Ollama บนเครื่องเดียวกัน
docker run -d \
  --name open-webui \
  -p 3000:8080 \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -v open-webui:/app/backend/data \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

**หมายเหตุ:**
- Port `3000` คือ port ที่จะเปิดให้เข้าถึง (เปลี่ยนได้ตามต้องการ)
- `--add-host=host.docker.internal:host-gateway` ทำให้ Docker เข้าถึง Ollama บน host ได้
- Ollama ต้องทำงานอยู่บน port `11434` (default)

**ถ้าเจอข้อความ “Ollama: Network Problem” (Linux):**
Ollama บน host อาจ bind แค่ `127.0.0.1` ทำให้ container เข้าถึงไม่ได้ ให้ใช้ host network แบบนี้:

```bash
docker run -d \
  --name open-webui \
  --network host \
  -e OLLAMA_BASE_URL=http://127.0.0.1:11434 \
  -e PORT=3000 \
  -v open-webui:/app/backend/data \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

### 3. เข้าใช้งาน

เปิดเบราว์เซอร์ไปที่:
```
http://localhost:3000
```

หรือถ้าอยู่คนละเครื่อง:
```
http://<your-server-ip>:3000
```

### 4. ตั้งค่าครั้งแรก

1. สร้าง account แรก (จะเป็น admin อัตโนมัติ)
2. ไปที่ **Settings** → **Connections**
3. ตั้งค่า Ollama URL:
  - ถ้ารันบนเครื่องเดียวกัน (Docker bridge): `http://host.docker.internal:11434`
  - ถ้าใช้ host network: `http://127.0.0.1:11434`
   - ถ้ารันคนละเครื่อง: `http://<ollama-server-ip>:11434`
4. กด **Verify connection** เพื่อทดสอบ
5. เลือก Model ที่จะใช้ เช่น `scb10x/typhoon2.5-qwen3-30b-a3b:latest`

---

## 🔧 Alternative: ติดตั้งแบบ Python (สำหรับ Development)

### 1. Clone Repository

```bash
git clone https://github.com/open-webui/open-webui.git
cd open-webui
```

### 2. ติดตั้ง Dependencies

#### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Frontend
```bash
cd ../frontend
npm install
```

### 3. ตั้งค่า Environment Variables

สร้างไฟล์ `.env` ในโฟลเดอร์ `backend/`:

```bash
# Ollama connection
OLLAMA_BASE_URL=http://localhost:11434

# Optional: OpenAI compatibility
# OPENAI_API_KEY=your-key-here

# Database
DATABASE_URL=sqlite:///./data/webui.db

# Secret key (generate random string)
SECRET_KEY=$(openssl rand -hex 32)

# Port
PORT=8080
```

### 4. รัน Application

```bash
# Terminal 1: Backend
cd backend
source venv/bin/activate
./start.sh

# Terminal 2: Frontend (ใน terminal ใหม่)
cd frontend
npm run dev
```

เปิดเบราว์เซอร์ที่: `http://localhost:5173`

---

## 🐳 Docker Compose (แนะนำสำหรับ Production)

สร้างไฟล์ `docker-compose.yml`:

```yaml
version: '3.8'

services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    restart: unless-stopped
    # ถ้ามี GPU (NVIDIA)
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: open-webui
    ports:
      - "3000:8080"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
    volumes:
      - open_webui_data:/app/backend/data
    depends_on:
      - ollama
    restart: unless-stopped

volumes:
  ollama_data:
  open_webui_data:
```

รันด้วย:
```bash
docker-compose up -d
```

---

## 📱 Features ของ Open WebUI

### 1. **Chat Interface**
- UI คล้าย ChatGPT
- รองรับ markdown, code highlighting
- Copy/paste รูปภาพ (ถ้า model รองรับ)

### 2. **Multiple Models**
- เลือกใช้ได้หลาย models
- สลับ model ระหว่างการสนทนา
- Compare responses จากหลาย models

### 3. **Conversation Management**
- บันทึก conversation history
- Search ในประวัติการสนทนา
- Export conversations

### 4. **Document/RAG Support**
- Upload เอกสาร (PDF, TXT, etc.)
- ระบบ RAG แบบ built-in
- Vector database (ChromaDB)

### 5. **User Management**
- Multi-user support
- Role-based access control
- Authentication & Authorization

### 6. **Customization**
- Custom prompts/templates
- System prompts
- Model parameters (temperature, top_p, etc.)

---

## 🔧 การตั้งค่า Models

### ดู Models ที่มี

ใน Open WebUI:
1. ไปที่ **Settings** → **Models**
2. จะเห็นรายการ models จาก Ollama

### Pull Model ใหม่

จาก Open WebUI:
1. **Settings** → **Models** → **Pull Model**
2. ใส่ชื่อ model เช่น `scb10x/typhoon2.5-qwen3-30b-a3b`
3. กด Pull

หรือจาก command line:
```bash
docker exec -it ollama ollama pull scb10x/typhoon2.5-qwen3-30b-a3b
```

---

## 🎨 Typhoon Models บน Open WebUI

Models ที่คุณมีอยู่แล้ว:

### 1. **Typhoon 2.5 Qwen3 30B** ⭐ (แนะนำ)
```
scb10x/typhoon2.5-qwen3-30b-a3b:latest
```
- Best for: Thai language tasks, long conversations
- Size: ~18 GB
- Context: 32K tokens

### 2. **Typhoon 2.5 Qwen3 4B**
```
scb10x/typhoon2.5-qwen3-4b:latest
```
- Best for: Fast responses, lighter tasks
- Size: ~2.5 GB
- Context: 32K tokens

### 3. **Typhoon OCR 3B**
```
scb10x/typhoon-ocr-3b:latest
```
- Best for: OCR tasks
- Size: ~7.5 GB

### 4. **Typhoon OCR 1.5 3B**
```
scb10x/typhoon-ocr1.5-3b:latest
```
- Best for: OCR tasks (older version)
- Size: ~3.2 GB

---

## 🌐 การเข้าถึงจากภายนอก

### 1. ใช้ ngrok (ง่ายที่สุด)

```bash
# ติดตั้ง ngrok
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# รัน ngrok
ngrok http 3000
```

จะได้ URL แบบ: `https://xxxx-xx-xx-xx-xx.ngrok-free.app`

### 2. ใช้ Cloudflare Tunnel

```bash
# ติดตั้ง cloudflared
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# สร้าง tunnel
cloudflared tunnel --url http://localhost:3000
```

### 3. เปิด Port บน Server โดยตรง

```bash
# เปิด port 3000 ใน firewall
sudo ufw allow 3000/tcp
```

**⚠️ คำเตือน:** อย่าลืมตั้งค่า authentication และใช้ HTTPS ใน production!

---

## 🔒 Security Best Practices

1. **ตั้งรหัสผ่านที่แข็งแรง** สำหรับ admin account
2. **ใช้ HTTPS** เสมอเมื่อเปิดให้เข้าถึงจากภายนอก
3. **จำกัดการเข้าถึง** ด้วย firewall rules
4. **Update เป็นประจำ** ทั้ง Open WebUI และ Ollama
5. **Backup data** ที่ `/app/backend/data` เป็นประจำ

---

## 🐛 Troubleshooting

### ปัญหา: ไม่เชื่อมต่อกับ Ollama

**แก้ไข:**
1. ตรวจสอบว่า Ollama ทำงานอยู่: `curl http://localhost:11434`
2. ตรวจสอบ Ollama URL ใน Settings → Connections
3. ถ้าใช้ Docker ให้ใช้ `host.docker.internal:11434`

### ปัญหา: Model ไม่แสดง

**แก้ไข:**
1. Pull model ก่อน: `ollama pull model-name`
2. Refresh หน้าเว็บ
3. ตรวจสอบ connection กับ Ollama

### ปัญหา: Response ช้า

**แก้ไข:**
1. ใช้ model เล็กกว่า (4B แทน 30B)
2. ลด max tokens ในการตั้งค่า
3. เช็ค GPU/CPU usage
4. เพิ่ม RAM/VRAM

---

## 📊 Performance Tips

1. **GPU Acceleration**: Ollama จะใช้ GPU อัตโนมัติถ้ามี
2. **Model Size**: เริ่มจาก 4B model ก่อน ค่อยขึ้น 30B ทีหลัง
3. **Concurrent Users**: 30B model รองรับประมาณ 2-3 users พร้อมกัน
4. **Memory**: 30B model ต้องการ ~30-60 GB RAM/VRAM

---

## 📚 เอกสารเพิ่มเติม

- [Open WebUI Documentation](https://docs.openwebui.com/)
- [Open WebUI GitHub](https://github.com/open-webui/open-webui)
- [Ollama Documentation](https://ollama.ai/docs)
- [Typhoon Models](https://huggingface.co/scb10x)

---

## 🎯 Quick Commands Summary

```bash
# ติดตั้ง Docker + Open WebUI
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# รัน Open WebUI
docker run -d \
  --name open-webui \
  -p 3000:8080 \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --restart always \
  ghcr.io/open-webui/open-webui:main

# ตรวจสอบสถานะ
docker ps
docker logs open-webui

# เข้าใช้งาน
# http://localhost:3000
```

---

**สร้างเมื่อ:** 3 February 2026  
**Ollama Models:** scb10x/typhoon2.5-qwen3-30b-a3b:latest  
**Open WebUI Version:** Latest
