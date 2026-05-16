from __future__ import annotations

import os
import re
from typing import List

try:
    import tiktoken
except Exception:  # pragma: no cover
    tiktoken = None  # type: ignore

try:
    from pythainlp.tokenize import word_tokenize
except Exception:  # pragma: no cover
    word_tokenize = None  # type: ignore


THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
ANCHOR_RE = re.compile(
    r"\b[A-Za-z]{2,6}\s*-?\s*\d{3}\b|\b\d+\.\d+\b|ข้อ\s*\d+(?:\.\d+)?|หมวด\s*\d+",
    re.IGNORECASE,
)
_TIKTOKEN = tiktoken.get_encoding("o200k_base") if tiktoken else None


def _thai_enabled() -> bool:
    return (os.getenv("THAI_TOKENIZER_PROVIDER", "pythainlp") or "pythainlp").strip().lower() == "pythainlp"


def _thai_engine() -> str:
    return (os.getenv("THAI_TOKENIZER_ENGINE", "newmm") or "newmm").strip().lower()


def contains_thai(text: str) -> bool:
    return bool(THAI_RE.search(text or ""))


def _protect_anchors(text: str) -> tuple[str, dict[str, str]]:
    mapping: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        key = f"__ANCHOR_{len(mapping)}__"
        mapping[key] = match.group(0)
        return f" {key} "

    return ANCHOR_RE.sub(repl, text or ""), mapping


def _restore_anchor(token: str, mapping: dict[str, str]) -> str:
    return mapping.get(token, token)


def tokenize(text: str) -> List[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    if contains_thai(raw) and _thai_enabled() and word_tokenize is not None:
        protected, mapping = _protect_anchors(raw)
        try:
            tokens = word_tokenize(protected, engine=_thai_engine(), keep_whitespace=False)
        except TypeError:
            tokens = word_tokenize(protected, engine=_thai_engine())
        out = []
        for token in tokens:
            token = _restore_anchor(str(token).strip(), mapping).strip()
            if token:
                out.append(token)
        return out
    return [tok for tok in re.split(r"\s+", raw) if tok]


def count_tokens(text: str) -> int:
    raw = (text or "").strip()
    if not raw:
        return 0
    if contains_thai(raw):
        return len(tokenize(raw))
    if _TIKTOKEN is not None:
        try:
            return len(_TIKTOKEN.encode(raw))
        except Exception:
            pass
    return max(1, int(len(raw.split()) * 1.3))


def split_by_tokens(text: str, max_tokens: int, overlap_tokens: int) -> List[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    tokens = tokenize(raw)
    if not tokens:
        return []
    if len(tokens) <= max_tokens:
        return [raw]
    step = max(1, max_tokens - max(0, overlap_tokens))
    chunks: list[str] = []
    for start in range(0, len(tokens), step):
        piece = tokens[start : start + max_tokens]
        if not piece:
            continue
        chunks.append(" ".join(piece).strip())
        if start + max_tokens >= len(tokens):
            break
    return [chunk for chunk in chunks if chunk]
