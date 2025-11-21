"""
Test script to verify RAG service can access data from ingestion-service/data
"""
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import DATA_DIR, CHROMA_DIR, SQLITE_PATH
from app.sqlite_client import get_conn, keyword_search
from app.chroma_client import semantic_search

def test_paths():
    print("=" * 60)
    print("📍 ตรวจสอบตำแหน่งข้อมูล")
    print("=" * 60)
    print(f"DATA_DIR:     {DATA_DIR}")
    print(f"CHROMA_DIR:   {CHROMA_DIR}")
    print(f"SQLITE_PATH:  {SQLITE_PATH}")
    print()
    
    print(f"✓ DATA_DIR exists:    {DATA_DIR.exists()}")
    print(f"✓ CHROMA_DIR exists:  {CHROMA_DIR.exists()}")
    print(f"✓ SQLITE_PATH exists: {SQLITE_PATH.exists()}")
    print()

def test_sqlite():
    print("=" * 60)
    print("🗄️ ทดสอบการเชื่อมต่อ SQLite")
    print("=" * 60)
    try:
        conn = get_conn()
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        print(f"Tables found: {tables}")
        
        # Count documents
        cur = conn.execute("SELECT COUNT(*) FROM documents")
        doc_count = cur.fetchone()[0]
        print(f"Total documents: {doc_count}")
        
        # Show sample
        if doc_count > 0:
            cur = conn.execute("SELECT doc_id, source, page_start FROM documents LIMIT 3")
            print("\nตัวอย่างเอกสาร:")
            for row in cur.fetchall():
                print(f"  - {row[0]} | {row[1]} | page {row[2]}")
        
        conn.close()
        print("✅ SQLite connection: OK")
    except Exception as e:
        print(f"❌ SQLite connection failed: {e}")
    print()

def test_chroma():
    print("=" * 60)
    print("🔍 ทดสอบการเชื่อมต่อ Chroma")
    print("=" * 60)
    try:
        # Try a simple semantic search
        results = semantic_search("ทดสอบ", top_k=3)
        print(f"Vector search results: {len(results)} chunks found")
        
        if results:
            print("\nตัวอย่างผลลัพธ์:")
            for i, r in enumerate(results[:3], 1):
                text_preview = r.get('text', '')[:100]
                print(f"  {i}. {r.get('doc_id')} - {text_preview}...")
        
        print("✅ Chroma connection: OK")
    except Exception as e:
        print(f"❌ Chroma connection failed: {e}")
    print()

def test_keyword_search():
    print("=" * 60)
    print("🔎 ทดสอบ Keyword Search")
    print("=" * 60)
    try:
        results = keyword_search("วิศวกรรม", limit=5)
        print(f"Keyword search results: {len(results)} document IDs found")
        
        if results:
            print("ตัวอย่าง doc_ids:", results[:5])
        
        print("✅ Keyword search: OK")
    except Exception as e:
        print(f"❌ Keyword search failed: {e}")
    print()

def main():
    print("\n🚀 ทดสอบการเชื่อมต่อข้อมูล RAG Service\n")
    
    test_paths()
    test_sqlite()
    test_chroma()
    test_keyword_search()
    
    print("=" * 60)
    print("✅ การทดสอบเสร็จสิ้น")
    print("=" * 60)

if __name__ == "__main__":
    main()
