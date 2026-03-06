"""Minimal MLflow helpers (optional).

This repo uses MLflow as an *opt-in* experiment tracker.
- Enable by setting env var `MLFLOW_ENABLE=1`.
- Tracking URI defaults to `http://localhost:5000`.

The helpers are dependency-safe: if MLflow isn't installed, calls become no-ops.
"""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional


def _truthy(v: str) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y"}


def enabled() -> bool:
    return _truthy(os.getenv("MLFLOW_ENABLE", "0"))


def tracking_uri() -> str:
    return (os.getenv("MLFLOW_TRACKING_URI") or "http://localhost:5000").strip()


def experiment_name() -> str:
    return (os.getenv("MLFLOW_EXPERIMENT") or "cpe-chat").strip()


def _artifact_location_is_legacy_local(loc: str) -> bool:
    s = (loc or "").strip().lower()
    if not s:
        return False
    # Local filesystem locations (often not writable from client when MLflow runs in Docker)
    return s.startswith("file:") or s.startswith("/")


def _tracking_uri_is_http(uri: str) -> bool:
    u = (uri or "").strip().lower()
    return u.startswith("http://") or u.startswith("https://")


def _import_mlflow():
    try:
        import mlflow  # type: ignore

        return mlflow
    except Exception:
        return None


def _safe_str(v: Any, max_len: int = 8000) -> str:
    s = "" if v is None else str(v)
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def log_params(params: Dict[str, Any]) -> None:
    if not enabled():
        return
    mlflow = _import_mlflow()
    if not mlflow:
        return

    flat = {k: _safe_str(v) for k, v in (params or {}).items() if k}
    if not flat:
        return

    mlflow.log_params(flat)


def log_metrics(metrics: Dict[str, Any]) -> None:
    if not enabled():
        return
    mlflow = _import_mlflow()
    if not mlflow:
        return

    for k, v in (metrics or {}).items():
        if not k:
            continue
        try:
            mlflow.log_metric(k, float(v))
        except Exception:
            # Keep eval scripts resilient; skip non-numeric.
            continue


def log_artifacts(paths: Iterable[str]) -> None:
    if not enabled():
        return
    mlflow = _import_mlflow()
    if not mlflow:
        return

    for p in paths or []:
        try:
            mlflow.log_artifact(str(p))
        except Exception:
            continue


def env_snapshot(
    *,
    prefixes: Iterable[str] = (
        "RAG_",
        "LLM_",
        "EMBEDDING_",
        "EMBED_",
        "TYPHOON_",
        "OPENAI_",
        "NEO4J_",
        "CPE_",
    ),
    extra_keys: Iterable[str] = (
        "DATA_DIR",
        "CHROMA_DIR",
        "SQLITE_PATH",
    ),
) -> Dict[str, str]:
    """Return a sanitized snapshot of selected environment variables.

    - Filters by prefix + explicit extra_keys.
    - Redacts likely secrets (KEY/TOKEN/SECRET/PASSWORD).
    """

    deny = ("KEY", "TOKEN", "SECRET", "PASSWORD")
    out: Dict[str, str] = {}

    want_keys = set(k for k in (extra_keys or []) if k)
    for k, v in os.environ.items():
        if not k:
            continue
        if k in want_keys or any(k.startswith(p) for p in (prefixes or [])):
            if any(d in k.upper() for d in deny):
                out[k] = "***REDACTED***"
            else:
                out[k] = _safe_str(v, max_len=4096)

    return dict(sorted(out.items(), key=lambda kv: kv[0]))


def log_dict_artifact(data: Dict[str, Any], *, artifact_file: str = "run_context.json") -> None:
    """Write dict to JSON and log as an MLflow artifact (no-op if disabled)."""

    if not enabled():
        return
    mlflow = _import_mlflow()
    if not mlflow:
        return

    try:
        payload = json.dumps(data or {}, ensure_ascii=False, indent=2)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / (artifact_file or "run_context.json")
            p.write_text(payload, encoding="utf-8")
            mlflow.log_artifact(str(p))
    except Exception:
        return


@contextmanager
def start_run(
    *,
    run_name: Optional[str] = None,
    tags: Optional[Dict[str, Any]] = None,
) -> Iterator[None]:
    """Start an MLflow run if enabled; otherwise no-op."""

    if not enabled():
        with nullcontext():
            yield
        return

    mlflow = _import_mlflow()
    if not mlflow:
        with nullcontext():
            yield
        return

    try:
        mlflow.set_tracking_uri(tracking_uri())

        # Ensure artifact uploads work when tracking server is remote (e.g. docker-compose).
        exp_name = experiment_name()
        exp_name_effective = exp_name
        try:
            if _tracking_uri_is_http(tracking_uri()):
                from mlflow.tracking import MlflowClient  # type: ignore

                client = MlflowClient(tracking_uri=tracking_uri())
                exp = client.get_experiment_by_name(exp_name)
                if exp and _artifact_location_is_legacy_local(getattr(exp, "artifact_location", "")):
                    exp_name_effective = f"{exp_name}-artifacts"
        except Exception:
            pass

        mlflow.set_experiment(exp_name_effective)
        with mlflow.start_run(run_name=run_name):
            if tags:
                try:
                    mlflow.set_tags({k: _safe_str(v, max_len=256) for k, v in tags.items() if k})
                except Exception:
                    pass
            yield
    except Exception:
        # Never let MLflow take down an eval run.
        yield
