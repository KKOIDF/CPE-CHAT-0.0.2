import os
import sys
from pathlib import Path

# Ensure local imports work when running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app


def _has_citation(text: str) -> bool:
    import re

    return bool(re.search(r"\[[^\]]+?/\d+\]", text or ""))


def main():
    client = TestClient(app)

    # Pick a likely-answerable question in announcements.
    payload = {
        "domain": "announcements",
        "question": "ประกาศสอบซ้อนทำอย่างไร",
    }

    r = client.post("/rag/answer", json=payload)
    print("status:", r.status_code)
    data = r.json()

    answer = data.get("answer")
    ctx_n = len(data.get("contexts") or [])

    print("contexts:", ctx_n)
    print("answer:")
    print(answer)
    print("has_citation:", _has_citation(answer or ""))
    print("fallback:", (answer or "").strip() == "ไม่พบข้อมูลในเอกสาร")

    # Extra: show which provider path is configured (best-effort)
    print("LLM_ENABLE:", os.getenv("LLM_ENABLE"))
    print("LLM_PROVIDER:", os.getenv("LLM_PROVIDER"))
    print("LLM_MODEL:", os.getenv("LLM_MODEL"))


if __name__ == "__main__":
    main()
