import threading
import uuid
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .main import run_ingest


app = FastAPI(title="Ingestion Service", version="0.1.0")


class IngestRequest(BaseModel):
    input_dir: str = Field(..., description="Directory containing PDF/Excel files")
    records_jsonl: str = Field(
        "data/db/records.jsonl", description="Path to write page/sheet records"
    )
    chunks_jsonl: str = Field(
        "data/db/chunks.jsonl", description="Path to write enriched chunks"
    )
    store: bool = Field(True, description="Persist chunks to SQLite + quality logs")
    embed: bool = Field(True, description="Insert chunks into Chroma")
    run_async: bool = Field(
        True,
        description=(
            "If true, schedule ingestion in the background and return immediately. "
            "If false, block until ingestion completes."
        ),
    )


class IngestResponse(BaseModel):
    status: str
    message: str
    run_id: str
    input_dir: str
    records_jsonl: str
    chunks_jsonl: str
    store: bool
    embed: bool
    run_async: bool


class IngestStatus(BaseModel):
    status: str = Field(..., description="idle|running|completed|error")
    progress: float = Field(0.0, ge=0.0, le=1.0, description="0.0 - 1.0")
    message: str = Field("", description="Human-readable progress message")
    run_id: Optional[str] = Field(None, description="Last run identifier")


_progress_lock = threading.Lock()
_progress_state = IngestStatus(status="idle", progress=0.0, message="Idle", run_id=None)


def _set_progress(status: str, progress: float, message: str, run_id: Optional[str]):
    with _progress_lock:
        global _progress_state
        _progress_state = IngestStatus(
            status=status,
            progress=max(0.0, min(1.0, progress)),
            message=message,
            run_id=run_id,
        )


def _get_progress() -> IngestStatus:
    with _progress_lock:
        return _progress_state


def _wrap_ingest(run_id: str, task_kwargs: dict):
    def reporter(progress: float, message: str):
        _set_progress("running", progress, message, run_id)

    try:
        _set_progress("running", 0.0, "Ingestion started", run_id)
        run_ingest(**task_kwargs, progress_callback=reporter)
        _set_progress("completed", 1.0, "Ingestion finished", run_id)
    except Exception as exc:  # noqa: BLE001
        _set_progress("error", _get_progress().progress, f"Error: {exc}", run_id)
        raise


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/ingest/status", response_model=IngestStatus)
def ingest_status():
    return _get_progress()


@app.post("/ingest", response_model=IngestResponse)
def trigger_ingest(request: IngestRequest, background_tasks: BackgroundTasks):
    input_dir = Path(request.input_dir)
    if not input_dir.exists() or not input_dir.is_dir():
        raise HTTPException(status_code=400, detail="input_dir must be an existing directory")

    task_kwargs = {
        "input_dir": str(input_dir),
        "jsonl_out": request.records_jsonl,
        "chunk_out": request.chunks_jsonl,
        "store": request.store,
        "embed": request.embed,
    }
    run_id = uuid.uuid4().hex

    if request.run_async:
        background_tasks.add_task(_wrap_ingest, run_id, task_kwargs)
        status = "accepted"
        message = "Ingestion scheduled"
        _set_progress("running", 0.0, "Scheduled", run_id)
    else:
        _set_progress("running", 0.0, "Started", run_id)
        _wrap_ingest(run_id, task_kwargs)
        status = "completed"
        message = "Ingestion finished"

    return IngestResponse(
        status=status,
        message=message,
        run_id=run_id,
        input_dir=str(input_dir),
        records_jsonl=request.records_jsonl,
        chunks_jsonl=request.chunks_jsonl,
        store=request.store,
        embed=request.embed,
        run_async=request.run_async,
    )
