import re
from typing import Dict, Optional

from .utils import (
    normalize_text,
    tidy_thai_spacing,
    thai_postprocess,
    clean_and_spell_correct_thai,
)


_BULLET_START = re.compile(r"^([\-\•\–\*]|\d+[\.)]|[ก-ฮ]\)|\([0-9]+\)|\([ก-ฮ]\))\s+")
_NOISE_LINE = re.compile(r"^[\s\-_=~•·\.]{6,}$")
_PAGE_NUM_LINE = re.compile(r"^\s*(หน้า\s*)?\d{1,4}\s*$")
_PAGE_CONT_LINE = re.compile(r"^\s*\d{1,3}\s*/\s*$")

_THAI_DIGITS_TO_ARABIC: Dict[str, str] = {
    '๐': '0',
    '๑': '1',
    '๒': '2',
    '๓': '3',
    '๔': '4',
    '๕': '5',
    '๖': '6',
    '๗': '7',
    '๘': '8',
    '๙': '9',
}


def _normalize_digits(text: str, thai_to_arabic: bool = False) -> str:
    if not text:
        return ''
    if not thai_to_arabic:
        return text
    t = text
    for th, ar in _THAI_DIGITS_TO_ARABIC.items():
        t = t.replace(th, ar)
    return t


def _strip_noise_lines(text: str, drop_page_numbers: bool = True) -> str:
    if not text:
        return ''
    kept = []
    for ln in text.split('\n'):
        s = ln.strip()
        if not s:
            kept.append('')
            continue
        if _NOISE_LINE.fullmatch(s):
            continue
        if drop_page_numbers and (_PAGE_NUM_LINE.fullmatch(s) or _PAGE_CONT_LINE.fullmatch(s)):
            continue
        s2 = _strip_garbage_prefix(s)
        if _is_mostly_garbage_line(s2):
            continue
        kept.append(s2)
    return '\n'.join(kept)


_THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_DIGIT_RE = re.compile(r"[0-9\u0E50-\u0E59]")


def _strip_garbage_prefix(line: str) -> str:
    """Remove a leading run of short OCR junk tokens if followed by real content.

    Example seen in the dataset:
      'จ7 1 7 ฆ่ 7 ๕เ งหลักสูตรฝึกอบรมหมายความว่า...' -> 'งหลักสูตรฝึกอบรมหมายความว่า...'
    """
    if not line:
        return ''
    tokens = line.split()
    if len(tokens) < 7:
        return line

    def is_content_token(tok: str) -> bool:
        if len(tok) >= 8:
            return True
        # Token with Thai letters that looks like a word, not a single char.
        if _THAI_RE.search(tok) and len(tok) >= 4:
            return True
        return False

    content_idx = None
    for i, tok in enumerate(tokens[:12]):
        if is_content_token(tok):
            content_idx = i
            break
    if content_idx is None or content_idx < 4:
        return line

    prefix = tokens[:content_idx]
    avg_len = sum(len(t) for t in prefix) / max(1, len(prefix))
    has_digits = any(_DIGIT_RE.search(t) for t in prefix)
    if avg_len <= 2.5 and has_digits:
        return ' '.join(tokens[content_idx:]).strip()
    return line


def _is_mostly_garbage_line(line: str) -> bool:
    if not line:
        return False
    s = re.sub(r"\s+", "", line)
    if len(s) < 18:
        return False

    thai = len(_THAI_RE.findall(s))
    latin = len(_LATIN_RE.findall(s))
    digits = len(_DIGIT_RE.findall(s))
    letters = thai + latin
    other = len(s) - (letters + digits)
    total = max(1, len(s))

    # Hard signal: long runs of digits/symbols are almost always garbage.
    if re.search(r"[0-9\u0E50-\u0E59]{14,}", s):
        return True

    digit_ratio = digits / total
    letter_ratio = letters / total
    other_ratio = other / total

    if digit_ratio >= 0.72 and letter_ratio <= 0.15:
        return True
    if other_ratio >= 0.45 and letter_ratio <= 0.20:
        return True
    return False


def _merge_wrapped_lines(text: str) -> str:
    """Merge single line-breaks produced by OCR line-wrapping.

    - Preserves blank lines as paragraph breaks.
    - Preserves bullets as separate logical paragraphs, while allowing continuations.
    """
    if not text:
        return ''

    blocks = re.split(r"\n\s*\n+", text.strip())
    out_blocks = []
    for block in blocks:
        lines = [ln.strip() for ln in block.split('\n') if ln.strip()]
        if not lines:
            continue

        merged_lines = []
        cur: Optional[str] = None
        for ln in lines:
            if _BULLET_START.search(ln):
                if cur:
                    merged_lines.append(cur.strip())
                cur = ln
                continue

            if cur is None:
                cur = ln
                continue

            # Continuation of previous logical line: join with a space.
            cur = f"{cur} {ln}".strip()

        if cur:
            merged_lines.append(cur.strip())

        out_blocks.append('\n'.join(merged_lines).strip())

    return '\n\n'.join(out_blocks).strip()


def postprocess_ocr_text(
    text: str,
    *,
    merge_lines: bool = False,
    normalize_thai_digits: bool = False,
    spell_correct_thai: bool = False,
    custom_map: Optional[Dict[str, str]] = None,
) -> str:
    """Post-process OCR text with conservative, deterministic steps.

    Recommended default usage:
    - Always run (enabled by env flag), but keep spell correction off unless validated.
    """
    if text is None:
        return ''

    t = normalize_text(text, preserve_newlines=True)
    t = _strip_noise_lines(t, drop_page_numbers=True)
    t = tidy_thai_spacing(t)
    t = thai_postprocess(t)
    t = _normalize_digits(t, thai_to_arabic=normalize_thai_digits)

    if merge_lines:
        t = _merge_wrapped_lines(t)

    if spell_correct_thai:
        # Spell-correct on a flattened string then re-normalize spacing.
        t = clean_and_spell_correct_thai(t, custom_map=custom_map, do_spell=True)
        t = normalize_text(t, preserve_newlines=True)

    # Final cleanup
    t = normalize_text(t, preserve_newlines=True)
    return t.strip()
