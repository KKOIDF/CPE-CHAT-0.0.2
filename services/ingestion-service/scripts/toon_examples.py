"""
Example demonstrating TOON format usage
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.toon_format import dumps, loads


def example_chunk_data():
    """Example of chunk data structure"""
    return {
        "doc_id": "5dd2f46650dba3aa604b2439416effbe",
        "source": "129.txt",
        "path": "C:\\Users\\KritChaJ\\OneDrive\\Documents\\CPE CHAT 0.0.2\\data\\raw_files\\129.pdf",
        "file_type": "pdf",
        "page_start": 1,
        "page_end": 2,
        "chunk_id": 0,
        "status": "ok",
        "owner": "owner:unknown",
        "sensitivity": "internal",
        "updated_at": 1764000977,
        "tokens_est": 822,
        "text": "ระเบียบสถาบันเทคโนโลยีพระจอมเกล้าธนบุรี..."
    }


def example_structured_array():
    """Example of structured array (like the hiking example)"""
    return {
        "context": {
            "task": "Our favorite hikes together",
            "location": "Boulder",
            "season": "spring_2025"
        },
        "friends": ["ana", "luis", "sam"],
        "hikes": [
            {"id": 1, "name": "Blue Lake Trail", "distanceKm": 7.5, "elevationGain": 320, "companion": "ana", "wasSunny": True},
            {"id": 2, "name": "Ridge Overlook", "distanceKm": 9.2, "elevationGain": 540, "companion": "luis", "wasSunny": False},
            {"id": 3, "name": "Wildflower Loop", "distanceKm": 5.1, "elevationGain": 180, "companion": "sam", "wasSunny": True}
        ]
    }


def main():
    print("=" * 70)
    print("TOON Format Examples")
    print("=" * 70)
    
    # Example 1: Hiking data
    print("\n📝 Example 1: Hiking Trip Data")
    print("-" * 70)
    hiking_data = example_structured_array()
    toon_str = dumps(hiking_data)
    print(toon_str)
    
    # Example 2: Document chunk
    print("\n\n📝 Example 2: Document Chunk Data")
    print("-" * 70)
    chunk_data = example_chunk_data()
    toon_str = dumps(chunk_data)
    print(toon_str)
    
    # Example 3: Parse back
    print("\n\n🔄 Example 3: Round-trip conversion")
    print("-" * 70)
    original = {"name": "Test", "value": 42, "items": ["a", "b", "c"]}
    print(f"Original Python dict: {original}")
    
    toon = dumps(original)
    print(f"\nTOON format:\n{toon}")
    
    parsed = loads(toon)
    print(f"\nParsed back to Python: {parsed}")
    print(f"\nData integrity check: {original == parsed}")
    
    # Example 4: Space efficiency comparison
    print("\n\n💾 Example 4: Space Efficiency")
    print("-" * 70)
    import json
    
    data = {
        "documents": [
            {"id": i, "title": f"Doc {i}", "score": 0.95 - i * 0.01}
            for i in range(5)
        ]
    }
    
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    toon_str = dumps(data)
    
    print(f"JSON size: {len(json_str)} characters")
    print(f"TOON size: {len(toon_str)} characters")
    print(f"Space saved: {(1 - len(toon_str) / len(json_str)) * 100:.1f}%")
    
    print("\nJSON output:")
    print(json_str)
    
    print("\nTOON output:")
    print(toon_str)
    
    print("\n" + "=" * 70)
    print("✨ TOON format is more compact and human-readable!")
    print("=" * 70)


if __name__ == '__main__':
    main()
