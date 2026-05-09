# Ingestion Timing Summary (gpu_host)

| Domain | Files | Records | Chunks | Embedded | Extract ms | Chunking ms | DB ms | Embedding ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `announcements` | 39 | 39 | 104 | 104 | 267.28 | 74.27 | 304.02 | 14954.21 | 33684.72 |
| `regulations` | 23 | 23 | 146 | 146 | 434.96 | 147.43 | 889.14 | 33947.54 | 49915.63 |
| `curriculum` | 8 | 8 | 1096 | 1096 | 782.54 | 127.33 | 3260.79 | 94874.82 | 137091.67 |

## Totals

| Metric | Value |
|---|---:|
| `files` | 70 |
| `records` | 70 |
| `chunks` | 1346 |
| `flagged_chunks` | 7 |
| `embedded_chunks` | 1346 |
| `extract_total_ms` | 1484.78 |
| `chunking_ms` | 349.02 |
| `db_store_ms` | 4453.95 |
| `structured_artifacts_ms` | 3655.17 |
| `embedding_ms` | 143776.57 |
| `neo4j_ms` | 0.00 |
| `total_ms` | 220692.02 |
