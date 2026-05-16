# Ingestion Timing Summary (gpu_host)

| Domain | Files | Records | Chunks | Embedded | Extract ms | Chunking ms | DB ms | Embedding ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `announcements` | 39 | 39 | 183 | 183 | 542.34 | 921.72 | 7412.02 | 9606.06 | 37404.74 |
| `regulations` | 23 | 23 | 196 | 196 | 468.17 | 1745.01 | 6545.72 | 14883.30 | 31068.99 |
| `curriculum` | 8 | 8 | 401 | 401 | 613.59 | 2680.47 | 9871.78 | 32529.95 | 70981.68 |

## Totals

| Metric | Value |
|---|---:|
| `files` | 70 |
| `records` | 70 |
| `chunks` | 780 |
| `flagged_chunks` | 32 |
| `embedded_chunks` | 780 |
| `extract_total_ms` | 1624.10 |
| `chunking_ms` | 5347.20 |
| `db_store_ms` | 23829.51 |
| `structured_artifacts_ms` | 2112.01 |
| `embedding_ms` | 57019.32 |
| `neo4j_ms` | 0.00 |
| `total_ms` | 139455.42 |
