from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..chroma_client import semantic_search_global
from ..sqlite_client import keyword_search_global_chunks


def vector_search(query: str, top_k: int, where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    return semantic_search_global(query, top_k=top_k, where=where)


def keyword_search(query: str, top_k: int, strict_domain: str | None = None) -> List[Dict[str, Any]]:
    return keyword_search_global_chunks(query, limit=top_k, strict_domain=strict_domain)
