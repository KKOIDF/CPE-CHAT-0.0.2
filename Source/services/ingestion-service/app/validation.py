from typing import Dict, Any
import re
try:
    from langdetect import detect
except Exception:
    detect = None


def assess_quality(text: str) -> Dict[str, Any]:
    length = len(text)
    lines = text.count("\n") + 1
    avg_line = length / lines if lines else 0
    whitespace_ratio = len(re.findall(r"\s", text)) / (length or 1)
    alpha_ratio = len(re.findall(r"[A-Za-z]", text)) / (length or 1)
    language = None
    if detect and length > 50:
        try:
            language = detect(text[:1000])
        except Exception:
            language = None
    return {
        "length": length,
        "lines": lines,
        "avg_line_length": avg_line,
        "whitespace_ratio": whitespace_ratio,
        "alpha_ratio": alpha_ratio,
        "language": language,
    }


def is_acceptable(stats: Dict[str, Any]) -> bool:
    if stats["length"] < 50:
        return False
    if stats["alpha_ratio"] < 0.2:
        return False
    return True

if __name__ == "__main__":
    sample = "Hello world\nThis is a test document for validation."
    s = assess_quality(sample)
    print(s)
    print("Acceptable?", is_acceptable(s))
