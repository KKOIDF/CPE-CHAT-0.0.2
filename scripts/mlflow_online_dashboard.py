from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

try:
    from mlflow.tracking import MlflowClient
except Exception:
    MlflowClient = None


DEFAULT_EXPERIMENT = os.getenv("MLFLOW_OBSERVABILITY_EXPERIMENT", "cpe-chat-online-observability")
DEFAULT_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")
DEFAULT_ENDPOINT = "rag_answer"


@dataclass
class MetricSnapshot:
    key: str
    latest: Optional[float]
    history: List[Dict[str, Any]]


class MlflowApi:
    def __init__(self, tracking_uri: str, timeout_s: float = 30.0) -> None:
        self.base = tracking_uri.rstrip("/")
        self.timeout_s = timeout_s
        self.client = MlflowClient(tracking_uri=tracking_uri) if MlflowClient else None

    def _get(self, path: str, **params: Any) -> Dict[str, Any]:
        response = requests.get(f"{self.base}{path}", params=params, timeout=self.timeout_s)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(f"{self.base}{path}", json=payload, timeout=self.timeout_s)
        response.raise_for_status()
        return response.json()

    def get_experiment_by_name(self, experiment_name: str) -> Dict[str, Any]:
        payload = self._get(
            "/api/2.0/mlflow/experiments/get-by-name",
            experiment_name=experiment_name,
        )
        experiment = payload.get("experiment")
        if not experiment:
            raise RuntimeError(f"Experiment not found: {experiment_name}")
        return experiment

    def search_runs(self, experiment_id: str, max_results: int = 5) -> List[Dict[str, Any]]:
        payload = self._post(
            "/api/2.0/mlflow/runs/search",
            {
                "experiment_ids": [experiment_id],
                "run_view_type": "ACTIVE_ONLY",
                "max_results": max_results,
                "order_by": ["attribute.start_time DESC"],
            },
        )
        return payload.get("runs", [])

    def get_metric_history(self, run_id: str, metric_key: str) -> List[Dict[str, Any]]:
        if self.client is not None:
            try:
                history = self.client.get_metric_history(run_id, metric_key)
                return [
                    {
                        "key": item.key,
                        "value": item.value,
                        "timestamp": item.timestamp,
                        "step": item.step,
                    }
                    for item in history
                ]
            except Exception:
                pass

        payload = self._get(
            "/api/2.0/mlflow/metrics/get-history",
            run_id=run_id,
            metric_key=metric_key,
        )
        return payload.get("metrics", [])


