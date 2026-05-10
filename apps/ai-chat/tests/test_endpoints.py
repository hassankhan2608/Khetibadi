import hashlib
import hmac
import time

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.main import app


def auth_headers(secret: str, user_id: str = "user-1") -> dict[str, str]:
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode(),
        f"{user_id}:{timestamp}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return {
        "X-User-ID": user_id,
        "X-Timestamp": timestamp,
        "X-HMAC-Signature": signature,
    }


def test_session_lifecycle_and_stream(monkeypatch: MonkeyPatch) -> None:
    secret = "test-hmac-secret-minimum-32-chars"
    monkeypatch.setenv("HMAC_SECRET", secret)
    monkeypatch.setenv("AI_CHAT_ALLOW_FAKE_LLM", "true")
    client = TestClient(app)

    create_response = client.post(
        "/ai/chat/sessions",
        headers=auth_headers(secret),
        json={"title": "Crop advice"},
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session"]["id"]

    stream_response = client.post(
        f"/ai/chat/sessions/{session_id}/messages",
        headers=auth_headers(secret),
        json={"message": "How should I irrigate wheat?", "language": "en"},
    )

    assert stream_response.status_code == 200
    assert "event: token" in stream_response.text
    assert "event: done" in stream_response.text

    history_response = client.get(
        f"/ai/chat/sessions/{session_id}/messages",
        headers=auth_headers(secret),
    )
    assert history_response.status_code == 200
    assert len(history_response.json()["messages"]) == 2


def test_chat_health_reports_degraded_without_fake_llm(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("AI_CHAT_ALLOW_FAKE_LLM", raising=False)
    client = TestClient(app)

    response = client.get("/ai/chat/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
