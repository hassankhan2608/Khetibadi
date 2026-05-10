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


def test_health_reports_stub_mode(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("ML_ALLOW_STUB_MODE", "true")
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "ml-crop"
    assert body["status"] == "ok"
    assert body["model_mode"] == "stub"


def test_crop_recommendation_requires_valid_hmac(monkeypatch: MonkeyPatch) -> None:
    secret = "test-hmac-secret-minimum-32-chars"
    monkeypatch.setenv("HMAC_SECRET", secret)
    monkeypatch.setenv("ML_ALLOW_STUB_MODE", "true")
    client = TestClient(app)

    response = client.post(
        "/ml/crop/recommend",
        headers=auth_headers(secret),
        json={
            "nitrogen": 100,
            "phosphorus": 45,
            "potassium": 70,
            "temperature": 28,
            "humidity": 82,
            "ph": 6.5,
            "rainfall": 1600,
            "season": "kharif",
            "state": "Punjab",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["crop"] in {"rice", "wheat", "maize", "cotton", "sugarcane", "millet", "pulses"}
    assert body["model_mode"] == "stub"