def _metric_map(run: Dict[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for item in run.get("data", {}).get("metrics", []):
        key = item.get("key")
        value = item.get("value")
        if key:
            try:
                out[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
    return out


def _latest_value(history: List[Dict[str, Any]]) -> Optional[float]:
    if not history:
        return None
    latest = max(history, key=lambda item: (int(item.get("step") or 0), int(item.get("timestamp") or 0)))
    try:
        return float(latest.get("value"))
    except (TypeError, ValueError):
        return None


def _fmt_number(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def _fmt_ratio(numerator: Optional[float], denominator: Optional[float]) -> str:
    if numerator is None or denominator in (None, 0):
        return "n/a"
    return f"{(100.0 * numerator / denominator):.2f}%"


def _fmt_ts(timestamp_ms: Optional[int]) -> str:
    if not timestamp_ms:
        return "n/a"
    dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def _tail_rows(history: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    rows = sorted(history, key=lambda item: (int(item.get("step") or 0), int(item.get("timestamp") or 0)))
    return rows[-limit:]


def build_dashboard_payload(
    *,
    run: Dict[str, Any],
    metric_histories: Dict[str, List[Dict[str, Any]]],
    endpoint: str,
    experiment_name: str,
    tracking_uri: str,
    history_limit: int,
) -> Dict[str, Any]:
    run_info = run.get("info", {})
    run_id = run_info.get("run_id") or run_info.get("run_uuid") or "unknown"
    metrics_latest = _metric_map(run)

    requests_key = f"requests_total__{endpoint}"
    guardrail_key = f"sum__guardrail_triggered__{endpoint}"
    fallback_key = f"sum__retrieval_domain_fallback_used__{endpoint}"
    final_ctx_key = f"avg__retrieval_final_n__{endpoint}"

    summary = {
        "tracking_uri": tracking_uri,
        "experiment": experiment_name,
        "endpoint": endpoint,
        "run_id": run_id,
        "run_name": run_info.get("run_name", "n/a"),
        "status": run_info.get("status", "n/a"),
        "started_at": _fmt_ts(run_info.get("start_time")),
        "last_flush_at": _fmt_ts(
            max(
                (int(item.get("timestamp") or 0) for history in metric_histories.values() for item in history),
                default=0,
            )
        ),
    }

    highlights = {
        "requests_total": metrics_latest.get("requests_total"),
        requests_key: metrics_latest.get(requests_key),
        f"latency_ms_p50__{endpoint}": metrics_latest.get(f"latency_ms_p50__{endpoint}"),
        f"latency_ms_p90__{endpoint}": metrics_latest.get(f"latency_ms_p90__{endpoint}"),
        f"latency_ms_p99__{endpoint}": metrics_latest.get(f"latency_ms_p99__{endpoint}"),
        f"latency_ms_avg__{endpoint}": metrics_latest.get(f"latency_ms_avg__{endpoint}"),
        guardrail_key: metrics_latest.get(guardrail_key, 0.0),
        fallback_key: metrics_latest.get(fallback_key, 0.0),
        final_ctx_key: metrics_latest.get(final_ctx_key),
    }

    derived = {
        "guardrail_hit_rate": _fmt_ratio(highlights.get(guardrail_key), highlights.get(requests_key)),
        "domain_fallback_rate": _fmt_ratio(highlights.get(fallback_key), highlights.get(requests_key)),
    }

    history_tails = {
        key: _tail_rows(history, history_limit)
        for key, history in metric_histories.items()
        if history
    }

    return {
        "summary": summary,
        "highlights": highlights,
        "derived": derived,
        "history": history_tails,
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = payload["summary"]
    highlights = payload["highlights"]
    derived = payload["derived"]
    history = payload["history"]
    endpoint = summary["endpoint"]

    lines: List[str] = []
    lines.append("# MLflow Online Observability Dashboard")
    lines.append("")
    lines.append(f"- Tracking URI: `{summary['tracking_uri']}`")
    lines.append(f"- Experiment: `{summary['experiment']}`")
    lines.append(f"- Run ID: `{summary['run_id']}`")
    lines.append(f"- Run Name: `{summary['run_name']}`")
    lines.append(f"- Status: `{summary['status']}`")
    lines.append(f"- Started At: `{summary['started_at']}`")
    lines.append(f"- Last Flush At: `{summary['last_flush_at']}`")
    lines.append("")
    lines.append("## KPI Summary")
    lines.append("")
    lines.append(f"- Total Requests: {_fmt_number(highlights.get('requests_total'), 0)}")
    rag_requests = next((value for key, value in highlights.items() if key.startswith("requests_total__")), None)
    lines.append(f"- RAG Answer Requests: {_fmt_number(rag_requests, 0)}")
    lines.append(f"- Latency P50: {_fmt_number(highlights.get(f'latency_ms_p50__{endpoint}'))} ms")
    lines.append(f"- Latency P90: {_fmt_number(highlights.get(f'latency_ms_p90__{endpoint}'))} ms")
    lines.append(f"- Latency P99: {_fmt_number(highlights.get(f'latency_ms_p99__{endpoint}'))} ms")
    lines.append(f"- Latency Avg: {_fmt_number(highlights.get(f'latency_ms_avg__{endpoint}'))} ms")
    lines.append(f"- Guardrail Hits: {_fmt_number(highlights.get(f'sum__guardrail_triggered__{endpoint}'), 0)}")
    lines.append(f"- Guardrail Hit Rate: {derived['guardrail_hit_rate']}")
    lines.append(f"- Domain Fallback Hits: {_fmt_number(highlights.get(f'sum__retrieval_domain_fallback_used__{endpoint}'), 0)}")
    lines.append(f"- Domain Fallback Rate: {derived['domain_fallback_rate']}")
    lines.append(f"- Avg Retrieval Final Context Count: {_fmt_number(highlights.get(f'avg__retrieval_final_n__{endpoint}'))}")
    lines.append("")
    lines.append("## Query Recipes")
    lines.append("")
    lines.append("- MLflow Run Filter: `tags.service = 'rag-service' AND tags.kind = 'observability'`")
    lines.append("- Primary Latency Metrics: `latency_ms_p50__rag_answer`, `latency_ms_p90__rag_answer`, `latency_ms_p99__rag_answer`, `latency_ms_avg__rag_answer`")
    lines.append("- Guardrail Metrics: `sum__guardrail_triggered__rag_answer`, `avg__guardrail_triggered__rag_answer`, `sum__guardrail_missing_exact_date_evidence__rag_answer`")
    lines.append("- Retrieval Metrics: `sum__retrieval_domain_fallback_used__rag_answer`, `avg__retrieval_final_n__rag_answer`, `avg__ctx_n__rag_answer`, `avg__retrieval_sem_n__rag_answer`")
    lines.append("")
    lines.append("## Metric History Tail")
    lines.append("")
    for metric_key, rows in history.items():
        lines.append(f"### `{metric_key}`")
        lines.append("")
        lines.append("| Step | Timestamp | Value |")
        lines.append("| --- | --- | ---: |")
        for row in rows:
            lines.append(
                f"| {row.get('step', 'n/a')} | {_fmt_ts(int(row.get('timestamp') or 0))} | {_fmt_number(float(row.get('value')))} |"
            )
        lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an MLflow dashboard summary for online observability metrics.")
    parser.add_argument("--tracking-uri", default=DEFAULT_TRACKING_URI)
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--history-limit", type=int, default=10)
    parser.add_argument("--output", default="")
    parser.add_argument("--json-output", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api = MlflowApi(args.tracking_uri)
    experiment = api.get_experiment_by_name(args.experiment)
    runs = api.search_runs(experiment["experiment_id"], max_results=1)
    if not runs:
        raise RuntimeError(f"No active runs found in experiment: {args.experiment}")

    run = runs[0]
    run_id = run.get("info", {}).get("run_id") or run.get("info", {}).get("run_uuid")
    metric_keys = [
        f"requests_total__{args.endpoint}",
        f"latency_ms_p50__{args.endpoint}",
        f"latency_ms_p90__{args.endpoint}",
        f"latency_ms_p99__{args.endpoint}",
        f"latency_ms_avg__{args.endpoint}",
        f"sum__guardrail_triggered__{args.endpoint}",
        f"sum__guardrail_missing_exact_date_evidence__{args.endpoint}",
        f"sum__retrieval_domain_fallback_used__{args.endpoint}",
        f"avg__retrieval_final_n__{args.endpoint}",
        f"avg__ctx_n__{args.endpoint}",
    ]
    histories = {key: api.get_metric_history(run_id, key) for key in metric_keys}
    payload = build_dashboard_payload(
        run=run,
        metric_histories=histories,
        endpoint=args.endpoint,
        experiment_name=args.experiment,
        tracking_uri=args.tracking_uri,
        history_limit=args.history_limit,
    )

    markdown = render_markdown(payload)
    print(markdown)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(markdown, encoding="utf-8")

    if args.json_output:
        json_path = Path(args.json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())