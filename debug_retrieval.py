#!/usr/bin/env python3
"""Debug script to inspect retrieved documents for course code queries."""
import os
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[0]
RAG_SERVICE_DIR = ROOT / 'services' / 'rag-service'
sys.path.insert(0, str(RAG_SERVICE_DIR))

os.environ['RAG_CURRICULUM_EXACT_CODE_FIRST'] = '1'

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

QUESTIONS = [
    'CPE 342 คือวิชาอะไร',
    'LNG 220 คือวิชาอะไร',
    'GEN 121 คือวิชาอะไร',
]

for question in QUESTIONS:
    print(f"\n{'='*80}")
    print(f"Question: {question}")
    print('='*80)
    
    res = client.post('/rag/query', json={'domain': 'curriculum', 'question': question})
    data = res.json()
    
    contexts = data.get('contexts', [])
    print(f"Total contexts: {len(contexts)}")
    
    for i, ctx in enumerate(contexts[:3]):
        print(f"\n--- Context {i+1} ---")
        print(f"Source: {ctx.get('source', 'N/A')}")
        print(f"Path: {ctx.get('path', 'N/A')}")
        
        text = (ctx.get('text') or '')[:500]
        print(f"Text preview:\n{text}")
        
        # Check if course codes appear
        codes_found = re.findall(r'[A-Z]{2,6}\s*[- ]?\s*\d{3}', text)
        if codes_found:
            print(f"Course codes found: {codes_found}")
        else:
            print("No course codes found in preview")
