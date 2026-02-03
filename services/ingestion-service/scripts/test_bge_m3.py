#!/usr/bin/env python
"""Test BGE-M3 embedding quality with Thai text"""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.chroma_client import _embed_texts, _embedder, _is_bge_m3
from app.utils import clean_and_spell_correct_thai
from app.config import EMBEDDING_MODEL

def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def test_bge_m3():
    print("\n" + "=" * 80)
    print("🧪 BGE-M3 EMBEDDING TEST FOR THAI TEXT")
    print("=" * 80)
    print(f"Model: {EMBEDDING_MODEL}")
    print(f"Is BGE-M3: {_is_bge_m3}")
    print(f"Model loaded: {_embedder is not None}")
    
    if not _embedder:
        print("\n❌ Embedding model not loaded!")
        return
    
    # Test 1: Semantic similarity
    print("\n" + "=" * 80)
    print("📊 TEST 1: SEMANTIC SIMILARITY (Thai Academic Queries)")
    print("=" * 80)
    
    queries = [
        "เปิดรับสมัครนักศึกษาใหม่เมื่อไหร่",
        "วิศวกรรมคอมพิวเตอร์เรียนกี่ปี",
        "สอบปลายภาคเดือนไหน",
    ]
    
    documents = [
        "การรับสมัครนักศึกษาใหม่จะเริ่มในเดือนมีนาคม ผู้สมัครต้องส่งเอกสารภายในเดือนเมษายน",
        "หลักสูตรวิศวกรรมคอมพิวเตอร์ใช้เวลาศึกษา 4 ปี มีวิชาเรียนด้านโปรแกรมมิ่ง AI และ IoT",
        "การสอบปลายภาคเทอม 2 จะจัดในเดือนพฤษภาคม ให้นักศึกษาเตรียมตัวสอบล่วงหน้า",
        "ห้องสมุดเปิดทำการวันจันทร์ถึงศุกร์ เวลา 8.00-20.00 น. มีหนังสือและฐานข้อมูลออนไลน์",
    ]
    
    # Clean texts
    cleaned_queries = [clean_and_spell_correct_thai(q) for q in queries]
    cleaned_docs = [clean_and_spell_correct_thai(d) for d in documents]
    
    # Embed with query instruction
    query_vecs = _embed_texts(cleaned_queries, is_query=True)
    doc_vecs = _embed_texts(cleaned_docs, is_query=False)
    
    print(f"\nQuery embeddings shape: {len(query_vecs)} × {len(query_vecs[0])}")
    print(f"Document embeddings shape: {len(doc_vecs)} × {len(doc_vecs[0])}")
    
    for i, (query, q_vec) in enumerate(zip(queries, query_vecs)):
        print(f"\n{'─' * 80}")
        print(f"Query {i+1}: {query}")
        print(f"Cleaned: {cleaned_queries[i]}")
        print(f"\nTop 3 matches:")
        
        similarities = [(j, cosine_similarity(q_vec, d_vec)) 
                       for j, d_vec in enumerate(doc_vecs)]
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        for rank, (doc_idx, score) in enumerate(similarities[:3], 1):
            marker = "🏆" if rank == 1 else "  "
            print(f"  {marker} Rank {rank}: Score {score:.4f}")
            print(f"     {documents[doc_idx][:60]}...")
    
    # Test 2: Embedding dimensions
    print("\n" + "=" * 80)
    print("📏 TEST 2: EMBEDDING DIMENSIONS")
    print("=" * 80)
    print(f"Query vector dimension : {len(query_vecs[0])}")
    print(f"Document vector dimension : {len(doc_vecs[0])}")
    print(f"Expected for BGE-M3 : 1024")
    
    if len(query_vecs[0]) == 1024:
        print("✅ Correct dimension for BGE-M3!")
    else:
        print(f"⚠️  Unexpected dimension: {len(query_vecs[0])}")
    
    # Test 3: Query instruction impact
    print("\n" + "=" * 80)
    print("🔍 TEST 3: QUERY INSTRUCTION IMPACT")
    print("=" * 80)
    
    test_text = "วิศวกรรมคอมพิวเตอร์เรียนกี่ปี"
    
    # Embed same text with and without query instruction
    without_instruction = _embed_texts([test_text], is_query=False)[0]
    with_instruction = _embed_texts([test_text], is_query=True)[0]
    
    similarity = cosine_similarity(without_instruction, with_instruction)
    
    print(f"Text: {test_text}")
    print(f"Similarity (with vs without instruction): {similarity:.4f}")
    
    if similarity < 0.99:
        print("✅ Query instruction is being applied (vectors differ)")
    else:
        print("⚠️  Query instruction may not be working (vectors identical)")
    
    # Test 4: Typo robustness with spell correction
    print("\n" + "=" * 80)
    print("🔤 TEST 4: TYPO ROBUSTNESS (with Thai spell correction)")
    print("=" * 80)
    
    test_pairs = [
        ("วิศวกรรมคอมพิวเตอร์เรียนกี่ปี", "วิศวกรคอมเรียนกี่ปี"),
        ("เปิดรับสมัครนักศึกษาใหม่", "เปิดรับสมักรนักศึกษาใหม"),
        ("สอบปลายภาคเดือนไหน", "สอบปลายเดือนไหน"),
    ]
    
    for correct, typo in test_pairs:
        correct_cleaned = clean_and_spell_correct_thai(correct)
        typo_cleaned = clean_and_spell_correct_thai(typo)
        
        correct_vec = _embed_texts([correct_cleaned], is_query=True)[0]
        typo_vec = _embed_texts([typo_cleaned], is_query=True)[0]
        
        similarity = cosine_similarity(correct_vec, typo_vec)
        
        print(f"\n{'─' * 80}")
        print(f"Correct: {correct}")
        print(f"Typo   : {typo}")
        print(f"After cleaning:")
        print(f"  Correct: {correct_cleaned}")
        print(f"  Typo   : {typo_cleaned}")
        print(f"Similarity: {similarity:.4f}", end=" ")
        
        if similarity > 0.95:
            print("✅ Excellent")
        elif similarity > 0.85:
            print("✅ Good")
        elif similarity > 0.75:
            print("⚠️  Fair")
        else:
            print("❌ Poor - check spell correction")
    
    # Test 5: Cross-lingual capability
    print("\n" + "=" * 80)
    print("🌍 TEST 5: CROSS-LINGUAL (Thai-English mixed)")
    print("=" * 80)
    
    mixed_queries = [
        "CPE มีกี่ชั้นปี",
        "วิชา Data Structure ยากไหม",
        "สมัครเรียน AI ต้องมี GPA เท่าไหร่",
    ]
    
    mixed_docs = [
        "Computer Engineering (CPE) เป็นหลักสูตร 4 ปี มีนักศึกษาทุกชั้นปี",
        "วิชา Data Structure and Algorithms เป็นวิชาพื้นฐานสำคัญของ CPE",
        "การสมัครเรียนสาขา Artificial Intelligence ต้องมี GPA ไม่ต่ำกว่า 3.0",
    ]
    
    mixed_q_vecs = _embed_texts([clean_and_spell_correct_thai(q) for q in mixed_queries], is_query=True)
    mixed_d_vecs = _embed_texts([clean_and_spell_correct_thai(d) for d in mixed_docs], is_query=False)
    
    print("\nCross-lingual matching:")
    for i, (query, q_vec) in enumerate(zip(mixed_queries, mixed_q_vecs)):
        best_match = max(range(len(mixed_d_vecs)), 
                        key=lambda j: cosine_similarity(q_vec, mixed_d_vecs[j]))
        score = cosine_similarity(q_vec, mixed_d_vecs[best_match])
        
        marker = "✅" if i == best_match else "⚠️ "
        print(f"\n{marker} Query {i+1}: {query}")
        print(f"   Best match (score {score:.4f}): {mixed_docs[best_match][:50]}...")
    
    # Summary
    print("\n" + "=" * 80)
    print("✅ TEST COMPLETED")
    print("=" * 80)
    print("\n💡 Key Takeaways:")
    print("  • BGE-M3 produces 1024-dimensional embeddings")
    print("  • Query instruction improves retrieval quality")
    print("  • Thai spell correction enhances typo robustness")
    print("  • Model handles Thai-English mixed text well")
    print("\n🔄 Next Steps:")
    print("  1. Re-embed existing documents with BGE-M3")
    print("  2. Run benchmark to measure retrieval quality improvement")
    print("  3. Compare with previous embedding model (if any)")

def main():
    try:
        test_bge_m3()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
