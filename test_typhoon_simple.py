#!/usr/bin/env python3
import requests
import time

print("Testing Typhoon API integration...")
time.sleep(2)

try:
    response = requests.post(
        "http://127.0.0.1:8001/rag/answer",
        json={"question": "สาขาวิชาไหนมีโครงการศึกษา", "domain": "curriculum"},
        timeout=60
    )
    print(f"✅ Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"\n📝 Question: {result.get('question')}")
        print(f"\n💡 Answer:\n{result.get('answer', '(no answer)')[:500]}")
        print(f"\n📚 Contexts found: {len(result.get('contexts', []))}")
    else:
        print(f"❌ Error {response.status_code}:\n{response.text[:500]}")
except Exception as e:
    print(f"❌ Connection failed: {e}")
