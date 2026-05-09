# Ingestion Timing Summary (gpu_host)

| Domain | Files | Records | Chunks | Embedded | Extract ms | Chunking ms | DB ms | Embedding ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `announcements` | 39 | 39 | 104 | 104 | 1506.92 | 76.35 | 391.47 | 16973.30 | 78625.65 |
| `regulations` | 23 | 23 | 146 | 146 | 668.06 | 141.99 | 1394.75 | 33167.87 | 52589.50 |
| `curriculum` | 8 | 8 | 1096 | 1096 | 938.44 | 124.35 | 3333.06 | 97503.63 | 140262.05 |

## Totals

| Metric | Value |
|---|---:|
| `files` | 70 |
| `records` | 70 |
| `chunks` | 1346 |
| `flagged_chunks` | 7 |
| `embedded_chunks` | 1346 |
| `extract_total_ms` | 3113.42 |
| `chunking_ms` | 342.68 |
| `db_store_ms` | 5119.29 |
| `structured_artifacts_ms` | 3745.30 |
| `embedding_ms` | 147644.79 |
| `neo4j_ms` | 0.00 |
| `total_ms` | 271477.20 |
