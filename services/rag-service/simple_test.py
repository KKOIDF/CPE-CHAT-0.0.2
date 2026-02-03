"""
Simple RAG query test - run specific questions and show results
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.rag_logic import rag_query

def test_query(question: str):
    """ทดสอบคำถามและแสดงผลลัพธ์"""
    print("\n" + "="*80)
    print(f"❓ คำถาม: {question}")
    print("="*80)
    
    try:
        result = rag_query(question)
        
        print(f"\n📊 สรุปผลลัพธ์:")
        print(f"   - จำนวน contexts ที่พบ: {len(result['contexts'])}")
        print(f"   - Token estimate: {result['token_est']}")
        
        print(f"\n📚 เอกสารที่เกี่ยวข้อง (Top 5):")
        for i, ctx in enumerate(result['contexts'][:5], 1):
            source = ctx.get('source', 'N/A')
            page = ctx.get('page_start', 'N/A')
            score = ctx.get('score_rrf', 0)
            print(f"   {i}. [{source}] หน้า {page} | score: {score:.4f}")
        
        # แสดง prompt ที่จะส่งให้ LLM (ส่วนหัว)
        print(f"\n📝 Prompt สำหรับ LLM (ตัวอย่าง 500 ตัวอักษรแรก):")
        print("-"*80)
        print(result['prompt'][:500])
        print("...\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n🧪 RAG Query Test Tool")
    print("="*80)
    
    # ตัวอย่างคำถามสำหรับทดสอบ
    test_questions = [
        "วิศวกรรมคอมพิวเตอร์คืออะไร",
        "หลักสูตรวิศวกรรมคอมพิวเตอร์มีอะไรบ้าง",
        "เกณฑ์การสำเร็จการศึกษา",
        "การถอนรายวิชาทำอย่างไร",
        "อาจารย์ประจำหลักสูตร",
    ]
    
    print(f"\nพบคำถามตัวอย่าง {len(test_questions)} คำถาม:")
    for i, q in enumerate(test_questions, 1):
        print(f"  {i}. {q}")
    
    print("\n" + "="*80)
    choice = input("เลือกหมายเลขคำถาม (1-5) หรือพิมพ์คำถามของคุณเอง: ").strip()
    
    if choice.isdigit() and 1 <= int(choice) <= len(test_questions):
        question = test_questions[int(choice) - 1]
    elif choice:
        question = choice
    else:
        print("ไม่ได้เลือกคำถาม - ใช้คำถามแรกเป็นตัวอย่าง")
        question = test_questions[0]
    
    test_query(question)
    
    # ถามต่อ
    while True:
        print("\n" + "="*80)
        next_q = input("ถามคำถามอื่นต่อ (หรือกด Enter เพื่อจบ): ").strip()
        if not next_q:
            print("\n✅ จบการทดสอบ")
            break
        test_query(next_q)

if __name__ == "__main__":
    main()
