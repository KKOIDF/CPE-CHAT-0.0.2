#!/usr/bin/env python3
import requests
import json
import traceback

print("=" * 60)
print("Testing RAG endpoint with Typhoon API")
print("=" * 60)

try:
    url = "http://127.0.0.1:8001/rag/answer"
    payload = {
        "question": "สาขาวิชาไหนมีหลักสูตร",
        "domain": "curriculum"
    }
    
    print(f"\n📤 Sending request to: {url}")
    print(f"📝 Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    
    response = requests.post(url, json=payload, timeout=120)
    
    print(f"\n📥 Response Status: {response.status_code}")
    print(f"📥 Response Headers: {dict(response.headers)}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ SUCCESS!")
        print(f"\n❓ Question: {result.get('question')}")
        print(f"\n💡 Answer:\n{result.get('answer', '(no answer)')}")
        print(f"\n📚 Contexts: {len(result.get('contexts', []))} found")
        print(f"⏱️  Token estimate: {result.get('token_est')}")
    else:
        print(f"\n❌ Error Response:")
        try:
            print(response.json())
        except:
            print(response.text[:1000])
            
except requests.exceptions.ConnectionError as e:
    print(f"❌ Connection Error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
    traceback.print_exc()
