"""
Test script to query RAG system with sample questions
"""
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.rag_logic import rag_query

def print_separator(char="=", length=70):
    print(char * length)

def print_section(title):
    print("\n")
    print_separator()
    print(f"  {title}")
    print_separator()

def test_single_query(question: str, show_full_context: bool = False):
    """ทดสอบคำถามเดียว"""
    print_section(f"❓ คำถาม: {question}")
    
    try:
        result = rag_query(question)
        
        # แสดงข้อมูลสรุป
        print(f"\n📊 สรุป:")
        print(f"   - จำนวน contexts: {len(result['contexts'])}")
        print(f"   - Token estimate: {result['token_est']}")
        
        # แสดง contexts ที่เกี่ยวข้อง
        print(f"\n📚 เอกสารที่เกี่ยวข้อง (Top 5):")
        for i, ctx in enumerate(result['contexts'][:5], 1):
            source = ctx.get('source', 'N/A')
            page = ctx.get('page_start', 'N/A')
            score = ctx.get('score_rrf', 0)
            print(f"   {i}. [{source}] หน้า {page} (score: {score:.4f})")
        
        # แสดง context ที่ใช้
        if show_full_context:
            print(f"\n📝 Context ที่จะส่งให้ LLM:")
            print("-" * 70)
            # แสดงเฉพาะส่วนหนึ่งของ prompt (ไม่ใช่ทั้งหมด)
            prompt_lines = result['prompt'].split('\n')
            for line in prompt_lines[:30]:  # แสดง 30 บรรทัดแรก
                print(line)
            if len(prompt_lines) > 30:
                print(f"... (และอีก {len(prompt_lines) - 30} บรรทัด)")
        else:
            # แสดงตัวอย่างข้อความจาก context
            prompt_lines = result['prompt'].split('\n')
            context_start = False
            context_lines = []
            for line in prompt_lines:
                if line.startswith('บริบท:'):
                    context_start = True
                    continue
                if context_start and line.startswith('อ้างอิง:'):
                    break
                if context_start and line.strip():
                    context_lines.append(line)
            
            if context_lines:
                print(f"\n📄 ตัวอย่างข้อความจาก Context:")
                print("-" * 70)
                for line in context_lines[:10]:  # แสดง 10 บรรทัดแรก
                    print(line[:150])  # ตัดที่ 150 ตัวอักษร
                if len(context_lines) > 10:
                    print(f"... (และอีก {len(context_lines) - 10} บรรทัด)")
        
        print("\n" + "=" * 70)
        return result
        
    except Exception as e:
        print(f"\n❌ เกิดข้อผิดพลาด: {e}")
        import traceback
        traceback.print_exc()
        return None

def interactive_mode():
    """โหมดถาม-ตอบแบบ interactive"""
    print_section("🤖 โหมดทดสอบ RAG แบบ Interactive")
    print("\nพิมพ์คำถาม (หรือพิมพ์ 'quit' เพื่อออก)")
    print("พิมพ์ 'full' เพื่อดู full context, 'short' เพื่อดูแบบย่อ")
    print_separator("-")
    
    show_full = False
    
    while True:
        try:
            user_input = input("\n❓ คำถาม: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 ขอบคุณที่ใช้งาน!")
                break
            
            if user_input.lower() == 'full':
                show_full = True
                print("✓ เปลี่ยนเป็นโหมดแสดง full context")
                continue
            
            if user_input.lower() == 'short':
                show_full = False
                print("✓ เปลี่ยนเป็นโหมดแสดงแบบย่อ")
                continue
            
            if not user_input:
                continue
            
            test_single_query(user_input, show_full_context=show_full)
            
        except KeyboardInterrupt:
            print("\n\n👋 ขอบคุณที่ใช้งาน!")
            break
        except Exception as e:
            print(f"\n❌ เกิดข้อผิดพลาด: {e}")

def run_sample_queries():
    """รันตัวอย่างคำถามหลายๆ คำถาม"""
    print_section("🧪 ทดสอบด้วยคำถามตัวอย่าง")
    
    sample_questions = [
        "วิศวกรรมคอมพิวเตอร์คืออะไร",
        "หลักสูตรวิศวกรรมคอมพิวเตอร์มีอะไรบ้าง",
        "เกณฑ์การสำเร็จการศึกษา",
        "วิชาบังคับในหลักสูตร",
        "คณะวิศวกรรมศาสตร์ มีอะไรบ้าง",
    ]
    
    for i, question in enumerate(sample_questions, 1):
        print(f"\n\n{'='*70}")
        print(f"ตัวอย่างที่ {i}/{len(sample_questions)}")
        test_single_query(question, show_full_context=False)
        
        if i < len(sample_questions):
            input("\nกด Enter เพื่อดำเนินการต่อ...")

def main():
    """Main function"""
    print("\n" + "="*70)
    print("🧪 RAG Query Testing Tool")
    print("="*70)
    
    print("\nเลือกโหมด:")
    print("1. ทดสอบด้วยคำถามตัวอย่าง")
    print("2. โหมด Interactive (ถาม-ตอบเอง)")
    print("3. ทดสอบคำถามเดียว (quick test)")
    
    choice = input("\nเลือก (1-3): ").strip()
    
    if choice == "1":
        run_sample_queries()
    elif choice == "2":
        interactive_mode()
    elif choice == "3":
        question = input("พิมพ์คำถาม: ").strip()
        if question:
            test_single_query(question, show_full_context=True)
    else:
        print("ตัวเลือกไม่ถูกต้อง")

if __name__ == "__main__":
    main()
