# GPU Ingestion Guide

RAG pipeline ingestion (embedding thousands of documents into ChromaDB/SQLite) can be heavily CPU-bound locally. To offload the compute burden to a remote GPU cluster (e.g., SLURM):

## Remote Sync Target
The repository includes a remote orchestrator: `make ingest-gpu`. 

Instead of waiting an hour for your Macbook to embed course notes into `BAAI/bge-m3`, this script:
1. Pushes your clean `data/raw/` repository into the GPU server.
2. Runs the native `ingest_all_domains.sbatch` SLURM manifest on the target environment.
3. Automatically bootstraps a standalone Python virtual environment on the cluster to host `PyTorch` weights without dirtying your local network.
4. Waits for completion, before securely pulling `data/db/` and `indexes/` directly into your local machine using `rsync`.

### Command Usage
```bash
# Provide the SSH target endpoint representing your GPU cluster.
make ingest-gpu GPU_HOST=student_id@gpu.university.edu
```

## Security & Version Control
By design, the orchestrator deliberately invokes `.gitignore` to protect upstream repository pollution.
- `indexes/...`
- `data/db/...`

These are computed artifacts that only live locally on your laptop, and transitorily on the remote GPU cluster. You get absolute throughput without compromising repository integrity.
