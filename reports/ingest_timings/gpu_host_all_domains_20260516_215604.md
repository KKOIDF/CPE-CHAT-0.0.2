# Ingestion Timing Summary (gpu_host)

| Domain | Files | Records | Chunks | Embedded | Extract ms | Chunking ms | DB ms | Embedding ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `announcements` | 39 | 39 | 183 | 183 | 154.66 | 936.58 | 3702.77 | 6087.00 | 17941.14 |
| `regulations` | 23 | 23 | 196 | 196 | 234.81 | 1728.68 | 4525.54 | 12901.18 | 26697.35 |
| `curriculum` | 8 | 8 | 401 | 401 | 410.22 | 2697.96 | 6845.54 | 30347.04 | 65002.41 |

## Totals

| Metric | Value |
|---|---:|
| `files` | 70 |
| `records` | 70 |
| `chunks` | 780 |
| `flagged_chunks` | 32 |
| `embedded_chunks` | 780 |
| `extract_total_ms` | 799.70 |
| `chunking_ms` | 5363.23 |
| `db_store_ms` | 15073.85 |
| `structured_artifacts_ms` | 2124.52 |
| `embedding_ms` | 49335.22 |
| `neo4j_ms` | 0.00 |
| `total_ms` | 109640.89 |
