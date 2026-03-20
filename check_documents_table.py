#!/usr/bin/env python3
"""Check curriculum documents for course codes."""
import sqlite3
import sys
from pathlib import Path

db_path = Path('/home/testuser/CPE-CHAT-0.0.2/indexes/curriculum/vector/sqlite/ingestion.db')

try:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Check total documents
    cursor.execute("SELECT COUNT(*) FROM documents")
    total = cursor.fetchone()[0]
    print(f"📊 Total documents in 'documents' table: {total}")
    
    # Check for specific course codes
    codes = ['CPE 342', 'CPE342', 'cpe 342', 'cpe342', 'LNG 220', 'GEN 121', 'CPE', 'LNG', 'GEN']
    print("\n🔍 Searching for course codes:")
    for code in codes:
        cursor.execute("SELECT COUNT(*) FROM documents WHERE text LIKE ?", (f'%{code}%',))
        count = cursor.fetchone()[0]
        status = "✓" if count > 0 else "✗"
        print(f"   {status} '{code}': {count} documents")
    
    # Get sample of what document content looks like
    print("\n📄 Sample document content (first 500 chars):")
    cursor.execute("SELECT substr(text, 1, 500) FROM documents LIMIT 1")
    sample = cursor.fetchone()
    if sample:
        print(f"   {sample[0][:300]}...")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
