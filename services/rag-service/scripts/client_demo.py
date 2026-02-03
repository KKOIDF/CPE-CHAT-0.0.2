#!/usr/bin/env python
import json
import time
import sys
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8001"

def post_json(path: str, payload: dict):
    url = f"{BASE}{path}"
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    q = sys.argv[1] if len(sys.argv) > 1 else "รับสมัครนักศึกษาใหม่"
    print(f"\n>>> Question: {q}")
    print("-- /rag/query ----------------------------------------------------")
    res = post_json("/rag/query", {"question": q})
    print(json.dumps({k: (res[k] if k != 'contexts' else res['contexts'][:3]) for k in res}, ensure_ascii=False, indent=2))

    print("\n-- /rag/answer ---------------------------------------------------")
    ans = post_json("/rag/answer", {"question": q})
    print(json.dumps({
        "question": ans.get("question"),
        "answer": ans.get("answer"),
        "contexts_preview": ans.get("contexts", [])[:3],
        "token_est": ans.get("token_est")
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
