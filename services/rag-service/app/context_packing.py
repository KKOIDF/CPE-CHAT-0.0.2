from __future__ import annotations

from pathlib import Path
import math
from typing import Dict, List, Tuple

from .config import TOKEN_BUDGET
from .normalization import CHAR_PER_TOKEN


def est_tokens(text: str) -> int:
    return max(1, int(math.ceil(len(text) / CHAR_PER_TOKEN)))


def _cite_label(c: Dict) -> str:
    src = c.get('source') or c.get('path') or 'unknown'
    try:
        name = Path(str(src)).name
    except Exception:
        name = str(src)
    page = c.get('page_start')
    try:
        page_i = int(page) if page is not None else 0
    except Exception:
        page_i = 0
    return f"{name}/{page_i}"


def pack_context_grouped(
    chunks: List[Dict],
    budget_tokens: int = TOKEN_BUDGET,
    truncate_chars: int | None = None,
) -> Tuple[str, Dict[int, str]]:
    if not chunks:
        return '', {}

    def _truncate_block_to_fit(prefix: str, text: str, remaining_tokens: int) -> str | None:
        """Return a possibly-truncated block that fits in remaining token budget.

        Uses a rough chars-per-token heuristic with a safety check via est_tokens.
        """
        if remaining_tokens <= 0:
            return None
        base = (prefix or '')
        base_tokens = est_tokens(base)
        if base_tokens >= remaining_tokens:
            return None
        txt = (text or '').strip()
        candidate = base + txt
        if est_tokens(candidate) <= remaining_tokens:
            return candidate

        avail_tokens = max(1, remaining_tokens - base_tokens)
        approx_chars = max(80, int(avail_tokens * 4))
        if approx_chars <= 0:
            return None
        clipped = txt[:approx_chars].rstrip()
        if clipped and clipped != txt:
            clipped = clipped + ' ...'
        candidate = base + clipped
        if est_tokens(candidate) > remaining_tokens:
            approx_chars = max(40, int(approx_chars * 0.6))
            clipped = txt[:approx_chars].rstrip()
            if clipped and clipped != txt:
                clipped = clipped + ' ...'
            candidate = base + clipped
        if est_tokens(candidate) <= remaining_tokens and candidate.strip() != base.strip():
            return candidate
        return None

    def _group_key(c: Dict) -> str:
        dom = str(c.get('domain') or '').strip()
        src = str(c.get('source') or c.get('path') or 'unknown').strip()
        if dom:
            return f"{dom}/{src}"
        return src

    groups: Dict[str, List[Dict]] = {}
    for c in chunks:
        groups.setdefault(_group_key(c), []).append(c)

    def _group_score(key: str) -> float:
        xs = groups.get(key, [])
        if not xs:
            return 0.0
        return max(float(x.get('score_final') or x.get('score_rrf') or 0.0) for x in xs)

    order = sorted(groups.keys(), key=_group_score, reverse=True)
    for k2 in order:
        groups[k2].sort(key=lambda x: float(x.get('score_final') or x.get('score_rrf') or 0.0), reverse=True)

    packed_blocks: List[str] = []
    used = 0
    cites: Dict[int, str] = {}
    i = 0

    for gk in order:
        remaining = budget_tokens - used
        if remaining <= 0:
            continue

        group_blocks: List[str] = []
        group_cites: List[str] = []

        for c in groups.get(gk, []):
            cite = _cite_label(c)
            txt = (c.get('text', '') or '').strip()
            if truncate_chars is not None and truncate_chars > 0 and len(txt) > truncate_chars:
                txt = txt[:truncate_chars].rstrip() + ' ...'

            prefix = f"[{cite}] "
            remaining = budget_tokens - used - est_tokens(f"[Source: {gk}]")
            if remaining <= 0:
                break

            block = _truncate_block_to_fit(prefix, txt, remaining_tokens=remaining)
            if not block:
                continue
            group_blocks.append(block)
            group_cites.append(cite)

            if (budget_tokens - used) < 80:
                break

        if not group_blocks:
            continue

        header = f"[Source: {gk}]"
        ht = est_tokens(header)
        if used + ht > budget_tokens:
            continue
        packed_blocks.append(header)
        used += ht

        for block, cite in zip(group_blocks, group_cites):
            t = est_tokens(block)
            if used + t > budget_tokens:
                continue
            packed_blocks.append(block)
            used += t
            i += 1
            cites[i] = cite

        packed_blocks.append('')

    return '\n'.join(packed_blocks).strip(), cites


def pack_context(
    chunks: List[Dict],
    budget_tokens: int = TOKEN_BUDGET,
    truncate_chars: int | None = None,
) -> Tuple[str, Dict[int, str]]:
    def _truncate_block_to_fit(prefix: str, text: str, remaining_tokens: int) -> str | None:
        if remaining_tokens <= 0:
            return None
        base = (prefix or '')
        base_tokens = est_tokens(base)
        if base_tokens >= remaining_tokens:
            return None
        txt = (text or '').strip()
        candidate = base + txt
        if est_tokens(candidate) <= remaining_tokens:
            return candidate
        avail_tokens = max(1, remaining_tokens - base_tokens)
        approx_chars = max(80, int(avail_tokens * 4))
        clipped = txt[:approx_chars].rstrip()
        if clipped and clipped != txt:
            clipped = clipped + ' ...'
        candidate = base + clipped
        if est_tokens(candidate) > remaining_tokens:
            approx_chars = max(40, int(approx_chars * 0.6))
            clipped = txt[:approx_chars].rstrip()
            if clipped and clipped != txt:
                clipped = clipped + ' ...'
            candidate = base + clipped
        if est_tokens(candidate) <= remaining_tokens and candidate.strip() != base.strip():
            return candidate
        return None

    packed_blocks = []
    used = 0
    cites = {}
    for i, c in enumerate(chunks, 1):
        cite = _cite_label(c)
        txt = (c.get('text', '') or '').strip()
        if truncate_chars is not None and truncate_chars > 0 and len(txt) > truncate_chars:
            txt = txt[:truncate_chars].rstrip() + ' ...'
        prefix = f"[{cite}] "
        remaining = budget_tokens - used
        block = _truncate_block_to_fit(prefix, txt, remaining_tokens=remaining)
        if not block:
            continue
        t = est_tokens(block)
        if used + t > budget_tokens:
            continue
        packed_blocks.append(block)
        used += t
        cites[i] = cite
    return '\n\n'.join(packed_blocks), cites
