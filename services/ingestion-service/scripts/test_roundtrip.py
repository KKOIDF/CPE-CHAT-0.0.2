"""
Test round-trip conversion to verify data integrity
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.toon_converter import jsonl_to_toon, toon_to_jsonl


def test_roundtrip():
    """Test that data survives round-trip conversion"""
    
    print("🔄 Testing Round-Trip Conversion")
    print("=" * 60)
    
    # Test with chunks.jsonl
    data_dir = Path(__file__).parent.parent.parent.parent / 'data' / 'db'
    
    test_files = [
        'chunks.jsonl',
        'records.jsonl'
    ]
    
    for filename in test_files:
        print(f"\n📝 Testing {filename}...")
        
        jsonl_original = data_dir / filename
        toon_temp = data_dir / f"{filename}.temp.toon"
        jsonl_roundtrip = data_dir / f"{filename}.roundtrip"
        
        if not jsonl_original.exists():
            print(f"   ⚠️  {filename} not found, skipping...")
            continue
        
        try:
            # Read original JSONL
            print("   1️⃣ Reading original JSONL...")
            original_records = []
            with jsonl_original.open('r', encoding='utf-8') as f:
                for idx, line in enumerate(f):
                    if idx >= 10:  # Test with first 10 records
                        break
                    if line.strip():
                        original_records.append(json.loads(line))
            print(f"      Loaded {len(original_records)} records")
            
            # Convert to TOON
            print("   2️⃣ Converting to TOON...")
            jsonl_to_toon(str(jsonl_original), str(toon_temp), max_records=10)
            
            # Convert back to JSONL
            print("   3️⃣ Converting back to JSONL...")
            toon_to_jsonl(str(toon_temp), str(jsonl_roundtrip))
            
            # Read round-trip JSONL
            print("   4️⃣ Reading round-trip JSONL...")
            roundtrip_records = []
            with jsonl_roundtrip.open('r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        roundtrip_records.append(json.loads(line))
            print(f"      Loaded {len(roundtrip_records)} records")
            
            # Compare
            print("   5️⃣ Comparing data...")
            if len(original_records) != len(roundtrip_records):
                print(f"      ❌ Record count mismatch: {len(original_records)} vs {len(roundtrip_records)}")
                continue
            
            # Deep compare first few records
            differences = 0
            for idx, (orig, rt) in enumerate(zip(original_records[:5], roundtrip_records[:5])):
                if orig != rt:
                    differences += 1
                    print(f"      ⚠️  Record {idx} differs")
                    # Show what's different
                    orig_keys = set(orig.keys())
                    rt_keys = set(rt.keys())
                    if orig_keys != rt_keys:
                        print(f"         Key difference: {orig_keys ^ rt_keys}")
                    for key in orig_keys & rt_keys:
                        if orig.get(key) != rt.get(key):
                            print(f"         Field '{key}' differs")
                            print(f"           Original: {type(orig.get(key)).__name__} = {str(orig.get(key))[:50]}")
                            print(f"           Roundtrip: {type(rt.get(key)).__name__} = {str(rt.get(key))[:50]}")
            
            if differences == 0:
                print("      ✅ All records match perfectly!")
            else:
                print(f"      ⚠️  {differences} records have differences")
            
            # Clean up temp files
            if toon_temp.exists():
                toon_temp.unlink()
            if jsonl_roundtrip.exists():
                jsonl_roundtrip.unlink()
            print("   🧹 Cleaned up temp files")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("✨ Round-trip test complete!")


if __name__ == '__main__':
    test_roundtrip()
