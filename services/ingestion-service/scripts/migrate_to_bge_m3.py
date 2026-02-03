#!/usr/bin/env python
"""
Migrate existing Chroma DB to BGE-M3 embeddings
⚠️  This will DELETE the old collection and re-embed all chunks
"""
import sys
import time
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.toon_converter import read_toon
from app.chroma_client import _client, _collection, upsert_chunks
from app.config import CHROMA_DIR, EMBEDDING_MODEL

def get_collection_stats():
    """Get current collection statistics"""
    try:
        count = _collection.count()
        return {
            'name': _collection.name,
            'count': count,
        }
    except Exception as e:
        return {'error': str(e)}

def load_chunks_from_toon(toon_path: Path) -> List[Dict]:
    """Load chunks from .toon file"""
    if not toon_path.exists():
        return []
    
    data = read_toon(str(toon_path))
    
    if isinstance(data, dict):
        chunks = data.get('chunks', data.get('data', []))
    else:
        chunks = data if isinstance(data, list) else []
    
    return chunks

def migrate_embeddings():
    """Re-embed all chunks with BGE-M3"""
    print("\n" + "=" * 80)
    print("🔄 MIGRATION TO BGE-M3 EMBEDDING MODEL")
    print("=" * 80)
    print(f"Model: {EMBEDDING_MODEL}")
    print(f"Chroma DB: {CHROMA_DIR}")
    
    # 1. Find chunks.toon files
    possible_paths = [
        Path(__file__).parent.parent.parent.parent / 'data' / 'db' / 'chunks.toon',
        Path(__file__).parent.parent / 'data' / 'db' / 'chunks.toon',
        Path(__file__).parent.parent / 'data' / 'db' / 'data_chunks.toon',
    ]
    
    chunks_path = None
    for p in possible_paths:
        if p.exists():
            chunks_path = p
            break
    
    if not chunks_path:
        print("\n❌ chunks.toon not found in any of:")
        for p in possible_paths:
            print(f"  • {p}")
        print("\n💡 Tip: Run ingestion first to create chunks.toon")
        return 1
    
    print(f"\n📖 Reading chunks from: {chunks_path}")
    chunks = load_chunks_from_toon(chunks_path)
    
    if not chunks:
        print("❌ No chunks found in file")
        return 1
    
    print(f"✅ Found {len(chunks)} chunks to re-embed")
    
    # 2. Show current collection stats
    print("\n" + "=" * 80)
    print("📊 CURRENT COLLECTION STATUS")
    print("=" * 80)
    stats = get_collection_stats()
    if 'error' in stats:
        print(f"⚠️  Could not get stats: {stats['error']}")
    else:
        print(f"Collection name: {stats.get('name', 'N/A')}")
        print(f"Document count : {stats.get('count', 0)}")
    
    # 3. Confirm migration
    print("\n" + "=" * 80)
    print("⚠️  WARNING")
    print("=" * 80)
    print("This will:")
    print("  1. DELETE the existing Chroma collection")
    print("  2. Re-embed all chunks with BGE-M3")
    print("  3. Create a new collection with new embeddings")
    print("\nThis process is IRREVERSIBLE!")
    
    response = input("\n❓ Continue with migration? Type 'yes' to proceed: ")
    if response.lower() != 'yes':
        print("❌ Migration cancelled by user")
        return 0
    
    # 4. Delete old collection
    print("\n" + "=" * 80)
    print("🗑️  DELETING OLD COLLECTION")
    print("=" * 80)
    
    try:
        _client.delete_collection(name='documents')
        print("✅ Old collection deleted successfully")
    except Exception as e:
        print(f"⚠️  Error deleting collection: {e}")
        print("   (This is OK if collection doesn't exist)")
    
    # Recreate collection
    try:
        global _collection
        from app import chroma_client
        chroma_client._collection = _client.get_or_create_collection(name="documents")
        print("✅ New collection created")
    except Exception as e:
        print(f"❌ Failed to create collection: {e}")
        return 1
    
    # 5. Re-embed with BGE-M3
    print("\n" + "=" * 80)
    print("🔄 RE-EMBEDDING WITH BGE-M3")
    print("=" * 80)
    
    batch_size = 50  # Smaller batches for large embeddings
    total_chunks = len(chunks)
    start_time = time.time()
    
    print(f"Total chunks: {total_chunks}")
    print(f"Batch size  : {batch_size}")
    print(f"Model       : {EMBEDDING_MODEL}")
    print("\nProgress:")
    
    failed_batches = []
    
    for i in range(0, total_chunks, batch_size):
        batch_num = i // batch_size + 1
        total_batches = (total_chunks + batch_size - 1) // batch_size
        batch = chunks[i:i + batch_size]
        
        try:
            upsert_chunks(batch)
            
            # Progress report
            elapsed = time.time() - start_time
            progress = min(i + batch_size, total_chunks)
            progress_pct = progress / total_chunks * 100
            rate = progress / elapsed if elapsed > 0 else 0
            eta = (total_chunks - progress) / rate if rate > 0 else 0
            
            print(f"  [{batch_num:3d}/{total_batches}] "
                  f"{progress:4d}/{total_chunks} chunks "
                  f"({progress_pct:5.1f}%) | "
                  f"{rate:5.1f} chunks/sec | "
                  f"ETA: {eta:5.0f}s")
        
        except Exception as e:
            print(f"  ❌ Batch {batch_num} failed: {e}")
            failed_batches.append(batch_num)
    
    # 6. Verify new collection
    print("\n" + "=" * 80)
    print("✅ MIGRATION COMPLETED")
    print("=" * 80)
    
    stats = get_collection_stats()
    print(f"\nNew collection statistics:")
    print(f"  Collection name : {stats.get('name', 'N/A')}")
    print(f"  Document count  : {stats.get('count', 0)}")
    
    total_time = time.time() - start_time
    successful_chunks = total_chunks - (len(failed_batches) * batch_size)
    
    print(f"\n⏱️  Performance:")
    print(f"  Total time      : {total_time:.1f} seconds")
    print(f"  Average rate    : {total_chunks/total_time:.1f} chunks/sec")
    print(f"  Successful      : {successful_chunks}/{total_chunks} chunks")
    
    if failed_batches:
        print(f"\n⚠️  Failed batches: {len(failed_batches)}")
        print(f"  Batch numbers: {failed_batches}")
        print("\n💡 Tip: You can re-run migration to retry failed batches")
        return 1
    
    print("\n" + "=" * 80)
    print("🎉 SUCCESS!")
    print("=" * 80)
    print("\n✅ All chunks successfully re-embedded with BGE-M3")
    print("\n🔄 Next steps:")
    print("  1. Test retrieval quality: python scripts/test_bge_m3.py")
    print("  2. Run benchmark: python scripts/benchmark_rag_system.py")
    print("  3. Update RAG service if needed")
    
    return 0

def main():
    try:
        return migrate_embeddings()
    except KeyboardInterrupt:
        print("\n\n❌ Migration interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
