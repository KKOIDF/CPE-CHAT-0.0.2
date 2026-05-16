from __future__ import annotations

import re
import unicodedata
from pathlib import Path


ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
HEADER_FOOTER_RE = re.compile(r"^(page\s+\d+|\d+\s*/\s*\d+)$", re.IGNORECASE)


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = ZERO_WIDTH_RE.sub("", value)
    value = CONTROL_RE.sub(" ", value)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.split("\n")]
    cleaned: list[str] = []
    prev_blank = False
    for line in lines:
        if HEADER_FOOTER_RE.match(line):
            continue
        if not line:
            if prev_blank:
                continue
            cleaned.append("")
            prev_blank = True
            continue
        prev_blank = False
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def infer_domain(source_path: str, fallback: str = "unknown") -> str:
    parts = {part.lower() for part in Path(source_path or "").parts}
    for name in ("announcements", "regulations", "curriculum", "test_domain"):
        if name in parts:
            return name
    return fallback
