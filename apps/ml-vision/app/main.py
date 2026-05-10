"""FastAPI entrypoint for plant disease detection."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile, status
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.logging_config import configure_logging

SERVICE_NAME = "ml-vision"
REPLAY_WINDOW_SECONDS = 300
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MIN_IMAGE_SIDE = 64
JOB_TTL_SECONDS = 3600

logger = logging.getLogger(SERVICE_NAME)


class AuthUser(BaseModel):
    user_id: str


class ImageMetadata(BaseModel):
    filename: str
    content_type: str
    width: int
    height: int
    size_bytes: int


class DiseaseDetection(BaseModel):
    disease: str
    confidence: float
    is_healthy: bool
    background_removed: bool
    fallback_resize: bool
    annotated_image_base64: str
    model_mode: Literal["stub"]
    warning: str | None
    metadata: ImageMetadata


class DetectionJob(BaseModel):
    job_id: str
    status: Literal["queued", "completed", "failed"]
    submitted_at: datetime
    expires_at: datetime
    result: DiseaseDetection | None = None
    error: str | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings: Settings = get_settings()
    configure_logging(settings.log_level)
    logger.info(
        "service starting",
        extra={"service": SERVICE_NAME, "env": settings.app_env, "port": settings.port},
    )
    try:
        yield
    finally:
        logger.info("service stopped cleanly", extra={"service": SERVICE_NAME})


app = FastAPI(title="khetibadi-ml-vision", lifespan=lifespan)
jobs: dict[str, DetectionJob] = {}


def require_hmac_user(
    x_user_id: Annotated[str | None, Header(alias="X-User-ID")] = None,
    x_hmac_signature: Annotated[str | None, Header(alias="X-HMAC-Signature")] = None,
    x_timestamp: Annotated[str | None, Header(alias="X-Timestamp")] = None,
) -> AuthUser:
    settings = get_settings()
    if settings.hmac_secret == "":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "service_unavailable", "message": "HMAC secret is not configured"},
        )
    if x_user_id is None or x_hmac_signature is None or x_timestamp is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "missing HMAC identity headers"},
        )
    try:
        timestamp = int(x_timestamp)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "invalid timestamp"},
        ) from exc
    if abs(time.time() - timestamp) > REPLAY_WINDOW_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "replay_detected",
                "message": "request timestamp is outside replay window",
            },
        )
    expected = hmac.new(
        settings.hmac_secret.encode(),
        f"{x_user_id}:{timestamp}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, x_hmac_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "invalid HMAC signature"},
        )
    return AuthUser(user_id=x_user_id)


AuthDependency = Annotated[AuthUser, Depends(require_hmac_user)]


@app.get("/health")
async def health() -> dict[str, object]:
    settings = get_settings()
    artifact_present = Path(settings.vision_model_path).exists()
    mode = "stub" if settings.ml_allow_stub_mode and not artifact_present else "model"
    return {
        "status": "ok" if artifact_present or settings.ml_allow_stub_mode else "degraded",
        "service": SERVICE_NAME,
        "model_mode": mode,
        "model_artifact_present": artifact_present,
        "cuda_available": False,
    }


@app.post("/ml/vision/detect")
async def detect_disease(
    _: AuthDependency,
    image: Annotated[UploadFile, File()],
    async_mode: Annotated[bool, Query(alias="async")] = False,
) -> DiseaseDetection | dict[str, str]:
    if async_mode:
        return await create_detection_job(image)
    image_bytes = await read_image(image)
    return build_detection(image, image_bytes)


@app.post("/ml/vision/detect/async", status_code=status.HTTP_202_ACCEPTED)
async def detect_disease_async(
    _: AuthDependency,
    image: Annotated[UploadFile, File()],
) -> dict[str, str]:
    return await create_detection_job(image)


@app.get("/ml/vision/detect/{job_id}")
async def get_detection_job(job_id: str, _: AuthDependency) -> DetectionJob:
    prune_expired_jobs()
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "detection job not found"},
        )
    return job


@app.get("/ml/vision/jobs/{job_id}")
async def get_detection_job_alias(job_id: str, user: AuthDependency) -> DetectionJob:
    return await get_detection_job(job_id, user)


@app.get("/ml/vision/classes")
async def disease_classes(_: AuthDependency) -> dict[str, list[str]]:
    return {"classes": supported_classes()}


async def create_detection_job(image: UploadFile) -> dict[str, str]:
    image_bytes = await read_image(image)
    job_id = str(uuid4())
    submitted_at = datetime.now(UTC)
    jobs[job_id] = DetectionJob(
        job_id=job_id,
        status="completed",
        submitted_at=submitted_at,
        expires_at=submitted_at + timedelta(seconds=JOB_TTL_SECONDS),
        result=build_detection(image, image_bytes),
    )
    return {"job_id": job_id, "status": "completed"}


async def read_image(image: UploadFile) -> bytes:
    content = await image.read()
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"error": "payload_too_large", "message": "image must be at most 10MB"},
        )
    if not is_supported_image(content):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"error": "unsupported_media_type", "message": "image must be JPG or PNG"},
        )
    return content


def build_detection(image: UploadFile, image_bytes: bytes) -> DiseaseDetection:
    ensure_stub_available()
    metadata = inspect_image(image, image_bytes)
    digest = hashlib.sha256(image_bytes).hexdigest()
    classes = supported_classes()
    disease = classes[int(digest[:8], 16) % len(classes)]
    confidence = 0.52 + ((int(digest[8:10], 16) % 40) / 100)
    settings = get_settings()
    if confidence < settings.confidence_threshold:
        disease = "uncertain"
        is_healthy = False
    else:
        is_healthy = "healthy" in disease
    return DiseaseDetection(
        disease=disease,
        confidence=round(min(confidence, 0.98), 2),
        is_healthy=is_healthy,
        background_removed=False,
        fallback_resize=metadata.width < 128 or metadata.height < 128,
        annotated_image_base64=encode_image(image_bytes),
        model_mode="stub",
        warning="model_artifact_missing",
        metadata=metadata,
    )


def inspect_image(image: UploadFile, image_bytes: bytes) -> ImageMetadata:
    try:
        with Image.open(BytesIO(image_bytes)) as opened:
            width, height = opened.size
            image_format = opened.format or "unknown"
            opened.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_image", "message": "image could not be decoded"},
        ) from exc
    if width < MIN_IMAGE_SIDE or height < MIN_IMAGE_SIDE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "image_too_small", "message": "image must be at least 64x64"},
        )
    return ImageMetadata(
        filename=image.filename or "upload",
        content_type=image.content_type or f"image/{image_format.lower()}",
        width=width,
        height=height,
        size_bytes=len(image_bytes),
    )


def ensure_stub_available() -> None:
    settings = get_settings()
    if Path(settings.vision_model_path).exists():
        return
    if settings.ml_allow_stub_mode:
        return
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"error": "model_unavailable", "message": "vision model artifact is not available"},
    )


def prune_expired_jobs() -> None:
    now = datetime.now(UTC)
    expired = [job_id for job_id, job in jobs.items() if job.expires_at <= now]
    for job_id in expired:
        del jobs[job_id]


def is_supported_image(content: bytes) -> bool:
    return content.startswith(b"\xff\xd8\xff") or content.startswith(b"\x89PNG\r\n\x1a\n")


def encode_image(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("ascii")


def supported_classes() -> list[str]:
    return [
        "apple_scab",
        "apple_black_rot",
        "apple_healthy",
        "corn_common_rust",
        "corn_healthy",
        "grape_black_rot",
        "grape_healthy",
        "potato_early_blight",
        "potato_late_blight",
        "potato_healthy",
        "tomato_bacterial_spot",
        "tomato_early_blight",
        "tomato_late_blight",
        "tomato_leaf_mold",
        "tomato_healthy",
        "uncertain",
    ]
