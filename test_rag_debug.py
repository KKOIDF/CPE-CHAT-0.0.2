#!/usr/bin/env python3
"""Debug RAG endpoint step by step"""
import sys
sys.path.insert(0, r'c:\Users\KritChaJ\CPE-CHAT-0.0.2\services\rag-service')

print("=" * 60)
print("Debugging RAG Endpoint")
print("=" * 60)

try:
    print("\n[1] Testing RAG query without LLM...")
    from app.rag_logic import rag_query_domain
    
    result = rag_query_domain("สาขาวิชา", "curriculum")
    print("[OK] RAG query succeeded")
    print(f"    Contexts found: {len(result.get('contexts', []))}")
    print(f"    Prompt length: {len(result.get('prompt', ''))}")
    
    print("\n[2] Testing LLM generation with RAG prompt...")
    from app.llm import llm_engine
    
    prompt = result.get('prompt', '')
    system_msg = { 'role': 'system', 'content': 'Test system message' }
    user_msg = { 'role': 'user', 'content': prompt[:200] + '...' }
    
    answer = llm_engine.generate(prompt, messages=[system_msg, user_msg])
    print("[OK] LLM generation succeeded")
    print(f"    Answer: {(answer or '(no answer)')[:200]}")
    
    print("\n[3] Testing full RAG answer endpoint logic...")
    result2 = rag_query_domain("สาขาวิชา", "curriculum")
    
    system_msg = {
        'role': 'system',
        'content': 'Test'
    }
    user_msg = {
        'role': 'user',
        'content': result2['prompt']
    }
    
    if result2.get('contexts'):
        answer2 = llm_engine.generate(result2['prompt'], messages=[system_msg, user_msg])
        print("[OK] Full logic succeeded")
        print(f"    Answer length: {len(answer2)}")
        print(f"    Answer: {answer2[:300]}")
    else:
        print("[WARNING] No contexts found")
        
    print("\n[SUCCESS] All steps passed!")
    
except Exception as e:
    print(f"\n[ERROR] Failed: {e}")
    import traceback
    traceback.print_exc()
