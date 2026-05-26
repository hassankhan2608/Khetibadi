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


def tiny_png() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00"
        b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )


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


def test_message_stream_accepts_image_attachment(monkeypatch: MonkeyPatch) -> None:
    secret = "test-hmac-secret-minimum-32-chars"
    monkeypatch.setenv("HMAC_SECRET", secret)
    monkeypatch.setenv("AI_CHAT_ALLOW_FAKE_LLM", "true")
    client = TestClient(app)

    create_response = client.post(
        "/ai/chat/sessions",
        headers=auth_headers(secret, user_id="user-attachment"),
        json={"title": "Image advice"},
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session"]["id"]

    response = client.post(
        f"/ai/chat/sessions/{session_id}/messages",
        headers=auth_headers(secret, user_id="user-attachment"),
        data={"message": "Check this leaf", "language": "en"},
        files={"image": ("leaf.png", tiny_png(), "image/png")},
    )

    assert response.status_code == 200
    assert "event: done" in response.text
    history_response = client.get(
        f"/ai/chat/sessions/{session_id}/messages",
        headers=auth_headers(secret, user_id="user-attachment"),
    )
    first_message = history_response.json()["messages"][0]
    assert "attached image" in first_message["content"]
