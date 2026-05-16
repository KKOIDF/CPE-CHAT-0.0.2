# Ingestion Timing Summary (gpu_host)

| Domain | Files | Records | Chunks | Embedded | Extract ms | Chunking ms | DB ms | Embedding ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `announcements` | 39 | 39 | 210 | 210 | 275.66 | 31.36 | 938.56 | 12543.25 | 32252.71 |
| `regulations` | 23 | 23 | 353 | 353 | 428.69 | 50.64 | 3060.23 | 31814.25 | 49756.27 |
| `curriculum` | 8 | 8 | 668 | 668 | 800.04 | 87.36 | 8150.00 | 77738.34 | 122338.52 |

## Totals

| Metric | Value |
|---|---:|
| `files` | 70 |
| `records` | 70 |
| `chunks` | 1231 |
| `flagged_chunks` | 35 |
| `embedded_chunks` | 1231 |
| `extract_total_ms` | 1504.39 |
| `chunking_ms` | 169.36 |
| `db_store_ms` | 12148.80 |
| `structured_artifacts_ms` | 3646.33 |
| `embedding_ms` | 122095.83 |
| `neo4j_ms` | 0.00 |
| `total_ms` | 204347.51 |
