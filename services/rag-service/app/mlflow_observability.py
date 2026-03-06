from __future__ import annotations

import logging
import os
import random
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Optional, Tuple


def _truthy(v: str) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_name(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "unknown"


def _redact_text(text: str, max_len: int) -> str:
    t = (text or "").strip()
    if len(t) > max_len:
        t = t[: max_len - 1] + "…"
    return t


@dataclass
class _Cfg:
    enabled: bool
    tracking_uri: str
    experiment: str
    run_name: str
    flush_s: float
    window_n: int
    tracing_enabled: bool
    trace_sample_rate: float
    trace_content: bool
    trace_max_chars: int


class MlflowObservability:
    """Opt-in MLflow observability for rag-service.

    Logs:
    - Usage: requests_total per endpoint
    - Latency: p50/p90/p99 over rolling window per endpoint
    - Errors: errors_total and error_rate_window per endpoint

    Optional tracing (sampling): logs per-request traces into MLflow traces.
    """

    def __init__(self) -> None:
        self._cfg = self._load_cfg()
        self._mlflow = None
        self._client = None
        self._run_id: Optional[str] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._counts: Dict[str, int] = defaultdict(int)
        self._errors: Dict[str, int] = defaultdict(int)
        self._latencies: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=self._cfg.window_n))
        self._last_flush: float = 0.0

    @staticmethod
    def _load_cfg() -> _Cfg:
        enabled = _truthy(os.getenv("MLFLOW_OBSERVABILITY_ENABLE", "0"))
        tracking_uri = (os.getenv("MLFLOW_TRACKING_URI") or "http://localhost:5000").strip()
        experiment = (os.getenv("MLFLOW_OBSERVABILITY_EXPERIMENT") or "cpe-chat-observability").strip()
        now = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
        run_name = (os.getenv("MLFLOW_OBSERVABILITY_RUN") or f"rag-service_{now}").strip()

        flush_s = float(os.getenv("MLFLOW_OBS_FLUSH_S", "10") or "10")
        window_n = int(os.getenv("MLFLOW_OBS_WINDOW_N", "500") or "500")

        tracing_enabled = _truthy(os.getenv("MLFLOW_TRACING_ENABLE", "0"))
        trace_sample_rate = float(os.getenv("MLFLOW_TRACE_SAMPLE_RATE", "0.05") or "0.05")
        trace_content = _truthy(os.getenv("MLFLOW_TRACE_CONTENT", "0"))
        trace_max_chars = int(os.getenv("MLFLOW_TRACE_MAX_CHARS", "1200") or "1200")

        # Clamp.
        if trace_sample_rate < 0:
            trace_sample_rate = 0.0
        if trace_sample_rate > 1:
            trace_sample_rate = 1.0

        return _Cfg(
            enabled=enabled,
            tracking_uri=tracking_uri,
            experiment=experiment,
            run_name=run_name,
            flush_s=max(1.0, flush_s),
            window_n=max(50, window_n),
            tracing_enabled=tracing_enabled,
            trace_sample_rate=trace_sample_rate,
            trace_content=trace_content,
            trace_max_chars=max(200, trace_max_chars),
        )

    def enabled(self) -> bool:
        return bool(self._cfg.enabled)

    def start(self) -> None:
        if not self._cfg.enabled:
            return

        try:
            import mlflow
            from mlflow.tracking import MlflowClient

            self._mlflow = mlflow
            self._client = MlflowClient(tracking_uri=self._cfg.tracking_uri)

            mlflow.set_tracking_uri(self._cfg.tracking_uri)
            mlflow.set_experiment(self._cfg.experiment)

            run = mlflow.start_run(run_name=self._cfg.run_name)
            self._run_id = run.info.run_id

            # Tags help filter.
            mlflow.set_tags(
                {
                    "service": "rag-service",
                    "kind": "observability",
                    "host": os.getenv("HOSTNAME", ""),
                }
            )

            self._last_flush = time.time()
            self._thread = threading.Thread(target=self._loop, name="mlflow-obs", daemon=True)
            self._thread.start()
        except Exception as e:
            # Observability must never crash the service.
            logging.getLogger(__name__).warning("MLflow observability disabled (init failed): %s", e)
            self._cfg = _Cfg(**{**self._cfg.__dict__, "enabled": False})

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t:
            try:
                t.join(timeout=2.0)
            except Exception:
                pass
        try:
            if self._mlflow and self._run_id:
                self._mlflow.end_run()
        except Exception:
            pass

    def observe(self, request_name: str, timings: Dict[str, float], metrics: Dict[str, Any]) -> None:
        if not self._cfg.enabled:
            return

        endpoint = str(metrics.get("endpoint") or request_name or "unknown")
        endpoint_key = _safe_name(endpoint)

        total_ms = float(timings.get("total") or 0.0)

        error = 0
        if metrics.get("error") in (1, True, "1", "true", "True"):
            error = 1
        # Heuristic: exception-like answer markers.
        ans = (metrics.get("answer") or "") if isinstance(metrics.get("answer"), str) else ""
        if ans.strip().startswith("(exception)"):
            error = 1

        with self._lock:
            self._counts[endpoint_key] += 1
            if error:
                self._errors[endpoint_key] += 1
            if total_ms > 0:
                self._latencies[endpoint_key].append(total_ms)

        # Optional trace.
        if self._cfg.tracing_enabled and random.random() < self._cfg.trace_sample_rate:
            self._log_trace(endpoint=endpoint, request_name=request_name, timings=timings, metrics=metrics, error=error)

    def _loop(self) -> None:
        while not self._stop.is_set():
            time.sleep(self._cfg.flush_s)
            try:
                self.flush()
            except Exception:
                continue

    def flush(self) -> None:
        if not (self._cfg.enabled and self._mlflow and self._run_id):
            return

        # Snapshot & reset window counters.
        with self._lock:
            counts = dict(self._counts)
            errors = dict(self._errors)
            lats = {k: list(v) for k, v in self._latencies.items()}

        now = time.time()
        step = int(now)

        metrics_to_log: Dict[str, float] = {}

        for ep, n in counts.items():
            metrics_to_log[f"requests_total__{ep}"] = float(n)
            e = float(errors.get(ep, 0))
            metrics_to_log[f"errors_total__{ep}"] = e

            window = lats.get(ep) or []
            if window:
                window_sorted = sorted(window)

                def pct(p: float) -> float:
                    if not window_sorted:
                        return 0.0
                    idx = int(round((p / 100.0) * (len(window_sorted) - 1)))
                    idx = max(0, min(len(window_sorted) - 1, idx))
                    return float(window_sorted[idx])

                metrics_to_log[f"latency_ms_p50__{ep}"] = pct(50)
                metrics_to_log[f"latency_ms_p90__{ep}"] = pct(90)
                metrics_to_log[f"latency_ms_p99__{ep}"] = pct(99)
                metrics_to_log[f"latency_ms_avg__{ep}"] = float(sum(window) / len(window))

                err_rate = (e / float(n)) if n else 0.0
                metrics_to_log[f"error_rate__{ep}"] = float(err_rate)

        # Global rollup (all endpoints).
        total = float(sum(counts.values()))
        total_err = float(sum(errors.values()))
        metrics_to_log["requests_total"] = total
        metrics_to_log["errors_total"] = total_err
        metrics_to_log["error_rate"] = (total_err / total) if total else 0.0

        # Log.
        try:
            for k, v in metrics_to_log.items():
                self._mlflow.log_metric(k, float(v), step=step)
        except Exception:
            pass

        self._last_flush = now

    def _log_trace(
        self,
        *,
        endpoint: str,
        request_name: str,
        timings: Dict[str, float],
        metrics: Dict[str, Any],
        error: int,
    ) -> None:
        # NOTE: tracing APIs are evolving; keep this best-effort.
        try:
            import mlflow
            import mlflow.tracing.fluent as tf

            mlflow.set_tracking_uri(self._cfg.tracking_uri)
            mlflow.set_experiment(self._cfg.experiment)

            attrs = {
                "endpoint": endpoint,
                "request_name": request_name,
                "error": bool(error),
                "total_ms": float(timings.get("total") or 0.0),
                "domain": metrics.get("domain"),
                "model": metrics.get("model"),
                "provider": metrics.get("provider"),
                "ctx_n": metrics.get("ctx_n"),
                "token_est": metrics.get("token_est"),
            }

            req_obj = None
            resp_obj = None

            if self._cfg.trace_content:
                q = metrics.get("question") if isinstance(metrics.get("question"), str) else None
                a = metrics.get("answer") if isinstance(metrics.get("answer"), str) else None
                if q is not None:
                    req_obj = {"question": _redact_text(q, self._cfg.trace_max_chars)}
                if a is not None:
                    resp_obj = {"answer": _redact_text(a, self._cfg.trace_max_chars)}

            # Deprecated but currently functional; OK for minimal tracing.
            tf.log_trace(
                name="llm_request",
                request=req_obj,
                response=resp_obj,
                attributes={k: v for k, v in attrs.items() if v is not None},
                tags={"service": "rag-service"},
                execution_time_ms=int(float(timings.get("total") or 0.0)),
            )
        except Exception:
            return


_OBS: Optional[MlflowObservability] = None


def init_mlflow_observability() -> Optional[MlflowObservability]:
    global _OBS
    if _OBS is not None:
        return _OBS

    obs = MlflowObservability()
    if not obs.enabled():
        _OBS = obs
        return _OBS

    obs.start()
    _OBS = obs
    return _OBS
