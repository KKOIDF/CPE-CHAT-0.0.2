from __future__ import annotations

import logging
import json
import os
import random
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Optional, Tuple
import uuid


_CATEGORICAL_METRIC_KEYS = {
    "intent_primary",
    "failure_intent",
    "requested_domain",
    "inferred_domain",
    "structured_path_miss_reason",
    "curriculum_lookup_mode",
    "top_k_rerank_mode",
    "routing_domain_initial",
    "routing_domain_final",
    "structured_regulations_miss_reason",
    "structured_regulations_source_kind",
    "structured_curriculum_consistency_guard_mode",
    "retrieval_cache_backend",
    "retrieval_cache_namespace",
}


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

    request_log_enabled: bool
    request_log_content: bool
    request_log_max_chars: int
    request_log_artifact_dir: str


@dataclass
class _SessionAgg:
    turns: int = 0
    cumulative_ms: float = 0.0
    last_seen_ts: float = 0.0


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
        self._stage_latencies: Dict[str, Dict[str, Deque[float]]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=self._cfg.window_n))
        )
        self._metric_sums: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._metric_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._category_counts: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(int))
        )
        self._last_flush: float = 0.0

        self._request_events: Deque[Dict[str, Any]] = deque(maxlen=max(1000, self._cfg.window_n * 2))
        self._dropped_request_events: int = 0
        self._sessions: Dict[str, _SessionAgg] = {}
        self._session_ttl_s: float = max(60.0, float(os.getenv("MLFLOW_OBS_SESSION_TTL_S", "3600") or "3600"))
        self._session_max_n: int = max(100, int(os.getenv("MLFLOW_OBS_SESSION_MAX_N", "5000") or "5000"))

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

        # Log one event per request (every question) as a JSONL artifact.
        # Enabled by default when observability is enabled.
        request_log_enabled = _truthy(os.getenv("MLFLOW_OBS_REQUEST_LOG_ENABLE", "1" if enabled else "0"))
        # Default: store question + answer + ctx_sources.
        request_log_content = _truthy(os.getenv("MLFLOW_OBS_REQUEST_LOG_CONTENT", "1"))
        request_log_max_chars = int(os.getenv("MLFLOW_OBS_REQUEST_LOG_MAX_CHARS", "2000") or "2000")
        request_log_artifact_dir = (os.getenv("MLFLOW_OBS_REQUEST_LOG_DIR") or "requests").strip() or "requests"

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

            request_log_enabled=request_log_enabled,
            request_log_content=request_log_content,
            request_log_max_chars=max(200, request_log_max_chars),
            request_log_artifact_dir=request_log_artifact_dir,
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

            logging.getLogger(__name__).info(
                "MLflow observability enabled: tracking_uri=%s experiment=%s run_id=%s request_log_dir=%s request_log_content=%s trace_sample_rate=%s",
                self._cfg.tracking_uri,
                self._cfg.experiment,
                self._run_id,
                self._cfg.request_log_artifact_dir,
                int(bool(self._cfg.request_log_content)),
                self._cfg.trace_sample_rate,
            )

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
        session_id = self._extract_session_id(metrics)

        total_ms = float(timings.get("total") or 0.0)

        error = 0
        if metrics.get("error") in (1, True, "1", "true", "True"):
            error = 1
        # Heuristic: exception-like answer markers.
        ans = (metrics.get("answer") or "") if isinstance(metrics.get("answer"), str) else ""
        if ans.strip().startswith("(exception)"):
            error = 1

        session_turn_index = 0
        session_cumulative_ms = 0.0

        with self._lock:
            now_ts = time.time()
            if session_id:
                self._gc_sessions_locked(now_ts)
                session_key = f"{endpoint_key}::{session_id}"
                agg = self._sessions.get(session_key)
                if agg is None:
                    if len(self._sessions) >= self._session_max_n:
                        oldest_key = min(self._sessions.items(), key=lambda kv: kv[1].last_seen_ts)[0]
                        self._sessions.pop(oldest_key, None)
                    agg = _SessionAgg(last_seen_ts=now_ts)
                    self._sessions[session_key] = agg
                agg.turns += 1
                if total_ms > 0:
                    agg.cumulative_ms += total_ms
                agg.last_seen_ts = now_ts
                session_turn_index = agg.turns
                session_cumulative_ms = agg.cumulative_ms

            self._counts[endpoint_key] += 1
            if error:
                self._errors[endpoint_key] += 1
            if total_ms > 0:
                self._latencies[endpoint_key].append(total_ms)
            for stage_name, stage_ms in (timings or {}).items():
                if not stage_name or stage_name == "total":
                    continue
                try:
                    v = float(stage_ms)
                except Exception:
                    continue
                if v > 0:
                    self._stage_latencies[endpoint_key][_safe_name(stage_name)].append(v)
            for key, value in (metrics or {}).items():
                if not key or key in {"question", "answer", "ctx_sources"}:
                    continue
                if key in _CATEGORICAL_METRIC_KEYS:
                    sval = str(value).strip()
                    if sval:
                        self._category_counts[endpoint_key][_safe_name(key)][_safe_name(sval)] += 1
                if isinstance(value, bool):
                    numeric = 1.0 if value else 0.0
                elif isinstance(value, (int, float)):
                    numeric = float(value)
                else:
                    continue
                self._metric_sums[endpoint_key][key] += numeric
                self._metric_counts[endpoint_key][key] += 1

        if session_id:
            try:
                metrics = dict(metrics or {})
                metrics["session_id"] = session_id
                metrics["session_turn_index"] = int(session_turn_index)
                metrics["session_cumulative_ms"] = float(session_cumulative_ms)
            except Exception:
                pass

        # Per-request event logging (every question).
        if self._cfg.request_log_enabled:
            self._enqueue_request_event(endpoint=endpoint, request_name=request_name, timings=timings, metrics=metrics, error=error)

        # Optional trace.
        if self._cfg.tracing_enabled and random.random() < self._cfg.trace_sample_rate:
            self._log_trace(endpoint=endpoint, request_name=request_name, timings=timings, metrics=metrics, error=error)

    def _enqueue_request_event(
        self,
        *,
        endpoint: str,
        request_name: str,
        timings: Dict[str, float],
        metrics: Dict[str, Any],
        error: int,
    ) -> None:
        # Keep this fast and non-blocking; never raise.
        try:
            q = metrics.get("question") if isinstance(metrics.get("question"), str) else ""
            a = metrics.get("answer") if isinstance(metrics.get("answer"), str) else ""
            sources = metrics.get("ctx_sources") if isinstance(metrics.get("ctx_sources"), str) else ""

            evt: Dict[str, Any] = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "id": uuid.uuid4().hex,
                "endpoint": endpoint,
                "request_name": request_name,
                "error": bool(error),
                "total_ms": float(timings.get("total") or 0.0),
                "session_id": metrics.get("session_id"),
                "session_turn_index": metrics.get("session_turn_index"),
                "session_cumulative_ms": metrics.get("session_cumulative_ms"),
                "domain": metrics.get("domain"),
                "requested_domain": metrics.get("requested_domain"),
                "model": metrics.get("model"),
                "provider": metrics.get("provider"),
                "ctx_n": metrics.get("ctx_n"),
                "token_est": metrics.get("token_est"),
                "guardrail_triggered": metrics.get("guardrail_triggered"),
                "q_len": metrics.get("q_len"),
                "answer_chars": metrics.get("answer_chars"),
                "intent_primary": metrics.get("intent_primary"),
                "failure_intent": metrics.get("failure_intent"),
                "structured_path_hit": metrics.get("structured_path_hit"),
                "structured_path_eligible": metrics.get("structured_path_eligible"),
                "structured_path_miss_reason": metrics.get("structured_path_miss_reason"),
                "curriculum_lookup_mode": metrics.get("curriculum_lookup_mode"),
                "top_k_rerank_n_docs": metrics.get("top_k_rerank_n_docs"),
                "top_k_rerank_mode": metrics.get("top_k_rerank_mode"),
                "top_k_rerank_cache_hit_ratio": metrics.get("top_k_rerank_cache_hit_ratio"),
                "routing_domain_initial": metrics.get("routing_domain_initial"),
                "routing_domain_final": metrics.get("routing_domain_final"),
                "path_langchain_used": metrics.get("path_langchain_used"),
                "path_nonstructured_used": metrics.get("path_nonstructured_used"),
                "citation_repair_attempt": metrics.get("citation_repair_attempt"),
                "citation_repair_success": metrics.get("citation_repair_success"),
                "retrieval_cache_hit": metrics.get("retrieval_cache_hit"),
                "retrieval_cache_miss": metrics.get("retrieval_cache_miss"),
                "retrieval_cache_expired": metrics.get("retrieval_cache_expired"),
                "retrieval_cache_invalidated": metrics.get("retrieval_cache_invalidated"),
                "retrieval_cache_fallback_to_memory": metrics.get("retrieval_cache_fallback_to_memory"),
                "retrieval_cache_backend": metrics.get("retrieval_cache_backend"),
                "retrieval_cache_namespace": metrics.get("retrieval_cache_namespace"),
            }

            # Store question always (requirement), with truncation.
            evt["question"] = _redact_text(q, self._cfg.request_log_max_chars)

            if self._cfg.request_log_content:
                evt["answer"] = _redact_text(a, self._cfg.request_log_max_chars)
                evt["ctx_sources"] = _redact_text(sources, self._cfg.request_log_max_chars)

            with self._lock:
                if len(self._request_events) >= self._request_events.maxlen:
                    self._dropped_request_events += 1
                else:
                    self._request_events.append(evt)
        except Exception:
            return

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

        # Drain request events first to avoid unbounded growth.
        drained_events: list[Dict[str, Any]] = []
        dropped = 0
        with self._lock:
            if self._request_events:
                drained_events = list(self._request_events)
                self._request_events.clear()
            dropped = int(self._dropped_request_events)
            self._dropped_request_events = 0

        # Snapshot & reset window counters.
        with self._lock:
            counts = dict(self._counts)
            errors = dict(self._errors)
            lats = {k: list(v) for k, v in self._latencies.items()}
            stage_lats = {
                ep: {stage: list(vals) for stage, vals in stage_map.items()}
                for ep, stage_map in self._stage_latencies.items()
            }
            metric_sums_all = {ep: dict(vals) for ep, vals in self._metric_sums.items()}
            metric_counts_all = {ep: dict(vals) for ep, vals in self._metric_counts.items()}
            category_counts_all = {
                ep: {k: dict(v) for k, v in key_map.items()}
                for ep, key_map in self._category_counts.items()
            }
            sessions_snapshot = {
                k: _SessionAgg(
                    turns=int(v.turns),
                    cumulative_ms=float(v.cumulative_ms),
                    last_seen_ts=float(v.last_seen_ts),
                )
                for k, v in self._sessions.items()
            }

        now = time.time()
        step = int(now)

        metrics_to_log: Dict[str, float] = {}

        for ep, n in counts.items():
            metrics_to_log[f"requests_total__{ep}"] = float(n)
            e = float(errors.get(ep, 0))
            metrics_to_log[f"errors_total__{ep}"] = e

            # Session-level visibility for chat analytics in MLflow metrics.
            ep_sessions: list[_SessionAgg] = []
            ep_prefix = f"{ep}::"
            for session_key, session_agg in sessions_snapshot.items():
                if session_key.startswith(ep_prefix):
                    ep_sessions.append(session_agg)
            if ep_sessions:
                metrics_to_log[f"sessions_active__{ep}"] = float(len(ep_sessions))
                metrics_to_log[f"session_turns_avg__{ep}"] = float(
                    sum(s.turns for s in ep_sessions) / float(len(ep_sessions))
                )
                metrics_to_log[f"session_turns_max__{ep}"] = float(
                    max(s.turns for s in ep_sessions)
                )

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

            for stage_name, stage_window in (stage_lats.get(ep) or {}).items():
                if not stage_window:
                    continue
                stage_sorted = sorted(stage_window)

                def stage_pct(p: float) -> float:
                    idx = int(round((p / 100.0) * (len(stage_sorted) - 1)))
                    idx = max(0, min(len(stage_sorted) - 1, idx))
                    return float(stage_sorted[idx])

                metrics_to_log[f"latency_ms_stage_p50__{stage_name}__{ep}"] = stage_pct(50)
                metrics_to_log[f"latency_ms_stage_p90__{stage_name}__{ep}"] = stage_pct(90)
                metrics_to_log[f"latency_ms_stage_p99__{stage_name}__{ep}"] = stage_pct(99)
                metrics_to_log[f"latency_ms_stage_avg__{stage_name}__{ep}"] = float(
                    sum(stage_window) / len(stage_window)
                )

            metric_sums = metric_sums_all.get(ep) or {}
            metric_counts = metric_counts_all.get(ep) or {}
            for key, total_value in metric_sums.items():
                count_value = int(metric_counts.get(key) or 0)
                safe_key = _safe_name(key)
                if key.startswith("guardrail_") or key.endswith("_hit") or key.endswith("_used") or key.endswith("_query"):
                    metrics_to_log[f"sum__{safe_key}__{ep}"] = float(total_value)
                if count_value > 0:
                    metrics_to_log[f"avg__{safe_key}__{ep}"] = float(total_value / count_value)

            # Ready-to-use decision rates.
            structured_eligible = float(metric_sums.get("structured_path_eligible") or 0.0)
            structured_hit = float(metric_sums.get("structured_path_hit") or 0.0)
            structured_fallback = float(metric_sums.get("structured_path_fallback_nonstructured") or 0.0)
            path_langchain_used = float(metric_sums.get("path_langchain_used") or 0.0)
            path_nonstructured_used = float(metric_sums.get("path_nonstructured_used") or 0.0)
            cite_attempt = float(metric_sums.get("citation_repair_attempt") or 0.0)
            cite_success = float(metric_sums.get("citation_repair_success") or 0.0)
            cache_hit = float(metric_sums.get("retrieval_cache_hit") or 0.0)
            cache_miss = float(metric_sums.get("retrieval_cache_miss") or 0.0)
            cache_expired = float(metric_sums.get("retrieval_cache_expired") or 0.0)
            cache_invalidated = float(metric_sums.get("retrieval_cache_invalidated") or 0.0)
            cache_fallback = float(metric_sums.get("retrieval_cache_fallback_to_memory") or 0.0)

            if structured_eligible > 0:
                metrics_to_log[f"rate__structured_path_hit__{ep}"] = structured_hit / structured_eligible
                metrics_to_log[f"rate__structured_path_fallback_nonstructured__{ep}"] = (
                    structured_fallback / structured_eligible
                )
            if n > 0:
                metrics_to_log[f"rate__path_langchain_used__{ep}"] = path_langchain_used / float(n)
                metrics_to_log[f"rate__path_nonstructured_used__{ep}"] = path_nonstructured_used / float(n)
            if cite_attempt > 0:
                metrics_to_log[f"rate__citation_repair_success__{ep}"] = cite_success / cite_attempt
            cache_attempts = cache_hit + cache_miss + cache_expired + cache_invalidated
            if cache_attempts > 0:
                metrics_to_log[f"rate__retrieval_cache_hit__{ep}"] = cache_hit / cache_attempts
                metrics_to_log[f"rate__retrieval_cache_stale__{ep}"] = (cache_expired + cache_invalidated) / cache_attempts
            if n > 0:
                metrics_to_log[f"rate__retrieval_cache_fallback_to_memory__{ep}"] = cache_fallback / float(n)

            # Top categorical signals (intent/domain/failure_intent).
            for cat_key, cat_vals in (category_counts_all.get(ep) or {}).items():
                top_vals = sorted(cat_vals.items(), key=lambda kv: kv[1], reverse=True)[:10]
                for val_key, cnt in top_vals:
                    metrics_to_log[f"count__{cat_key}__{val_key}__{ep}"] = float(cnt)

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

        # Log per-request JSONL artifact batch.
        if drained_events:
            try:
                # Include a small meta line to indicate drops (if any).
                if dropped:
                    drained_events.insert(
                        0,
                        {
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "kind": "meta",
                            "dropped_request_events": dropped,
                        },
                    )
                jsonl = "\n".join([json.dumps(e, ensure_ascii=False) for e in drained_events]) + "\n"
                stamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
                fname = f"requests_{stamp}_{uuid.uuid4().hex[:8]}.jsonl"
                artifact_file = f"{self._cfg.request_log_artifact_dir.rstrip('/')}/{fname}"

                # MLflow 2.5+ has log_text; keep fallback for safety.
                log_text = getattr(self._mlflow, "log_text", None)
                if callable(log_text):
                    log_text(jsonl, artifact_file=artifact_file)
                else:
                    import tempfile
                    from pathlib import Path

                    with tempfile.TemporaryDirectory() as td:
                        p = Path(td) / fname
                        p.write_text(jsonl, encoding="utf-8")
                        # artifact_path must be a directory; split.
                        self._mlflow.log_artifact(str(p), artifact_path=self._cfg.request_log_artifact_dir)
            except Exception:
                pass

        self._last_flush = now

    def flush_now(self) -> None:
        """Best-effort immediate flush (useful at shutdown)."""
        try:
            self.flush()
        except Exception:
            pass

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            counts = dict(self._counts)
            errors = dict(self._errors)
            latencies = {k: list(v) for k, v in self._latencies.items()}
        return {
            "enabled": bool(self._cfg.enabled),
            "counts": counts,
            "errors": errors,
            "latencies": latencies,
        }

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
                "request_total_ms": float(timings.get("total") or 0.0),
                "session_id": str(metrics.get("session_id") or ""),
                "session_cumulative_ms": float(metrics.get("session_cumulative_ms") or 0.0),
                "session_turn_index": int(metrics.get("session_turn_index") or 0),
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
                sources = metrics.get("ctx_sources") if isinstance(metrics.get("ctx_sources"), str) else None
                if q is not None:
                    req_obj = {"question": _redact_text(q, self._cfg.trace_max_chars)}
                    if sources:
                        req_obj["context_sources"] = sources
                if a is not None:
                    resp_obj = {"answer": _redact_text(a, self._cfg.trace_max_chars)}

            for key, value in (metrics or {}).items():
                if key in {"question", "answer"}:
                    continue
                if value is None:
                    continue
                attr_key = f"metric_{_safe_name(key)}"
                if isinstance(value, (int, float, bool, str)):
                    attrs[attr_key] = value
                else:
                    attrs[attr_key] = _redact_text(json.dumps(value, ensure_ascii=False), self._cfg.trace_max_chars)

            # Deprecated but currently functional; OK for minimal tracing.
            trace_tags = {
                "service": "rag-service",
                "endpoint": _safe_name(endpoint),
            }
            if metrics.get("session_id"):
                trace_tags["session_id"] = _redact_text(str(metrics.get("session_id")), 128)

            tf.log_trace(
                name="llm_request",
                request=req_obj,
                response=resp_obj,
                attributes={k: v for k, v in attrs.items() if v is not None},
                tags=trace_tags,
                execution_time_ms=int(
                    round(
                        float(metrics.get("session_cumulative_ms") or 0.0)
                        or float(timings.get("total") or 0.0)
                    )
                ),
            )
        except Exception:
            return

    @staticmethod
    def _extract_session_id(metrics: Dict[str, Any]) -> str:
        if not isinstance(metrics, dict):
            return ""
        for key in ("session_id", "sessionId", "chat_id", "chatId", "conversation_id", "thread_id"):
            v = metrics.get(key)
            if v is None:
                continue
            s = str(v).strip()
            if s:
                return s[:128]
        return ""

    def _gc_sessions_locked(self, now_ts: float) -> None:
        if not self._sessions:
            return
        stale_keys = [
            k for k, v in self._sessions.items()
            if (now_ts - float(v.last_seen_ts or 0.0)) > self._session_ttl_s
        ]
        for k in stale_keys:
            self._sessions.pop(k, None)


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
