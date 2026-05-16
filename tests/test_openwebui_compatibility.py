import sys
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = REPO_ROOT / "services" / "rag-service"
for key in list(sys.modules):
    if key == "app" or key.startswith("app."):
        sys.modules.pop(key, None)
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

import app.main as main  # noqa: E402


def test_openwebui_chat_completion_schema_compatible():
    client = TestClient(main.app)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "สวัสดี"}],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["object"] == "chat.completion"
    assert isinstance(payload["choices"], list)
    assert payload["choices"][0]["message"]["role"] == "assistant"
    assert "content" in payload["choices"][0]["message"]
