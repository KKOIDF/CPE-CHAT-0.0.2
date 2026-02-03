#!/usr/bin/env python
"""
Test Thai tokenization quality with different engines
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils import tokenize_thai_words, segment_sentences_thai, clean_and_spell_correct_thai
from app.toon_converter import read_toon

# Test samples
THAI_SAMPLES = [
    "การรับสมัครนักศึกษาใหม่จะเริ่มในเดือนมีนาคม นักศึกษาต้องส่งเอกสารภายในวันที่กำหนด",
    "คณะวิศวกรรมศาสตร์มีหลักสูตรหลายสาขา ได้แก่ วิศวกรรมคอมพิวเตอร์ วิศวกรรมไฟฟ้า และวิศวกรรมโยธา",
    "ข้อกำหนดการสอบ: นักศึกษาต้องมีเวลาเรียนไม่ต่ำกว่า 80% และส่งงานครบทุกครั้ง"
]


def test_word_tokenizers():
    """Test different word tokenizers"""
    print("=" * 80)
    print("WORD TOKENIZATION COMPARISON")
    print("=" * 80)
    
    engines = ['newmm', 'attacut', 'longest']
    
    for i, text in enumerate(THAI_SAMPLES, 1):
        print(f"\n[Sample {i}] {text[:60]}...")
        print("-" * 80)
        
        for engine in engines:
            try:
                tokens = tokenize_thai_words(text, engine=engine)
                print(f"{engine:12} ({len(tokens):2} words): {' | '.join(tokens)}")
            except Exception as e:
                print(f"{engine:12} ERROR: {e}")
        print()


def test_sentence_tokenizers():
    """Test different sentence tokenizers"""
    print("\n" + "=" * 80)
    print("SENTENCE TOKENIZATION COMPARISON")
    print("=" * 80)
    
    engines = ['crfcut', 'tltk']
    
    for i, text in enumerate(THAI_SAMPLES, 1):
        print(f"\n[Sample {i}] {text}")
        print("-" * 80)
        
        for engine in engines:
            try:
                sents = segment_sentences_thai(text, engine=engine)
                print(f"{engine:12} ({len(sents):2} sents):")
                for j, s in enumerate(sents, 1):
                    print(f"  {j}. {s}")
            except Exception as e:
                print(f"{engine:12} ERROR: {e}")
        print()


def test_with_real_chunks():
    """Test tokenization with real data from chunks.toon"""
    print("\n" + "=" * 80)
    print("REAL DATA TOKENIZATION TEST (from chunks.toon)")
    print("=" * 80)
    
    # Try multiple paths
    base_paths = [
        Path(__file__).parent.parent.parent.parent / 'data' / 'db' / 'chunks.toon',
        Path(__file__).parent.parent / 'data' / 'db' / 'chunks.toon',
    ]
    
    chunks_path = None
    for p in base_paths:
        if p.exists():
            chunks_path = p
            break
    
    if not chunks_path:
        print(f"chunks.toon not found in any of:")
        for p in base_paths:
            print(f"  - {p}")
        return
    
    try:
        print(f"Reading from: {chunks_path}")
        data = read_toon(str(chunks_path))
        
        # Handle different data structures
        if isinstance(data, dict):
            chunks = data.get('chunks', data.get('data', []))
        else:
            chunks = data if isinstance(data, list) else []
        
        print(f"Found {len(chunks)} chunks")
        
        if not chunks:
            print("No chunks data found in file")
            return
        
        # Test first 3 chunks
        for i, chunk in enumerate(chunks[:3], 1):
            text = chunk.get('text', '')[:200]  # First 200 chars
            if not text:
                continue
            
            print(f"\n[Chunk {i}] {text}...")
            print("-" * 80)
            
            # Test word tokenization
            print("\nWord Tokenization:")
            for engine in ['newmm', 'attacut']:
                try:
                    tokens = tokenize_thai_words(text, engine=engine)
                    print(f"  {engine:12}: {len(tokens):3} words")
                    print(f"    Sample: {' | '.join(tokens[:10])}...")
                except Exception as e:
                    print(f"  {engine:12}: ERROR - {e}")
            
            # Test sentence tokenization
            print("\nSentence Tokenization:")
            for engine in ['crfcut', 'tltk']:
                try:
                    sents = segment_sentences_thai(text, engine=engine)
                    print(f"  {engine:12}: {len(sents):2} sentences")
                    for j, s in enumerate(sents[:2], 1):
                        print(f"    {j}. {s[:80]}...")
                except Exception as e:
                    print(f"  {engine:12}: ERROR - {e}")
            
            print()
    
    except Exception as e:
        print(f"ERROR reading chunks.toon: {e}")


def test_clean_and_spell():
    print("\n" + "=" * 80)
    print("THAI CLEAN + SPELL CORRECTION")
    print("=" * 80)
    samples = [
        "อยากใช้ pythainlp ตรวจคำผิดแล้วค่อยทำ embadding ดีมั้ยยย",
        "รุ่นใหมมม่นี้เปิดตัววว 10/12/2025 ที่ www.example.com !!!",
        "ราคาประมาณ 12,345.67 บาท นะครับบบ",
    ]
    for s in samples:
        cleaned = clean_and_spell_correct_thai(s, custom_map={"embadding": "embedding"})
        print(f"RAW   : {s}")
        print(f"CLEAN : {cleaned}")
        print("-" * 80)


def main():
    print("\n🔍 Thai Tokenization Quality Test\n")
    
    test_word_tokenizers()
    test_sentence_tokenizers()
    test_with_real_chunks()
    test_clean_and_spell()
    
    print("\n" + "=" * 80)
    print("✅ RECOMMENDATIONS:")
    print("=" * 80)
    print("""
    Word Tokenizer:
    - 'attacut'  : Best accuracy for modern Thai text (recommended for CPE content)
    - 'longest'  : Good for formal/academic text with technical terms
    - 'newmm'    : Fast, good baseline
    
    Sentence Tokenizer:
    - 'crfcut'   : Best for Thai academic text (recommended)
    - 'tltk'     : Better for mixed Thai/English content
    
    Set in environment:
        THAI_WORD_TOKENIZER=attacut
        THAI_SENT_TOKENIZER=crfcut
    """)


if __name__ == '__main__':
    main()
