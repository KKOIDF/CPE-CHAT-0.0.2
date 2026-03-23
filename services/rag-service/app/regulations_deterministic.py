import re
import os
import glob
from typing import Any


def _find_exam_rule_files() -> list[str]:
    """Find rule_exam*.txt files, checking multiple possible data locations."""
    candidates = [
        os.getenv("DATA_DIR", ""),
        "/home/testuser/CPE-CHAT-0.0.2/data",
        "/app/data",
        os.path.join(os.getcwd(), "data"),
    ]
    for base in candidates:
        if not base:
            continue
        files = glob.glob(os.path.join(base, "regulations", "rule_exam*.txt"))
        if files:
            return files
    return []


def _read_exam_rules() -> str:
    """Return combined text of all rule_exam files, or empty string."""
    files = _find_exam_rule_files()
    if not files:
        return ""
    parts = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                parts.append(fh.read())
        except Exception:
            pass
    return "\n\n".join(parts)


def fetch_exam_clause(clause_num: str) -> str | None:
    """Return the text of a specific numbered clause from exam rules."""
    txt = _read_exam_rules()
    if not txt:
        return None
    pattern = rf"(ข้อ {clause_num}\s.*?)(?=ข้อ \d+|$)"
    m = re.search(pattern, txt, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# Topic-based lookup: matches policy keywords without needing a clause number
# ---------------------------------------------------------------------------

_TOPIC_PATTERNS: list[tuple[list[str], re.Pattern, str]] = [
    # (keywords_to_match_in_question, regex_in_rules_text, topic_label)
    (
        ["ทุจริต", "โกง"],
        re.compile(r"(ข้อ\s*\d+\s[^\n]*ทุจริต.*?)(?=ข้อ \d+|$)", re.DOTALL | re.IGNORECASE),
        "ทุจริตสอบ",
    ),
    (
        ["อุทธรณ์"],
        re.compile(r"(ข้อ\s*\d+\s[^\n]*อุทธรณ์.*?)(?=ข้อ \d+|$)", re.DOTALL | re.IGNORECASE),
        "อุทธรณ์ผลการสอบ",
    ),
    (
        ["บทลงโทษ", "โทษ", "ลงโทษ"],
        re.compile(r"(ข้อ\s*\d+\s[^\n]*(?:โทษ|ลงโทษ|บทกำหนดโทษ).*?)(?=ข้อ \d+|$)", re.DOTALL | re.IGNORECASE),
        "บทลงโทษ",
    ),
    (
        ["แต่งกาย", "ชุดนักศึกษา", "เครื่องแต่งกาย"],
        re.compile(r"(ข้อ\s*\d+\s[^\n]*(?:แต่งกาย|เครื่องแต่งกาย|ชุดนักศึกษา).*?)(?=ข้อ \d+|$)", re.DOTALL | re.IGNORECASE),
        "การแต่งกายเข้าสอบ",
    ),
    (
        ["หมดสิทธิ์", "ขาดสอบ"],
        re.compile(r"(ข้อ\s*\d+\s[^\n]*(?:หมดสิทธิ์|ขาดสอบ).*?)(?=ข้อ \d+|$)", re.DOTALL | re.IGNORECASE),
        "การหมดสิทธิ์สอบ",
    ),
    (
        ["คณะกรรมการ"],
        re.compile(r"(ข้อ\s*\d+\s[^\n]*คณะกรรมการ.*?)(?=ข้อ \d+|$)", re.DOTALL | re.IGNORECASE),
        "คณะกรรมการจัดสอบ",
    ),
]


def _topic_lookup(q: str, rules_text: str) -> dict[str, Any] | None:
    """Try to find relevant clauses by topic keywords."""
    ql = q.lower()
    for keywords, pattern, label in _TOPIC_PATTERNS:
        if any(k in ql for k in keywords):
            matches = pattern.findall(rules_text)
            if matches:
                # Return up to 2 matches to keep answer concise
                snippets = [m.strip() for m in matches[:2]]
                ans = f"ระเบียบสอบที่เกี่ยวกับ{label}:\n\n" + "\n\n".join(snippets) + "\n\n[rule_exam2560.txt/1]"
                return {
                    "answer": ans,
                    "lookup_mode": f"exam_topic_{label}",
                    "miss_reason": "",
                }
    return None


def structured_regulations_lookup(question: str) -> dict[str, Any]:
    """Deterministic lookup for regulations domain.

    Priority:
    1. Numbered clause lookup  (ข้อ 12 ...)
    2. Topic keyword lookup    (ทุจริต, อุทธรณ์, แต่งกาย, ...)
    """
    q = (question or "").strip()

    # Priority 1: Numbered clause
    m = re.search(r"ข้อ\s*(\d+)", q)
    if m and any(k in q for k in ("ห้องสอบ", "มาสาย", "สอบ", "ทุจริต", "เข้าสอบ", "ออก", "นาที", "ชั่วโมง")):
        clause_num = m.group(1)
        clause_text = fetch_exam_clause(clause_num)
        if clause_text:
            ans = f"ระเบียบการสอบ ข้อ {clause_num} กำหนดไว้ดังนี้:\n\n{clause_text}\n\n[rule_exam2560.txt/1]"
            return {"answer": ans, "lookup_mode": f"exam_clause_{clause_num}", "miss_reason": ""}

    # Priority 2: Topic-based search
    rules_text = _read_exam_rules()
    if rules_text:
        result = _topic_lookup(q, rules_text)
        if result:
            return result

    return {"answer": None, "lookup_mode": "none", "miss_reason": "no_deterministic_match"}
