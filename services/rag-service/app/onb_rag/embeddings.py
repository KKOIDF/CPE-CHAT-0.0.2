"""Compatibility wrappers around the existing CPE-CHAT embedding path."""

from __future__ import annotations

from typing import List

from ..chroma_client import embed_texts


def generate_embeddings(texts: List[str], is_query: bool = False) -> List[List[float]]:
    return embed_texts(texts, is_query=is_query)
