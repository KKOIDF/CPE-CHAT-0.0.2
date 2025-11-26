#!/usr/bin/env python
import os
import sys
from pathlib import Path
import json

os.environ.setdefault('EMBED_DEVICE', 'cpu')

# Ensure app package is importable
HERE = Path(__file__).resolve()
SERVICE_DIR = HERE.parent.parent
APP_DIR = SERVICE_DIR / 'app'
sys.path.insert(0, str(SERVICE_DIR))
sys.path.insert(0, str(APP_DIR))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

q = "รับสมัครนักศึกษาใหม่"

print("-- /health ------------------------------------------------------")
r = client.get('/health')
print(r.status_code, r.json())

print("\n-- /rag/query ----------------------------------------------------")
r = client.post('/rag/query', json={'question': q})
print(r.status_code)
data = r.json()
print(json.dumps({k: (data[k] if k != 'contexts' else data['contexts'][:3]) for k in data}, ensure_ascii=False, indent=2))

print("\n-- /rag/answer ---------------------------------------------------")
r = client.post('/rag/answer', json={'question': q})
print(r.status_code)
data = r.json()
print(json.dumps({
    'question': data.get('question'),
    'answer': data.get('answer'),
    'contexts_preview': data.get('contexts', [])[:3],
    'token_est': data.get('token_est')
}, ensure_ascii=False, indent=2))
