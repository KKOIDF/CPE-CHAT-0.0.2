#!/usr/bin/env python3
"""Check curriculum database schema."""
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
    
    # Check what tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    if not tables:
        print("❌ NO TABLES FOUND IN DATABASE - DATABASE IS EMPTY!")
        print("\nThe curriculum database was created but never populated.")
        print("The 'docs' table doesn't exist, so retrieval will fail.")
        sys.exit(1)
    
    print(f"📊 Tables in database:")
    for (table,) in tables:
        cursor.execute(f"SELECT COUNT(*) FROM '{table}'")
        count = cursor.fetchone()[0]
        print(f"   - {table}: {count} rows")
    
    conn.close()
    
    print("\n⚠️  DIAGNOSIS: Curriculum table exists but docs table is missing.")
    print("    → Need to re-ingest curriculum data")
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
