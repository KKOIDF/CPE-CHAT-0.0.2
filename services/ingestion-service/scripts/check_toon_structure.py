#!/usr/bin/env python
"""Check TOON file structure"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.toon_converter import read_toon

chunks_path = Path(__file__).parent.parent / 'data' / 'db' / 'chunks.toon'
if not chunks_path.exists():
    chunks_path = Path(__file__).parent.parent.parent.parent / 'data' / 'db' / 'chunks.toon'

print(f"Reading: {chunks_path}")
data = read_toon(str(chunks_path))

print(f"\nType: {type(data)}")

if isinstance(data, dict):
    print(f"Keys: {list(data.keys())}")
    for k, v in data.items():
        print(f"  {k}: {type(v)} - length {len(v) if hasattr(v, '__len__') else 'N/A'}")
        if isinstance(v, list) and len(v) > 0:
            print(f"    First item type: {type(v[0])}")
            if isinstance(v[0], dict):
                print(f"    First item keys: {list(v[0].keys())[:5]}")
elif isinstance(data, list):
    print(f"List length: {len(data)}")
    if len(data) > 0:
        print(f"First item type: {type(data[0])}")
        if isinstance(data[0], dict):
            print(f"First item keys: {list(data[0].keys())}")

print(f"\nFirst 500 chars of raw data:\n{str(data)[:500]}")
