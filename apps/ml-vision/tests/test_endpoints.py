import hashlib
import hmac
import time
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
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


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (128, 128), color=(50, 180, 80)).save(buffer, format="PNG")
    return buffer.getvalue()


def wallpaper_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (128, 128), color=(110, 90, 180)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_detect_returns_stub_result(monkeypatch: MonkeyPatch) -> None:
    secret = "test-hmac-secret-minimum-32-chars"
    monkeypatch.setenv("HMAC_SECRET", secret)
    monkeypatch.setenv("ML_ALLOW_STUB_MODE", "true")
    client = TestClient(app)

    response = client.post(
        "/ml/vision/detect",
        headers=auth_headers(secret),
        files={"image": ("leaf.png", png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model_mode"] == "stub"
    assert body["metadata"]["width"] == 128
    assert body["metadata"]["height"] == 128


def test_detect_rejects_obvious_non_plant_image(monkeypatch: MonkeyPatch) -> None:
    secret = "test-hmac-secret-minimum-32-chars"
    monkeypatch.setenv("HMAC_SECRET", secret)
    monkeypatch.setenv("ML_ALLOW_STUB_MODE", "true")
    client = TestClient(app)

    response = client.post(
        "/ml/vision/detect",
        headers=auth_headers(secret),
        files={"image": ("wallpaper.png", wallpaper_bytes(), "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["disease"] == "not_plant"
    assert body["warning"] == "non_plant_image"
    assert body["confidence"] == 0


def test_invalid_file_type_is_rejected(monkeypatch: MonkeyPatch) -> None:
    secret = "test-hmac-secret-minimum-32-chars"
    monkeypatch.setenv("HMAC_SECRET", secret)
    monkeypatch.setenv("ML_ALLOW_STUB_MODE", "true")
    client = TestClient(app)

    response = client.post(
        "/ml/vision/detect",
        headers=auth_headers(secret),
        files={"image": ("leaf.txt", b"not-image", "text/plain")},
    )

    assert response.status_code == 415
