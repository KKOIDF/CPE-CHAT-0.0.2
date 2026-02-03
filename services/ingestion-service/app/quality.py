import re, time, hashlib
from typing import Dict

from langdetect import detect

WEIRD_CHAR_PATTERN = re.compile(r"[^\wก-ฮะ-์\s.,;:!?()\[\]/\-]")


def ocr_quality_score(text: str) -> float:
    if not text or not text.strip():
        return 0.0
    total = len(text)
    weird = len(WEIRD_CHAR_PATTERN.findall(text))
    score = 1.0 - (weird / max(1, total))
    return max(0.0, min(1.0, score))


def is_valid_ocr(text: str, expected_lang: str = 'th', min_score: float = 0.7, min_length: int = 30) -> bool:
    if not text or len(text.strip()) < min_length:
        return False
    try:
        lang = detect(text)
    except Exception:
        return False
    score = ocr_quality_score(text)
    return (lang in [expected_lang, 'en']) and score >= min_score


def make_quality_entry(doc_id: str, page_num: int, text: str, engine: str, status: str, notes: str = '') -> Dict:
    return {
        'doc_id': doc_id,
        'page_num': page_num,
        'quality_score': ocr_quality_score(text),
        'engine': engine,
        'status': status,
        'notes': notes,
        'created_at': int(time.time())
    }
