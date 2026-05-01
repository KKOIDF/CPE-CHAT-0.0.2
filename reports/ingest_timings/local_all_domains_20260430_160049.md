# Ingestion Timing Summary (local)

| Domain | Files | Records | Chunks | Embedded | Extract ms | Chunking ms | DB ms | Embedding ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `announcements` | 39 | 39 | 68 | 68 | 470.31 | 20230.62 | 113.65 | 257179.85 | 288757.46 |
| `regulations` | 23 | 23 | 135 | 135 | 1116.18 | 5877.69 | 218.52 | 529225.76 | 545603.98 |
| `curriculum` | 8 | 8 | 233 | 233 | 1056.04 | 5513.89 | 732.79 | 1013480.49 | 1043647.37 |

## Totals

| Metric | Value |
|---|---:|
| `files` | 70 |
| `records` | 70 |
| `chunks` | 436 |
| `flagged_chunks` | 1 |
| `embedded_chunks` | 436 |
| `extract_total_ms` | 2642.53 |
| `chunking_ms` | 31622.21 |
| `db_store_ms` | 1064.96 |
| `structured_artifacts_ms` | 6926.66 |
| `embedding_ms` | 1799886.09 |
| `neo4j_ms` | 4012.17 |
| `total_ms` | 1878008.81 |
