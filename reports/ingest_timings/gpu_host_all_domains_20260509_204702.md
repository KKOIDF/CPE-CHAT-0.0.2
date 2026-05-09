# Ingestion Timing Summary (gpu_host)

| Domain | Files | Records | Chunks | Embedded | Extract ms | Chunking ms | DB ms | Embedding ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `announcements` | 39 | 39 | 104 | 104 | 295.00 | 77.87 | 697.15 | 15426.89 | 35373.24 |
| `regulations` | 23 | 23 | 146 | 146 | 432.12 | 152.30 | 1848.99 | 33377.06 | 50102.63 |
| `curriculum` | 8 | 8 | 1096 | 1096 | 769.94 | 129.81 | 5171.48 | 100924.08 | 144700.16 |

## Totals

| Metric | Value |
|---|---:|
| `files` | 70 |
| `records` | 70 |
| `chunks` | 1346 |
| `flagged_chunks` | 7 |
| `embedded_chunks` | 1346 |
| `extract_total_ms` | 1497.06 |
| `chunking_ms` | 359.98 |
| `db_store_ms` | 7717.62 |
| `structured_artifacts_ms` | 3696.65 |
| `embedding_ms` | 149728.02 |
| `neo4j_ms` | 0.00 |
| `total_ms` | 230176.02 |
