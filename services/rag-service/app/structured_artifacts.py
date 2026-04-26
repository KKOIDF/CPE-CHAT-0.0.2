from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import ROOT_DIR


def _artifact_candidates(domain: str, filename: str) -> list[Path]:
    dom = str(domain or '').strip().lower()
    if not dom:
        return []
    return [
        ROOT_DIR / 'indexes' / dom / 'structured' / filename,
        ROOT_DIR / 'data' / 'structured' / dom / filename,
        ROOT_DIR / 'data' / dom / 'structured' / filename,
    ]


def _load_json(paths: list[Path]) -> dict[str, Any]:
    for path in paths:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding='utf-8'))
                if isinstance(data, dict):
                    return data
        except Exception:
            continue
    return {}


@lru_cache(maxsize=1)
def load_announcement_calendar_artifact() -> dict[str, Any]:
    return _load_json(_artifact_candidates('announcements', 'announcement_calendar.json'))


@lru_cache(maxsize=1)
def load_course_prerequisites_artifact() -> dict[str, Any]:
    return _load_json(_artifact_candidates('curriculum', 'course_prerequisites.json'))


@lru_cache(maxsize=1)
def load_regulation_clauses_artifact() -> dict[str, Any]:
    return _load_json(_artifact_candidates('regulations', 'regulation_clauses.json'))
