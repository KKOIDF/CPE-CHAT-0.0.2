import sys
from pathlib import Path
from unittest.mock import patch

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


def test_openwebui_chat_completion_delegates_to_rag_answer_with_same_domain_and_messages():
    client = TestClient(main.app)
    captured = {}

    def fake_rag_answer(req):
        captured['question'] = req.question
        captured['domain'] = req.domain
        captured['messages'] = req.messages
        captured['session_id'] = req.session_id
        captured['model'] = req.model
        return main.RagAnswerResponse(
            question=req.question,
            prompt='p',
            answer='delegated answer',
            contexts=[],
            token_est=7,
            meta={},
        )

    with patch.object(main, 'rag_answer_endpoint', side_effect=fake_rag_answer):
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "domain": "curriculum",
                "messages": [{"role": "user", "content": "ปี 1 เทอม 1 เรียนอะไรบ้าง"}],
                "session_id": "sess-1",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['choices'][0]['message']['content'] == 'delegated answer'
    assert captured['question'] == 'ปี 1 เทอม 1 เรียนอะไรบ้าง'
    assert captured['domain'] == 'curriculum'
    assert captured['messages'][0]['content'] == 'ปี 1 เทอม 1 เรียนอะไรบ้าง'
    assert captured['session_id'] == 'sess-1'
    assert captured['model'] == 'test-model'
