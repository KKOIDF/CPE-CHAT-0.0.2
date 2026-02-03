"""
Quick RAG test - automatic test with sample questions
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
        
        print(f"\n📊 สรุป:")
        print(f"   ✓ จำนวน contexts: {len(result['contexts'])}")
        print(f"   ✓ Token estimate: {result['token_est']}")
        
        print(f"\n📚 เอกสารอ้างอิง (Top 5):")
        for i, ctx in enumerate(result['contexts'][:5], 1):
            source = ctx.get('source', 'N/A')
            page = ctx.get('page_start', 'N/A')
            score = ctx.get('score_rrf', 0)
            print(f"   {i}. {source} [หน้า {page}] - score: {score:.4f}")
        
        # แยก context จาก prompt
        lines = result['prompt'].split('\n')
        context_section = []
        in_context = False
        
        for line in lines:
            if 'บริบท:' in line:
                in_context = True
                continue
            if 'อ้างอิง:' in line:
                break
            if in_context and line.strip():
                context_section.append(line)
        
        if context_section:
            print(f"\n📄 ตัวอย่างข้อความจาก Context:")
            print("-"*80)
            # แสดง 5 บรรทัดแรก
            for line in context_section[:5]:
                preview = line[:120] + "..." if len(line) > 120 else line
                print(f"   {preview}")
            if len(context_section) > 5:
                print(f"   ... (อีก {len(context_section) - 5} บรรทัด)")
        
        print("\n✅ สำเร็จ")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

def main():
    print("\n" + "="*80)
    print("🧪 RAG QUERY TEST - Automatic Testing")
    print("="*80)
    
    # ชุดคำถามทดสอบ
    test_questions = [
        "วิศวกรรมคอมพิวเตอร์คืออะไร",
        "หลักสูตรวิศวกรรมคอมพิวเตอร์มีรายวิชาอะไรบ้าง",
        "เกณฑ์การสำเร็จการศึกษา",
        "วิธีการถอนรายวิชา",
    ]
    
    print(f"\nจะทดสอบ {len(test_questions)} คำถาม...\n")
    
    success_count = 0
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'#'*80}")
        print(f"# TEST {i}/{len(test_questions)}")
        print(f"{'#'*80}")
        
        if test_query(question):
            success_count += 1
        
        if i < len(test_questions):
            print("\n" + "-"*80)
            print("กำลังดำเนินการต่อ...")
            print("-"*80)
    
    # สรุปผล
    print("\n" + "="*80)
    print("📊 สรุปผลการทดสอบ")
    print("="*80)
    print(f"✅ สำเร็จ: {success_count}/{len(test_questions)}")
    print(f"❌ ล้มเหลว: {len(test_questions) - success_count}/{len(test_questions)}")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
