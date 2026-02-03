"""
Quick test script for Ollama integration with Typhoon 2.5 model.

Usage:
    python test_ollama_typhoon.py
"""

import os
import sys

# Set up environment for Ollama
os.environ['LLM_ENABLE'] = '1'
os.environ['LLM_PROVIDER'] = 'ollama'
os.environ['LLM_MODEL'] = 'scb10x/typhoon2.5-qwen3-30b-a3b'
os.environ['OLLAMA_BASE_URL'] = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.llm import llm_engine

def test_simple_prompt():
    """Test simple prompt generation"""
    print("=" * 60)
    print("Test 1: Simple Prompt")
    print("=" * 60)
    
    prompt = "อธิบายสั้นๆ ว่า RAG (Retrieval-Augmented Generation) คืออะไร"
    print(f"\nPrompt: {prompt}\n")
    
    response = llm_engine.generate(prompt)
    print(f"Response:\n{response}\n")
    return response

def test_chat_messages():
    """Test chat messages format"""
    print("=" * 60)
    print("Test 2: Chat Messages Format")
    print("=" * 60)
    
    messages = [
        {
            "role": "system",
            "content": "คุณเป็น AI ผู้ช่วยตอบคำถามเกี่ยวกับระบบการศึกษาของมหาวิทยาลัย"
        },
        {
            "role": "user",
            "content": "มหาวิทยาลัยมีกี่ภาคการศึกษาต่อปี และแต่ละภาคยาวกี่เดือน"
        }
    ]
    
    print("\nMessages:")
    for msg in messages:
        print(f"  [{msg['role']}]: {msg['content']}")
    print()
    
    response = llm_engine.generate("", messages=messages)
    print(f"Response:\n{response}\n")
    return response

def test_thai_english_mix():
    """Test mixed Thai-English prompt"""
    print("=" * 60)
    print("Test 3: Mixed Thai-English")
    print("=" * 60)
    
    messages = [
        {
            "role": "system",
            "content": "You are a helpful AI assistant that can respond in both Thai and English."
        },
        {
            "role": "user",
            "content": "Explain the concept of 'vector embedding' in Thai language เพื่อให้นักศึกษาเข้าใจง่าย"
        }
    ]
    
    print("\nMessages:")
    for msg in messages:
        print(f"  [{msg['role']}]: {msg['content']}")
    print()
    
    response = llm_engine.generate("", messages=messages)
    print(f"Response:\n{response}\n")
    return response

def test_rag_context():
    """Test with RAG-style context"""
    print("=" * 60)
    print("Test 4: RAG Context Simulation")
    print("=" * 60)
    
    context = """
    [1] หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิศวกรรมคอมพิวเตอร์ มีระยะเวลาการศึกษา 4 ปี
    [2] นักศึกษาต้องเรียนไม่น้อยกว่า 132 หน่วยกิต
    [3] แบ่งเป็นวิชาศึกษาทั่วไป 30 หน่วยกิต วิชาเฉพาะ 96 หน่วยกิต และวิชาเลือกเสรี 6 หน่วยกิต
    """
    
    question = "หลักสูตรวิศวกรรมคอมพิวเตอร์เรียนกี่ปี และต้องเก็บหน่วยกิตทั้งหมดกี่หน่วย"
    
    prompt = f"""คำถาม: {question}

บริบทที่เกี่ยวข้อง:
{context}

คำตอบ (ตอบโดยอ้างอิงจากบริบทที่ให้มา และระบุแหล่งอ้างอิงด้วยหมายเลขในวงเล็บ):"""
    
    print(f"\nPrompt:\n{prompt}\n")
    
    response = llm_engine.generate(prompt)
    print(f"Response:\n{response}\n")
    return response

def main():
    """Run all tests"""
    print("\n🚀 Starting Ollama + Typhoon 2.5 Integration Tests\n")
    print(f"Model: {os.getenv('LLM_MODEL')}")
    print(f"Ollama URL: {os.getenv('OLLAMA_BASE_URL')}")
    print(f"Provider: {os.getenv('LLM_PROVIDER')}\n")
    
    try:
        # Run all tests
        test_simple_prompt()
        input("Press Enter to continue to next test...")
        
        test_chat_messages()
        input("Press Enter to continue to next test...")
        
        test_thai_english_mix()
        input("Press Enter to continue to next test...")
        
        test_rag_context()
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Ollama is running: ollama serve")
        print("2. Make sure the model is pulled: ollama pull scb10x/typhoon2.5-qwen3-30b-a3b")
        print("3. Check Ollama status: curl http://localhost:11434")
        sys.exit(1)

if __name__ == "__main__":
    main()
