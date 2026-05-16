# Ingestion Timing Summary (gpu_host)

| Domain | Files | Records | Chunks | Embedded | Extract ms | Chunking ms | DB ms | Embedding ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `announcements` | 39 | 39 | 183 | 183 | 147.93 | 924.00 | 4531.22 | 7876.37 | 35140.38 |
| `regulations` | 23 | 23 | 196 | 196 | 487.52 | 1751.35 | 4574.40 | 15755.31 | 29806.28 |
| `curriculum` | 8 | 8 | 401 | 401 | 634.80 | 2632.37 | 8029.21 | 30744.26 | 66472.21 |

## Totals

| Metric | Value |
|---|---:|
| `files` | 70 |
| `records` | 70 |
| `chunks` | 780 |
| `flagged_chunks` | 32 |
| `embedded_chunks` | 780 |
| `extract_total_ms` | 1270.25 |
| `chunking_ms` | 5307.71 |
| `db_store_ms` | 17134.82 |
| `structured_artifacts_ms` | 2104.33 |
| `embedding_ms` | 54375.94 |
| `neo4j_ms` | 0.00 |
| `total_ms` | 131418.87 |
