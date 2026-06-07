import hashlib
import hmac
import time
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.main import (
    AgentRequest,
    ChatMessage,
    app,
    build_user_prompt,
    compact_tool_context,
    should_preload_market_data,
)


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
    assert history_response.json()["messages"][0]["channel"] == "dashboard"


def test_bridge_message_persists_whatsapp_session_and_messages(
    monkeypatch: MonkeyPatch,
) -> None:
    secret = "test-hmac-secret-minimum-32-chars"
    monkeypatch.setenv("HMAC_SECRET", secret)
    monkeypatch.setenv("AI_CHAT_ALLOW_FAKE_LLM", "true")
    client = TestClient(app)

    response = client.post(
        "/ai/chat/internal/bridge/messages",
        headers=auth_headers(secret, user_id="whatsapp-user"),
        json={
            "message": "How should I water onion today?",
            "language": "en",
            "channel": "whatsapp",
            "external_thread_id": "919999999999@s.whatsapp.net",
            "account_name": "WhatsApp Beta Farmer",
        },
    )

    assert response.status_code == 200
    payload = response.json()["message"]
    assert payload["status"] == "complete"
    assert "Khetibadi AI" in payload["response"]
    session_id = payload["session_id"]

    history_response = client.get(
        f"/ai/chat/sessions/{session_id}/messages",
        headers=auth_headers(secret, user_id="whatsapp-user"),
    )
    messages = history_response.json()["messages"]
    assert [message["channel"] for message in messages] == ["whatsapp", "whatsapp"]

    sessions_response = client.get(
        "/ai/chat/sessions",
        headers=auth_headers(secret, user_id="whatsapp-user"),
    )
    session = sessions_response.json()["sessions"][0]
    assert session["channel"] == "whatsapp"
    assert session["external_thread_id"] == "919999999999@s.whatsapp.net"


def test_compact_tool_context_includes_linked_account_name() -> None:
    compact = compact_tool_context({"farmer_profile": {"name": "WhatsApp Beta Farmer"}})

    assert compact["farmer_profile"] == {"name": "WhatsApp Beta Farmer"}


def test_market_context_only_preloads_for_market_questions() -> None:
    assert should_preload_market_data("What is today's onion mandi price?")
    assert should_preload_market_data("गेहूं का भाव क्या है?")
    assert not should_preload_market_data("What is my linked account name?")


def test_user_prompt_includes_recent_chat_history() -> None:
    created_at = datetime.now(UTC)
    prompt = build_user_prompt(
        AgentRequest(message="What did I say before?", language="en"),
        None,
        {"farmer_profile": {"name": "WhatsApp Beta Farmer"}},
        [
            ChatMessage(
                id="m1",
                session_id="s1",
                user_id="u1",
                role="user",
                content="My field has yellow leaves.",
                created_at=created_at,
            ),
            ChatMessage(
                id="m2",
                session_id="s1",
                user_id="u1",
                role="assistant",
                content="Check nitrogen and irrigation first.",
                created_at=created_at,
            ),
        ],
    )

    assert "Recent conversation in this thread" in prompt
    assert "Farmer: My field has yellow leaves." in prompt
    assert "Khetibadi AI: Check nitrogen and irrigation first." in prompt


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
