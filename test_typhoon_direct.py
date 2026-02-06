#!/usr/bin/env python3
"""Test Typhoon LLM generation directly"""
import sys
sys.path.insert(0,  r'c:\Users\KritChaJ\CPE-CHAT-0.0.2\services\rag-service')

print("=" * 60)
print("Testing Typhoon LLM Generation")
print("=" * 60)

try:
    # Import and test config
    print("\n1️⃣ Loading config...")
    from app.config import LLM_PROVIDER, LLM_MODEL, TYPHOON_API_KEY, TYPHOON_BASE_URL
    print(f"   LLM_PROVIDER: {LLM_PROVIDER}")
    print(f"   LLM_MODEL: {LLM_MODEL}")
    print(f"   TYPHOON_API_KEY exists: {bool(TYPHOON_API_KEY)}")
    print(f"   TYPHOON_BASE_URL: {TYPHOON_BASE_URL}")
    
    # Import and test LLM engine
    print("\n2️⃣ Creating LLM engine...")
    from app.llm import llm_engine
    print(f"   Model: {llm_engine.model_name}")
    
    # Test generation with Typhoon
    print("\n3️⃣ Testing Typhoon generation...")
    test_prompt = "สวัสดีค่ะ"
    result = llm_engine.generate(test_prompt)
    print(f"   Prompt: {test_prompt}")
    print(f"   Response: {result}")
    
    if result.startswith("(Typhoon"):
        print("   ❌ Error detected in response")
    else:
        print("   ✅ Got a response!")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
