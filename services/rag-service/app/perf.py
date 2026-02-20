import contextvars
import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

logger = logging.getLogger("rag-service")

_TIMINGS: contextvars.ContextVar[Optional[Dict[str, float]]] = contextvars.ContextVar(
    "rag_timings", default=None
)
_METRICS: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "rag_metrics", default=None
)


def _enabled() -> bool:
    return (os.getenv("RAG_TIMING", "0") or "0").strip().lower() in ("1", "true", "yes", "on")


def _min_ms() -> float:
    try:
        return float(os.getenv("RAG_TIMING_MIN_MS", "0") or "0")
    except Exception:
        return 0.0


def add_metric(key: str, value: Any) -> None:
    metrics = _METRICS.get()
    if metrics is None:
        return
    metrics[key] = value


@contextmanager
def time_block(name: str) -> Iterator[None]:
    timings = _TIMINGS.get()
    if timings is None:
        yield
        return

    t0 = time.perf_counter()
    try:
        yield
    finally:
        dt_ms = (time.perf_counter() - t0) * 1000.0
        timings[name] = timings.get(name, 0.0) + dt_ms


@contextmanager
def request_timing(request_name: str, **initial_metrics: Any) -> Iterator[None]:
    if not _enabled():
        yield
        return

    timings: Dict[str, float] = {}
    metrics: Dict[str, Any] = {k: v for k, v in initial_metrics.items() if v is not None}
    token_t = _TIMINGS.set(timings)
    token_m = _METRICS.set(metrics)

    t0 = time.perf_counter()
    try:
        yield
    finally:
        total_ms = (time.perf_counter() - t0) * 1000.0
        timings["total"] = total_ms

        min_ms = _min_ms()
        if total_ms >= min_ms:
            # Keep output compact: stable ordering with total first, then by duration desc.
            items = [(k, v) for k, v in timings.items()]
            items.sort(key=lambda kv: (0 if kv[0] == "total" else 1, -kv[1]))
            timing_str = " ".join([f"{k}={v:.1f}ms" for k, v in items])
            metric_str = " ".join([f"{k}={metrics[k]}" for k in sorted(metrics.keys())])
            if metric_str:
                logger.info("[TIMING][%s] %s | %s", request_name, timing_str, metric_str)
            else:
                logger.info("[TIMING][%s] %s", request_name, timing_str)

        try:
            _TIMINGS.reset(token_t)
            _METRICS.reset(token_m)
        except Exception:
            pass
