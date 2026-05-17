# Ingestion Timing Summary (gpu_host)

| Domain | Files | Records | Chunks | Embedded | Extract ms | Chunking ms | DB ms | Embedding ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `announcements` | 39 | 39 | 183 | 183 | 174.29 | 947.38 | 129.75 | 3546.01 | 18971.61 |
| `regulations` | 23 | 23 | 196 | 196 | 413.73 | 1744.82 | 555.44 | 8741.17 | 20798.08 |
| `curriculum` | 8 | 8 | 401 | 401 | 536.75 | 2675.07 | 1595.48 | 24204.53 | 57952.08 |

## Totals

| Metric | Value |
|---|---:|
| `files` | 70 |
| `records` | 70 |
| `chunks` | 780 |
| `flagged_chunks` | 32 |
| `embedded_chunks` | 780 |
| `extract_total_ms` | 1124.76 |
| `chunking_ms` | 5367.27 |
| `db_store_ms` | 2280.66 |
| `structured_artifacts_ms` | 2107.72 |
| `embedding_ms` | 36491.71 |
| `neo4j_ms` | 0.00 |
| `total_ms` | 97721.76 |
