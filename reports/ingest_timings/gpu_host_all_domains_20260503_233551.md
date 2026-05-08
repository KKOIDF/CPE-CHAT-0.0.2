# Ingestion Timing Summary (gpu_host)

| Domain | Files | Records | Chunks | Embedded | Extract ms | Chunking ms | DB ms | Embedding ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `announcements` | 39 | 39 | 79 | 79 | 1513.84 | 20.37 | 194.40 | 5424.89 | 60145.51 |
| `regulations` | 23 | 23 | 165 | 165 | 462.09 | 72.30 | 679.35 | 10036.47 | 22064.78 |
| `curriculum` | 8 | 8 | 319 | 319 | 587.86 | 69.91 | 1119.28 | 25504.57 | 44606.72 |

## Totals

| Metric | Value |
|---|---:|
| `files` | 70 |
| `records` | 70 |
| `chunks` | 563 |
| `flagged_chunks` | 1 |
| `embedded_chunks` | 563 |
| `extract_total_ms` | 2563.79 |
| `chunking_ms` | 162.59 |
| `db_store_ms` | 1993.03 |
| `structured_artifacts_ms` | 2100.59 |
| `embedding_ms` | 40965.93 |
| `neo4j_ms` | 1892.57 |
| `total_ms` | 126817.02 |
