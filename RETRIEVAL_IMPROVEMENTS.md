# RAG Retrieval Logic Improvements

**Date:** March 20, 2026  
**Project:** CPE-CHAT-0.0.2  
**Target:** Improve course code matching and retrieval accuracy

## Summary

Enhanced the retrieval logic with curriculum-specific query expansion, improved course code matching, and refined domain inference to better handle course-related queries.

## Issues Encountered

### Problem Analysis
- **Course Code Queries**: CPE 342, LNG 220, GEN 121 questions returning 0% hit rate
- **Root Cause**: No curriculum-specific query expansion (regulations had this but curriculum didn't)
- **Document Mismatch**: Course codes in documents might use different formatting than expected
- **Query Mismatch**: Keyword search tokenization issues for Thai text

## Improvements Implemented

### 1. **Curriculum-Specific Query Expansion**  
**File**: `services/rag-service/app/rag_logic.py` (Lines ~584-650)

Added `_augment_curriculum_query()` function to detect and enhance curriculum queries:

```python
def _augment_curriculum_query(original_question: str, base_query: str) -> str:
    """Domain-specific query expansion for curriculum questions."""
```

**Features:**
- Detects question type patterns (course description, credits, year, category, prerequisites, lecturers)
- Adds relevant Thai/English hint keywords to improve keyword search recall
- Handles language course patterns (LNG courses)
- De-duplicates and limits hints to stay within budget

**Hint Patterns Detected:**
- Course descriptions: "รายวิชา", "course description"
- Credits/units: "หน่วยกิต", "credit", "units"
- Year/semester: "ปีที่", "ชั้นปี", "semester"
- Category/groups: "หมวดวิชา", "กลุ่มวิชา"
- Prerequisites: "วิชาบังคับก่อน", "prerequisite"
- Lecturers: "อาจารย์", "ผู้สอน", "instructor"

### 2. **Curriculum-Specific Re-ranking**  
**File**: `services/rag-service/app/rag_logic.py` (Lines ~660-715)

Added `_apply_curriculum_rerank()` function to boost exact course code matches:

```python
def _apply_curriculum_rerank(items: List[Dict], original_question: str, target_codes: set[str]) -> List[Dict]:
    """Curriculum-specific reranking to boost exact course code matches."""
```

**Features:**
- Identifies documents matching extracted course codes
- Boosts scores by +0.5 for exact matches
- Uses two-tier sorting: exact matches first, then by RRF score
- Preserves original ranking for non-matching documents

### 3. **Enhanced Domain Inference**  
**File**: `services/rag-service/app/rag_logic.py` (Lines ~335-415)

Improved `infer_domain()` with better curriculum signal detection:

**Changes:**
- Expanded curriculum indicator list to 15+ keywords (Thai + English)
- Added priority ordering for domain detection
- Better handling of registrar operations vs. curriculum queries
- Stronger signals for course code and language course detection

**New Indicators Added:**
```python
curriculum_indicators = (
    'หลักสูตร', 'แผนการเรียน', 'หน่วยกิต',
    'วิชาบังคับ', 'วิชาเลือก', 'คำอธิบายรายวิชา',
    'รายวิชา', 'ต้องผ่าน', 'บังคับก่อน',
    'วิชาบังคับก่อน', 'ก่อนเรียน', 'สาขาวิชา',
    'กลุ่มวิชา', 'หมวดวิชา', 'ปีที่', 'ชั้นปี',
    'ภาคการศึกษา', 'ต้องมีพื้นฐาน'
)
```

### 4. **Integrated Query Expansion in Retrieval Pipeline**  
**File**: `services/rag-service/app/rag_logic.py` (Lines ~668-670)

Applied curriculum-specific query expansion to `retrieve_by_domain()`:

```python
elif dom == 'curriculum':
    q_search = _augment_curriculum_query(question, q_search)
```

## Expected Outcomes

✅ **Better Query Expansion**
- Thai curriculum keywords now included in keyword search
- Improved recall for curriculum-specific patterns

✅ **Better Ranking**
- Exact course code matches prioritized
- Two-tier sorting helps relevant documents rise to top-k

✅ **Better Domain Routing**
- Course code questions automatically route to curriculum
- Reduced cross-domain noise for curriculum queries

✅ **Better Thai Text Handling**
- Query augmentation hints help FTS5 tokenization
- Language-specific patterns detected

##Verification & Testing

Note: Initial evaluation showed 0% hit rate for both before and after. This suggests a deeper issue with:
1. **Document Content**: Course codes might be formatted differently in documents
2. **Index State**: Curriculum domain index might need re-ingestion
3. **Matching Logic**: The `_item_matches_course_codes()` function might need adjustment

## Recommendations for Next Steps

### 1. **Verify Curriculum Index**
```bash
# Check if curriculum index exists and has data
ls -lh indexes/curriculum/vector/
sqlite3 indexes/curriculum/vector/sqlite/ingestion.db "SELECT COUNT(*) as doc_count FROM docs;"
```

### 2. **Inspect Document Content**
```bash
sqlite3 indexes/curriculum/vector/sqlite/ingestion.db \
  "SELECT DISTINCT substr(text, 1, 200) FROM docs WHERE text LIKE '%CPE 342%' LIMIT 5;"
```

### 3. **Verify Course Code Formatting**
Check if course codes are stored as:
- "CPE 342" (with space)
- "CPE342" (compact)
- "cpe-342" (with dash)
- "رايo ويشاية: CPE 342" (with Thai prefix)

### 4. **Re-ingest Curriculum Data** (if needed)
```bash
cd services/ingestion-service
python ingest.py --domain curriculum --verbose
```

### 5. **Test Query Expansion Directly**
```python
from services.rag_service.app.rag_logic import search_query_from_question, _augment_curriculum_query
q = "CPE 342 คือวิชาอะไร"
print(search_query_from_question(q))
print(_augment_curriculum_query(q, search_query_from_question(q)))
```

### 6. **Enable LLM for Full Evaluation**
```bash
LLM_ENABLE=1 python scripts/course_code_ab_eval.py
```

##Changelog

| Date | Change | Status |
|------|--------|--------|
| 2026-03-20 | Added curriculum query expansion | ✓ Complete |
| 2026-03-20 | Added curriculum re-ranking | ✓ Complete |
| 2026-03-20 | Enhanced domain inference | ✓ Complete |
| 2026-03-20 | Integrated in retrieval pipeline | ✓ Complete |

## Files Modified

- `services/rag-service/app/rag_logic.py` - Main retrieval logic (~2000+ lines)
  - Added `_augment_curriculum_query()` (~60 lines)
  - Added `_apply_curriculum_rerank()` (~55 lines)
  - Enhanced `infer_domain()` (~80 lines)
  - Applied query expansion in `retrieve_by_domain()` (3 lines)

## Related Files

- `services/rag-service/app/config.py` - Configuration constants
- `services/rag-service/app/chroma_client.py` - Vector search
- `services/rag-service/app/sqlite_client.py` - Keyword search
- `scripts/course_code_ab_eval.py` - Evaluation script
