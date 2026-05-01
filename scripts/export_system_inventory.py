#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_service_blocks(compose_text: str) -> dict[str, list[str]]:
    lines = compose_text.splitlines()
    services: dict[str, list[str]] = {}
    in_services = False
    current: str | None = None

    for line in lines:
        if line.startswith("services:"):
            in_services = True
            continue
        if not in_services:
            continue
        if re.match(r"^[A-Za-z0-9_-]+:\s*$", line):
            # stop when leaving top-level service section
            if line.strip() in {"networks:", "volumes:"}:
                break
        m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if m:
            current = m.group(1)
            services[current] = []
            continue
        if current is not None:
            services[current].append(line)
    return services


def extract_ports(block: list[str]) -> str:
    ports: list[str] = []
    in_ports = False
    for line in block:
        if re.match(r"^    ports:\s*$", line):
            in_ports = True
            continue
        if in_ports:
            if re.match(r"^    [A-Za-z_]", line):
                break
            m = re.match(r'^\s*-\s*"?(.*?)"?\s*$', line.strip())
            if m:
                ports.append(m.group(1))
    return ", ".join(ports) if ports else "-"


def extract_env(block: list[str]) -> list[tuple[str, str]]:
    envs: list[tuple[str, str]] = []
    in_env = False
    for line in block:
        if re.match(r"^    environment:\s*$", line):
            in_env = True
            continue
        if in_env:
            if re.match(r"^    [A-Za-z_]", line):
                break
            m = re.match(r'^\s*([A-Z0-9_]+):\s*"?([^"]*)"?\s*$', line.strip())
            if m:
                envs.append((m.group(1), m.group(2)))
    return envs


def extract_volumes(block: list[str]) -> list[str]:
    vols: list[str] = []
    in_vol = False
    for line in block:
        if re.match(r"^    volumes:\s*$", line):
            in_vol = True
            continue
        if in_vol:
            if re.match(r"^    [A-Za-z_]", line):
                break
            m = re.match(r'^\s*-\s*(.*?)\s*$', line.strip())
            if m:
                vols.append(m.group(1))
    return vols


def service_description(name: str) -> str:
    return {
        "rag-service": "Main FastAPI back-end for retrieval, answer generation, and OpenAI-compatible API.",
        "openweb-ui": "Web chat interface connected to the back-end through the OpenAI-compatible endpoint.",
        "mlflow": "Experiment tracking and observability service for online and offline monitoring.",
        "redis": "Session and follow-up memory store for multi-turn conversations.",
    }.get(name, "-")


def config_table(config_text: str) -> list[tuple[str, str]]:
    keys = [
        "KNOWN_DOMAINS",
        "EMBEDDING_MODEL",
        "TOKEN_BUDGET",
        "MAX_CONTEXTS",
        "LLM_MODEL",
        "LLM_MAX_TOKENS",
        "LLM_TEMPERATURE",
        "LLM_PROVIDER",
        "OPENAI_BASE_URL",
        "TYPHOON_BASE_URL",
        "OLLAMA_BASE_URL",
    ]
    rows: list[tuple[str, str]] = []
    for key in keys:
        m = re.search(rf"{re.escape(key)}\s*=\s*(.+)", config_text)
        if m:
            rows.append((key, m.group(1).strip()))
    return rows


def build_markdown(compose_path: Path, config_path: Path) -> str:
    compose_text = read_text(compose_path)
    config_text = read_text(config_path)
    services = extract_service_blocks(compose_text)

    lines: list[str] = []
    lines.append("# System Inventory")
    lines.append("")
    lines.append(f"Generated from `{compose_path}` and `{config_path}`.")
    lines.append("")

    lines.append("## Services")
    lines.append("")
    lines.append("| Service | Description | Ports / Interface |")
    lines.append("|---|---|---|")
    for name, block in services.items():
        lines.append(f"| `{name}` | {service_description(name)} | `{extract_ports(block)}` |")
    lines.append("")

    lines.append("## Service Volumes")
    lines.append("")
    lines.append("| Service | Volumes |")
    lines.append("|---|---|")
    for name, block in services.items():
        vols = extract_volumes(block)
        lines.append(f"| `{name}` | {'; '.join(f'`{v}`' for v in vols) if vols else '-'} |")
    lines.append("")

    lines.append("## Important Environment Variables")
    lines.append("")
    lines.append("| Service | Variable | Example / Value |")
    lines.append("|---|---|---|")
    allow = {
        "rag-service": {
            "RAG_HOST",
            "RAG_PORT",
            "CPE_INDEX_ROOT",
            "TOKEN_BUDGET",
            "MAX_CONTEXTS",
            "LLM_PROVIDER",
            "LLM_MODEL",
            "LLM_AUX_PROVIDER",
            "LLM_AUX_MODEL",
            "TYPHOON_BASE_URL",
            "OLLAMA_BASE_URL",
            "RAG_SESSION_REDIS_URL",
            "MLFLOW_TRACKING_URI",
        },
        "openweb-ui": {"OPENAI_API_BASE_URL", "OPENAI_API_KEY"},
    }
    for name, block in services.items():
        for key, value in extract_env(block):
            if key in allow.get(name, set()):
                lines.append(f"| `{name}` | `{key}` | `{value}` |")
    lines.append("")

    lines.append("## Runtime Configuration From `config.py`")
    lines.append("")
    lines.append("| Key | Definition |")
    lines.append("|---|---|")
    for key, value in config_table(config_text):
        lines.append(f"| `{key}` | `{value}` |")
    lines.append("")

    lines.append("## Data and Index Paths")
    lines.append("")
    lines.append("| Path | Description |")
    lines.append("|---|---|")
    path_rows = [
        ("data/raw/announcements", "Raw source documents for the announcements domain."),
        ("data/raw/regulations", "Raw source documents for the regulations domain."),
        ("data/raw/curriculum", "Raw source documents for the curriculum domain."),
        ("indexes/<domain>/vector/chroma", "Vector index storage used for semantic retrieval."),
        ("indexes/<domain>/vector/sqlite/ingestion.db", "SQLite/FTS index used for keyword retrieval."),
        ("services/ingestion-service/data", "Default data area used by ingestion tooling."),
        ("out/", "Generated report artifacts from export scripts."),
    ]
    for path, desc in path_rows:
        lines.append(f"| `{path}` | {desc} |")
    lines.append("")

    lines.append("## System Data Flow")
    lines.append("")
    lines.append("1. Raw documents are stored under `data/raw/<domain>`.")
    lines.append("2. `ingestion-service` performs extraction, OCR, chunking, and indexing.")
    lines.append("3. Index data is written to Chroma and SQLite under `indexes/<domain>/vector/...`.")
    lines.append("4. `rag-service` loads these indexes to support retrieval and answer generation.")
    lines.append("5. `openweb-ui` calls `rag-service` through `/v1/chat/completions` for end-user interaction.")
    lines.append("6. `redis` stores session and follow-up state, while `mlflow` captures observability data.")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export system inventory from docker-compose and config.")
    parser.add_argument("--compose", default="docker-compose.yml", help="Path to docker-compose.yml")
    parser.add_argument("--config", default="services/rag-service/app/config.py", help="Path to config.py")
    parser.add_argument("--output", default="out/system_inventory.md", help="Output Markdown path")
    args = parser.parse_args()

    compose_path = ROOT / args.compose
    config_path = ROOT / args.config
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_markdown(compose_path, config_path), encoding="utf-8")
    print(f"Wrote {output_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
