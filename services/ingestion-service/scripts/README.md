# Flagged Chunks Management Scripts

Scripts for analyzing and reprocessing low-quality (flagged) chunks from the ingestion pipeline.

## Overview

When EMBED_FLAGGED=false, low-quality chunks are written to timestamped review files under data/db/review/flagged_*.jsonl. These scripts help analyze, reprocess, and improve those chunks.

## Scripts

### 1. analyze_flagged.py

Analyze and report statistics about flagged chunks.

**Usage:**
```powershell
python services/ingestion-service/scripts/analyze_flagged.py data/db/review/flagged_20251121111219.jsonl
```

**Output:**
- Total flagged chunks
- Files with flagged content
- Text length statistics
- Sample previews

---

### 2. reprocess_flagged.py

Reprocess flagged chunks with alternative OCR engines to improve quality.

**Usage:**
```powershell
# Reprocess with Typhoon OCR (default)
python services/ingestion-service/scripts/reprocess_flagged.py data/db/review/flagged_20251121111219.jsonl

# Use specific engine
python services/ingestion-service/scripts/reprocess_flagged.py data/db/review/flagged_20251121111219.jsonl --engine tesseract

# Skip storage/embedding (dry run)
python services/ingestion-service/scripts/reprocess_flagged.py data/db/review/flagged_20251121111219.jsonl --no-store --no-embed

# Adjust quality threshold
python services/ingestion-service/scripts/reprocess_flagged.py data/db/review/flagged_20251121111219.jsonl --quality-threshold 0.4
```

**Options:**
- --engine {auto,typhoon,tesseract,poppler} : OCR engine (default: typhoon)
- --no-store : Skip database storage
- --no-embed : Skip embedding to Chroma
- --quality-threshold FLOAT : Minimum quality score (default: 0.3)

**Output:**
- Improved chunks saved to improved_<engine>_flagged_*.jsonl
- Updated in database (if --no-store not set)
- Embedded to Chroma (if --no-embed not set)

---

### 3. export_flagged_images.py

Export flagged PDF pages as PNG images for manual inspection.

**Usage:**
```powershell
# Export all flagged pages
python services/ingestion-service/scripts/export_flagged_images.py data/db/review/flagged_20251121111219.jsonl

# Export to specific directory
python services/ingestion-service/scripts/export_flagged_images.py data/db/review/flagged_20251121111219.jsonl --output manual_review

# Limit number of pages
python services/ingestion-service/scripts/export_flagged_images.py data/db/review/flagged_20251121111219.jsonl --max-pages 10
```

**Options:**
- --output DIR : Output directory (default: review_dir/flagged_images)
- --max-pages N : Maximum pages to export

**Output:**
- PNG images named <filename>_page<N>.png
- Default location: data/db/review/flagged_images/

---

## Workflow Example

```powershell
# 1. Analyze flagged chunks
python services/ingestion-service/scripts/analyze_flagged.py data/db/review/flagged_20251121111219.jsonl

# 2. Try reprocessing with Typhoon OCR
python services/ingestion-service/scripts/reprocess_flagged.py data/db/review/flagged_20251121111219.jsonl --engine typhoon

# 3. If still poor quality, export images for manual review
python services/ingestion-service/scripts/export_flagged_images.py data/db/review/flagged_20251121111219.jsonl --max-pages 5

# 4. Try Tesseract with higher DPI
$env:OCR_DPI=\"600\"; python services/ingestion-service/scripts/reprocess_flagged.py data/db/review/flagged_20251121111219.jsonl --engine tesseract
```

## Configuration

Set environment variables in .env:

```env
EMBED_FLAGGED=false          # Don't embed low-quality chunks
MIN_QUALITY_SCORE=0.2        # Quality threshold for flagging
MIN_LENGTH=50                # Min text length
OCR_ENGINE=auto              # Default engine for reprocess
TY_OCR_ENABLE=1              # Enable Typhoon OCR
TY_OCR_API_KEY=sk-...        # Typhoon API key
POPPLER_PATH=C:\\...          # Poppler binaries path
```

## Notes

- Reprocessed chunks get new doc_id like eprocess_typhoon_0
- Original flagged chunks remain in review files
- Improved chunks are added to DB/Chroma (not replacing originals)
- Review files are never modified by scripts

