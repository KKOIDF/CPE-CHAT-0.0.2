import re
import os
import glob
from typing import Any

def fetch_exam_clause(clause_num: str) -> str | None:
    # Use standard CWD fallback if DATA_DIR missing
    data_dir = os.getenv('DATA_DIR', os.path.join(os.getcwd(), 'data'))
    pattern = os.path.join(data_dir, 'regulations', 'rule_exam*.txt')
    files = glob.glob(pattern)
    if not files:
        # Fallback hardcoded for dev
        data_dir = '/home/testuser/CPE-CHAT-0.0.2/data'
        files = glob.glob(os.path.join(data_dir, 'regulations', 'rule_exam*.txt'))
        if not files:
            return None
            
    try:
        with open(files[0], 'r', encoding='utf-8') as f:
            txt = f.read()
            
        # Match 'ข้อ X ' up to the next 'ข้อ Y ' or EOF
        # \s follows the clause number
        pattern = rf"(ข้อ {clause_num}\s.*?)(?=ข้อ \d+|$)"
        m = re.search(pattern, txt, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return None

def structured_regulations_lookup(question: str) -> dict[str, Any]:
    """Deterministic lookup for regulations domain."""
    q = (question or '').strip().lower()
    
    # Check if there is "ข้อ X" and some exam keywords.
    m = re.search(r"ข้อ\s*(\d+)", q)
    if m and any(k in q for k in ('ห้องสอบ', 'มาสาย', 'สอบ', 'ทุจริต', 'เข้าสอบ', 'ออก')):
        clause_num = m.group(1)
        clause_text = fetch_exam_clause(clause_num)
        if clause_text:
            ans = f"ระเบียบการสอบ ข้อ {clause_num} กำหนดไว้ดังนี้:\n\n{clause_text}\n\n[rule_exam2560.txt/1]"
            return {"answer": ans, "lookup_mode": f"exam_clause_{clause_num}", "miss_reason": ""}
            
    return {"answer": None, "lookup_mode": "none", "miss_reason": "no_deterministic_match"}
