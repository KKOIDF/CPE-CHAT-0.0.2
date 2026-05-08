# Ingestion Timing Summary (gpu_host)

| Domain | Files | Records | Chunks | Embedded | Extract ms | Chunking ms | DB ms | Embedding ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `announcements` | 39 | 39 | 79 | 79 | 197.47 | 27.72 | 502.21 | 3806.93 | 23836.99 |
| `regulations` | 23 | 23 | 165 | 165 | 248.17 | 98.79 | 1603.36 | 10645.63 | 23835.94 |
| `curriculum` | 8 | 8 | 319 | 319 | 416.37 | 81.48 | 2673.95 | 28629.32 | 48369.98 |

## Totals

| Metric | Value |
|---|---:|
| `files` | 70 |
| `records` | 70 |
| `chunks` | 563 |
| `flagged_chunks` | 1 |
| `embedded_chunks` | 563 |
| `extract_total_ms` | 862.00 |
| `chunking_ms` | 207.99 |
| `db_store_ms` | 4779.52 |
| `structured_artifacts_ms` | 2144.43 |
| `embedding_ms` | 43081.88 |
| `neo4j_ms` | 1834.95 |
| `total_ms` | 96042.91 |
