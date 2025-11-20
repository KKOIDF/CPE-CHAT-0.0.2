from typing import List
import re

DEFAULT_MAX_CHARS = 1200
DEFAULT_MIN_CHARS = 300

_sentence_splitter = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> List[str]:
    # naive sentence split
    return _sentence_splitter.split(text.strip())


def chunk_text(text: str, max_chars: int = DEFAULT_MAX_CHARS, min_chars: int = DEFAULT_MIN_CHARS) -> List[str]:
    sentences = split_sentences(text)
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if current_len + len(s) + 1 <= max_chars:
            current.append(s)
            current_len += len(s) + 1
        else:
            if current_len >= min_chars:
                chunks.append(" ".join(current))
                current = [s]
                current_len = len(s)
            else:
                # if too small, allow overflow chunk
                current.append(s)
                chunks.append(" ".join(current))
                current = []
                current_len = 0
    if current:
        chunks.append(" ".join(current))
    return chunks

if __name__ == "__main__":
    sample = "This is sentence one. This is sentence two! Another sentence? Final sentence here." * 20
    ch = chunk_text(sample)
    for i, c in enumerate(ch):
        print(i, len(c))
