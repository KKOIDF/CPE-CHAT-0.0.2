#!/usr/bin/env python3
"""Check curriculum database for course codes."""
import sqlite3
import sys
from pathlib import Path

db_path = Path('/home/testuser/CPE-CHAT-0.0.2/indexes/curriculum/vector/sqlite/ingestion.db')

if not db_path.exists():
    print(f"❌ Database not found: {db_path}")
    sys.exit(1)

try:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Check total documents
    cursor.execute("SELECT COUNT(*) FROM docs")
    total = cursor.fetchone()[0]
    print(f"📊 Total documents: {total}")
    
    # Check for specific course codes
    codes = ['CPE 342', 'CPE342', 'cpe 342', 'cpe342', 'LNG 220', 'GEN 121']
    for code in codes:
        cursor.execute("SELECT COUNT(*) FROM docs WHERE text LIKE ?", (f'%{code}%',))
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"✓ Found {count} documents with '{code}'")
        else:
            print(f"✗ No documents with '{code}'")
    
    # Sample text from first doc to see formatting
    print("\n📄 Sample document content:")
    cursor.execute("SELECT substr(text, 1, 300) FROM docs LIMIT 1")
    sample = cursor.fetchone()
    if sample:
        print(f"   {sample[0]}")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
