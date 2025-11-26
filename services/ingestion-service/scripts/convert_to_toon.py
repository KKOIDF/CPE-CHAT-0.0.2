"""
Script to convert existing JSONL data files to TOON format
Usage: python convert_to_toon.py
"""

import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.toon_converter import jsonl_to_toon, json_to_toon


def main():
    # Define data directories - check both ingestion service data and root data
    ingestion_data_dir = Path(__file__).parent.parent / 'data' / 'db'
    root_data_dir = Path(__file__).parent.parent.parent.parent / 'data' / 'db'
    
    # Use root data dir if it exists, otherwise ingestion service data dir
    if root_data_dir.exists():
        data_dir = root_data_dir
        print(f"Using root data directory: {data_dir}")
    else:
        data_dir = ingestion_data_dir
        print(f"Using ingestion service data directory: {data_dir}")
    
    # Files to convert
    files_to_convert = [
        ('chunks.jsonl', 'chunks.toon'),
        ('records.jsonl', 'records.toon'),
    ]
    
    print("=" * 60)
    print("Converting JSONL files to TOON format")
    print("=" * 60)
    
    for jsonl_file, toon_file in files_to_convert:
        jsonl_path = data_dir / jsonl_file
        toon_path = data_dir / toon_file
        
        if jsonl_path.exists():
            print(f"\n📄 Converting {jsonl_file}...")
            try:
                # Convert with a reasonable limit for demonstration
                count = jsonl_to_toon(str(jsonl_path), str(toon_path), max_records=100)
                
                # Show file sizes
                jsonl_size = jsonl_path.stat().st_size
                toon_size = toon_path.stat().st_size
                compression = (1 - toon_size / jsonl_size) * 100 if jsonl_size > 0 else 0
                
                print(f"   ✅ Converted {count} records")
                print(f"   📊 Original size: {jsonl_size:,} bytes")
                print(f"   📊 TOON size: {toon_size:,} bytes")
                print(f"   💾 Size reduction: {compression:.1f}%")
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
        else:
            print(f"\n⚠️  {jsonl_file} not found, skipping...")
    
    # Also check for review flagged files
    review_dir = data_dir / 'review'
    if review_dir.exists():
        print(f"\n📁 Checking review directory...")
        flagged_files = list(review_dir.glob('flagged_*.jsonl'))
        if flagged_files:
            print(f"   Found {len(flagged_files)} flagged files")
            for flagged_file in flagged_files[:3]:  # Convert first 3
                toon_file = flagged_file.with_suffix('.toon')
                print(f"   Converting {flagged_file.name}...")
                try:
                    jsonl_to_toon(str(flagged_file), str(toon_file), max_records=50)
                    print(f"      ✅ Done")
                except Exception as e:
                    print(f"      ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("✨ Conversion complete!")
    print("=" * 60)
    print("\nTOON files are more compact and human-readable.")
    print("You can now use --use-toon flag with ingestion service.")


if __name__ == '__main__':
    main()
