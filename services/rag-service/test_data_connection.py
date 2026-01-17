"""Test script to verify RAG service can access per-domain indexes.

Usage:
    python test_data_connection.py --domain announcements
    python test_data_connection.py --domain regulations
    python test_data_connection.py --domain curriculum

If --domain is omitted, it uses CPE_DOMAIN env (or legacy defaults).
"""
import sys
from pathlib import Path
import argparse

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import DATA_DIR, CHROMA_DIR, SQLITE_PATH, domain_paths
from app.sqlite_client import get_conn, keyword_search, domain_sqlite_path
from app.chroma_client import semantic_search_domain


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--domain', default=None, help='announcements|regulations|curriculum')
    return p.parse_args()

def test_paths(domain: str | None):
    print("=" * 60)
    print("📍 ตรวจสอบตำแหน่งข้อมูล")
    print("=" * 60)
    chroma_dir, sqlite_path = domain_paths(domain)
    print(f"Domain:       {domain}")
    print(f"DATA_DIR:     {DATA_DIR} (legacy)")
    print(f"CHROMA_DIR:   {chroma_dir}")
    print(f"SQLITE_PATH:  {sqlite_path}")
    print()
    
    print(f"✓ DATA_DIR exists:    {DATA_DIR.exists()}")
    print(f"✓ CHROMA_DIR exists:  {Path(chroma_dir).exists()}")
    print(f"✓ SQLITE_PATH exists: {Path(sqlite_path).exists()}")
    print()

def test_sqlite(domain: str | None):
    print("=" * 60)
    print("🗄️ ทดสอบการเชื่อมต่อ SQLite")
    print("=" * 60)
    try:
        sqlite_path = domain_sqlite_path(domain) if domain else None
        conn = get_conn(sqlite_path)
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        print(f"Tables found: {tables}")

        if 'documents' not in tables:
            print("⚠️ SQLite ยังไม่ได้ถูก init/ingest สำหรับโดเมนนี้ (ยังไม่มีตาราง documents)")
            conn.close()
            return
        
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

def test_chroma(domain: str | None):
    print("=" * 60)
    print("🔍 ทดสอบการเชื่อมต่อ Chroma")
    print("=" * 60)
    try:
        # Try a simple semantic search
        results = semantic_search_domain("ทดสอบ", top_k=3, domain=domain)
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

def test_keyword_search(domain: str | None):
    print("=" * 60)
    print("🔎 ทดสอบ Keyword Search")
    print("=" * 60)
    try:
        sqlite_path = domain_sqlite_path(domain) if domain else None
        results = keyword_search("วิศวกรรม", limit=5, sqlite_path=sqlite_path)
        print(f"Keyword search results: {len(results)} document IDs found")
        
        if results:
            print("ตัวอย่าง doc_ids:", results[:5])
        
        print("✅ Keyword search: OK")
    except Exception as e:
        print(f"❌ Keyword search failed: {e}")
    print()

def main():
    args = parse_args()
    dom = args.domain
    print("\n🚀 ทดสอบการเชื่อมต่อข้อมูล RAG Service\n")
    
    test_paths(dom)
    test_sqlite(dom)
    test_chroma(dom)
    test_keyword_search(dom)
    
    print("=" * 60)
    print("✅ การทดสอบเสร็จสิ้น")
    print("=" * 60)

if __name__ == "__main__":
    main()
