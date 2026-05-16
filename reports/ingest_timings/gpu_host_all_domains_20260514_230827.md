# Ingestion Timing Summary (gpu_host)

| Domain | Files | Records | Chunks | Embedded | Extract ms | Chunking ms | DB ms | Embedding ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `announcements` | 39 | 39 | 132 | 132 | 273.29 | 11559.61 | 630.18 | 16188.04 | 37308.63 |
| `regulations` | 23 | 23 | 195 | 195 | 436.72 | 6573.81 | 2063.46 | 33504.32 | 51745.59 |
| `curriculum` | 8 | 8 | 957 | 957 | 748.33 | 8913.61 | 4646.26 | 89482.11 | 132866.10 |

## Totals

| Metric | Value |
|---|---:|
| `files` | 70 |
| `records` | 70 |
| `chunks` | 1284 |
| `flagged_chunks` | 7 |
| `embedded_chunks` | 1284 |
| `extract_total_ms` | 1458.34 |
| `chunking_ms` | 27047.03 |
| `db_store_ms` | 7339.89 |
| `structured_artifacts_ms` | 3663.44 |
| `embedding_ms` | 139174.47 |
| `neo4j_ms` | 0.00 |
| `total_ms` | 221920.32 |
