# Ingestion Timing Summary (gpu_host)

| Domain | Files | Records | Chunks | Embedded | Extract ms | Chunking ms | DB ms | Embedding ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `announcements` | 39 | 39 | 68 | 68 | 1433.73 | 36793.50 | 228.98 | 5422.65 | 62049.39 |
| `regulations` | 23 | 23 | 135 | 135 | 479.08 | 6055.50 | 727.44 | 8912.87 | 23167.99 |
| `curriculum` | 8 | 8 | 233 | 233 | 591.70 | 4136.32 | 1069.60 | 23710.32 | 41004.08 |

## Totals

| Metric | Value |
|---|---:|
| `files` | 70 |
| `records` | 70 |
| `chunks` | 436 |
| `flagged_chunks` | 1 |
| `embedded_chunks` | 436 |
| `extract_total_ms` | 2504.51 |
| `chunking_ms` | 46985.32 |
| `db_store_ms` | 2026.03 |
| `structured_artifacts_ms` | 1908.25 |
| `embedding_ms` | 38045.84 |
| `neo4j_ms` | 2318.70 |
| `total_ms` | 126221.46 |
