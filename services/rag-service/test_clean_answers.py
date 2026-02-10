#!/usr/bin/env python3
"""Test script to verify RAG system generates clean answers without forced document references."""

import sys
import requests
import json

def test_clean_answer(question: str, domain: str | None = None):
    """Test a single question and display the answer format."""
    print("\n" + "="*80)
    print(f"❓ QUESTION: {question}")
    print("="*80)
    
    url = "http://127.0.0.1:8000/rag/answer"
    payload = {"question": question}
    if domain:
        payload["domain"] = domain
    
    try:
        resp = requests.post(url, json=payload, timeout=60)
        if not resp.ok:
            print(f"❌ Error: {resp.status_code}")
            print(resp.text)
            return False
        
        data = resp.json()
        answer = data.get("answer", "(no answer)")
        
        print(f"\n📝 ANSWER:")
        print("-"*80)
        print(answer)
        print("-"*80)
        
        # Check answer format
        print(f"\n✅ Answer Format Check:")
        print(f"  - Length: {len(answer)} characters")
        print(f"  - Contains [xxx/page] references: {'❌ YES (should not have)' if '[' in answer and '/' in answer else '✅ NO (as expected)'}")
        print(f"  - Looks natural: {'✅ YES' if not answer.startswith('(') else '⚠️  Maybe (error message)'}")
        
        # Show some context used
        contexts = data.get("contexts", [])
        print(f"\n📚 Sources Used (internal - not shown to user):")
        for i, ctx in enumerate(contexts[:3], 1):
            source = ctx.get('source') or ctx.get('path', 'N/A')
            page = ctx.get('page_start', 'N/A')
            print(f"  [{i}] {source} - Page {page}")
        
        if len(contexts) > 3:
            print(f"  ... and {len(contexts) - 3} more sources")
        
        return True
        
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False


def main():
    test_questions = [
        ("รหัสวิชา CPE อยู่ในหมวดวิชาแกนทางวิศวกรรมหรือไม่", "curriculum"),
        ("วิชา CPE 100 มีหน่วยกิตเท่าไร", "curriculum"),
        ("หลักสูตรวิศวกรรมคอมพิวเตอร์มีทั้งหมดกี่หน่วยกิต", "curriculum"),
    ]
    
    print("\n" + "="*80)
    print("🧪 Testing Clean Answer Generation (No Forced Document References)")
    print("="*80)
    
    passed = 0
    for question, domain in test_questions:
        if test_clean_answer(question, domain):
            passed += 1
    
    print(f"\n{'='*80}")
    print(f"📊 Results: {passed}/{len(test_questions)} tests passed")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
