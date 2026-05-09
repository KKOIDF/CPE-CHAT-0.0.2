# Ingestion Timing Summary (gpu_host)

| Domain | Files | Records | Chunks | Embedded | Extract ms | Chunking ms | DB ms | Embedding ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `announcements` | 39 | 39 | 104 | 104 | 278.65 | 76.69 | 643.37 | 14962.12 | 34720.92 |
| `regulations` | 23 | 23 | 146 | 146 | 430.87 | 160.52 | 1832.53 | 34125.07 | 50917.49 |
| `curriculum` | 8 | 8 | 1096 | 1096 | 764.21 | 128.20 | 5361.35 | 101169.76 | 146514.28 |

## Totals

| Metric | Value |
|---|---:|
| `files` | 70 |
| `records` | 70 |
| `chunks` | 1346 |
| `flagged_chunks` | 7 |
| `embedded_chunks` | 1346 |
| `extract_total_ms` | 1473.72 |
| `chunking_ms` | 365.41 |
| `db_store_ms` | 7837.24 |
| `structured_artifacts_ms` | 3663.25 |
| `embedding_ms` | 150256.96 |
| `neo4j_ms` | 0.00 |
| `total_ms` | 232152.68 |
