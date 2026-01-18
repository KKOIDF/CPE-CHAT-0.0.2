import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app


def main() -> None:
    c = TestClient(app)

    payload = {
        "question": "เกณฑ์การสำเร็จการศึกษา หลักสูตรวิศวกรรมคอมพิวเตอร์",
        "domain": "curriculum",
    }
    r = c.post("/rag/query", json=payload)
    print("status", r.status_code)
    data = r.json()
    print("token_est", data.get("token_est"))
    ctxs = data.get("contexts") or []
    print("contexts", len(ctxs))
    if ctxs:
        print("first_source", ctxs[0].get("source") or ctxs[0].get("path"))


if __name__ == "__main__":
    main()
