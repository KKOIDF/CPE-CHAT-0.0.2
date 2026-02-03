import re
from collections import Counter


def text_quality_score(text: str) -> float:
    if not text:
        return 0.0
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    signal = sum(1 for c in chars if c.isalpha() or c.isdigit())
    return signal / max(1, len(chars))

_TH_RANGE = re.compile(r'[\u0E00-\u0E7F]')
_LATIN_RANGE = re.compile(r'[A-Za-z]')


def script_ratios(text: str):
    if not text:
        return 0.0, 0.0
    th = len(_TH_RANGE.findall(text))
    la = len(_LATIN_RANGE.findall(text))
    total = th + la
    if total == 0:
        return 0.0, 0.0
    return th / total, la / total
